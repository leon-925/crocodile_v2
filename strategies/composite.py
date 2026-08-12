"""CompositeStrategy — 策略乐高引擎

将 Entry/Exit/Filter/StopLoss/TakeProfit 组件组合成完整策略。
支持向量化模式（信号列）和逐K线模式（带持仓追踪）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from .base_strategy import BaseStrategy
from .components import (
    EntryRule, ExitRule, Filter, StopLoss, TakeProfit,
)


class CompositeStrategy(BaseStrategy):
    """组合策略 — 把入场/出场/过滤/止损/止盈拼成一个策略

    用法:
        strat = CompositeStrategy("我的策略")
        strat.set_entry(MACrossEntry(5, 20))
        strat.add_filter(RSIFilter(max=70))
        strat.set_exit(MACrossExit(5, 20))
        strat.set_stop_loss(ATRStopLoss(multiplier=2))
        strat.set_take_profit(FixedPctTakeProfit(target=0.15))
        sig = strat.generate_signal(df)
    """

    def __init__(self, name: str = "Composite"):
        super().__init__(name)
        self._entry: Optional[EntryRule] = None
        self._exit: Optional[ExitRule] = None
        self._filters: List[Filter] = []
        self._stop_losses: List[StopLoss] = []
        self._take_profits: List[TakeProfit] = []

    # ── 配置组件 ─────────────────────────────────

    def set_entry(self, rule: EntryRule) -> "CompositeStrategy":
        self._entry = rule
        return self

    def set_exit(self, rule: ExitRule) -> "CompositeStrategy":
        self._exit = rule
        return self

    def add_filter(self, f: Filter) -> "CompositeStrategy":
        self._filters.append(f)
        return self

    def set_stop_loss(self, sl: StopLoss) -> "CompositeStrategy":
        self._stop_losses = [sl]
        return self

    def add_stop_loss(self, sl: StopLoss) -> "CompositeStrategy":
        self._stop_losses.append(sl)
        return self

    def set_take_profit(self, tp: TakeProfit) -> "CompositeStrategy":
        self._take_profits = [tp]
        return self

    def add_take_profit(self, tp: TakeProfit) -> "CompositeStrategy":
        self._take_profits.append(tp)
        return self

    # ── 信号生成（向量化：纯信号列，无持仓追踪）──

    def generate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号列（向量化模式）

        入场信号 = entry & all filters pass
        出场信号 = exit | stop_loss | take_profit
        """
        df = df.copy()
        df["signal"] = 0

        if self._entry is None:
            return df

        # 入场信号
        entry_mask = self._entry.generate(df)

        # 过滤器
        for f in self._filters:
            entry_mask &= f.apply(df)

        df.loc[entry_mask, "signal"] = 1

        # 出场信号（合并 exit + stop_loss + take_profit）
        exit_mask = pd.Series(False, index=df.index)
        if self._exit:
            exit_mask |= self._exit.generate(df)

        for sl in self._stop_losses:
            exit_mask |= sl.check(df)

        for tp in self._take_profits:
            exit_mask |= tp.check(df)

        df.loc[exit_mask & (df["signal"] != 1), "signal"] = -1

        return df

    # ── 信号生成（逐K线：带持仓追踪）──────────────

    def generate_signal_with_state(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号（逐K线模式，追踪持仓状态和入场价）

        比向量化更准确：止损/止盈基于实际入场价计算。
        """
        df = df.copy()
        df["signal"] = 0
        n = len(df)

        in_position = False
        entry_idx: Optional[int] = None

        for i in range(n):
            if not in_position:
                # 检查入场
                if self._check_entry_at(df, i):
                    df.iloc[i, df.columns.get_loc("signal")] = 1
                    in_position = True
                    entry_idx = i
            else:
                # 检查出场
                if self._check_exit_at(df, i, entry_idx):
                    df.iloc[i, df.columns.get_loc("signal")] = -1
                    in_position = False
                    entry_idx = None
                # 检查止损
                elif self._check_stop_loss_at(df, i, entry_idx):
                    df.iloc[i, df.columns.get_loc("signal")] = -1
                    in_position = False
                    entry_idx = None
                # 检查止盈
                elif self._check_take_profit_at(df, i, entry_idx):
                    df.iloc[i, df.columns.get_loc("signal")] = -1
                    in_position = False
                    entry_idx = None

        return df

    # ── 逐点检查 ─────────────────────────────────

    def _check_entry_at(self, df: pd.DataFrame, idx: int) -> bool:
        """检查第 idx 行是否满足入场条件"""
        if self._entry is None:
            return False

        # 构建截至当前 bar 的窗口
        window = df.iloc[: idx + 1]

        # 入场信号（取最后一行的值）
        try:
            entry_signal = self._entry.generate(window)
            if not entry_signal.iloc[-1]:
                return False
        except Exception:
            return False

        # 过滤器
        for f in self._filters:
            try:
                if not f.apply(window).iloc[-1]:
                    return False
            except Exception:
                return False

        return True

    def _check_exit_at(self, df: pd.DataFrame, idx: int, entry_idx: int) -> bool:
        """检查第 idx 行是否满足出场条件"""
        if self._exit is None:
            return False

        window = df.iloc[: idx + 1]
        try:
            return bool(self._exit.generate(window).iloc[-1])
        except Exception:
            return False

    def _check_stop_loss_at(self, df: pd.DataFrame, idx: int, entry_idx: int) -> bool:
        """检查第 idx 行是否触发止损"""
        for sl in self._stop_losses:
            try:
                if sl.check(df.iloc[: idx + 1], entry_idx).iloc[-1]:
                    return True
            except Exception:
                pass
        return False

    def _check_take_profit_at(self, df: pd.DataFrame, idx: int, entry_idx: int) -> bool:
        """检查第 idx 行是否触发止盈"""
        for tp in self._take_profits:
            try:
                if tp.check(df.iloc[: idx + 1], entry_idx).iloc[-1]:
                    return True
            except Exception:
                pass
        return False

    # ── 序列化 ───────────────────────────────────

    def get_params(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "entry": self._entry.get_params() if self._entry else None,
            "exit": self._exit.get_params() if self._exit else None,
            "filters": [f.get_params() for f in self._filters],
            "stop_loss": [sl.get_params() for sl in self._stop_losses],
            "take_profit": [tp.get_params() for tp in self._take_profits],
        }

    @property
    def component_summary(self) -> str:
        parts = []
        if self._entry:
            parts.append(f"Entry: {self._entry.get_params().get('type')}")
        if self._exit:
            parts.append(f"Exit: {self._exit.get_params().get('type')}")
        if self._filters:
            parts.append(f"Filters: {len(self._filters)}")
        if self._stop_losses:
            parts.append(f"SL: {len(self._stop_losses)}")
        if self._take_profits:
            parts.append(f"TP: {len(self._take_profits)}")
        return " | ".join(parts) if parts else "Empty"

    def __repr__(self):
        return f"CompositeStrategy({self.name}, {self.component_summary})"

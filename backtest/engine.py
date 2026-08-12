"""BacktestRunner — 统一回测入口

根据 mode 自动选择引擎：
- "vectorized"  → VectorizedBacktest（极速，纯信号）
- "bar_by_bar"  → BarByBarBacktest（标准，全模块串联）
- "event_driven" → EventDrivenBacktest（高仿真，事件队列）
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional, Union

import pandas as pd

from .result import BacktestResult
from .vectorized import VectorizedBacktest
from .bar_by_bar import BarByBarBacktest
from .event_driven import EventDrivenBacktest


BacktestMode = Literal["vectorized", "bar_by_bar", "event_driven"]


class BacktestRunner:
    """统一回测入口 — 一套配置，三种模式

    使用:
        runner = BacktestRunner(
            data_source=ds,
            account=acc,
            broker=broker,
            strategy=strategy,
            portfolio_manager=pm,
        )

        # 快速验证（纯信号列）
        result = runner.run_vectorized(df)

        # 标准回测（全模块）
        result = runner.run(df, mode="bar_by_bar")

        # 高仿真
        result = runner.run(df, mode="event_driven")
    """

    def __init__(
        self,
        data_source=None,
        account=None,
        broker=None,
        strategy=None,
        portfolio_manager=None,
        risk_manager=None,
        initial_cash: float = 100_000,
        commission: float = 0.0003,
        slippage: float = 0.0,
    ):
        self.data_source = data_source
        self.account = account
        self.broker = broker
        self.strategy = strategy
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.initial_cash = initial_cash
        self.commission = commission
        self.slippage = slippage

        # 懒加载引擎
        self._vectorized: Optional[VectorizedBacktest] = None
        self._bar_by_bar: Optional[BarByBarBacktest] = None
        self._event_driven: Optional[EventDrivenBacktest] = None

    # ── 主入口 ──────────────────────────────────

    def run(
        self,
        df: pd.DataFrame,
        mode: BacktestMode = "bar_by_bar",
        price_col: str = "close",
        signal_col: str = "signal",
        rebalance_freq: str = "daily",
        **kwargs,
    ) -> BacktestResult:
        """执行回测

        参数:
            df: OHLCV + 指标 + signal 列的 DataFrame
            mode: "vectorized" | "bar_by_bar" | "event_driven"
            price_col: 价格列名
            signal_col: 信号列名 (vectorized 模式用)
            rebalance_freq: 调仓频率 (bar_by_bar)
            **kwargs: 传递给具体引擎

        返回:
            BacktestResult
        """
        if mode == "vectorized":
            return self.run_vectorized(df, signal_col, price_col, **kwargs)
        elif mode == "bar_by_bar":
            return self.run_bar_by_bar(df, price_col, rebalance_freq, **kwargs)
        elif mode == "event_driven":
            return self.run_event_driven(df, price_col, **kwargs)
        else:
            raise ValueError(f"Unknown mode: {mode}. Use 'vectorized', 'bar_by_bar', or 'event_driven'")

    # ── 分模式 ──────────────────────────────────

    def run_vectorized(
        self,
        df: pd.DataFrame,
        signal_col: str = "signal",
        price_col: str = "close",
        **kwargs,
    ) -> BacktestResult:
        """向量化回测（极速）"""
        if self._vectorized is None:
            self._vectorized = VectorizedBacktest(
                initial_cash=self.initial_cash,
                commission=self.commission,
                slippage=self.slippage,
            )
        return self._vectorized.run(df, signal_col=signal_col, price_col=price_col, **kwargs)

    def run_bar_by_bar(
        self,
        df: pd.DataFrame,
        price_col: str = "close",
        rebalance_freq: str = "daily",
        **kwargs,
    ) -> BacktestResult:
        """逐 K 线回测（标准）"""
        if self.account is None or self.broker is None:
            raise ValueError("Bar-by-Bar 模式需要 account 和 broker")

        if self._bar_by_bar is None:
            self._bar_by_bar = BarByBarBacktest(
                account=self.account,
                broker=self.broker,
                portfolio_manager=self.portfolio_manager,
                risk_manager=self.risk_manager,
            )
        return self._bar_by_bar.run(
            df,
            strategy=self.strategy,
            price_col=price_col,
            rebalance_freq=rebalance_freq,
            **kwargs,
        )

    def run_event_driven(
        self,
        df: pd.DataFrame,
        price_col: str = "close",
        **kwargs,
    ) -> BacktestResult:
        """事件驱动回测（高仿真）"""
        if self.account is None or self.broker is None:
            raise ValueError("Event-Driven 模式需要 account 和 broker")

        if self._event_driven is None:
            self._event_driven = EventDrivenBacktest(
                account=self.account,
                broker=self.broker,
                portfolio_manager=self.portfolio_manager,
                risk_manager=self.risk_manager,
            )
        return self._event_driven.run(df, price_col=price_col, **kwargs)

    # ── 快捷方法 ────────────────────────────────

    def compare(
        self,
        df: pd.DataFrame,
        price_col: str = "close",
        signal_col: str = "signal",
    ) -> Dict[str, BacktestResult]:
        """三种模式对比运行"""
        results = {}
        for mode in ["vectorized", "bar_by_bar", "event_driven"]:
            try:
                results[mode] = self.run(df, mode=mode, price_col=price_col, signal_col=signal_col)
            except Exception as e:
                results[mode] = None
                print(f"[{mode}] 跳过: {e}")
        return results

    def from_source(
        self,
        symbols: list,
        start_date=None,
        end_date=None,
        mode: BacktestMode = "bar_by_bar",
    ) -> BacktestResult:
        """从 DataSource 拉数据 + 回测（一键式）"""
        if self.data_source is None:
            raise ValueError("需要 data_source 才能使用 from_source()")

        df = self.data_source.get_history_batch(symbols, start_date, end_date)

        # 计算指标
        if "close" in df.columns:
            df["SMA_5"] = df["close"].rolling(5).mean()
            df["SMA_20"] = df["close"].rolling(20).mean()
            df["boll_upper"] = df["SMA_20"] + 2 * df["close"].rolling(20).std()
            df["boll_lower"] = df["SMA_20"] - 2 * df["close"].rolling(20).std()
            df["momentum_20"] = df["close"].pct_change(20)
            df.dropna(inplace=True)

        return self.run(df, mode=mode, price_col="close")

    def __repr__(self):
        parts = [f"mode=any"]
        if self.strategy:
            parts.append(f"strategy={self.strategy.name}")
        if self.account:
            parts.append(f"cash={self.account.initial_cash:,.0f}")
        return f"BacktestRunner({', '.join(parts)})"


# 兼容旧接口
class BacktestEngine:
    """旧版简单回测引擎（兼容）"""

    def __init__(self, initial_cash=100000, commission=0.0003):
        self.initial_cash = initial_cash
        self.commission = commission

    def run(self, df):
        """简单向量化回测"""
        engine = VectorizedBacktest(self.initial_cash, self.commission)
        result = engine.run(df)
        return result.equity_curve, result.trades

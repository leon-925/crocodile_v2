"""Account — 资金账户

职责：
- 管理现金（总额/可用/冻结）
- 持有 PositionBook（持仓簿）
- 记录交易流水和净值曲线
- 提供 Execution 对齐接口（查询 + 成交回调）

Account 是唯一的状态源（Single Source of Truth）。
Execution/Broker 不持有独立仓位——通过 Account 接口查询和回写。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from .market_rule import MarketRule
from .position import Position
from .position_book import PositionBook


class Account:
    """资金账户 — 管理现金 + 持仓 + 交易记录"""

    # ── 构造 ────────────────────────────────────

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        positions_df: Optional[pd.DataFrame] = None,
    ):
        self.initial_cash = float(initial_cash)
        self._cash = float(initial_cash)
        self._available_cash = float(initial_cash)
        self._frozen_cash = 0.0

        self.market_rule = MarketRule()

        # 核心：持仓簿（替代旧 positions DataFrame）
        self.book = PositionBook()
        if positions_df is not None and not positions_df.empty:
            self._import_positions(positions_df)

        # 交易流水
        self.trades = pd.DataFrame(
            columns=["time", "symbol", "market", "side", "price", "quantity", "fee", "realized_pnl"]
        )

        # 净值曲线
        self.equity_curve = pd.DataFrame(
            columns=["time", "cash", "market_value", "equity", "nav"]
        )

    def _import_positions(self, df: pd.DataFrame) -> None:
        """从旧格式 DataFrame 导入初始持仓"""
        for _, row in df.iterrows():
            self.book.add(
                symbol=row["symbol"],
                quantity=row.get("quantity", 0),
                price=row.get("avg_price", row.get("current_price", 0)),
                market=row.get("market", "CN"),
            )

    # ── 现金属性 ────────────────────────────────

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def available_cash(self) -> float:
        return self._available_cash

    @property
    def frozen_cash(self) -> float:
        return self._frozen_cash

    # ── 持仓属性（向后兼容）─────────────────────

    @property
    def positions(self) -> pd.DataFrame:
        """兼容旧接口：返回持仓 DataFrame"""
        return self.book.to_dataframe()

    # ── 查询 — Execution 对齐接口 ────────────────

    def get_available_cash(self) -> float:
        """Execution 查询可用资金（下单前校验）"""
        return self._available_cash

    def get_equity(self) -> float:
        """Execution 查询总权益"""
        return self._cash + self.book.total_market_value

    def get_market_value(self) -> float:
        """Execution 查询持仓总市值"""
        return self.book.total_market_value

    def get_position(self, symbol: str) -> Optional[Position]:
        """Execution 查询单票持仓（返回 Position 对象）"""
        return self.book.get(symbol)

    def get_positions_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Execution 查询全部持仓快照（轻量 dict，不依赖 pandas）"""
        return self.book.to_dict()

    def get_account_snapshot(self) -> Dict[str, Any]:
        """Execution 一次性获取账户全貌"""
        return {
            "cash": self._cash,
            "available_cash": self._available_cash,
            "frozen_cash": self._frozen_cash,
            "market_value": self.book.total_market_value,
            "equity": self.get_equity(),
            "position_count": self.book.count,
            "return": self.get_equity() / self.initial_cash - 1,
        }

    # ── 行情更新 — Execution 对齐接口 ─────────────

    def update_market_prices(self, prices: Dict[str, float]) -> None:
        """Execution 推送实时行情，更新所有持仓市值"""
        self.book.update_prices(prices)

    # ── 成交回调 — Execution 对齐接口 ─────────────

    def on_order_filled(
        self,
        symbol: str,
        side: str,
        price: float,
        quantity: float,
        market: str = "CN",
        time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Execution 成交后回调 Account 更新状态

        返回成交摘要 dict，供 Execution 确认。
        """
        if side.upper() == "BUY":
            return self._execute_buy(symbol, price, quantity, market, time)
        else:
            return self._execute_sell(symbol, price, quantity, market, time)

    # ── 内部成交逻辑 ─────────────────────────────

    def _execute_buy(
        self, symbol: str, price: float, quantity: float, market: str, time: Optional[datetime]
    ) -> Dict[str, Any]:
        value = price * quantity
        fee = self.market_rule.calculate_fee(market, price, quantity, side="BUY")
        total_cost = value + fee

        if total_cost > self._available_cash:
            raise ValueError(
                f"资金不足！需支付: {total_cost:.2f} (含手续费 {fee:.2f}), 可用: {self._available_cash:.2f}"
            )

        self._cash -= total_cost
        self._available_cash -= total_cost
        self.book.add(symbol, quantity, price, market)

        self._record_trade(symbol, market, "BUY", price, quantity, fee, realized_pnl=0.0, time=time)

        return {
            "symbol": symbol,
            "side": "BUY",
            "price": price,
            "quantity": quantity,
            "fee": fee,
            "cash_after": self._cash,
            "available_after": self._available_cash,
        }

    def _execute_sell(
        self, symbol: str, price: float, quantity: float, market: str, time: Optional[datetime]
    ) -> Dict[str, Any]:
        pos = self.book.get(symbol)
        if pos is None:
            raise ValueError(f"卖出失败：未持有标的 '{symbol}'")

        value = price * quantity
        fee = self.market_rule.calculate_fee(market, price, quantity, side="SELL")
        realized_pnl = self.book.reduce(symbol, quantity, price)
        realized_pnl -= fee  # 扣除手续费

        self._cash += value - fee
        self._available_cash += value - fee

        self._record_trade(symbol, market, "SELL", price, quantity, fee, realized_pnl=realized_pnl, time=time)

        return {
            "symbol": symbol,
            "side": "SELL",
            "price": price,
            "quantity": quantity,
            "fee": fee,
            "realized_pnl": realized_pnl,
            "cash_after": self._cash,
            "available_after": self._available_cash,
        }

    # ── 便捷交易方法（直接调用，不走 Execution）───

    def buy(
        self,
        symbol: str,
        price: float,
        quantity: float,
        market: str = "CN",
        time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """直接买入（回测/手动场景）"""
        return self.on_order_filled(symbol, "BUY", price, quantity, market, time)

    def sell(
        self,
        symbol: str,
        price: float,
        quantity: float,
        market: str = "CN",
        time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """直接卖出（回测/手动场景）"""
        return self.on_order_filled(symbol, "SELL", price, quantity, market, time)

    # ── 资金操作 ────────────────────────────────

    def freeze_cash(self, amount: float) -> None:
        """冻结资金（下单时）"""
        if amount > self._available_cash:
            raise ValueError(f"冻结失败：可用资金不足 ({self._available_cash:.2f} < {amount:.2f})")
        self._available_cash -= amount
        self._frozen_cash += amount

    def unfreeze_cash(self, amount: float) -> None:
        """解冻资金（撤单/拒单时）"""
        amount = min(amount, self._frozen_cash)
        self._available_cash += amount
        self._frozen_cash -= amount

    # ── 净值快照 ────────────────────────────────

    def snapshot(self, time: Optional[datetime] = None) -> Dict[str, Any]:
        """记录当前净值快照，返回快照 dict"""
        record_time = time or datetime.now()
        eq = self.get_equity()
        entry = {
            "time": record_time,
            "cash": self._cash,
            "market_value": self.book.total_market_value,
            "equity": eq,
            "nav": eq / self.initial_cash,
        }
        self.equity_curve = pd.concat(
            [self.equity_curve, pd.DataFrame([entry])], ignore_index=True
        )
        return entry

    # ── 内部 ────────────────────────────────────

    def _record_trade(
        self,
        symbol: str,
        market: str,
        side: str,
        price: float,
        quantity: float,
        fee: float,
        realized_pnl: float = 0.0,
        time: Optional[datetime] = None,
    ) -> None:
        trade_time = time or datetime.now()
        row = pd.DataFrame([{
            "time": trade_time,
            "symbol": symbol,
            "market": market,
            "side": side,
            "price": price,
            "quantity": quantity,
            "fee": fee,
            "realized_pnl": realized_pnl,
        }])
        self.trades = pd.concat([self.trades, row], ignore_index=True)

    # ── 聚合查询 ────────────────────────────────

    def market_value(self) -> float:
        return self.book.total_market_value

    def equity(self) -> float:
        return self.get_equity()

    def return_rate(self) -> float:
        return (self.get_equity() / self.initial_cash) - 1.0

    # ── 兼容旧接口 ──────────────────────────────

    def record_equity(self, time: Optional[datetime] = None) -> None:
        """兼容旧方法名"""
        self.snapshot(time)

    def record_trade(self, *args, **kwargs) -> None:
        """兼容旧方法名 — 不推荐直接调用"""
        self._record_trade(*args, **kwargs)

    def __repr__(self) -> str:
        eq = self.get_equity()
        ret = (eq / self.initial_cash - 1) * 100
        return (
            f"Account(cash={self._cash:,.0f}, equity={eq:,.0f}, "
            f"return={ret:+.2f}%, positions={self.book.count})"
        )

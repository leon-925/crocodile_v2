"""Position — 单标的持仓对象

职责：管理单只标的的持仓数量、成本、盈亏计算。
不关心资金、不关心组合——只关注这一只票。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import pandas as pd


class Position:
    """单标的持仓"""

    __slots__ = (
        "symbol",
        "market",
        "quantity",
        "available_quantity",
        "avg_price",
        "current_price",
        "open_time",
        "realized_profit",
    )

    def __init__(
        self,
        symbol: str,
        quantity: float = 0,
        avg_price: float = 0,
        market: str = "CN",
        current_price: float = 0,
    ):
        self.symbol = symbol
        self.market = market
        self.quantity = quantity
        self.available_quantity = quantity
        self.avg_price = avg_price
        self.current_price = current_price or avg_price
        self.open_time = datetime.now()
        self.realized_profit = 0.0

    # ── 仓位操作 ──────────────────────────────

    def add(self, quantity: float, price: float) -> None:
        """加仓，更新均价"""
        if quantity <= 0:
            raise ValueError("加仓数量必须 > 0")
        old_value = self.quantity * self.avg_price
        new_value = quantity * price
        self.quantity += quantity
        self.available_quantity += quantity
        self.avg_price = (old_value + new_value) / self.quantity

    def reduce(self, quantity: float, price: float) -> float:
        """减仓，返回已实现盈亏"""
        if quantity > self.available_quantity:
            raise ValueError(f"可卖数量不足: {self.available_quantity} < {quantity}")
        profit = (price - self.avg_price) * quantity
        self.realized_profit += profit
        self.quantity -= quantity
        self.available_quantity -= quantity
        return profit

    def update_price(self, price: float) -> None:
        """更新市价"""
        self.current_price = price

    # ── 查询 ──────────────────────────────────

    @property
    def is_empty(self) -> bool:
        return self.quantity <= 0

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.avg_price) * self.quantity

    @property
    def total_pnl(self) -> float:
        return self.realized_profit + self.unrealized_pnl

    @property
    def pnl_pct(self) -> float:
        if self.avg_price == 0:
            return 0.0
        return (self.current_price / self.avg_price) - 1.0

    # ── 序列化 ────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "market": self.market,
            "quantity": self.quantity,
            "available_quantity": self.available_quantity,
            "avg_price": round(self.avg_price, 4),
            "current_price": round(self.current_price, 4),
            "market_value": round(self.market_value, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "realized_profit": round(self.realized_profit, 2),
            "total_pnl": round(self.total_pnl, 2),
            "pnl_pct": round(self.pnl_pct, 4),
        }

    def to_series(self) -> pd.Series:
        """导出为 pandas Series，供 PositionBook 拼 DataFrame"""
        return pd.Series(self.to_dict())

    def __repr__(self) -> str:
        return (
            f"Position({self.symbol}, qty={self.quantity}, "
            f"avg={self.avg_price:.2f}, px={self.current_price:.2f}, "
            f"pnl={self.total_pnl:+.2f})"
        )

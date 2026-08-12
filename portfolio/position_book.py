"""PositionBook — 持仓簿

职责：管理所有持仓的集合，提供增/减/查/行情更新/导出。
Account 持有 PositionBook，Execution 通过 Account 接口查询。
"""

from __future__ import annotations

from typing import Dict, Iterator, List, Optional

import pandas as pd

from .position import Position

# 兼容旧 Account positions DataFrame 的列名
POSITION_DF_COLUMNS = [
    "symbol",
    "market",
    "quantity",
    "available_quantity",
    "avg_price",
    "current_price",
    "market_value",
    "unrealized_pnl",
    "realized_pnl",
]


class PositionBook:
    """持仓簿 — 所有持仓的集合容器"""

    def __init__(self):
        self._positions: Dict[str, Position] = {}

    # ── 增 / 减 ────────────────────────────────

    def add(self, symbol: str, quantity: float, price: float, market: str = "CN") -> None:
        """加仓（不存在则新建 Position）"""
        if symbol in self._positions:
            self._positions[symbol].add(quantity, price)
        else:
            pos = Position(symbol=symbol, quantity=quantity, avg_price=price, market=market, current_price=price)
            self._positions[symbol] = pos

    def reduce(self, symbol: str, quantity: float, price: float) -> float:
        """减仓，返回已实现盈亏。清仓时自动移除 Position"""
        pos = self._get_or_raise(symbol)
        if quantity > pos.available_quantity:
            raise ValueError(f"可卖数量不足: {pos.available_quantity} < {quantity}")
        pnl = pos.reduce(quantity, price)
        if pos.is_empty:
            del self._positions[symbol]
        return pnl

    # ── 查 ──────────────────────────────────────

    def get(self, symbol: str) -> Optional[Position]:
        """获取单票持仓，不存在返回 None"""
        return self._positions.get(symbol)

    def has(self, symbol: str) -> bool:
        return symbol in self._positions

    @property
    def symbols(self) -> List[str]:
        return list(self._positions.keys())

    @property
    def count(self) -> int:
        return len(self._positions)

    @property
    def is_empty(self) -> bool:
        return len(self._positions) == 0

    def __len__(self) -> int:
        return len(self._positions)

    def __iter__(self) -> Iterator[Position]:
        return iter(self._positions.values())

    def __contains__(self, symbol: str) -> bool:
        return symbol in self._positions

    # ── 行情更新 ────────────────────────────────

    def update_prices(self, prices: Dict[str, float]) -> None:
        """批量更新市价"""
        for symbol, price in prices.items():
            pos = self._positions.get(symbol)
            if pos is not None:
                pos.update_price(price)

    def update_price(self, symbol: str, price: float) -> None:
        """更新单票市价"""
        pos = self._get_or_raise(symbol)
        pos.update_price(price)

    # ── 聚合查询 ────────────────────────────────

    @property
    def total_market_value(self) -> float:
        return sum(pos.market_value for pos in self._positions.values())

    @property
    def total_unrealized_pnl(self) -> float:
        return sum(pos.unrealized_pnl for pos in self._positions.values())

    @property
    def total_realized_pnl(self) -> float:
        return sum(pos.realized_profit for pos in self._positions.values())

    # ── 导出 ────────────────────────────────────

    def to_dataframe(self) -> pd.DataFrame:
        """导出为 DataFrame（兼容旧接口）"""
        if not self._positions:
            return pd.DataFrame(columns=POSITION_DF_COLUMNS)
        rows = [pos.to_series() for pos in self._positions.values()]
        df = pd.DataFrame(rows)
        # 确保列顺序与旧接口一致
        existing = [c for c in POSITION_DF_COLUMNS if c in df.columns]
        extra = [c for c in df.columns if c not in POSITION_DF_COLUMNS]
        return df[existing + extra]

    def to_dict(self) -> Dict[str, dict]:
        """{symbol: pos_dict}"""
        return {symbol: pos.to_dict() for symbol, pos in self._positions.items()}

    # ── 内部 ────────────────────────────────────

    def _get_or_raise(self, symbol: str) -> Position:
        pos = self._positions.get(symbol)
        if pos is None:
            raise KeyError(f"未持有标的: {symbol}")
        return pos

    def __repr__(self) -> str:
        return f"PositionBook(positions={self.count}, mv={self.total_market_value:,.0f})"

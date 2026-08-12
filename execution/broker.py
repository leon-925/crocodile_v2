"""Crocodile Broker — 统一交易执行层

职责：
- 订单管理（提交 / 撮合 / 撤销）
- 滑点模拟
- 手续费计算（MarketRule）
- 委托 Account 完成实际资金/持仓变更

Broker 不持有独立状态——所有资金和持仓变更通过 Account 接口完成。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from .broker_base import BrokerBase
from .order import Order, OrderSide, OrderStatus, OrderType, TimeInForce
from portfolio.market_rule import MarketRule


class Broker(BrokerBase):
    """统一交易执行层 — 对接 Account"""

    def __init__(
        self,
        account,  # Account 实例
        slippage: float = 0.0005,
    ):
        super().__init__()
        self.account = account
        self.slippage = slippage
        self.market_rule = MarketRule()

        # 订单存储（Broker 唯一持有的状态）
        self._orders: Dict[str, Order] = {}
        self._trades: List[Order] = []

    # ── 下单 ────────────────────────────────────

    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "market",
    ) -> str:
        """提交订单 → 返回 order_id"""
        order = Order(
            symbol=symbol,
            side=OrderSide(side.upper()),
            quantity=quantity,
            price=price,
            order_type=OrderType(order_type.upper()),
            time_in_force=TimeInForce.DAY,
        )
        order.submit()
        self._orders[order.order_id] = order
        return order.order_id

    # ── 撮合 ────────────────────────────────────

    def match_orders(self, market_price: Dict[str, float]) -> List[str]:
        """市价撮合所有待处理订单 → 返回成交 order_id 列表"""
        filled: List[str] = []
        for oid, order in list(self._orders.items()):
            if not order.is_active:
                continue
            symbol = order.symbol
            if symbol not in market_price:
                continue

            px = market_price[symbol]

            # 限价单检查
            if order.order_type == OrderType.LIMIT:
                if order.side == OrderSide.BUY and px > order.price:
                    continue
                if order.side == OrderSide.SELL and px < order.price:
                    continue

            # 滑点
            if order.side == OrderSide.BUY:
                fill_price = px * (1 + self.slippage)
            else:
                fill_price = px * (1 - self.slippage)

            if self._execute(order, fill_price):
                filled.append(oid)
        return filled

    # ── 撤单 ────────────────────────────────────

    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order is None or not order.is_active:
            return False
        order.cancel()
        return True

    # ── 查询 ────────────────────────────────────

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def get_orders(self) -> Dict[str, Order]:
        return self._orders

    def get_positions(self) -> pd.DataFrame:
        """委托 Account"""
        return self.account.positions

    def get_account(self) -> Dict[str, Any]:
        """委托 Account"""
        return self.account.get_account_snapshot()

    def update_market_price(self, market_data: Dict[str, float]):
        """委托 Account"""
        self.account.update_market_prices(market_data)

    # ── 内部成交 ────────────────────────────────

    def _execute(self, order: Order, price: float) -> bool:
        """执行单笔成交：算费 → Account 记账 → Order 记录"""
        qty = order.quantity
        value = price * qty

        # 手续费
        fee = self.market_rule.calculate_fee(
            order.market, price, qty, side=order.side.value
        )

        # 买入：检查资金
        if order.side == OrderSide.BUY:
            total_needed = value + fee
            if self.account.available_cash < total_needed:
                order.reject(f"资金不足: need {total_needed:.2f}, avail {self.account.available_cash:.2f}")
                return False

        # 卖出：检查持仓
        if order.side == OrderSide.SELL:
            pos = self.account.get_position(order.symbol)
            if pos is None or pos.available_quantity < qty:
                order.reject(f"持仓不足: {order.symbol}")
                return False

        # → Account 记账
        try:
            self.account.on_order_filled(
                symbol=order.symbol,
                side=order.side.value,
                price=price,
                quantity=qty,
                market=order.market,
            )
        except ValueError as e:
            order.reject(str(e))
            return False

        # → Order 记录成交
        order.fill(price=price, quantity=qty, fee=fee)
        self._trades.append(order)
        return True

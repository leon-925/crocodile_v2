"""PortfolioManager — 投资组合管理器

职责：
1. 管理目标仓位权重 (Target Weights)
2. 计算持仓偏离度并自动生成调仓订单
3. 资金预占控制 (先卖后买，防止资金超扣)
4. 遵守市场交易规则 (如 A 股 100 股整手限制)
5. 集成风控检查 (Risk Control)

依赖 Account 的标准接口（不再用 hasattr/getattr 兼容写法）。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pandas as pd

from execution.order import Order, OrderSide, OrderType, TimeInForce


class PortfolioManager:
    """投资组合管理器"""

    def __init__(
        self,
        account,  # Account 实例
        commission_rate: float = 0.0003,
        stamp_tax: float = 0.001,
        max_position: float = 0.2,
        min_trade_value: float = 1000.0,
        lot_size: int = 100,
        risk_manager=None,
    ):
        self.account = account
        self.max_position = max_position
        self.commission_rate = commission_rate
        self.stamp_tax = stamp_tax
        self.min_trade_value = min_trade_value
        self.lot_size = lot_size
        self.risk_manager = risk_manager

        self.target_weights: Dict[str, float] = {}

    # ── 目标组合设置 ─────────────────────────────

    def set_target_weights(self, weights: Dict[str, float]) -> None:
        total = sum(weights.values())
        if total > 1.0001:
            raise ValueError(f"目标总仓位 ({total:.2%}) 不能超过 100%")

        for symbol, weight in weights.items():
            if weight < 0:
                raise ValueError(f"股票 {symbol} 目标仓位不能为负数")
            if weight > self.max_position + 1e-5:
                raise ValueError(
                    f"股票 {symbol} 目标仓位 ({weight:.2%}) 超过上限 ({self.max_position:.2%})"
                )

        self.target_weights = weights.copy()

    # ── 查询（委托给 Account 标准接口）───────────

    @property
    def total_value(self) -> float:
        return self.account.get_equity()

    @property
    def available_cash(self) -> float:
        return self.account.available_cash

    def get_position(self, symbol: str):
        """返回 Position 对象或 None"""
        return self.account.get_position(symbol)

    def position_ratio(self, symbol: str) -> float:
        """当前持仓占比"""
        pos = self.get_position(symbol)
        if pos is None or pos.is_empty:
            return 0.0
        total = self.total_value
        return pos.market_value / total if total > 0 else 0.0

    # ── 估值 ─────────────────────────────────────

    def estimate_cost(self, trade_value: float, side: OrderSide) -> float:
        """估算交易费用"""
        fee = trade_value * self.commission_rate
        if side == OrderSide.SELL:
            fee += trade_value * self.stamp_tax
        return fee

    # ── 调仓计算 ─────────────────────────────────

    def calculate_adjust_quantity(
        self, symbol: str, price: float
    ) -> Tuple[int, float, OrderSide]:
        """计算调仓股数 (quantity, diff_value, side)"""
        if price <= 0:
            return 0, 0.0, OrderSide.BUY

        current_ratio = self.position_ratio(symbol)
        target_ratio = self.target_weights.get(symbol, 0.0)
        diff_ratio = target_ratio - current_ratio
        diff_value = diff_ratio * self.total_value

        if abs(diff_value) < self.min_trade_value:
            return 0, diff_value, OrderSide.BUY

        side = OrderSide.BUY if diff_value > 0 else OrderSide.SELL
        raw_qty = abs(diff_value) / price

        pos = self.get_position(symbol)
        available_qty = pos.available_quantity if pos else 0

        if side == OrderSide.BUY:
            quantity = int(raw_qty // self.lot_size) * self.lot_size
        else:
            if target_ratio == 0 or (available_qty - raw_qty) < self.lot_size:
                quantity = int(available_qty)
            else:
                quantity = int(raw_qty // self.lot_size) * self.lot_size
                quantity = min(quantity, int(available_qty))

        return quantity, diff_value, side

    # ── 核心调仓 ─────────────────────────────────

    def rebalance(self, prices: Dict[str, float]) -> List[Order]:
        """根据当前价格生成调仓订单列表（先卖后买 + 虚拟资金池 + 风控）"""
        held = set(self.account.book.symbols)
        all_symbols = set(self.target_weights.keys()) | held

        sells: List[Tuple[str, float, int]] = []
        buys: List[Tuple[str, float, int]] = []

        for symbol in all_symbols:
            price = prices.get(symbol)
            if price is None or price <= 0:
                continue
            qty, _, side = self.calculate_adjust_quantity(symbol, price)
            if qty <= 0:
                continue
            if side == OrderSide.SELL:
                sells.append((symbol, price, qty))
            else:
                buys.append((symbol, price, qty))

        orders: List[Order] = []
        projected_cash = self.available_cash

        # 先卖
        for symbol, price, qty in sells:
            order = Order(
                symbol=symbol, market="CN", side=OrderSide.SELL,
                quantity=qty, price=price, order_type=OrderType.LIMIT,
                time_in_force=TimeInForce.DAY,
            )
            if self._risk_ok(order):
                orders.append(order)
                est_val = qty * price
                projected_cash += est_val - self.estimate_cost(est_val, OrderSide.SELL)

        # 后买
        for symbol, price, qty in buys:
            while qty >= self.lot_size:
                est_val = qty * price
                total_needed = est_val + self.estimate_cost(est_val, OrderSide.BUY)
                if total_needed <= projected_cash:
                    break
                qty -= self.lot_size

            if qty < self.lot_size:
                continue

            order = Order(
                symbol=symbol, market="CN", side=OrderSide.BUY,
                quantity=qty, price=price, order_type=OrderType.LIMIT,
                time_in_force=TimeInForce.DAY,
            )
            if self._risk_ok(order):
                orders.append(order)
                projected_cash -= qty * price + self.estimate_cost(qty * price, OrderSide.BUY)

        return orders

    # ── 单股减仓 ─────────────────────────────────

    def reduce_position(
        self, symbol: str, target_ratio: float, price: float
    ) -> Optional[Order]:
        """对单只股票主动减仓"""
        current_ratio = self.position_ratio(symbol)
        if current_ratio <= target_ratio or price <= 0:
            return None

        pos = self.get_position(symbol)
        if pos is None or pos.is_empty:
            return None

        reduce_val = (current_ratio - target_ratio) * self.total_value
        raw_qty = reduce_val / price
        available = pos.available_quantity

        if target_ratio == 0 or (available - raw_qty) < self.lot_size:
            qty = int(available)
        else:
            qty = int(raw_qty // self.lot_size) * self.lot_size
            qty = min(qty, int(available))

        if qty <= 0:
            return None

        order = Order(
            symbol=symbol, market="CN", side=OrderSide.SELL,
            quantity=qty, price=price, order_type=OrderType.LIMIT,
            time_in_force=TimeInForce.DAY,
        )
        return order if self._risk_ok(order) else None

    # ── 风控 ─────────────────────────────────────

    def _risk_ok(self, order: Order) -> bool:
        if self.risk_manager is None:
            return True
        if hasattr(self.risk_manager, "check"):
            return self.risk_manager.check(order)
        if callable(self.risk_manager):
            return self.risk_manager(order)
        return True

    # ── 摘要 ────────────────────────────────────

    def summary(self) -> Dict:
        """当前组合摘要"""
        book = self.account.book
        total = self.total_value
        mv = book.total_market_value

        return {
            "cash": self.available_cash,
            "equity": total,
            "market_value": mv,
            "stock_ratio": mv / total if total > 0 else 0.0,
            "position_count": book.count,
            "target_weights": self.target_weights,
        }

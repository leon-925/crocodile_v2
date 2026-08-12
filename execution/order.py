"""Order — 交易订单

纯数据+状态机，不依赖任何业务模块。
手续费由外部（Broker/Account）计算后注入。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
import uuid
from typing import Any, Dict, List, Optional, Union

import pandas as pd


# ── 枚举 ────────────────────────────────────────

class OrderStatus(Enum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class TimeInForce(Enum):
    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


# ── Order ───────────────────────────────────────

class Order:
    """交易订单 — 纯状态机，零业务依赖"""

    __slots__ = (
        "order_id", "account_id", "symbol", "market", "side", "order_type",
        "time_in_force", "quantity", "price", "filled_quantity", "avg_fill_price",
        "fee", "executions", "status", "create_time", "submit_time",
        "cancel_time", "update_time", "reject_reason",
    )

    def __init__(
        self,
        symbol: str,
        side: Union[OrderSide, str],
        quantity: float,
        market: str = "CN",
        price: Optional[float] = None,
        order_type: Union[OrderType, str] = OrderType.MARKET,
        time_in_force: Union[TimeInForce, str] = TimeInForce.DAY,
        account_id: Optional[str] = None,
        create_time: Optional[datetime] = None,
    ):
        # 枚举容错
        self.side = OrderSide(side) if isinstance(side, str) else side
        self.order_type = OrderType(order_type) if isinstance(order_type, str) else order_type
        self.time_in_force = TimeInForce(time_in_force) if isinstance(time_in_force, str) else time_in_force

        # 校验
        if quantity <= 0:
            raise ValueError("订单委托数量必须大于0")
        if self.order_type == OrderType.LIMIT and (price is None or price <= 0):
            raise ValueError("限价单必须提供大于 0 的委托价格")
        if price is not None and price < 0:
            raise ValueError("委托价格不能小于 0")

        # 标识
        now = create_time or datetime.now()
        ts = now.strftime("%Y%m%d%H%M%S")
        self.order_id = f"ord-{ts}-{uuid.uuid4().hex[:6]}"
        self.account_id = account_id

        # 委托
        self.symbol = symbol
        self.market = market
        self.quantity = quantity
        self.price = price

        # 成交
        self.filled_quantity = 0.0
        self.avg_fill_price = 0.0
        self.fee = 0.0  # 由 Broker 设置
        self.executions = pd.DataFrame(
            columns=["execution_time", "price", "quantity", "fee"]
        )

        # 状态
        self.status = OrderStatus.CREATED
        self.create_time = now
        self.submit_time: Optional[datetime] = None
        self.cancel_time: Optional[datetime] = None
        self.update_time: Optional[datetime] = now
        self.reject_reason: Optional[str] = None

    # ── 状态机 ──────────────────────────────────

    _TRANSITIONS = {
        OrderStatus.CREATED: [
            OrderStatus.SUBMITTED, OrderStatus.CANCELLED, OrderStatus.REJECTED,
        ],
        OrderStatus.SUBMITTED: [
            OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED,
            OrderStatus.CANCELLED, OrderStatus.REJECTED,
        ],
        OrderStatus.PARTIALLY_FILLED: [
            OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED,
            OrderStatus.CANCELLED, OrderStatus.REJECTED,
        ],
        OrderStatus.FILLED: [],
        OrderStatus.CANCELLED: [],
        OrderStatus.REJECTED: [],
    }

    def _change_status(self, new_status: OrderStatus, update_time: Optional[datetime] = None):
        if new_status not in self._TRANSITIONS[self.status]:
            raise ValueError(
                f"非法状态转换: {self.status.value} -> {new_status.value} ({self.order_id})"
            )
        self.status = new_status
        self.update_time = update_time or datetime.now()

    # ── 生命周期 ────────────────────────────────

    def submit(self, time: Optional[datetime] = None):
        self._change_status(OrderStatus.SUBMITTED, time)
        self.submit_time = time or datetime.now()

    def fill(
        self,
        price: float,
        quantity: float,
        fee: float = 0.0,
        time: Optional[datetime] = None,
    ):
        """记录一笔成交（fee 由外部 Broker 计算后传入）"""
        if self.status not in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED):
            raise ValueError(f"订单状态 {self.status.value} 无法成交")

        if quantity <= 0:
            raise ValueError("成交数量必须 > 0")

        remaining = self.remaining_quantity
        if quantity > remaining + 1e-7:
            raise ValueError(f"成交数量 ({quantity}) 超过剩余 ({remaining})")

        exec_time = time or datetime.now()

        # 记录成交明细
        row = pd.DataFrame([{
            "execution_time": exec_time,
            "price": price,
            "quantity": quantity,
            "fee": fee,
        }])
        self.executions = pd.concat([self.executions, row], ignore_index=True)

        # 累加
        prev_filled = self.filled_quantity
        self.filled_quantity += quantity
        self.avg_fill_price = (
            (self.avg_fill_price * prev_filled + price * quantity)
            / self.filled_quantity
        )
        self.fee += fee

        # 状态
        if abs(self.filled_quantity - self.quantity) < 1e-7:
            self._change_status(OrderStatus.FILLED, exec_time)
        else:
            self._change_status(OrderStatus.PARTIALLY_FILLED, exec_time)

    def cancel(self, time: Optional[datetime] = None):
        self._change_status(OrderStatus.CANCELLED, time)
        self.cancel_time = time or datetime.now()

    def reject(self, reason: str = "", time: Optional[datetime] = None):
        self.reject_reason = reason
        self._change_status(OrderStatus.REJECTED, time)

    # ── 查询 ────────────────────────────────────

    @property
    def remaining_quantity(self) -> float:
        return max(0.0, self.quantity - self.filled_quantity)

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.CREATED, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED)

    @property
    def is_finished(self) -> bool:
        return self.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED)

    def get_value(self) -> Optional[float]:
        if self.filled_quantity > 0:
            return self.avg_fill_price * self.filled_quantity
        if self.price is not None:
            return self.price * self.quantity
        return None

    # ── 序列化 ──────────────────────────────────

    def to_dict(self, include_executions: bool = False) -> Dict[str, Any]:
        fmt = lambda t: t.strftime("%Y-%m-%d %H:%M:%S.%f") if isinstance(t, datetime) else t

        d = {
            "order_id": self.order_id,
            "account_id": self.account_id,
            "symbol": self.symbol,
            "market": self.market,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "time_in_force": self.time_in_force.value,
            "status": self.status.value,
            "quantity": self.quantity,
            "price": self.price,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "avg_fill_price": self.avg_fill_price,
            "fee": self.fee,
            "reject_reason": self.reject_reason,
            "create_time": fmt(self.create_time),
            "submit_time": fmt(self.submit_time),
            "cancel_time": fmt(self.cancel_time),
            "update_time": fmt(self.update_time),
        }

        if include_executions:
            d["executions"] = [e.to_dict() for e in self.executions]

        return d

    def __repr__(self):
        return (
            f"Order(id={self.order_id}, {self.symbol}, {self.side.value}, "
            f"{self.order_type.value}, px={self.price}, qty={self.quantity}, "
            f"filled={self.filled_quantity}, {self.status.value})"
        )

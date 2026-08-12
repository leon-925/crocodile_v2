"""EventDrivenBacktest — 事件驱动回测引擎

事件队列 + 回调机制。最接近实盘环境的回测方式：
MarketEvent → SignalEvent → OrderEvent → FillEvent → PortfolioEvent

适用：复杂策略（多时间框架、条件订单）、需要精确模拟交易所撮合的场合。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Deque, Dict, List, Optional

import pandas as pd

from .result import BacktestResult


# ── 事件类型 ────────────────────────────────────

class EventType(Enum):
    MARKET = auto()     # 行情更新
    SIGNAL = auto()     # 策略信号
    ORDER = auto()      # 订单提交
    FILL = auto()       # 订单成交
    CANCEL = auto()     # 订单撤销
    PORTFOLIO = auto()  # 组合更新/快照
    RISK = auto()       # 风控事件


@dataclass
class Event:
    """事件基类"""
    type: EventType
    timestamp: Any
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""

    def __repr__(self):
        return f"Event({self.type.name}, t={self.timestamp})"


# ── 事件处理器 ──────────────────────────────────

EventHandler = Callable[[Event, "EventDrivenBacktest"], List[Event]]


class EventDrivenBacktest:
    """事件驱动回测引擎

    使用方式:
        engine = EventDrivenBacktest(account, broker)
        engine.register_handler(EventType.MARKET, my_market_handler)
        engine.register_handler(EventType.SIGNAL, my_signal_handler)
        result = engine.run(price_data)
    """

    def __init__(
        self,
        account,
        broker,
        portfolio_manager=None,
        risk_manager=None,
    ):
        self.account = account
        self.broker = broker
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager

        self._queue: Deque[Event] = deque()
        self._handlers: Dict[EventType, List[EventHandler]] = {t: [] for t in EventType}
        self._event_log: List[Event] = []

        # 状态
        self.current_time = None
        self._bars_processed = 0
        self._filled_events: List[Dict] = []

    # ── 注册处理器 ───────────────────────────────

    def register_handler(self, event_type: EventType, handler: EventHandler):
        """注册事件处理器（可多个）"""
        self._handlers[event_type].append(handler)

    def on(self, event_type: EventType):
        """装饰器：注册事件处理器"""
        def decorator(func: EventHandler):
            self.register_handler(event_type, func)
            return func
        return decorator

    # ── 主循环 ───────────────────────────────────

    def run(
        self,
        df: pd.DataFrame,
        price_col: str = "close",
    ) -> BacktestResult:
        """执行事件驱动回测

        参数:
            df: OHLCV + 指标 DataFrame (index 为日期)
            price_col: 价格列名

        返回:
            BacktestResult
        """
        if df.empty:
            raise ValueError("数据为空")

        # 将每根 bar 转为 MarketEvent 入队
        for date, row in df.iterrows():
            evt = Event(
                type=EventType.MARKET,
                timestamp=date,
                data={
                    "date": date,
                    "price": row[price_col],
                    "row": row.to_dict(),
                },
            )
            self._queue.append(evt)

        snapshots = []

        # 事件循环
        while self._queue:
            event = self._queue.popleft()
            self.current_time = event.timestamp
            self._event_log.append(event)
            self._bars_processed += 1

            # 分发事件给已注册的处理器
            for handler in self._handlers.get(event.type, []):
                try:
                    new_events = handler(event, self)
                    if new_events:
                        # 按优先级插队（ORDER 优先于 SIGNAL 等）
                        self._enqueue_sorted(new_events)
                except Exception as e:
                    # 事件异常不中断回测
                    pass

            # 默认处理器（未注册时）
            if not self._handlers.get(event.type):
                self._default_handler(event)

            # 每个 MarketEvent 后记录快照
            if event.type == EventType.MARKET:
                snap = self.account.snapshot(time=event.timestamp)
                snap["date"] = event.timestamp
                snapshots.append(snap)

        # 构建结果
        eq_df = pd.DataFrame(snapshots)
        if not eq_df.empty and "date" in eq_df.columns:
            eq_df.set_index("date", inplace=True)

        return BacktestResult(
            equity_curve=eq_df,
            trades=self.account.trades.copy() if not self.account.trades.empty
            else pd.DataFrame(columns=["date", "symbol", "side", "price", "quantity", "fee", "realized_pnl"]),
            engine_name="EventDriven",
        )

    # ── 默认处理器 ───────────────────────────────

    def _default_handler(self, event: Event) -> None:
        """默认事件处理逻辑（未注册自定义处理器时）"""
        if event.type == EventType.MARKET:
            # 行情更新
            data = event.data
            row = data["row"]
            price = data["price"]

            self.account.update_market_prices({row.get("symbol", ""): price})

            # 如果有策略信号列，转为 SignalEvent
            signal = row.get("signal", 0)
            if signal != 0:
                self._queue.append(Event(
                    type=EventType.SIGNAL,
                    timestamp=event.timestamp,
                    data={"signal": signal, "symbol": row.get("symbol", ""), "price": price},
                ))

        elif event.type == EventType.SIGNAL:
            # 信号 → 目标权重 → 调仓订单
            symbol = str(event.data.get("symbol", ""))
            price = event.data["price"]
            sig = event.data["signal"]

            if self.portfolio_manager and symbol:
                if sig == 1:
                    self.portfolio_manager.set_target_weights({symbol: 0.3})
                elif sig == -1:
                    self.portfolio_manager.set_target_weights({symbol: 0.0})

                orders = self.portfolio_manager.rebalance({symbol: price})
                for order in orders:
                    try:
                        oid = self.broker.submit_order(
                            order.symbol, order.side.value, order.quantity,
                            price=price, order_type="limit",
                        )
                    except Exception:
                        pass

            # 撮合所有待处理订单
            self.broker.match_orders({symbol: price})

        elif event.type == EventType.FILL:
            # 成交后风控检查
            if self.risk_manager:
                dd_ok, _ = self.risk_manager.check_drawdown(self.account.get_equity())
                if not dd_ok:
                    self._queue.append(Event(
                        type=EventType.RISK,
                        timestamp=event.timestamp,
                        data={"action": "stop", "reason": "max_drawdown"},
                    ))

    # ── 事件排序 ─────────────────────────────────

    def _enqueue_sorted(self, events: List[Event]):
        """按优先级插入队列头部"""
        priority = {
            EventType.RISK: 0,
            EventType.CANCEL: 0,
            EventType.FILL: 1,
            EventType.ORDER: 2,
            EventType.SIGNAL: 3,
            EventType.PORTFOLIO: 4,
            EventType.MARKET: 5,
        }
        sorted_events = sorted(events, key=lambda e: priority.get(e.type, 99))
        self._queue.extendleft(reversed(sorted_events))

    # ── 查询 ────────────────────────────────────

    @property
    def event_count(self) -> int:
        return len(self._event_log)

    def event_summary(self) -> pd.DataFrame:
        """事件类型统计"""
        counts = {}
        for e in self._event_log:
            counts[e.type.name] = counts.get(e.type.name, 0) + 1
        return pd.DataFrame(list(counts.items()), columns=["event_type", "count"])

    def __repr__(self):
        return f"EventDrivenBacktest(events={self.event_count}, handlers={sum(len(h) for h in self._handlers.values())})"

"""Scheduler — 定时调度器

管理定时任务：开盘启动、盘中轮询、收盘清算、盘后报告。
内置 A 股交易时段日历。
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, time as dtime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ScheduleEvent(Enum):
    MARKET_OPEN = "market_open"        # 9:30
    MORNING_SESSION = "morning"        # 9:30-11:30
    LUNCH_BREAK = "lunch_break"        # 11:30-13:00
    AFTERNOON_SESSION = "afternoon"    # 13:00-15:00
    MARKET_CLOSE = "market_close"      # 15:00
    AFTER_HOURS = "after_hours"        # 15:00-次日
    WEEKLY_REPORT = "weekly_report"    # 周五收盘后
    CUSTOM = "custom"


class Scheduler:
    """定时调度器 — 按市场时间触发回调

    用法:
        sched = Scheduler()
        sched.on(ScheduleEvent.MARKET_OPEN, lambda: robot.start())
        sched.on(ScheduleEvent.MARKET_CLOSE, lambda: robot.stop())
        sched.on(ScheduleEvent.AFTER_HOURS, generate_daily_report)
        sched.run()
    """

    def __init__(self, check_interval: float = 1.0):
        self.check_interval = check_interval
        self._handlers: Dict[ScheduleEvent, List[Callable]] = {
            e: [] for e in ScheduleEvent
        }
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._triggered: Dict[str, bool] = {}  # 防止重复触发

    # ── 交易日判断 ──────────────────────────────

    @staticmethod
    def is_trading_day(dt: Optional[datetime] = None) -> bool:
        """判断是否为交易日（简化版：周一到周五）"""
        dt = dt or datetime.now()
        return dt.weekday() < 5

    @staticmethod
    def current_session() -> ScheduleEvent:
        """判断当前处于哪个交易时段"""
        now = datetime.now().time()
        if now < dtime(9, 30):
            return ScheduleEvent.AFTER_HOURS
        elif now < dtime(11, 30):
            return ScheduleEvent.MORNING_SESSION
        elif now < dtime(13, 0):
            return ScheduleEvent.LUNCH_BREAK
        elif now < dtime(15, 0):
            return ScheduleEvent.AFTERNOON_SESSION
        else:
            return ScheduleEvent.AFTER_HOURS

    # ── 注册回调 ────────────────────────────────

    def on(self, event: ScheduleEvent, handler: Callable) -> "Scheduler":
        """注册事件回调（可多次注册）"""
        self._handlers[event].append(handler)
        return self

    def at_time(self, hour: int, minute: int, handler: Callable, name: str = "") -> "Scheduler":
        """在指定时间触发（如 14:50 预收盘）"""
        key = f"at_{hour:02d}{minute:02d}"
        if name:
            key = name

        def checker():
            now = datetime.now()
            if now.hour == hour and now.minute == minute:
                if not self._triggered.get(key):
                    self._triggered[key] = True
                    handler()

        # 包装进自定义事件
        self._handlers[ScheduleEvent.CUSTOM].append(checker)
        return self

    # ── 运行 ────────────────────────────────────

    def run(self, blocking: bool = True):
        """启动调度循环"""
        self._running = True

        if blocking:
            self._loop()
        else:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def _loop(self):
        last_session = None
        last_date = None

        while self._running:
            now = datetime.now()

            # 交易日变化 → 重置触发标记
            today = now.date()
            if today != last_date:
                self._triggered.clear()
                last_date = today

            # ── 标准时段事件 ──
            session = self.current_session()

            # 开盘（仅交易日）
            if self.is_trading_day(now) and not self._triggered.get("market_open"):
                if now.time() >= dtime(9, 30):
                    self._triggered["market_open"] = True
                    self._dispatch(ScheduleEvent.MARKET_OPEN)

            # 收盘
            if self.is_trading_day(now) and not self._triggered.get("market_close"):
                if now.time() >= dtime(15, 0):
                    self._triggered["market_close"] = True
                    self._dispatch(ScheduleEvent.MARKET_CLOSE)

            # 盘后（仅交易日，收盘后触发一次）
            if self.is_trading_day(now) and not self._triggered.get("after_hours"):
                if now.time() >= dtime(15, 1):
                    self._triggered["after_hours"] = True
                    self._dispatch(ScheduleEvent.AFTER_HOURS)

            # 周报（周五盘后）
            if now.weekday() == 4 and not self._triggered.get("weekly_report"):
                if now.time() >= dtime(15, 1):
                    self._triggered["weekly_report"] = True
                    self._dispatch(ScheduleEvent.WEEKLY_REPORT)

            # 时段切换事件
            if session != last_session:
                self._dispatch(session)
                last_session = session

            # 自定义时间事件
            for h in self._handlers[ScheduleEvent.CUSTOM]:
                try:
                    h()
                except Exception:
                    pass

            time.sleep(self.check_interval)

    def stop(self):
        self._running = False

    def _dispatch(self, event: ScheduleEvent):
        for handler in self._handlers.get(event, []):
            try:
                handler()
            except Exception:
                pass

    def __repr__(self):
        handlers_count = sum(len(h) for h in self._handlers.values())
        return f"Scheduler(handlers={handlers_count})"

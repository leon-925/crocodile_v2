"""Crocodile v2 — Trading Module (实盘交易)

TradingRobot : 自动交易脑 — 全链路自动化循环
Scheduler    : 定时调度器 — 按交易日时段触发
RiskMonitor  : 实盘风控 — 回撤/亏损/仓位熔断
Notifier     : 告警推送 — Console/File/Webhook
"""

from .robot import TradingRobot, RobotState
from .scheduler import Scheduler, ScheduleEvent
from .risk_monitor import RiskMonitor
from .notifier import (
    Notifier,
    ConsoleNotifier,
    FileNotifier,
    WebhookNotifier,
    MultiNotifier,
    create_notifier,
)

__all__ = [
    "TradingRobot", "RobotState",
    "Scheduler", "ScheduleEvent",
    "RiskMonitor",
    "Notifier", "ConsoleNotifier", "FileNotifier",
    "WebhookNotifier", "MultiNotifier", "create_notifier",
]

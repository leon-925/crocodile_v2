"""Crocodile v2 — Backtest Module

BacktestRunner    : 统一回测入口（选择引擎模式）
VectorizedBacktest: 向量化回测（极速，纯信号）
BarByBarBacktest  : 逐 K 线回测（标准，全模块串联）
EventDrivenBacktest: 事件驱动回测（高仿真，事件队列）
BacktestResult    : 统一回测结果（报表 + 画图 + 导出）
analyze           : 旧版绩效分析（兼容）
"""

from .engine import BacktestRunner
from .vectorized import VectorizedBacktest
from .bar_by_bar import BarByBarBacktest
from .event_driven import EventDrivenBacktest
from .result import BacktestResult
from .performance import analyze

# 保留旧引擎兼容
from .engine import BacktestEngine

__all__ = [
    "BacktestRunner",
    "VectorizedBacktest",
    "BarByBarBacktest",
    "EventDrivenBacktest",
    "BacktestResult",
    "BacktestEngine",
    "analyze",
]

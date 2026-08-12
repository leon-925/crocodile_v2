"""Crocodile v2 — Data Module

DataSource      : 统一数据门面（策略/回测唯一入口）
DataStore       : SQLite 持久层
HistoricalFetcher : 历史数据拉取器
RealtimeFetcher : 实时行情拉取器
RealtimeRecorder : 实时行情记录器
FetcherBackend  : 数据源抽象基类
AkshareBackend  : akshare 数据源实现
"""

from .data_source import DataSource
from .data_store import DataStore
from .fetcher_backend import FetcherBackend
from .fetcher_akshare import AkshareBackend
from .historical_fetcher import HistoricalFetcher
from .realtime_fetcher import RealtimeFetcher
from .realtime_recorder import RealtimeRecorder
from .realtime_kline import RealtimeKLine
from .indicators import IndicatorCalculator, compute_indicators

__all__ = [
    "DataSource",
    "DataStore",
    "FetcherBackend",
    "AkshareBackend",
    "HistoricalFetcher",
    "RealtimeFetcher",
    "RealtimeRecorder",
    "RealtimeKLine",
    "IndicatorCalculator",
    "compute_indicators",
]

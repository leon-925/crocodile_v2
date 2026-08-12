"""DataSource — 统一数据门面

对外唯一入口。自动判断走历史缓存还是实时拉取。
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

import pandas as pd

from .data_store import DataStore
from .fetcher_akshare import AkshareBackend
from .fetcher_backend import FetcherBackend
from .historical_fetcher import HistoricalFetcher
from .realtime_fetcher import RealtimeFetcher
from .realtime_recorder import RealtimeRecorder


class DataSource:
    """统一数据门面 — 策略/回测只调这一个"""

    def __init__(
        self,
        db_path: str = "crocodile.db",
        backend: Optional[FetcherBackend] = None,
    ):
        self.store = DataStore(db_path)
        self.backend = backend or AkshareBackend()
        self.historical = HistoricalFetcher(self.backend, self.store)
        self.realtime = RealtimeFetcher(self.backend)
        self.recorder = RealtimeRecorder(self.realtime, self.store)

    # ── 历史数据 ────────────────────────────────

    def get_history(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        force_refetch: bool = False,
    ) -> pd.DataFrame:
        """获取历史日线（本地优先，缺则拉取）"""
        return self.historical.fetch(symbol, start_date, end_date, force=force_refetch)

    def get_history_batch(
        self,
        symbols: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        force_refetch: bool = False,
    ) -> pd.DataFrame:
        """批量获取多标的历史日线"""
        return self.historical.fetch_batch(symbols, start_date, end_date, force=force_refetch)

    # ── 实时数据 ────────────────────────────────

    def get_realtime(self, symbols: List[str]) -> pd.DataFrame:
        """获取实时行情快照"""
        return self.realtime.fetch(symbols)

    def get_realtime_prices(self, symbols: List[str]) -> Dict[str, float]:
        """获取实时价格映射 {symbol: price}"""
        return self.realtime.fetch_price_map(symbols)

    # ── 实时记录 ────────────────────────────────

    def start_recording(self, symbols: List[str], interval: float = 60.0, on_tick=None):
        """启动实时行情记录"""
        if on_tick:
            self.recorder.on_tick = on_tick
        self.recorder.start(symbols, interval)

    def stop_recording(self):
        """停止记录并持久化"""
        self.recorder.stop()

    def is_recording(self) -> bool:
        return self.recorder.is_running

    # ── 本地查询 ────────────────────────────────

    def get_local(self, symbol: str, start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
        """直接从本地 DataStore 查日线（不拉取）"""
        return self.store.get_daily(symbol, start, end)

    def get_local_minute(
        self, symbol: str, freq: str = "1m", start: Optional[str] = None, end: Optional[str] = None
    ) -> pd.DataFrame:
        """直接从本地 DataStore 查分钟线"""
        return self.store.get_minute(symbol, freq, start, end)

    def get_symbols(self) -> pd.DataFrame:
        """本地已有的股票列表"""
        return self.store.get_symbols()

    # ── 搜索 ────────────────────────────────────

    def search(self, keyword: str) -> pd.DataFrame:
        """搜索股票代码/名称"""
        return self.backend.search_symbols(keyword)

    def __repr__(self):
        return f"DataSource(backend={self.backend.name}, {self.store})"

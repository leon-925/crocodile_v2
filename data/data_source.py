"""DataSource — 统一数据门面

对外唯一入口。自动判断走历史缓存还是实时拉取。

增强接口:
    search_and_fetch(keyword) → 搜股票+拉数据一步到位
    get_kline(symbol, freq)   → 统一K线查询（日线/分钟线）
    get_realtime_kline(symbols) → 实时K线数据
    quick_view(symbol)        → 一股脑给你所有该看的
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from .data_store import DataStore
from .fetcher_akshare import AkshareBackend
from .fetcher_backend import FetcherBackend
from .historical_fetcher import HistoricalFetcher
from .realtime_fetcher import RealtimeFetcher
from .realtime_recorder import RealtimeRecorder
from .realtime_kline import RealtimeKLine


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
        self.kline = RealtimeKLine(freqs=["1m", "5m", "15m", "30m", "60m", "1d"])

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

    def search_and_fetch(
        self,
        keyword: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        force_refetch: bool = False,
    ) -> Optional[pd.DataFrame]:
        """搜股票 + 拉数据一步到位

        输入 "茅台" → 自动搜到 600519.SH → 拉历史日线
        """
        results = self.search(keyword)
        if results.empty:
            return None

        # 取第一个匹配结果
        symbol = results.iloc[0]["symbol"]
        name = results.iloc[0].get("name", "")

        df = self.get_history(symbol, start_date, end_date, force_refetch)
        if df is not None and not df.empty:
            df.attrs["symbol"] = symbol
            df.attrs["name"] = name
        return df

    # ── 统一 K 线接口 ───────────────────────────

    def get_kline(
        self,
        symbol: str,
        freq: str = "1d",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """统一 K 线查询接口

        freq: "1d" | "1m" | "5m" | "15m" | "30m" | "60m"
        """
        if freq == "1d":
            return self.get_history(symbol, start_date, end_date)

        # 分钟线从本地查
        return self.store.get_minute(
            symbol, freq,
            start_date.strftime("%Y-%m-%d") if start_date else None,
            end_date.strftime("%Y-%m-%d") if end_date else None,
        )

    # ── 实时 K 线 ───────────────────────────────

    def feed_realtime_kline(
        self,
        symbol: str,
        price: float,
        volume: float = 0,
        amount: float = 0,
        timestamp: Optional[datetime] = None,
    ):
        """喂入实时 tick 数据，自动合成所有周期 K 线"""
        self.kline.feed(symbol, price, volume, amount, timestamp)

    def get_realtime_kline(self, symbol: str, freq: str = "1m") -> pd.DataFrame:
        """获取实时 K 线数据"""
        return self.kline.get_bars(symbol, freq)

    def get_current_bar(self, symbol: str, freq: str = "1m") -> Optional[Dict[str, Any]]:
        """获取当前未闭合的 bar"""
        bar = self.kline.get_current(symbol, freq)
        return bar.to_dict() if bar else None

    def get_all_current_bars(self, symbol: str) -> Dict[str, Dict[str, Any]]:
        """获取所有周期的当前 bar"""
        return {
            freq: bar.to_dict()
            for freq, bar in self.kline.get_all_current(symbol).items()
        }

    # ── 一键快览 ────────────────────────────────

    def quick_view(self, symbol: str) -> Dict[str, Any]:
        """一股脑返回所有该看的数据

        返回:
            {
                "symbol": "600519.SH",
                "daily_kline": DataFrame,
                "realtime_quote": DataFrame,
                "realtime_kline_1m": DataFrame,
                "realtime_kline_5m": DataFrame,
                "current_bars": {...},
                "local_info": {...},
            }
        """
        result: Dict[str, Any] = {
            "symbol": symbol,
        }

        # 历史日线
        try:
            result["daily_kline"] = self.get_history(symbol)
        except Exception:
            result["daily_kline"] = None

        # 实时行情
        try:
            result["realtime_quote"] = self.get_realtime([symbol])
        except Exception:
            result["realtime_quote"] = None

        # 实时 K 线
        for freq in ["1m", "5m"]:
            try:
                result[f"realtime_kline_{freq}"] = self.kline.get_bars(symbol, freq)
            except Exception:
                result[f"realtime_kline_{freq}"] = None

        # 当前 bar
        try:
            result["current_bars"] = self.get_all_current_bars(symbol)
        except Exception:
            result["current_bars"] = {}

        # 本地存储信息
        try:
            info = self.store.get_symbol_info(symbol)
            result["local_info"] = info if info else {"symbol": symbol, "cached": False}
        except Exception:
            result["local_info"] = {"symbol": symbol, "cached": False}

        return result

    def __repr__(self):
        return f"DataSource(backend={self.backend.name}, {self.store})"

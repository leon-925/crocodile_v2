"""RealtimeRecorder — 实时行情记录器

职责：
- 定期轮询 RealtimeFetcher 获取快照
- 缓存盘中 tick 数据到内存
- 合成分钟 K 线 → 写入 DataStore
- 收盘后合成为日线 → 写入 DataStore
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

import pandas as pd

from .data_store import DataStore
from .fetcher_backend import FetcherBackend
from .realtime_fetcher import RealtimeFetcher


class RealtimeRecorder:
    """实时行情记录器

    使用方式:
        recorder = RealtimeRecorder(fetcher, store)
        recorder.start(symbols=['600519.SH'], interval=60)

        # ... 交易时段 ...

        recorder.stop()
        recorder.flush()  # 强制写入
    """

    def __init__(
        self,
        fetcher: RealtimeFetcher,
        store: DataStore,
        on_tick: Optional[Callable] = None,
    ):
        self.fetcher = fetcher
        self.store = store
        self.on_tick = on_tick  # 每次 tick 回调（可选，推送给策略/Account）

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._symbols: List[str] = []

        # 缓存
        self._ticks: List[Dict] = []  # 原始 tick 记录
        self._ohlc_cache: Dict[str, Dict] = {}  # {symbol: {open, high, low, close, volume, amount, start_time}}
        self._lock = threading.Lock()

    # ── 启停 ────────────────────────────────────

    def start(self, symbols: List[str], interval: float = 60.0):
        """启动后台轮询

        interval: 轮询间隔（秒），默认 60s
        """
        if self._running:
            return

        self._symbols = [
            FetcherBackend.normalize_symbol(s, to_format="internal")
            for s in symbols
        ]
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, args=(interval,), daemon=True)
        self._thread.start()

    def stop(self):
        """停止轮询并写入"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        self.flush()

    @property
    def is_running(self) -> bool:
        return self._running

    # ── 轮询循环 ────────────────────────────────

    def _poll_loop(self, interval: float):
        """后台轮询线程"""
        while self._running:
            try:
                self._poll_once()
            except Exception as e:
                # 记录但不中断
                pass
            time.sleep(interval)

    def _poll_once(self):
        """单次轮询"""
        now = datetime.now()
        df = self.fetcher.fetch(self._symbols)
        if df.empty:
            return

        for _, row in df.iterrows():
            symbol = row["symbol"]
            price = row["price"]
            volume = row.get("volume", 0)
            amount = row.get("amount", 0)

            # 记录 tick
            tick = {
                "symbol": symbol,
                "time": now,
                "price": price,
                "volume": volume,
                "amount": amount,
                "change_pct": row.get("change_pct"),
            }
            with self._lock:
                self._ticks.append(tick)
                self._update_ohlc_cache(symbol, price, volume, amount, now)

            # 回调
            if self.on_tick:
                self.on_tick(tick)

            # 分钟线到整分时写入
            self._flush_minute_if_due(now)

    # ── OHLC 缓存 ───────────────────────────────

    def _update_ohlc_cache(self, symbol: str, price: float, volume: float, amount: float, now: datetime):
        """更新当前分钟 K 线缓存"""
        minute_key = now.strftime("%Y-%m-%d %H:%M:00")
        cache = self._ohlc_cache

        if symbol not in cache or cache[symbol].get("minute_key") != minute_key:
            # 新分钟：写入上一分钟线
            if symbol in cache:
                prev = cache[symbol]
                self._write_minute_bar(symbol, prev)

            cache[symbol] = {
                "minute_key": minute_key,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "amount": amount,
                "start_time": now,
            }
        else:
            bar = cache[symbol]
            bar["high"] = max(bar["high"], price)
            bar["low"] = min(bar["low"], price)
            bar["close"] = price
            bar["volume"] = volume  # akshare 返回累计量，暂存最新
            bar["amount"] = amount

    def _write_minute_bar(self, symbol: str, bar: Dict):
        """写入单根分钟 K 线"""
        row = pd.DataFrame([{
            "symbol": symbol,
            "datetime": bar["minute_key"],
            "open": bar["open"],
            "high": bar["high"],
            "low": bar["low"],
            "close": bar["close"],
            "volume": bar.get("volume", 0),
            "amount": bar.get("amount", 0),
        }])
        try:
            self.store.upsert_minute(row, freq="1m")
        except Exception:
            pass

    def _flush_minute_if_due(self, now: datetime):
        """整分已过 5 秒时，写入当前缓存"""
        if now.second < 5:
            return
        for symbol in list(self._ohlc_cache.keys()):
            bar = self._ohlc_cache[symbol]
            bar_time = bar.get("start_time", now)
            if (now - bar_time).total_seconds() >= 55:
                self._write_minute_bar(symbol, bar)
                del self._ohlc_cache[symbol]

    # ── 写入 ────────────────────────────────────

    def flush(self):
        """强制写入所有缓存数据"""
        with self._lock:
            for symbol, bar in self._ohlc_cache.items():
                self._write_minute_bar(symbol, bar)
            self._ohlc_cache.clear()

            if self._ticks:
                self._synthesize_daily()

    def _synthesize_daily(self):
        """从 tick/分钟数据合成日线"""
        if not self._ticks:
            return

        df = pd.DataFrame(self._ticks)
        df["date"] = pd.to_datetime(df["time"]).dt.strftime("%Y-%m-%d")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

        daily = df.groupby(["symbol", "date"]).agg(
            open=("price", "first"),
            high=("price", "max"),
            low=("price", "min"),
            close=("price", "last"),
            volume=("volume", "last"),
            amount=("amount", "last"),
        ).reset_index()

        self.store.upsert_daily(daily)
        self._ticks.clear()

    # ── 查询 ────────────────────────────────────

    def get_ticks(self) -> pd.DataFrame:
        """返回原始 tick 数据"""
        with self._lock:
            return pd.DataFrame(self._ticks)

    def get_current_bar(self, symbol: str) -> Optional[Dict]:
        """获取当前分钟 K 线（未闭合）"""
        return self._ohlc_cache.get(symbol)

    def __repr__(self):
        return f"RealtimeRecorder(symbols={self._symbols}, running={self._running}, ticks={len(self._ticks)})"

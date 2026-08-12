"""HistoricalFetcher — 历史数据拉取器

职责：
- 按 symbol + 日期范围拉取历史 OHLCV
- 自动写入 DataStore
- 增量拉取（只拉缺的日期）
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

import pandas as pd

from .data_store import DataStore
from .fetcher_backend import FetcherBackend


class HistoricalFetcher:
    """历史数据拉取器"""

    def __init__(self, backend: FetcherBackend, store: DataStore):
        self.backend = backend
        self.store = store

    # ── 拉取单只股票 ────────────────────────────

    def fetch(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        force: bool = False,
    ) -> pd.DataFrame:
        """拉取历史日线 → 写入 DataStore → 返回 DataFrame"""
        symbol = FetcherBackend.normalize_symbol(symbol, to_format="internal")
        end_date = end_date or date.today()

        # 增量：检查已有范围
        if not force and not start_date:
            existing = self.store.get_fetch_range(symbol, freq="1d", source=self.backend.name)
            if existing:
                last_end = datetime.strptime(existing[1], "%Y-%m-%d").date()
                if last_end >= end_date - timedelta(days=1):
                    # 已有覆盖，直接查库返回
                    return self.store.get_daily(symbol, str(existing[0]), str(existing[1]))
                start_date = last_end + timedelta(days=1)

        if start_date is None:
            start_date = date(1990, 1, 1)

        # 拉取
        raw = self.backend.fetch_daily_kline(symbol, start_date, end_date)
        if raw.empty:
            return raw

        # 写入
        n = self.store.upsert_daily(raw)

        # 记录拉取日志
        dates = pd.to_datetime(raw["date"])
        self.store.log_fetch(
            symbol=symbol,
            start_date=dates.min().strftime("%Y-%m-%d"),
            end_date=dates.max().strftime("%Y-%m-%d"),
            row_count=n,
            source=self.backend.name,
        )

        return self.store.get_daily(symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

    # ── 批量拉取 ────────────────────────────────

    def fetch_batch(
        self,
        symbols: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        force: bool = False,
    ) -> pd.DataFrame:
        """批量拉取，返回多标的拼接 DataFrame"""
        frames = []
        for sym in symbols:
            df = self.fetch(sym, start_date, end_date, force)
            if not df.empty:
                df = df.reset_index()
                df["symbol"] = sym
                frames.append(df)

        if not frames:
            return pd.DataFrame()

        result = pd.concat(frames, ignore_index=True)
        result.set_index("date", inplace=True)
        return result

    # ── 获取缺失的日期范围 ──────────────────────

    def get_missing_ranges(
        self, symbol: str, start: date, end: date
    ) -> List[Tuple[date, date]]:
        """获取本地缺失的需要拉取的日期区间"""
        existing = self.store.get_daily(
            symbol,
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
        )
        if existing.empty:
            return [(start, end)]

        existing_dates = set(existing.index.date)
        missing: List[Tuple[date, date]] = []
        current = start
        gap_start = None

        while current <= end:
            if current not in existing_dates:
                if gap_start is None:
                    gap_start = current
            else:
                if gap_start is not None:
                    missing.append((gap_start, current - timedelta(days=1)))
                    gap_start = None
            current += timedelta(days=1)

        if gap_start is not None:
            missing.append((gap_start, end))

        return missing

    def __repr__(self):
        return f"HistoricalFetcher(backend={self.backend.name}, store={self.store})"

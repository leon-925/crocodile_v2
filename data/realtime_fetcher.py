"""RealtimeFetcher — 实时行情拉取器

职责：拉取当前实时行情，返回轻量快照 dict。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from .fetcher_backend import FetcherBackend


class RealtimeFetcher:
    """实时行情拉取器"""

    def __init__(self, backend: FetcherBackend):
        self.backend = backend

    def fetch(self, symbols: List[str]) -> pd.DataFrame:
        """拉取实时行情快照 → DataFrame"""
        symbols = [
            FetcherBackend.normalize_symbol(s, to_format="internal")
            for s in symbols
        ]
        return self.backend.fetch_realtime_quote(symbols)

    def fetch_one(self, symbol: str) -> Optional[Dict[str, Any]]:
        """拉取单票实时行情 → dict"""
        df = self.fetch([symbol])
        if df.empty:
            return None
        return df.iloc[0].to_dict()

    def fetch_price_map(self, symbols: List[str]) -> Dict[str, float]:
        """拉取多票最新价 → {symbol: price}，供 Broker/Account 行情更新用"""
        df = self.fetch(symbols)
        if df.empty:
            return {}
        return dict(zip(df["symbol"], df["price"]))

    def __repr__(self):
        return f"RealtimeFetcher(backend={self.backend.name})"

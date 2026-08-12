"""FetcherBackend — 数据源抽象基类

所有数据源（akshare / tushare / yfinance）必须实现此接口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Dict, List, Optional

import pandas as pd


class FetcherBackend(ABC):
    """数据源抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称"""
        ...

    @abstractmethod
    def fetch_daily_kline(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """拉取日线 OHLCV

        返回 DataFrame 列:
            date, open, high, low, close, volume, amount
        """
        ...

    @abstractmethod
    def fetch_realtime_quote(self, symbols: List[str]) -> pd.DataFrame:
        """拉取实时行情

        返回 DataFrame 列:
            symbol, name, price, change_pct, volume, amount, time
        """
        ...

    @abstractmethod
    def search_symbols(self, keyword: str) -> pd.DataFrame:
        """搜索股票代码

        返回 DataFrame 列:
            symbol, name, market, type
        """
        ...

    @staticmethod
    def validate_kline(df: pd.DataFrame) -> pd.DataFrame:
        """校验 OHLCV 数据合法性"""
        if df.empty:
            return df

        required = {"open", "high", "low", "close"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"缺少必要列: {missing}")

        # high 必须 >= low
        bad = df["high"] < df["low"]
        if bad.any():
            df.loc[bad, ["high", "low"]] = df.loc[bad, ["low", "high"]].values

        # high >= max(open, close)
        for idx in df.index:
            row = df.loc[idx]
            mx = max(row["open"], row["close"])
            if row["high"] < mx:
                df.loc[idx, "high"] = mx

        # low <= min(open, close)
        for idx in df.index:
            row = df.loc[idx]
            mn = min(row["open"], row["close"])
            if row["low"] > mn:
                df.loc[idx, "low"] = mn

        return df

    @staticmethod
    def normalize_symbol(symbol: str, to_format: str = "internal") -> str:
        """代码格式转换

        internal: 600519.SH / 000001.SZ
        akshare:  sh600519 / sz000001
        """
        if to_format == "internal":
            symbol = symbol.lower().strip()
            if symbol.startswith("sh"):
                return f"{symbol[2:]}.SH"
            elif symbol.startswith("sz"):
                return f"{symbol[2:]}.SZ"
            elif symbol.startswith("bj"):
                return f"{symbol[2:]}.BJ"
            return symbol.upper()
        elif to_format == "akshare":
            parts = symbol.upper().split(".")
            if len(parts) == 2:
                return f"{parts[1].lower()}{parts[0]}"
            return symbol.lower()
        return symbol

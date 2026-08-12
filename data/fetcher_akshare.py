"""AkshareBackend — akshare 数据源实现"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

import pandas as pd

from .fetcher_backend import FetcherBackend


class AkshareBackend(FetcherBackend):
    """基于 akshare 的数据源"""

    @property
    def name(self) -> str:
        return "akshare"

    # ── 日线 ────────────────────────────────────

    def fetch_daily_kline(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """拉取 A 股日线（前复权）"""
        try:
            import akshare as ak
        except ImportError:
            raise ImportError("请安装 akshare: pip install akshare")

        raw_symbol = self.normalize_symbol(symbol, to_format="akshare")
        start = start_date.strftime("%Y%m%d") if start_date else "19900101"
        end = end_date.strftime("%Y%m%d") if end_date else datetime.now().strftime("%Y%m%d")

        try:
            df = ak.stock_zh_a_hist(
                symbol=raw_symbol,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="qfq",  # 前复权
            )
        except Exception:
            # fallback: 不复权
            df = ak.stock_zh_a_hist(
                symbol=raw_symbol,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="",
            )

        if df.empty:
            return pd.DataFrame(columns=KLINE_COLUMNS)

        # 列名标准化
        col_map = {
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
        }
        df.rename(columns=col_map, inplace=True)

        df["symbol"] = self.normalize_symbol(symbol, to_format="internal")

        # 类型转换
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df["date"] = pd.to_datetime(df["date"])

        df.dropna(subset=["open", "close"], inplace=True)
        return self.validate_kline(df)

    # ── 实时行情 ────────────────────────────────

    def fetch_realtime_quote(self, symbols: List[str]) -> pd.DataFrame:
        """拉取实时行情"""
        try:
            import akshare as ak
        except ImportError:
            raise ImportError("请安装 akshare: pip install akshare")

        try:
            df = ak.stock_zh_a_spot_em()
        except Exception:
            return pd.DataFrame(
                columns=["symbol", "name", "price", "change_pct", "volume", "amount", "time"]
            )

        col_map = {
            "代码": "symbol",
            "名称": "name",
            "最新价": "price",
            "涨跌幅": "change_pct",
            "成交量": "volume",
            "成交额": "amount",
        }
        df.rename(columns=col_map, inplace=True)

        # 标准化 symbol
        df["symbol"] = df["symbol"].apply(
            lambda x: self.normalize_symbol(str(x), to_format="internal")
        )

        df["time"] = datetime.now()
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["change_pct"] = pd.to_numeric(df["change_pct"], errors="coerce") / 100.0
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

        cols = ["symbol", "name", "price", "change_pct", "volume", "amount", "time"]
        result = df[df["symbol"].isin(symbols)][cols] if symbols else df[cols]
        return result.reset_index(drop=True)

    # ── 搜索 ────────────────────────────────────

    def search_symbols(self, keyword: str) -> pd.DataFrame:
        """搜索股票代码/名称"""
        try:
            import akshare as ak
        except ImportError:
            raise ImportError("请安装 akshare: pip install akshare")

        try:
            df = ak.stock_info_a_code_name()
        except Exception:
            return pd.DataFrame(columns=["symbol", "name", "market", "type"])

        mask = df["名称"].str.contains(keyword, na=False) | df["代码"].str.contains(keyword, na=False)
        result = df[mask].copy()

        result["symbol"] = result["代码"].apply(
            lambda x: self.normalize_symbol(str(x), to_format="internal")
        )
        result["name"] = result["名称"]
        result["market"] = result["symbol"].str.extract(r"\.(\w+)$", expand=False)
        result["type"] = "stock"

        return result[["symbol", "name", "market", "type"]].reset_index(drop=True)


# 常量导出
KLINE_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume", "amount"]

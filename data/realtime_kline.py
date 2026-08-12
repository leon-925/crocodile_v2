"""RealtimeKLine — 实时 K 线合成器

从实时 tick/快照数据合成多周期 OHLC K 线。
支持 1m / 5m / 15m / 30m / 60m / 1d。

用法:
    kline = RealtimeKLine(freqs=['1m', '5m', '1d'])
    
    for tick in feed:
        kline.feed(symbol='600519.SH', price=150.5, volume=10000, timestamp=now)
    
    df = kline.get_bars('600519.SH', '5m')  # 完整的5分钟K线
    bar = kline.get_current('600519.SH', '1m')  # 当前未闭合的1分钟K线
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterator, List, Optional, Tuple

import pandas as pd


class Bar:
    """单根 K 线"""

    __slots__ = ("open", "high", "low", "close", "volume", "amount", "start_time", "symbol", "freq")

    def __init__(self, symbol: str, freq: str, start_time: datetime, price: float, volume: float = 0, amount: float = 0):
        self.symbol = symbol
        self.freq = freq
        self.start_time = start_time
        self.open = price
        self.high = price
        self.low = price
        self.close = price
        self.volume = volume
        self.amount = amount

    def update(self, price: float, volume: float = 0, amount: float = 0):
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += volume
        self.amount += amount

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "freq": self.freq,
            "datetime": self.start_time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "amount": self.amount,
            "is_closed": True,  # 历史 bar 都是已闭合的
        }

    @property
    def ohlc(self) -> Tuple[float, float, float, float]:
        return self.open, self.high, self.low, self.close

    def __repr__(self):
        return f"Bar({self.symbol} {self.freq} [{self.start_time}] O={self.open:.2f} H={self.high:.2f} L={self.low:.2f} C={self.close:.2f} V={self.volume:.0f})"


class RealtimeKLine:
    """实时 K 线合成器 — 从 tick 合成多周期 OHLC"""

    FREQ_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "60m": 60, "1h": 60}

    def __init__(self, freqs: List[str] = None):
        """
        freqs: ["1m", "5m", "15m", "30m", "60m", "1d"]
        """
        self.freqs = freqs or ["1m", "5m", "1d"]
        self._bars: Dict[str, List[Bar]] = defaultdict(list)  # key: "symbol:freq"
        self._current: Dict[str, Bar] = {}  # key: "symbol:freq:bar_start"
        self._daily_ohlc: Dict[str, Dict] = {}  # 日线缓存

    # ── Tick 喂入 ───────────────────────────────

    def feed(
        self,
        symbol: str,
        price: float,
        volume: float = 0,
        amount: float = 0,
        timestamp: Optional[datetime] = None,
    ):
        """喂入一个 tick/快照，自动更新所有周期的 K 线"""
        now = timestamp or datetime.now()

        for freq in self.freqs:
            bar_start = self._bar_start(now, freq)
            key = f"{symbol}:{freq}:{bar_start.isoformat()}"

            if key not in self._current:
                # 如果有上一根 bar，闭合它
                self._close_previous(symbol, freq, bar_start)

                # 新 bar
                self._current[key] = Bar(symbol, freq, bar_start, price, volume, amount)
            else:
                self._current[key].update(price, volume, amount)

        # 日线特殊处理
        self._update_daily(symbol, price, volume, amount, now)

    def _close_previous(self, symbol: str, freq: str, new_bar_start: datetime):
        """闭合当前周期上未完成的所有 bar"""
        prefix = f"{symbol}:{freq}:"
        closed = []
        for key, bar in list(self._current.items()):
            if key.startswith(prefix) and bar.start_time < new_bar_start:
                closed.append(bar)
                del self._current[key]

        for bar in closed:
            store_key = f"{symbol}:{freq}"
            self._bars[store_key].append(bar)

    def _bar_start(self, dt: datetime, freq: str) -> datetime:
        """计算 bar 的起始时间"""
        if freq == "1d":
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)

        minutes = self.FREQ_MINUTES.get(freq, 1)
        total_minutes = dt.hour * 60 + dt.minute
        bar_minute = (total_minutes // minutes) * minutes
        return dt.replace(hour=bar_minute // 60, minute=bar_minute % 60, second=0, microsecond=0)

    def _update_daily(self, symbol: str, price: float, volume: float, amount: float, now: datetime):
        """更新日线 OHLC"""
        today = now.strftime("%Y-%m-%d")
        key = f"{symbol}:{today}"

        if key not in self._daily_ohlc:
            self._daily_ohlc[key] = {
                "symbol": symbol,
                "date": today,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "amount": amount,
            }
        else:
            d = self._daily_ohlc[key]
            d["high"] = max(d["high"], price)
            d["low"] = min(d["low"], price)
            d["close"] = price
            d["volume"] = volume  # 日线 volume 取最新累计
            d["amount"] = amount

    # ── 查询 ────────────────────────────────────

    def get_bars(self, symbol: str, freq: str = "1m") -> pd.DataFrame:
        """获取已闭合的历史 K 线"""
        store_key = f"{symbol}:{freq}"
        bars = self._bars.get(store_key, [])

        if not bars:
            return pd.DataFrame(
                columns=["datetime", "open", "high", "low", "close", "volume", "amount"]
            )

        rows = [b.to_dict() for b in bars]
        df = pd.DataFrame(rows)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df.set_index("datetime", inplace=True)
        return df.sort_index()

    def get_current(self, symbol: str, freq: str = "1m") -> Optional[Bar]:
        """获取当前未闭合的 bar"""
        prefix = f"{symbol}:{freq}:"
        for key, bar in self._current.items():
            if key.startswith(prefix):
                return bar
        return None

    def get_all_current(self, symbol: str) -> Dict[str, Bar]:
        """获取某标的所有周期的当前 bar"""
        result = {}
        for freq in self.freqs:
            bar = self.get_current(symbol, freq)
            if bar:
                result[freq] = bar
        return result

    def get_daily(self) -> pd.DataFrame:
        """获取所有日线数据"""
        if not self._daily_ohlc:
            return pd.DataFrame(
                columns=["symbol", "date", "open", "high", "low", "close", "volume", "amount"]
            )
        return pd.DataFrame(list(self._daily_ohlc.values()))

    def get_all_bars(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """获取某标的所有周期数据"""
        return {freq: self.get_bars(symbol, freq) for freq in self.freqs}

    # ── 统计 ────────────────────────────────────

    @property
    def bar_count(self) -> int:
        return sum(len(v) for v in self._bars.values())

    @property
    def symbols(self) -> List[str]:
        seen = set()
        for key in self._bars:
            sym = key.split(":")[0]
            seen.add(sym)
        for key in self._current:
            sym = key.split(":")[0]
            seen.add(sym)
        return list(seen)

    # ── 清空 ────────────────────────────────────

    def flush(self):
        """强制闭合所有当前 bar 并导出"""
        for key in list(self._current.keys()):
            parts = key.split(":")
            symbol, freq = parts[0], parts[1]
            bar = self._current[key]
            store_key = f"{symbol}:{freq}"
            self._bars[store_key].append(bar)
        self._current.clear()

    def clear(self):
        """清空所有数据"""
        self._bars.clear()
        self._current.clear()
        self._daily_ohlc.clear()

    def __repr__(self):
        return f"RealtimeKLine(freqs={self.freqs}, bars={self.bar_count}, current={len(self._current)}, symbols={len(self.symbols)})"

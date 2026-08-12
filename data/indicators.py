"""IndicatorCalculator — 技术指标计算器

Fluent API，链式调用。输出直接喂策略：
    df = IndicatorCalculator(ohlcv).sma(5).sma(20).macd().bollinger().result()
    strategy.generate_signal(df)
"""

from __future__ import annotations

from typing import List, Optional, Union

import numpy as np
import pandas as pd


class IndicatorCalculator:
    """技术指标计算器 — 链式调用 + 批量快捷方法"""

    def __init__(self, df: pd.DataFrame):
        self._df = df.copy()
        # 自动检测 OHLCV 列名（大小写/中英文）
        self._col = self._detect_columns()

    def _detect_columns(self):
        """自动映射 OHLCV 列名"""
        c = self._df.columns
        return {
            "open": self._find(c, ["open", "Open", "开盘"]),
            "high": self._find(c, ["high", "High", "最高"]),
            "low": self._find(c, ["low", "Low", "最低"]),
            "close": self._find(c, ["close", "Close", "收盘"]),
            "volume": self._find(c, ["volume", "Volume", "vol", "Vol", "成交量"]),
        }

    @staticmethod
    def _find(columns, candidates):
        for c in candidates:
            if c in columns:
                return c
        return None

    def _col_close(self):
        return self._col["close"] or self._df.columns[0]

    def _col_high(self):
        return self._col["high"] or self._col_close()

    def _col_low(self):
        return self._col["low"] or self._col_close()

    # ── 移动平均 ────────────────────────────────

    def sma(self, period: Union[int, List[int]], col: Optional[str] = None, prefix: str = "SMA") -> "IndicatorCalculator":
        """简单移动平均"""
        col = col or self._col_close()
        periods = [period] if isinstance(period, int) else period
        for p in periods:
            self._df[f"{prefix}_{p}"] = self._df[col].rolling(p).mean()
        return self

    def ema(self, period: Union[int, List[int]], col: Optional[str] = None, prefix: str = "EMA") -> "IndicatorCalculator":
        """指数移动平均"""
        col = col or self._col_close()
        periods = [period] if isinstance(period, int) else period
        for p in periods:
            self._df[f"{prefix}_{p}"] = self._df[col].ewm(span=p, adjust=False).mean()
        return self

    # ── MACD ────────────────────────────────────

    def macd(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        col: Optional[str] = None,
    ) -> "IndicatorCalculator":
        """MACD: DIF / DEA / 柱状图"""
        col = col or self._col_close()
        ema_fast = self._df[col].ewm(span=fast, adjust=False).mean()
        ema_slow = self._df[col].ewm(span=slow, adjust=False).mean()
        self._df["macd_dif"] = ema_fast - ema_slow
        self._df["macd_dea"] = self._df["macd_dif"].ewm(span=signal, adjust=False).mean()
        self._df["macd_hist"] = self._df["macd_dif"] - self._df["macd_dea"]
        return self

    # ── RSI ─────────────────────────────────────

    def rsi(self, period: int = 14, col: Optional[str] = None) -> "IndicatorCalculator":
        """RSI 相对强弱指标"""
        col = col or self._col_close()
        delta = self._df[col].diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        self._df[f"rsi_{period}"] = 100 - 100 / (1 + rs)
        return self

    # ── 布林带 ──────────────────────────────────

    def bollinger(
        self,
        period: int = 20,
        std: float = 2.0,
        col: Optional[str] = None,
    ) -> "IndicatorCalculator":
        """布林带: upper / middle / lower / bandwidth / %b"""
        col = col or self._col_close()
        mid = self._df[col].rolling(period).mean()
        s = self._df[col].rolling(period).std()
        self._df["boll_upper"] = mid + std * s
        self._df["boll_middle"] = mid
        self._df["boll_lower"] = mid - std * s
        self._df["boll_bandwidth"] = (self._df["boll_upper"] - self._df["boll_lower"]) / mid
        self._df["boll_pct_b"] = (self._df[col] - self._df["boll_lower"]) / (
            self._df["boll_upper"] - self._df["boll_lower"]
        )
        return self

    # ── ATR ─────────────────────────────────────

    def atr(self, period: int = 14) -> "IndicatorCalculator":
        """ATR 平均真实波幅"""
        high, low = self._col_high(), self._col_low()
        prev_close = self._df[self._col_close()].shift(1)
        tr = pd.concat([
            self._df[high] - self._df[low],
            (self._df[high] - prev_close).abs(),
            (self._df[low] - prev_close).abs(),
        ], axis=1).max(axis=1)
        self._df[f"atr_{period}"] = tr.ewm(alpha=1 / period, adjust=False).mean()
        return self

    # ── 动量 ────────────────────────────────────

    def momentum(self, period: int = 20, col: Optional[str] = None) -> "IndicatorCalculator":
        """动量 (ROC)"""
        col = col or self._col_close()
        self._df[f"mom_{period}"] = self._df[col] - self._df[col].shift(period)
        self._df[f"momentum_{period}"] = self._df[col].pct_change(period)
        return self

    # ── 成交量 ──────────────────────────────────

    def volume_sma(self, period: int = 20) -> "IndicatorCalculator":
        """成交量均线"""
        if self._col["volume"]:
            self._df[f"vol_sma_{period}"] = self._df[self._col["volume"]].rolling(period).mean()
        return self

    def obv(self) -> "IndicatorCalculator":
        """OBV 能量潮"""
        close = self._col_close()
        vol = self._col["volume"]
        if vol:
            direction = np.where(self._df[close] > self._df[close].shift(1), 1, -1)
            self._df["obv"] = (direction * self._df[vol]).cumsum()
        return self

    # ── 其他常用 ────────────────────────────────

    def highest(self, period: int, col: Optional[str] = None) -> "IndicatorCalculator":
        col = col or self._col_close()
        self._df[f"hhv_{period}"] = self._df[col].rolling(period).max()
        return self

    def lowest(self, period: int, col: Optional[str] = None) -> "IndicatorCalculator":
        col = col or self._col_close()
        self._df[f"llv_{period}"] = self._df[col].rolling(period).min()
        return self

    def returns(self, period: int = 1, col: Optional[str] = None) -> "IndicatorCalculator":
        """收益率"""
        col = col or self._col_close()
        self._df[f"ret_{period}"] = self._df[col].pct_change(period)
        return self

    def volatility(self, period: int = 20, col: Optional[str] = None) -> "IndicatorCalculator":
        """历史波动率 (年化)"""
        col = col or self._col_close()
        ret = self._df[col].pct_change()
        self._df[f"volatility_{period}"] = ret.rolling(period).std() * np.sqrt(252)
        return self

    # ── 批量快捷方法 ─────────────────────────────

    def basic(self, sma_periods=(5, 20, 60)) -> "IndicatorCalculator":
        """基础包: SMA"""
        return self.sma(list(sma_periods))

    def momentum_pack(self) -> "IndicatorCalculator":
        """动量包: RSI(14) + MACD + MOM(20)"""
        return self.rsi(14).macd().momentum(20)

    def volatility_pack(self) -> "IndicatorCalculator":
        """波动包: Bollinger(20) + ATR(14) + VOLATILITY(20)"""
        return self.bollinger(20).atr(14).volatility(20)

    def volume_pack(self) -> "IndicatorCalculator":
        """量能包: vol_sma + obv"""
        return self.volume_sma(20).obv()

    def full(
        self,
        sma_periods=(5, 20, 60),
        ema_periods=(12, 26),
    ) -> "IndicatorCalculator":
        """全家桶: 所有常用指标"""
        return (
            self.sma(list(sma_periods))
            .ema(list(ema_periods))
            .macd().rsi(14)
            .bollinger(20).atr(14)
            .momentum(20).volume_sma(20)
            .highest(20).lowest(20)
        )

    def turtle(self, entry: int = 20, exit_period: int = 10, atr_period: int = 20) -> "IndicatorCalculator":
        """海龟策略专用: entry_high_X + exit_low_Y + atr"""
        high_col = self._col_high()
        low_col = self._col_low()
        self._df[f"entry_high_{entry}"] = self._df[high_col].rolling(entry).max()
        self._df[f"exit_low_{exit_period}"] = self._df[low_col].rolling(exit_period).min()
        # Turtle 策略里直接用 "atr" 不带周期
        if f"atr_{atr_period}" not in self._df.columns:
            self.atr(atr_period)
        self._df["atr"] = self._df.get(f"atr_{atr_period}", self._df[self._col_close()] * 0.01)
        return self

    def turtle_pack(self, entry: int = 20, exit_period: int = 10, atr_period: int = 20) -> "IndicatorCalculator":
        """海龟全家桶: entry/exit + ATR + 基础均线"""
        return self.turtle(entry, exit_period, atr_period).sma([5, 20, 60])

    # ── 结果 ────────────────────────────────────

    @property
    def df(self) -> pd.DataFrame:
        return self._df

    def result(self) -> pd.DataFrame:
        """返回结果 DataFrame（去 NaN）"""
        return self._df.dropna()

    def result_raw(self) -> pd.DataFrame:
        """返回结果 DataFrame（保留 NaN）"""
        return self._df

    def __repr__(self):
        indicator_cols = [c for c in self._df.columns if c not in self._col.values()]
        return f"IndicatorCalculator(indicators={len(indicator_cols)}: {', '.join(indicator_cols[:8])})"


# ── 快捷函数 ──────────────────────────────────────


def compute_indicators(df: pd.DataFrame, method: str = "full", **kwargs) -> pd.DataFrame:
    """一行计算指标

    用法:
        df = compute_indicators(ohlcv)                    # 全家桶
        df = compute_indicators(ohlcv, 'basic', sma_periods=(5,10,30))
        df = compute_indicators(ohlcv, 'momentum_pack')
    """
    calc = IndicatorCalculator(df)
    fn = getattr(calc, method, None)
    if fn is None:
        raise ValueError(f"Unknown method: {method}. Use basic/momentum_pack/volatility_pack/volume_pack/full")
    return fn(**kwargs).result()

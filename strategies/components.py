"""策略组件库 — 可插拔的交易逻辑积木

五种组件类型：
- EntryRule   : 入场规则（什么时候买）
- ExitRule    : 出场规则（什么时候卖）
- Filter      : 过滤器（什么情况下不买）
- StopLoss    : 止损（亏多少走人）
- TakeProfit  : 止盈（赚多少落袋）

所有组件纯函数：pd.Series 进 → pd.Series 出
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np


# ════════════════════════════════════════════════════
# 抽象基类
# ════════════════════════════════════════════════════

class EntryRule(ABC):
    """入场规则：返回 bool Series（True=买入信号）"""
    @abstractmethod
    def generate(self, df: pd.DataFrame) -> pd.Series: ...
    def get_params(self) -> Dict[str, Any]: return {"type": self.__class__.__name__}


class ExitRule(ABC):
    """出场规则：返回 bool Series（True=卖出信号）"""
    @abstractmethod
    def generate(self, df: pd.DataFrame) -> pd.Series: ...
    def get_params(self) -> Dict[str, Any]: return {"type": self.__class__.__name__}


class Filter(ABC):
    """过滤器：返回 bool Series（True=通过，False=阻止买入）"""
    @abstractmethod
    def apply(self, df: pd.DataFrame) -> pd.Series: ...
    def get_params(self) -> Dict[str, Any]: return {"type": self.__class__.__name__}


class StopLoss(ABC):
    """止损：在已有持仓的前提下，返回 bool Series（True=触发止损）"""
    @abstractmethod
    def check(self, df: pd.DataFrame, entry_idx: Optional[int] = None) -> pd.Series: ...
    def get_params(self) -> Dict[str, Any]: return {"type": self.__class__.__name__}


class TakeProfit(ABC):
    """止盈：在已有持仓的前提下，返回 bool Series（True=触发止盈）"""
    @abstractmethod
    def check(self, df: pd.DataFrame, entry_idx: Optional[int] = None) -> pd.Series: ...
    def get_params(self) -> Dict[str, Any]: return {"type": self.__class__.__name__}


# ════════════════════════════════════════════════════
# 辅助：列名自动检测
# ════════════════════════════════════════════════════

def _find_col(df: pd.DataFrame, candidates: List[str], fallback: str = "close") -> str:
    for c in candidates:
        if c in df.columns:
            return c
    return fallback


# ════════════════════════════════════════════════════
# ENTRY RULES
# ════════════════════════════════════════════════════

class MACrossEntry(EntryRule):
    """均线金叉入场：短线上穿长线"""
    def __init__(self, short: int = 5, long: int = 20):
        self.short = short
        self.long = long

    def generate(self, df: pd.DataFrame) -> pd.Series:
        s = df[_find_col(df, [f"SMA_{self.short}", f"sma_{self.short}"])]
        l = df[_find_col(df, [f"SMA_{self.long}", f"sma_{self.long}"])]
        prev_s, prev_l = s.shift(1), l.shift(1)
        return (s > l) & (prev_s <= prev_l)

    def get_params(self):
        return {"type": "ma_cross", "short": self.short, "long": self.long}


class BollingerLowerEntry(EntryRule):
    """布林下轨入场：价格跌破下轨"""
    def __init__(self, price_col: str = "close"):
        self.price_col = price_col

    def generate(self, df: pd.DataFrame) -> pd.Series:
        px = df[_find_col(df, [self.price_col, "close"])]
        lower = df[_find_col(df, ["boll_lower", "BOLL_LOWER"])]
        return px < lower

    def get_params(self):
        return {"type": "boll_lower"}


class MomentumTurnEntry(EntryRule):
    """动量转正入场：动量由负变正"""
    def __init__(self, period: int = 20):
        self.period = period

    def generate(self, df: pd.DataFrame) -> pd.Series:
        mom = df[_find_col(df, [f"momentum_{self.period}", f"mom_{self.period}"])]
        prev_mom = mom.shift(1)
        return (mom > 0) & (prev_mom <= 0)

    def get_params(self):
        return {"type": "momentum_turn", "period": self.period}


class TurtleBreakoutEntry(EntryRule):
    """海龟突破入场：价格突破 N 日最高价"""
    def __init__(self, period: int = 20):
        self.period = period

    def generate(self, df: pd.DataFrame) -> pd.Series:
        high = df[_find_col(df, ["high", "High"])]
        entry_col = f"entry_high_{self.period}"
        if entry_col in df.columns:
            return high > df[entry_col].shift(1)
        return high > high.rolling(self.period).max().shift(1)

    def get_params(self):
        return {"type": "turtle_breakout", "period": self.period}


class PriceBreakEntry(EntryRule):
    """价格突破入场：收盘价突破 N 日最高"""
    def __init__(self, period: int = 20, price_col: str = "close"):
        self.period = period
        self.price_col = price_col

    def generate(self, df: pd.DataFrame) -> pd.Series:
        px = df[_find_col(df, [self.price_col, "close"])]
        return px > px.rolling(self.period).max().shift(1)

    def get_params(self):
        return {"type": "price_break", "period": self.period}


# ════════════════════════════════════════════════════
# EXIT RULES
# ════════════════════════════════════════════════════

class MACrossExit(ExitRule):
    """均线死叉出场：短线下穿长线"""
    def __init__(self, short: int = 5, long: int = 20):
        self.short = short
        self.long = long

    def generate(self, df: pd.DataFrame) -> pd.Series:
        s = df[_find_col(df, [f"SMA_{self.short}", f"sma_{self.short}"])]
        l = df[_find_col(df, [f"SMA_{self.long}", f"sma_{self.long}"])]
        prev_s, prev_l = s.shift(1), l.shift(1)
        return (s < l) & (prev_s >= prev_l)

    def get_params(self):
        return {"type": "ma_cross", "short": self.short, "long": self.long}


class BollingerUpperExit(ExitRule):
    """布林上轨出场：价格突破上轨"""
    def __init__(self, price_col: str = "close"):
        self.price_col = price_col

    def generate(self, df: pd.DataFrame) -> pd.Series:
        px = df[_find_col(df, [self.price_col, "close"])]
        upper = df[_find_col(df, ["boll_upper", "BOLL_UPPER"])]
        return px > upper

    def get_params(self):
        return {"type": "boll_upper"}


class MomentumTurnExit(ExitRule):
    """动量转负出场：动量由正变负"""
    def __init__(self, period: int = 20):
        self.period = period

    def generate(self, df: pd.DataFrame) -> pd.Series:
        mom = df[_find_col(df, [f"momentum_{self.period}", f"mom_{self.period}"])]
        prev_mom = mom.shift(1)
        return (mom < 0) & (prev_mom >= 0)

    def get_params(self):
        return {"type": "momentum_turn", "period": self.period}


class TurtleExit(ExitRule):
    """海龟出场：价格跌破 N 日最低价"""
    def __init__(self, period: int = 10):
        self.period = period

    def generate(self, df: pd.DataFrame) -> pd.Series:
        low = df[_find_col(df, ["low", "Low"])]
        exit_col = f"exit_low_{self.period}"
        if exit_col in df.columns:
            return low < df[exit_col].shift(1)
        return low < low.rolling(self.period).min().shift(1)

    def get_params(self):
        return {"type": "turtle_exit", "period": self.period}


class TimeExit(ExitRule):
    """持仓天数出场：持有 N 天后自动卖出"""
    def __init__(self, days: int = 20):
        self.days = days

    def generate(self, df: pd.DataFrame) -> pd.Series:
        # 需要 CompositeStrategy 传入持仓起始点
        # 默认返回全 False，由 CompositeStrategy 覆盖
        return pd.Series(False, index=df.index)

    def get_params(self):
        return {"type": "time_exit", "days": self.days}


# ════════════════════════════════════════════════════
# FILTERS
# ════════════════════════════════════════════════════

class RSIFilter(Filter):
    """RSI 过滤：超买不买，超卖不卖（可配置）"""
    def __init__(self, period: int = 14, max_rsi: float = 70.0, min_rsi: float = 0.0):
        self.period = period
        self.max_rsi = max_rsi
        self.min_rsi = min_rsi

    def apply(self, df: pd.DataFrame) -> pd.Series:
        rsi = df[_find_col(df, [f"rsi_{self.period}", f"RSI_{self.period}"], "close")]
        result = pd.Series(True, index=df.index)
        if self.max_rsi < 100:
            result &= rsi <= self.max_rsi
        if self.min_rsi > 0:
            result &= rsi >= self.min_rsi
        return result

    def get_params(self):
        return {"type": "rsi", "period": self.period, "max": self.max_rsi, "min": self.min_rsi}


class VolumeFilter(Filter):
    """成交量过滤：成交量 > N 日均量的 M 倍才允许交易"""
    def __init__(self, period: int = 20, min_ratio: float = 1.0):
        self.period = period
        self.min_ratio = min_ratio

    def apply(self, df: pd.DataFrame) -> pd.Series:
        vol = df[_find_col(df, ["volume", "Volume"], "close")]
        vol_sma = df.get(f"vol_sma_{self.period}", vol.rolling(self.period).mean())
        return vol >= vol_sma * self.min_ratio

    def get_params(self):
        return {"type": "volume", "period": self.period, "min_ratio": self.min_ratio}


class TrendFilter(Filter):
    """趋势过滤：价格在 N 日均线之上才允许买入"""
    def __init__(self, period: int = 60, price_col: str = "close"):
        self.period = period
        self.price_col = price_col

    def apply(self, df: pd.DataFrame) -> pd.Series:
        px = df[_find_col(df, [self.price_col, "close"])]
        ma = df.get(f"SMA_{self.period}", df.get(f"sma_{self.period}", px.rolling(self.period).mean()))
        return px > ma

    def get_params(self):
        return {"type": "trend", "period": self.period}


class VolatilityFilter(Filter):
    """波动率过滤：波动率 < 阈值才允许交易"""
    def __init__(self, period: int = 20, max_vol: float = 0.5):
        self.period = period
        self.max_vol = max_vol

    def apply(self, df: pd.DataFrame) -> pd.Series:
        vol = df[_find_col(df, [f"volatility_{self.period}", f"VOLATILITY_{self.period}"], "close")]
        return vol <= self.max_vol

    def get_params(self):
        return {"type": "volatility", "period": self.period, "max": self.max_vol}


# ════════════════════════════════════════════════════
# STOP LOSS
# ════════════════════════════════════════════════════

class ATRStopLoss(StopLoss):
    """ATR 止损：价格 < 入场价 - N * ATR"""
    def __init__(self, atr_period: int = 14, multiplier: float = 2.0):
        self.atr_period = atr_period
        self.multiplier = multiplier

    def check(self, df: pd.DataFrame, entry_idx: Optional[int] = None) -> pd.Series:
        close = df[_find_col(df, ["close", "Close"])]
        atr = df[_find_col(df, [f"atr_{self.atr_period}", f"ATR_{self.atr_period}", "atr"], "close")]

        if entry_idx is not None:
            entry_price = close.iloc[entry_idx]
            return close < entry_price - self.multiplier * atr
        return pd.Series(False, index=df.index)

    def get_params(self):
        return {"type": "atr", "atr_period": self.atr_period, "multiplier": self.multiplier}


class FixedPctStopLoss(StopLoss):
    """固定比例止损：亏损超过 X%"""
    def __init__(self, pct: float = 0.05):
        self.pct = pct

    def check(self, df: pd.DataFrame, entry_idx: Optional[int] = None) -> pd.Series:
        close = df[_find_col(df, ["close", "Close"])]
        if entry_idx is not None:
            entry_price = close.iloc[entry_idx]
            return close < entry_price * (1 - self.pct)
        return pd.Series(False, index=df.index)

    def get_params(self):
        return {"type": "fixed_pct", "pct": self.pct}


class TrailingStopLoss(StopLoss):
    """移动止损：从最高点回撤超过 X%"""
    def __init__(self, pct: float = 0.05):
        self.pct = pct

    def check(self, df: pd.DataFrame, entry_idx: Optional[int] = None) -> pd.Series:
        close = df[_find_col(df, ["close", "Close"])]
        if entry_idx is not None:
            window = close.iloc[entry_idx:]
            peak = window.expanding().max()
            return window < peak * (1 - self.pct)
        # 无 entry_idx 时，检查 price 是否从历史最高回撤
        peak = close.expanding().max()
        return close < peak * (1 - self.pct)

    def get_params(self):
        return {"type": "trailing", "pct": self.pct}


# ════════════════════════════════════════════════════
# TAKE PROFIT
# ════════════════════════════════════════════════════

class FixedPctTakeProfit(TakeProfit):
    """固定比例止盈：盈利超过 X%"""
    def __init__(self, target: float = 0.15):
        self.target = target

    def check(self, df: pd.DataFrame, entry_idx: Optional[int] = None) -> pd.Series:
        close = df[_find_col(df, ["close", "Close"])]
        if entry_idx is not None:
            entry_price = close.iloc[entry_idx]
            return close > entry_price * (1 + self.target)
        return pd.Series(False, index=df.index)

    def get_params(self):
        return {"type": "fixed_pct", "target": self.target}


class MATouchTakeProfit(TakeProfit):
    """均线止盈：价格触碰均线"""
    def __init__(self, period: int = 5):
        self.period = period

    def check(self, df: pd.DataFrame, entry_idx: Optional[int] = None) -> pd.Series:
        close = df[_find_col(df, ["close", "Close"])]
        ma = df.get(f"SMA_{self.period}", df.get(f"sma_{self.period}", close.rolling(self.period).mean()))
        return close <= ma

    def get_params(self):
        return {"type": "ma_touch", "period": self.period}


# ════════════════════════════════════════════════════
# 组件注册表
# ════════════════════════════════════════════════════

ENTRY_REGISTRY = {
    "ma_cross": MACrossEntry,
    "boll_lower": BollingerLowerEntry,
    "momentum_turn": MomentumTurnEntry,
    "turtle_breakout": TurtleBreakoutEntry,
    "price_break": PriceBreakEntry,
}

EXIT_REGISTRY = {
    "ma_cross": MACrossExit,
    "boll_upper": BollingerUpperExit,
    "momentum_turn": MomentumTurnExit,
    "turtle_exit": TurtleExit,
    "time_exit": TimeExit,
}

FILTER_REGISTRY = {
    "rsi": RSIFilter,
    "volume": VolumeFilter,
    "trend": TrendFilter,
    "volatility": VolatilityFilter,
}

STOP_LOSS_REGISTRY = {
    "atr": ATRStopLoss,
    "fixed_pct": FixedPctStopLoss,
    "trailing": TrailingStopLoss,
}

TAKE_PROFIT_REGISTRY = {
    "fixed_pct": FixedPctTakeProfit,
    "ma_touch": MATouchTakeProfit,
}

"""FactorEngine — 量化因子工程引擎

从 OHLCV + 指标数据自动构造 ML-ready 特征矩阵。

核心流程:
    FactorEngine(df)
        .add_price_factors()      # 价量因子
        .add_momentum_factors()   # 动量因子
        .add_volatility_factors() # 波动因子
        .add_volume_factors()     # 量能因子
        .add_rolling_stats()      # 滚动统计
        .add_lag_features()       # 滞后特征
        .create_labels()          # 监督学习标签
        .clean()                  # 清洗
        .build()                  # → X, y
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, RobustScaler


class FactorEngine:
    """量化因子工程引擎"""

    def __init__(self, df: pd.DataFrame):
        self._df = df.copy()
        self._factor_cols: List[str] = []
        self._label_col: Optional[str] = None
        self._col_map = self._detect_columns()

    def _detect_columns(self):
        c = self._df.columns
        return {
            "open": self._first(c, ["open", "Open", "开盘"]),
            "high": self._first(c, ["high", "High", "最高"]),
            "low": self._first(c, ["low", "Low", "最低"]),
            "close": self._first(c, ["close", "Close", "收盘"]),
            "volume": self._first(c, ["volume", "Volume", "vol", "成交量"]),
        }

    @staticmethod
    def _first(columns, candidates):
        for c in candidates:
            if c in columns:
                return c
        return None

    # ── 价量因子 ─────────────────────────────────

    def add_price_factors(self) -> "FactorEngine":
        """价量基础因子"""
        o, h, l, c, v = self._get_ohlcv()
        df = self._df

        # 收益率
        for p in [1, 3, 5, 10, 20]:
            df[f"ret_{p}d"] = df[c].pct_change(p)
            self._factor_cols.append(f"ret_{p}d")

        # 日内振幅
        if h and l:
            df["amplitude"] = (df[h] - df[l]) / df[c]
            self._factor_cols.append("amplitude")

        # 上下影线
        if o and h and l and c:
            df["upper_shadow"] = (df[h] - df[[o, c]].max(axis=1)) / (df[h] - df[l] + 1e-9)
            df["lower_shadow"] = (df[[o, c]].min(axis=1) - df[l]) / (df[h] - df[l] + 1e-9)
            self._factor_cols.extend(["upper_shadow", "lower_shadow"])

        # 相对位置 (close 在 high-low 区间的位置)
        if h and l:
            df["position_in_range"] = (df[c] - df[l]) / (df[h] - df[l] + 1e-9)
            self._factor_cols.append("position_in_range")

        return self

    # ── 动量因子 ─────────────────────────────────

    def add_momentum_factors(self, periods: List[int] = None) -> "FactorEngine":
        """动量因子"""
        if periods is None:
            periods = [5, 10, 20, 60]
        c = self._get_ohlcv()[3]
        df = self._df

        for p in periods:
            # RSI 简化版
            delta = df[c].diff()
            gain = delta.clip(lower=0)
            loss = (-delta).clip(lower=0)
            avg_gain = gain.ewm(alpha=1 / p, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1 / p, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            df[f"rsi_{p}"] = 100 - 100 / (1 + rs)
            self._factor_cols.append(f"rsi_{p}")

            # 价格位置（相比 N 日均线）
            ma = df[c].rolling(p).mean()
            df[f"ma_dev_{p}"] = (df[c] - ma) / ma
            self._factor_cols.append(f"ma_dev_{p}")

            # N 日新高/新低距离
            high_n = df[c].rolling(p).max()
            low_n = df[c].rolling(p).min()
            df[f"high_dist_{p}"] = (df[c] - high_n) / high_n
            df[f"low_dist_{p}"] = (df[c] - low_n) / low_n
            self._factor_cols.extend([f"high_dist_{p}", f"low_dist_{p}"])

            # 涨跌天数比例
            up_days = (df[c].diff() > 0).rolling(p).sum()
            df[f"up_ratio_{p}"] = up_days / p
            self._factor_cols.append(f"up_ratio_{p}")

        return self

    # ── 波动因子 ─────────────────────────────────

    def add_volatility_factors(self, periods: List[int] = None) -> "FactorEngine":
        """波动率因子"""
        if periods is None:
            periods = [5, 10, 20]
        c = self._get_ohlcv()[3]
        df = self._df
        ret = df[c].pct_change()

        for p in periods:
            # 历史波动率
            df[f"volatility_{p}"] = ret.rolling(p).std() * np.sqrt(252)
            self._factor_cols.append(f"volatility_{p}")

            # ATR 简化
            h, l = self._get_ohlcv()[1], self._get_ohlcv()[2]
            if h and l:
                prev_c = df[c].shift(1)
                tr = pd.concat([
                    df[h] - df[l],
                    (df[h] - prev_c).abs(),
                    (df[l] - prev_c).abs(),
                ], axis=1).max(axis=1)
                df[f"atr_{p}"] = tr.ewm(alpha=1 / p, adjust=False).mean()
                self._factor_cols.append(f"atr_{p}")

            # 波动率变化
            df[f"vol_change_{p}"] = df[f"volatility_{p}"].diff(p)
            self._factor_cols.append(f"vol_change_{p}")

        return self

    # ── 量能因子 ─────────────────────────────────

    def add_volume_factors(self, periods: List[int] = None) -> "FactorEngine":
        """成交量因子"""
        if periods is None:
            periods = [5, 20]
        v = self._get_ohlcv()[4]
        c = self._get_ohlcv()[3]
        if v is None:
            return self
        df = self._df

        for p in periods:
            # 量比
            vol_ma = df[v].rolling(p).mean()
            df[f"volume_ratio_{p}"] = df[v] / vol_ma
            self._factor_cols.append(f"volume_ratio_{p}")

            # 量价相关性
            df[f"vol_price_corr_{p}"] = df[v].rolling(p).corr(df[c])
            self._factor_cols.append(f"vol_price_corr_{p}")

            # 量波动
            df[f"vol_volatility_{p}"] = df[v].pct_change().rolling(p).std()
            self._factor_cols.append(f"vol_volatility_{p}")

        # OBV 变化率
        if c:
            direction = np.where(df[c].diff() > 0, 1, -1)
            obv = (direction * df[v].fillna(0)).cumsum()
            df["obv_change"] = obv.pct_change(5)
            self._factor_cols.append("obv_change")

        return self

    # ── 滚动统计 ─────────────────────────────────

    def add_rolling_stats(
        self,
        cols: Optional[List[str]] = None,
        windows: List[int] = None,
    ) -> "FactorEngine":
        """对已有因子做滚动统计（均值/标准差/偏度/最大/最小）"""
        if windows is None:
            windows = [5, 10, 20]
        if cols is None:
            cols = [self._get_ohlcv()[3]]  # default: close
            if self._factor_cols:
                cols = cols + list(self._factor_cols)[:10]  # top 10 factors

        df = self._df
        for col in cols:
            if col not in df.columns:
                continue
            for w in windows:
                s = df[col].dropna()
                df[f"{col}_sma_{w}"] = s.rolling(w).mean()
                df[f"{col}_std_{w}"] = s.rolling(w).std()
                df[f"{col}_max_{w}"] = s.rolling(w).max()
                df[f"{col}_min_{w}"] = s.rolling(w).min()
                self._factor_cols.extend([
                    f"{col}_sma_{w}", f"{col}_std_{w}",
                    f"{col}_max_{w}", f"{col}_min_{w}",
                ])

        return self

    # ── 滞后特征 ─────────────────────────────────

    def add_lag_features(self, lags: List[int] = None) -> "FactorEngine":
        """给已有因子加滞后（让模型看到前几天的值）"""
        if lags is None:
            lags = [1, 2, 3, 5]

        cols = list(self._factor_cols)
        df = self._df
        for col in cols:
            if col not in df.columns or col.startswith("target_"):
                continue
            for lag in lags:
                df[f"{col}_lag{lag}"] = df[col].shift(lag)
                self._factor_cols.append(f"{col}_lag{lag}")

        return self

    # ── 标签生成 ─────────────────────────────────

    def create_labels(
        self,
        forward_period: int = 5,
        label_type: str = "return",  # "return" | "direction" | "triple_barrier"
        threshold: float = 0.01,
    ) -> "FactorEngine":
        """生成监督学习标签

        forward_period: 预测未来 N 天的收益
        label_type:
            "return"   - 连续值（回归）
            "direction" - 二分类 (1=涨, 0=跌)
            "triple_barrier" - 三分类 (1=涨超阈值, -1=跌超阈值, 0=震荡)
        """
        c = self._get_ohlcv()[3]
        df = self._df

        # 未来收益率
        future_ret = df[c].shift(-forward_period) / df[c] - 1
        self._label_col = f"target_{forward_period}d"

        if label_type == "return":
            df[self._label_col] = future_ret
        elif label_type == "direction":
            df[self._label_col] = (future_ret > 0).astype(int)
        elif label_type == "triple_barrier":
            df[self._label_col] = 0
            df.loc[future_ret > threshold, self._label_col] = 1
            df.loc[future_ret < -threshold, self._label_col] = -1
        else:
            raise ValueError(f"Unknown label_type: {label_type}")

        return self

    # ── 清洗 ─────────────────────────────────────

    def clean(
        self,
        drop_na: bool = True,
        clip_percentile: float = 0.01,
        scale: str = "robust",  # "robust" | "standard" | None
    ) -> "FactorEngine":
        """清洗特征矩阵"""
        df = self._df
        available = [c for c in self._factor_cols if c in df.columns]

        if not available:
            return self

        # 1. 去除 Inf
        df[available] = df[available].replace([np.inf, -np.inf], np.nan)

        # 2. 截尾（去掉极端值）
        if clip_percentile > 0:
            lower = df[available].quantile(clip_percentile)
            upper = df[available].quantile(1 - clip_percentile)
            df[available] = df[available].clip(lower, upper, axis=1)

        # 3. 标准化
        if scale == "robust":
            scaler = RobustScaler()
            valid_mask = df[available].notna().all(axis=1)
            if valid_mask.any():
                df.loc[valid_mask, available] = scaler.fit_transform(
                    df.loc[valid_mask, available]
                )
        elif scale == "standard":
            scaler = StandardScaler()
            valid_mask = df[available].notna().all(axis=1)
            if valid_mask.any():
                df.loc[valid_mask, available] = scaler.fit_transform(
                    df.loc[valid_mask, available]
                )

        # 4. 去 NaN
        if drop_na:
            # 只对因子列去 NaN，保留 label 的 NaN（最后 N 天的标签无法计算）
            self._df = df.dropna(subset=available)

        return self

    # ── 构建 ─────────────────────────────────────

    def build(
        self,
        return_xy: bool = True,
    ) -> Tuple[pd.DataFrame, Optional[pd.Series]]:
        """构建特征矩阵 X 和标签 y"""
        available = [c for c in self._factor_cols if c in self._df.columns]
        X = self._df[available].copy()

        y = None
        if self._label_col and self._label_col in self._df.columns:
            y = self._df[self._label_col]

        if return_xy:
            return X, y
        return X

    @property
    def df(self) -> pd.DataFrame:
        return self._df

    @property
    def factor_names(self) -> List[str]:
        return [c for c in self._factor_cols if c in self._df.columns]

    @property
    def n_factors(self) -> int:
        return len(self.factor_names)

    # ── 快捷方法 ─────────────────────────────────

    def full_pipeline(
        self,
        forward_period: int = 5,
        label_type: str = "direction",
    ) -> "FactorEngine":
        """一键全流程"""
        return (
            self.add_price_factors()
            .add_momentum_factors()
            .add_volatility_factors()
            .add_volume_factors()
            .add_rolling_stats()
            .add_lag_features()
            .create_labels(forward_period, label_type)
            .clean()
        )

    # ── 内部 ────────────────────────────────────

    def _get_ohlcv(self):
        m = self._col_map
        return m["open"], m["high"], m["low"], m["close"], m["volume"]

    def __repr__(self):
        return f"FactorEngine(factors={self.n_factors}, label={self._label_col}, rows={len(self._df)})"

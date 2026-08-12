"""
双均线策略

短期均线上穿长期均线买入，下穿卖出。
"""

import pandas as pd

from .base_strategy import BaseStrategy


class DualMAStrategy(BaseStrategy):
    """双均线交叉策略"""

    def __init__(self, short: int = 5, long: int = 20, period_prefix: str = "S"):
        super().__init__(f"DualMA({short}/{long})")
        self.short = short
        self.long = long
        self.prefix = period_prefix

    def generate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        short_col = f"{self.prefix}MA_{self.short}"
        long_col = f"{self.prefix}MA_{self.long}"
        df["signal"] = 0

        valid = df[short_col].notna() & df[long_col].notna()
        prev_s = df[short_col].shift(1)
        prev_l = df[long_col].shift(1)

        # 金叉: 短线上穿长线
        buy = valid & (df[short_col] > df[long_col]) & (prev_s <= prev_l)
        # 死叉: 短线下穿长线
        sell = valid & (df[short_col] < df[long_col]) & (prev_s >= prev_l)

        df.loc[buy, "signal"] = 1
        df.loc[sell, "signal"] = -1
        return df

    def get_params(self):
        return {**super().get_params(), "short": self.short, "long": self.long}

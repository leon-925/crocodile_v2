"""
布林带策略

价格跌破下轨买入，突破上轨卖出。
"""

import pandas as pd

from .base_strategy import BaseStrategy


class BollingerStrategy(BaseStrategy):
    """布林带突破策略"""

    def __init__(
        self,
        upper_col: str = "boll_upper",
        lower_col: str = "boll_lower",
        price_col: str = "close",
    ):
        super().__init__("Bollinger")
        self.upper_col = upper_col
        self.lower_col = lower_col
        self.price_col = price_col

    def generate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["signal"] = 0

        valid = df[self.upper_col].notna() & df[self.lower_col].notna()
        df.loc[valid & (df[self.price_col] < df[self.lower_col]), "signal"] = 1
        df.loc[valid & (df[self.price_col] > df[self.upper_col]), "signal"] = -1
        return df

    def get_params(self):
        return {**super().get_params(), "upper_col": self.upper_col, "lower_col": self.lower_col}

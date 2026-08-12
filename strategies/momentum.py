"""
动量策略

动量由负转正时买入，由正转负时卖出。
"""

import pandas as pd

from .base_strategy import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """动量轮动策略"""

    def __init__(self, period: int = 20, momentum_col: str = ""):
        super().__init__(f"Momentum({period})")
        self.period = period
        self.momentum_col = momentum_col or f"momentum_{period}"

    def generate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["signal"] = 0

        valid = df[self.momentum_col].notna()
        pos = df[self.momentum_col] > 0
        prev_pos = pos.shift(1).fillna(False)

        df.loc[valid & pos & ~prev_pos, "signal"] = 1
        df.loc[valid & ~pos & prev_pos, "signal"] = -1
        return df

    def get_params(self):
        return {**super().get_params(), "period": self.period}

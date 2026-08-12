"""
海龟交易策略

突破 N 日最高价买入，跌破 M 日最低价卖出。
"""

import pandas as pd

from .base_strategy import BaseStrategy


class TurtleStrategy(BaseStrategy):
    """海龟交易策略"""

    def __init__(
        self,
        entry: int = 20,
        exit: int = 10,
        atr_period: int = 20,
        use_filter: bool = False,
    ):
        super().__init__(f"Turtle({entry}/{exit})")
        self.entry = entry
        self.exit = exit
        self.atr_period = atr_period
        self.use_filter = use_filter

    def generate_signal(
        self,
        df: pd.DataFrame,
        position: int = 0,
        ma_prefix: str = "S",
        ma_duration: int = 55,
    ) -> pd.DataFrame:
        df = df.copy()
        df["signal"] = 0

        entry_col = f"entry_high_{self.entry}"
        exit_col = f"exit_low_{self.exit}"

        warmup = max(self.entry, self.exit, self.atr_period)
        if len(df) < warmup:
            return df

        latest = df.iloc[-1]
        for col in [entry_col, exit_col, "atr"]:
            if col not in df.columns:
                raise KeyError(f"crocodile: missing column '{col}'")

        if pd.isna(latest[entry_col]) or pd.isna(latest[exit_col]) or pd.isna(latest["atr"]):
            return df

        price = latest["close"]

        if position == 0:
            condition = price > latest[entry_col]
            if self.use_filter:
                condition &= price > latest[f"{ma_prefix}ma_{ma_duration}"]
            if condition:
                df.loc[df.index[-1], "signal"] = 1

        elif position > 0:
            if price < latest[exit_col]:
                df.loc[df.index[-1], "signal"] = -1

        return df

    def get_params(self):
        return {
            **super().get_params(),
            "entry": self.entry,
            "exit": self.exit,
            "atr_period": self.atr_period,
            "use_filter": self.use_filter,
        }

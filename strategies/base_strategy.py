"""
Crocodile 策略基类

所有交易策略必须继承 BaseStrategy 并实现 generate_signal。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import pandas as pd


class BaseStrategy(ABC):
    """策略抽象基类"""

    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号

        参数:
            df: 包含 OHLCV 和技术指标的 DataFrame

        返回:
            df: 添加 'signal' 列 (1=买入, -1=卖出, 0=持有)
                 以及策略所需的额外列
        """
        ...

    def get_params(self) -> Dict[str, Any]:
        """返回策略参数，方便记录和调优"""
        return {
            "name": self.name,
        }

    def validate(self, df: pd.DataFrame) -> bool:
        """校验数据是否满足策略最低要求"""
        required = ["open", "high", "low", "close"]
        return all(col in df.columns for col in required)

    def __repr__(self):
        return f"{self.name}"

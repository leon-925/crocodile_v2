"""
Broker 抽象基类

所有交易接口（模拟、实盘）必须实现此接口。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BrokerBase(ABC):
    """Broker 抽象基类 — 定义统一的交易接口"""

    def __init__(self):
        pass

    @abstractmethod
    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "market",
    ) -> str:
        """提交订单，返回 order_id

        side: 'buy' / 'sell'
        order_type: 'market' / 'limit'
        """
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """撤销订单"""
        ...

    @abstractmethod
    def get_order(self, order_id: str):
        """查询单个订单"""
        ...

    @abstractmethod
    def get_orders(self):
        """查询全部订单"""
        ...

    @abstractmethod
    def get_positions(self):
        """查询当前持仓"""
        ...

    @abstractmethod
    def get_account(self) -> Dict[str, Any]:
        """查询账户信息"""
        ...

    @abstractmethod
    def update_market_price(self, market_data: Dict[str, float]):
        """更新实时行情"""
        ...

    @abstractmethod
    def match_orders(self, market_price: Dict[str, float]) -> List[str]:
        """撮合订单，返回成交 order_id 列表"""
        ...

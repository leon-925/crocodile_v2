"""Crocodile v2 — Strategies Module

BaseStrategy       : 策略抽象基类
CompositeStrategy  : 组合策略引擎（组件乐高）
StrategyBuilder    : 策略构建器（Fluent API + YAML + 预设）
组件注册表          : ENTRY/EXIT/FILTER/STOP_LOSS/TAKE_PROFIT

Legacy (兼容):
  DualMAStrategy, BollingerStrategy, MomentumStrategy, TurtleStrategy
"""

from .base_strategy import BaseStrategy
from .composite import CompositeStrategy
from .builder import StrategyBuilder

# 组件类
from .components import (
    EntryRule, ExitRule, Filter, StopLoss, TakeProfit,
    ENTRY_REGISTRY, EXIT_REGISTRY, FILTER_REGISTRY,
    STOP_LOSS_REGISTRY, TAKE_PROFIT_REGISTRY,
)

# 旧版策略（兼容）
from .dual import DualMAStrategy
from .bollinger import BollingerStrategy
from .momentum import MomentumStrategy
from .turtle import TurtleStrategy

__all__ = [
    # 新架构
    "BaseStrategy", "CompositeStrategy", "StrategyBuilder",
    "EntryRule", "ExitRule", "Filter", "StopLoss", "TakeProfit",
    "ENTRY_REGISTRY", "EXIT_REGISTRY", "FILTER_REGISTRY",
    "STOP_LOSS_REGISTRY", "TAKE_PROFIT_REGISTRY",
    # 旧版
    "DualMAStrategy", "BollingerStrategy", "MomentumStrategy", "TurtleStrategy",
]

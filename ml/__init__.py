"""Crocodile v2 — ML Module

FactorEngine : 因子工程引擎 (特征构造 + 清洗 + 标签)
ModelTrainer : 模型训练器 (XGBoost/LightGBM/RF + 交叉验证 + 保存/加载)
"""

from .features import FactorEngine
from .trainer import ModelTrainer

__all__ = ["FactorEngine", "ModelTrainer"]

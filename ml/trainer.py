"""ModelTrainer — 量化 ML 模型训练器

支持 XGBoost / LightGBM / RandomForest，内置时间序列交叉验证。
模型输出直接转信号，接入现有回测引擎。

用法:
    X, y = FactorEngine(df).full_pipeline().build()

    trainer = ModelTrainer('xgboost')
    trainer.train(X, y)
    trainer.metrics        # 准确率/精确率/召回率/F1
    trainer.feature_importance  # Top 特征
    trainer.save('model.json')

    signals = trainer.predict_signals(X_test)  # → signal 列
    result = runner.run(df_with_signals)
"""

from __future__ import annotations

import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)


class ModelTrainer:
    """量化 ML 模型训练器"""

    def __init__(self, model_type: str = "xgboost", **params):
        """
        model_type: "xgboost" | "lightgbm" | "random_forest"
        params: 传给底层模型的参数
        """
        self.model_type = model_type
        self.params = params
        self.model: Any = None
        self._metrics: Dict[str, Any] = {}
        self._feature_importance: Optional[pd.DataFrame] = None
        self._feature_names: List[str] = []
        self._train_date: Optional[str] = None

    # ── 训练 ────────────────────────────────────

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        validation_split: float = 0.2,
        **extra_params,
    ) -> "ModelTrainer":
        """训练模型 —— 时间序列分割（不打乱顺序）

        validation_split: 最后 N% 作为验证集
        """
        self._feature_names = list(X.columns)
        self._train_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.params.update(extra_params)

        # 时间序列分割（不能用 shuffle）
        split_idx = int(len(X) * (1 - validation_split))
        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

        if self.model_type == "xgboost":
            self.model = self._train_xgboost(X_train, y_train, X_val, y_val)
        elif self.model_type == "lightgbm":
            self.model = self._train_lightgbm(X_train, y_train, X_val, y_val)
        elif self.model_type == "random_forest":
            self.model = self._train_random_forest(X_train, y_train)
        else:
            raise ValueError(f"Unknown model_type: {self.model_type}")

        # 评估
        if X_val is not None and len(X_val) > 0:
            y_pred = self.model.predict(X_val)
            y_pred_binary = self._to_binary(y_pred)
            y_val_binary = self._to_binary(y_val.values)
            self._compute_metrics(y_val_binary, y_pred_binary)
            self._compute_importance()

        return self

    def _train_xgboost(self, X_train, y_train, X_val, y_val):
        try:
            import xgboost as xgb
        except ImportError:
            raise ImportError("需要 xgboost: pip install xgboost")

        params = {
            "max_depth": 5,
            "learning_rate": 0.05,
            "n_estimators": 200,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_alpha": 1.0,
            "reg_lambda": 1.0,
            "random_state": 42,
            "eval_metric": "logloss",
            **self.params,
        }

        model = xgb.XGBClassifier(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )
        return model

    def _train_lightgbm(self, X_train, y_train, X_val, y_val):
        try:
            import lightgbm as lgb
        except ImportError:
            raise ImportError("需要 lightgbm: pip install lightgbm")

        params = {
            "max_depth": 5,
            "learning_rate": 0.05,
            "n_estimators": 200,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_alpha": 1.0,
            "reg_lambda": 1.0,
            "random_state": 42,
            "verbosity": -1,
            **self.params,
        }

        model = lgb.LGBMClassifier(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
        )
        return model

    def _train_random_forest(self, X_train, y_train):
        from sklearn.ensemble import RandomForestClassifier

        params = {
            "n_estimators": 200,
            "max_depth": 10,
            "min_samples_split": 10,
            "random_state": 42,
            "n_jobs": -1,
            **self.params,
        }
        return RandomForestClassifier(**params).fit(X_train, y_train)

    # ── 交叉验证 ────────────────────────────────

    def cross_validate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_splits: int = 5,
        gap: int = 10,
    ) -> pd.DataFrame:
        """时间序列交叉验证（带间隔防止数据泄露）

        gap: 训练集和验证集之间的间隔天数
        """
        n = len(X)
        fold_size = n // (n_splits + 1)
        results = []

        for i in range(n_splits):
            train_end = (i + 1) * fold_size
            val_start = train_end + gap
            val_end = val_start + fold_size

            if val_end > n:
                break

            X_tr = X.iloc[:train_end]
            y_tr = y.iloc[:train_end]
            X_val = X.iloc[val_start:val_end]
            y_val = y.iloc[val_start:val_end]

            if self.model_type == "xgboost":
                m = self._train_xgboost(X_tr, y_tr, X_val, y_val)
            elif self.model_type == "lightgbm":
                m = self._train_lightgbm(X_tr, y_tr, X_val, y_val)
            else:
                m = self._train_random_forest(X_tr, y_tr)

            y_pred = self._to_binary(m.predict(X_val))
            y_true = self._to_binary(y_val.values)

            from sklearn.metrics import accuracy_score, precision_score, f1_score
            results.append({
                "fold": i + 1,
                "train_end": X.index[train_end - 1],
                "val_start": X.index[val_start],
                "val_end": X.index[min(val_end - 1, n - 1)],
                "accuracy": accuracy_score(y_true, y_pred),
                "precision": precision_score(y_true, y_pred, zero_division=0),
                "f1": f1_score(y_true, y_pred, zero_division=0),
                "n_train": len(X_tr),
                "n_val": len(X_val),
            })

        return pd.DataFrame(results)

    # ── 预测 → 信号 ─────────────────────────────

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """返回模型预测"""
        if self.model is None:
            raise RuntimeError("模型尚未训练")
        return self.model.predict(X)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """返回预测概率"""
        if self.model is None:
            raise RuntimeError("模型尚未训练")
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X)
        return self.model.predict(X)

    def predict_signals(
        self,
        X: pd.DataFrame,
        threshold: float = 0.5,
        original_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """将模型预测转为交易信号 DataFrame

        返回原 DataFrame + signal 列，可直接喂回测引擎。
        """
        if self.model is None:
            raise RuntimeError("模型尚未训练")

        proba = self.predict_proba(X)

        # 二分类概率
        if proba.ndim == 2 and proba.shape[1] >= 2:
            buy_prob = proba[:, 1]
        else:
            buy_prob = proba

        # 转信号
        signals = np.zeros(len(buy_prob))
        signals[buy_prob > threshold] = 1
        signals[buy_prob < (1 - threshold)] = -1

        if original_df is not None:
            result = original_df.iloc[-len(signals):].copy()
            result["signal"] = signals
            result["ml_proba"] = buy_prob
            return result

        return pd.DataFrame({"signal": signals, "ml_proba": buy_prob})

    # ── 指标 ────────────────────────────────────

    def _compute_metrics(self, y_true, y_pred):
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score,
            f1_score, confusion_matrix, classification_report,
        )

        self._metrics = {
            "accuracy": accuracy_score(y_true, y_pred),
            "precision": precision_score(y_true, y_pred, zero_division=0),
            "recall": recall_score(y_true, y_pred, zero_division=0),
            "f1": f1_score(y_true, y_pred, zero_division=0),
            "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
        }

    def _compute_importance(self):
        if self.model is None or not self._feature_names:
            return

        if hasattr(self.model, "feature_importances_"):
            imp = self.model.feature_importances_
        elif hasattr(self.model, "coef_"):
            imp = np.abs(self.model.coef_).flatten()
        else:
            return

        idx = np.argsort(imp)[::-1]
        self._feature_importance = pd.DataFrame({
            "feature": [self._feature_names[i] for i in idx],
            "importance": imp[idx],
        })

    @staticmethod
    def _to_binary(arr) -> np.ndarray:
        return (np.array(arr) > 0.5).astype(int) if arr.dtype != int else np.array(arr).astype(int)

    # ── 属性 ────────────────────────────────────

    @property
    def metrics(self) -> Dict[str, Any]:
        return self._metrics

    @property
    def feature_importance(self) -> Optional[pd.DataFrame]:
        return self._feature_importance

    @property
    def top_features(self, n: int = 10) -> List[str]:
        if self._feature_importance is None:
            return []
        return self._feature_importance.head(n)["feature"].tolist()

    # ── 保存/加载 ───────────────────────────────

    def save(self, path: str):
        """保存模型"""
        import joblib
        data = {
            "model": self.model,
            "model_type": self.model_type,
            "feature_names": self._feature_names,
            "metrics": self._metrics,
            "train_date": self._train_date,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(data, path)

    @classmethod
    def load(cls, path: str) -> "ModelTrainer":
        """加载模型"""
        import joblib
        data = joblib.load(path)
        trainer = cls(data["model_type"])
        trainer.model = data["model"]
        trainer._feature_names = data.get("feature_names", [])
        trainer._metrics = data.get("metrics", {})
        trainer._train_date = data.get("train_date", "")
        return trainer

    # ── 报告 ────────────────────────────────────

    def report(self) -> str:
        """打印训练报告"""
        lines = [
            "=" * 50,
            f"  Model Training Report ({self.model_type})",
            "=" * 50,
            f"  Train Date : {self._train_date or 'N/A'}",
            f"  Features   : {len(self._feature_names)}",
        ]
        if self._metrics:
            m = self._metrics
            lines += [
                f"  Accuracy   : {m.get('accuracy', 0):.4f}",
                f"  Precision  : {m.get('precision', 0):.4f}",
                f"  Recall     : {m.get('recall', 0):.4f}",
                f"  F1 Score   : {m.get('f1', 0):.4f}",
            ]

        if self._feature_importance is not None:
            lines.append("-" * 50)
            lines.append("  Top 10 Features:")
            for _, row in self._feature_importance.head(10).iterrows():
                lines.append(f"    {row['feature']:<40} {row['importance']:.4f}")

        lines.append("=" * 50)
        text = "\n".join(lines)
        print(text)
        return text

    def __repr__(self):
        f1 = self._metrics.get("f1", 0)
        return f"ModelTrainer({self.model_type}, features={len(self._feature_names)}, f1={f1:.3f})"

"""StrategyBuilder — 策略构建器

Fluent API + YAML 配置，一套语法创建任意组合策略。

用法:
    # Fluent API
    strat = StrategyBuilder("我的策略") \
        .entry("ma_cross", short=5, long=20) \
        .filter("rsi", max=70) \
        .exit("ma_cross", short=5, long=20) \
        .stop_loss("atr", multiplier=2) \
        .take_profit("fixed_pct", target=0.15) \
        .build()

    # YAML
    strat = StrategyBuilder.from_yaml("my_strategy.yaml")

    # 预设
    strat = StrategyBuilder.preset("dual_ma")
    strat = StrategyBuilder.preset("bollinger_band")
    strat = StrategyBuilder.preset("turtle")
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

from .components import (
    ENTRY_REGISTRY, EXIT_REGISTRY, FILTER_REGISTRY,
    STOP_LOSS_REGISTRY, TAKE_PROFIT_REGISTRY,
    EntryRule, ExitRule, Filter, StopLoss, TakeProfit,
)
from .composite import CompositeStrategy


class StrategyBuilder:
    """策略构建器 — 小白友好的策略拼装工具"""

    def __init__(self, name: str = "MyStrategy"):
        self._name = name
        self._entry_type: Optional[str] = None
        self._entry_kwargs: Dict[str, Any] = {}
        self._exit_type: Optional[str] = None
        self._exit_kwargs: Dict[str, Any] = {}
        self._filters: List[tuple] = []  # [(type, kwargs), ...]
        self._stop_losses: List[tuple] = []
        self._take_profits: List[tuple] = []

    # ── Fluent API ───────────────────────────────

    def entry(self, component_type: str, **kwargs) -> "StrategyBuilder":
        """设置入场规则

        可选: ma_cross, boll_lower, momentum_turn, turtle_breakout, price_break
        """
        if component_type not in ENTRY_REGISTRY:
            raise ValueError(f"未知入场类型: {component_type}。可选: {list(ENTRY_REGISTRY.keys())}")
        self._entry_type = component_type
        self._entry_kwargs = kwargs
        return self

    def exit(self, component_type: str, **kwargs) -> "StrategyBuilder":
        """设置出场规则

        可选: ma_cross, boll_upper, momentum_turn, turtle_exit, time_exit
        """
        if component_type not in EXIT_REGISTRY:
            raise ValueError(f"未知出场类型: {component_type}。可选: {list(EXIT_REGISTRY.keys())}")
        self._exit_type = component_type
        self._exit_kwargs = kwargs
        return self

    def filter(self, component_type: str, **kwargs) -> "StrategyBuilder":
        """添加过滤器

        可选: rsi, volume, trend, volatility
        """
        if component_type not in FILTER_REGISTRY:
            raise ValueError(f"未知过滤类型: {component_type}。可选: {list(FILTER_REGISTRY.keys())}")
        self._filters.append((component_type, kwargs))
        return self

    def stop_loss(self, component_type: str, **kwargs) -> "StrategyBuilder":
        """设置止损

        可选: atr, fixed_pct, trailing
        """
        if component_type not in STOP_LOSS_REGISTRY:
            raise ValueError(f"未知止损类型: {component_type}。可选: {list(STOP_LOSS_REGISTRY.keys())}")
        self._stop_losses.append((component_type, kwargs))
        return self

    def take_profit(self, component_type: str, **kwargs) -> "StrategyBuilder":
        """设置止盈

        可选: fixed_pct, ma_touch
        """
        if component_type not in TAKE_PROFIT_REGISTRY:
            raise ValueError(f"未知止盈类型: {component_type}。可选: {list(TAKE_PROFIT_REGISTRY.keys())}")
        self._take_profits.append((component_type, kwargs))
        return self

    # ── 构建 ─────────────────────────────────────

    def build(self) -> CompositeStrategy:
        """构建 CompositeStrategy 实例"""
        strat = CompositeStrategy(self._name)

        if self._entry_type:
            strat.set_entry(self._make(ENTRY_REGISTRY, self._entry_type, self._entry_kwargs))

        if self._exit_type:
            strat.set_exit(self._make(EXIT_REGISTRY, self._exit_type, self._exit_kwargs))

        for ft, fk in self._filters:
            strat.add_filter(self._make(FILTER_REGISTRY, ft, fk))

        for st, sk in self._stop_losses:
            strat.add_stop_loss(self._make(STOP_LOSS_REGISTRY, st, sk))

        for tt, tk in self._take_profits:
            strat.add_take_profit(self._make(TAKE_PROFIT_REGISTRY, tt, tk))

        return strat

    def _make(self, registry, ctype: str, kwargs: dict):
        cls = registry[ctype]
        # Filter kwargs to only valid params for this class
        valid_params = cls.__init__.__code__.co_varnames[1:]  # skip 'self'
        filtered = {k: v for k, v in kwargs.items() if k in valid_params}
        return cls(**filtered)

    # ── YAML ─────────────────────────────────────

    def to_yaml(self, path: Optional[str] = None) -> str:
        """导出为 YAML 字符串或文件"""
        if yaml is None:
            raise ImportError("需要 pyyaml: pip install pyyaml")
        config = {
            "name": self._name,
            "entry": {"type": self._entry_type, **self._entry_kwargs} if self._entry_type else None,
            "exit": {"type": self._exit_type, **self._exit_kwargs} if self._exit_type else None,
            "filters": [{"type": t, **k} for t, k in self._filters],
            "stop_loss": [{"type": t, **k} for t, k in self._stop_losses],
            "take_profit": [{"type": t, **k} for t, k in self._take_profits],
        }
        text = yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False)

        if path:
            Path(path).write_text(text, encoding="utf-8")
        return text

    @classmethod
    def from_yaml(cls, path: str) -> CompositeStrategy:
        """从 YAML 文件加载策略"""
        if yaml is None:
            raise ImportError("需要 pyyaml: pip install pyyaml")
        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        builder = cls(config.get("name", "YAMLStrategy"))

        if config.get("entry"):
            e = config["entry"]
            builder.entry(e.pop("type"), **e)

        if config.get("exit"):
            x = config["exit"]
            builder.exit(x.pop("type"), **x)

        for f in config.get("filters", []):
            ft = f.pop("type")
            builder.filter(ft, **f)

        for s in config.get("stop_loss", []):
            st = s.pop("type")
            builder.stop_loss(st, **s)

        for t in config.get("take_profit", []):
            tt = t.pop("type")
            builder.take_profit(tt, **t)

        return builder.build()

    # ── 预设 ─────────────────────────────────────

    @classmethod
    def preset(cls, name: str, **overrides) -> CompositeStrategy:
        """快捷预设策略

        可选: dual_ma, bollinger_band, momentum, turtle, trend_following
        """
        presets = {
            "dual_ma": lambda: (
                cls("双均线")
                .entry("ma_cross", short=5, long=20)
                .exit("ma_cross", short=5, long=20)
            ),
            "bollinger_band": lambda: (
                cls("布林带")
                .entry("boll_lower")
                .exit("boll_upper")
            ),
            "momentum": lambda: (
                cls("动量轮动")
                .entry("momentum_turn", period=20)
                .exit("momentum_turn", period=20)
            ),
            "turtle": lambda: (
                cls("海龟交易")
                .entry("turtle_breakout", period=20)
                .exit("turtle_exit", period=10)
                .stop_loss("atr", multiplier=2)
            ),
            "trend_following": lambda: (
                cls("趋势跟随")
                .entry("ma_cross", short=5, long=60)
                .filter("trend", period=120)
                .filter("volume", min_ratio=1.2)
                .exit("ma_cross", short=5, long=20)
                .stop_loss("trailing", pct=0.08)
                .take_profit("fixed_pct", target=0.30)
            ),
        }

        fn = presets.get(name)
        if fn is None:
            raise ValueError(f"未知预设: {name}。可选: {list(presets.keys())}")

        builder = fn()
        for k, v in overrides.items():
            if hasattr(builder, k):
                setattr(builder, k, v)
        return builder.build()

    # ── 列出可用组件 ─────────────────────────────

    @staticmethod
    def list_components() -> Dict[str, List[str]]:
        """列出所有可用组件类型"""
        return {
            "entry": list(ENTRY_REGISTRY.keys()),
            "exit": list(EXIT_REGISTRY.keys()),
            "filter": list(FILTER_REGISTRY.keys()),
            "stop_loss": list(STOP_LOSS_REGISTRY.keys()),
            "take_profit": list(TAKE_PROFIT_REGISTRY.keys()),
        }

    @staticmethod
    def list_presets() -> List[str]:
        return ["dual_ma", "bollinger_band", "momentum", "turtle", "trend_following"]

    def __repr__(self):
        parts = [self._name]
        if self._entry_type:
            parts.append(f"entry={self._entry_type}")
        if self._exit_type:
            parts.append(f"exit={self._exit_type}")
        if self._filters:
            parts.append(f"filters={len(self._filters)}")
        return f"StrategyBuilder({', '.join(parts)})"

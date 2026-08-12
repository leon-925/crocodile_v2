# Crocodile v2 🐊

量化交易平台 — Data → Strategy → Backtest → Live Trading

## 架构

```
crocodile_v2/
├── portfolio/        账户 + 持仓 + 组合管理
├── execution/        订单 + Broker（单一状态源）
├── data/             SQLite存储 + 历史/实时拉取 + 指标计算
├── strategies/       策略乐高 (22组件 + 5预设 + YAML)
├── backtest/         向量化/逐K线/事件驱动 三引擎
├── trading/          自动交易脑 + 调度 + 风控 + 告警
├── visualization/    K线/信号/回撤/指标
├── app.py            Streamlit 面板
└── crocodile.jpg     封面
```

## 安装

```bash
pip install streamlit pandas numpy matplotlib pyyaml akshare
```

## 启动面板

```bash
streamlit run app.py
```

然后打开 http://localhost:8502

## 策略乐高

```python
from strategies import StrategyBuilder

# 预设
strat = StrategyBuilder.preset("trend_following")

# 自定义
strat = StrategyBuilder("我的策略") \
    .entry("ma_cross", short=5, long=20) \
    .filter("rsi", max=70) \
    .exit("ma_cross", short=5, long=20) \
    .stop_loss("atr", multiplier=2) \
    .take_profit("fixed_pct", target=0.15) \
    .build()

# YAML
strat = StrategyBuilder.from_yaml("my_strategy.yaml")
```

## 回测

```python
from backtest import BacktestRunner

result = runner.run(df, mode="bar_by_bar")
result.summary()   # 打印报表
result.plot()      # 画图
```

## 实盘机器人

```python
from trading import TradingRobot

robot = TradingRobot(
    data_source=ds, account=acc, broker=broker,
    strategy=strat, portfolio_manager=pm,
)
robot.run_loop(symbols=['600519.SH'], interval=60)
```

## 部署到 Streamlit Cloud

1. Push 到 GitHub
2. 打开 https://share.streamlit.io
3. 连接仓库 → 选择 `app.py` → Deploy

---

Built with 🐊 by Crocodile

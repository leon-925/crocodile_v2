"""VectorizedBacktest — 向量化回测引擎

最快最轻量。纯 pandas/numpy 向量运算，无逐行循环。
适用：快速策略验证、参数扫描、海量标的批量回测。
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .result import BacktestResult


class VectorizedBacktest:
    """向量化回测引擎

    输入: OHLCV DataFrame + signal 列
    输出: BacktestResult
    """

    def __init__(
        self,
        initial_cash: float = 100_000,
        commission: float = 0.0003,
        stamp_tax: float = 0.001,
        slippage: float = 0.0,
    ):
        self.initial_cash = initial_cash
        self.commission = commission
        self.stamp_tax = stamp_tax
        self.slippage = slippage

    def run(
        self,
        df: pd.DataFrame,
        signal_col: str = "signal",
        price_col: str = "close",
        position_pct: float = 1.0,
        allow_short: bool = False,
    ) -> BacktestResult:
        """执行向量化回测

        参数:
            df: 包含 OHLCV 和 signal 列的 DataFrame (index 为日期)
            signal_col: 信号列名 (1=买入, -1=卖出, 0=持有)
            price_col: 价格列名
            position_pct: 每次交易投入资金比例 (0~1)
            allow_short: 是否允许做空
        """
        df = df.copy()
        if signal_col not in df.columns:
            raise ValueError(f"DataFrame 缺少信号列 '{signal_col}'")
        if price_col not in df.columns:
            raise ValueError(f"DataFrame 缺少价格列 '{price_col}'")

        n = len(df)
        price = df[price_col].values
        signal = df[signal_col].values

        # 滑点价格
        buy_price = price * (1 + self.slippage)
        sell_price = price * (1 - self.slippage)

        # 状态数组
        position = np.zeros(n, dtype=float)      # 持仓股数
        cash = np.zeros(n, dtype=float)           # 现金
        equity = np.zeros(n, dtype=float)         # 总权益

        cash[0] = self.initial_cash
        equity[0] = self.initial_cash

        trades = []

        for i in range(1, n):
            # 继承上期状态
            position[i] = position[i - 1]
            cash[i] = cash[i - 1]

            sig = signal[i]
            px = price[i]

            # 买入
            if sig == 1 and position[i] == 0:
                available = (cash[i] + position[i] * px) * position_pct if allow_short else cash[i] * position_pct
                qty = int(available / buy_price[i])
                if qty > 0:
                    cost = qty * buy_price[i]
                    fee = max(cost * self.commission, 5.0)
                    cash[i] -= cost + fee
                    position[i] = qty
                    trades.append({
                        "date": df.index[i], "symbol": "", "side": "BUY",
                        "price": buy_price[i], "quantity": qty, "fee": fee,
                        "realized_pnl": 0.0,
                    })

            # 卖出
            elif sig == -1 and position[i] > 0:
                qty = int(position[i])
                if qty > 0:
                    value = qty * sell_price[i]
                    fee = value * self.commission + value * self.stamp_tax
                    cost_basis = position[i] * price[i]
                    pnl = value - cost_basis - fee
                    cash[i] += value - fee
                    trades.append({
                        "date": df.index[i], "symbol": "", "side": "SELL",
                        "price": sell_price[i], "quantity": qty, "fee": fee,
                        "realized_pnl": pnl,
                    })
                    position[i] = 0

            # 做空卖出
            elif sig == -1 and allow_short and position[i] == 0:
                available = cash[i] * position_pct
                qty = int(available / sell_price[i])
                if qty > 0:
                    cash[i] += qty * sell_price[i]
                    position[i] = -qty
                    trades.append({
                        "date": df.index[i], "symbol": "", "side": "SELL",
                        "price": sell_price[i], "quantity": qty, "fee": 0,
                        "realized_pnl": 0.0,
                    })

            # 做空平仓
            elif sig == 1 and allow_short and position[i] < 0:
                qty = int(abs(position[i]))
                cost = qty * buy_price[i]
                fee = max(cost * self.commission, 5.0)
                pnl = abs(position[i]) * (sell_price[i] - buy_price[i]) - fee
                cash[i] -= cost + fee
                trades.append({
                    "date": df.index[i], "symbol": "", "side": "BUY",
                    "price": buy_price[i], "quantity": qty, "fee": fee,
                    "realized_pnl": pnl,
                })
                position[i] = 0

            # 计算权益
            equity[i] = cash[i] + position[i] * price[i]

        # 构建结果 DataFrame
        result_df = pd.DataFrame({
            "equity": equity,
            "cash": cash,
            "position": position * price,
        }, index=df.index)

        trades_df = pd.DataFrame(trades) if trades else pd.DataFrame(
            columns=["date", "symbol", "side", "price", "quantity", "fee", "realized_pnl"]
        )
        if not trades_df.empty and "date" in trades_df.columns:
            trades_df.set_index("date", inplace=True)

        return BacktestResult(
            equity_curve=result_df,
            trades=trades_df,
            engine_name=f"Vectorized(commission={self.commission:.4f})",
        )

    def scan(
        self,
        df: pd.DataFrame,
        signal_col: str = "signal",
        price_col: str = "close",
    ) -> pd.DataFrame:
        """快速批量参数扫描"""
        results = []
        for comm in [0.0001, 0.0003, 0.0005]:
            for pct in [0.5, 0.8, 1.0]:
                self.commission = comm
                result = self.run(df, signal_col, price_col, position_pct=pct)
                results.append({
                    "commission": comm,
                    "position_pct": pct,
                    "total_return": result.total_return,
                    "sharpe": result.sharpe_ratio,
                    "max_dd": result.max_drawdown,
                })
        return pd.DataFrame(results).sort_values("sharpe", ascending=False)

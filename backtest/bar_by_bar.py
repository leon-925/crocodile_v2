"""BarByBarBacktest — 逐 K 线回测引擎

最常用的回测方式。每根 K 线迭代一次，完整走：
行情更新 → 策略信号 → 组合调仓 → 提交撮合 → 成交记账 → 净值快照
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from .result import BacktestResult


class BarByBarBacktest:
    """逐 K 线回测引擎 — 完整串联 Account/Broker/PortfolioManager/Strategy"""

    def __init__(
        self,
        account,
        broker,
        portfolio_manager=None,
        risk_manager=None,
    ):
        self.account = account
        self.broker = broker
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager

    # ── 主循环 ──────────────────────────────────

    def run(
        self,
        df: pd.DataFrame,
        strategy,
        symbol: str = "",
        price_col: str = "close",
        target_weight: float = 0.3,
        rebalance_freq: str = "daily",
    ) -> BacktestResult:
        """执行逐 K 线回测

        参数:
            df: OHLCV + 指标 DataFrame (index 为日期)
            strategy: 策略实例
            symbol: 交易标的
            price_col: 价格列
            target_weight: 买入时的目标仓位权重
            rebalance_freq: 调仓频率
        """
        if df.empty:
            raise ValueError("数据为空")
        if not symbol and "symbol" in df.columns:
            symbol = str(df["symbol"].iloc[0])

        snapshots = []
        prev_rebalance_date = None
        signal_col = "signal"

        # 预生成全量信号（避免每次窗口重复计算，且策略用 copy() 不修改原 df）
        df_sig = strategy.generate_signal(df)
        signal_series = df_sig.get(signal_col, pd.Series(0, index=df.index))

        for i, (date, row) in enumerate(df.iterrows()):
            price = float(row[price_col])
            prices = {symbol: price}

            # 1. 行情更新
            self.account.update_market_prices(prices)

            # 2. 当前信号
            current_signal = int(signal_series.iloc[i]) if i < len(signal_series) else 0

            # 3. 风控
            if self.risk_manager is not None and current_signal != 0:
                dd_ok, _ = self.risk_manager.check_drawdown(self.account.get_equity())
                if not dd_ok:
                    current_signal = 0

            # 4. 信号 → 目标权重
            if self.portfolio_manager is not None and current_signal != 0:
                if current_signal == 1:
                    self.portfolio_manager.set_target_weights({symbol: target_weight})
                elif current_signal == -1:
                    self.portfolio_manager.set_target_weights({symbol: 0.0})

            # 5. 调仓
            should_rebalance = self._should_rebalance(date, rebalance_freq, prev_rebalance_date)
            if should_rebalance and self.portfolio_manager is not None:
                orders = self.portfolio_manager.rebalance(prices)
                prev_rebalance_date = date

                if orders:
                    # 提交 → 撮合
                    for order in orders:
                        try:
                            oid = self.broker.submit_order(
                                order.symbol, order.side.value, order.quantity,
                                price=price, order_type="limit",
                            )
                        except Exception:
                            pass
                    self.broker.match_orders(prices)

            # 6. 净值快照
            snap = self.account.snapshot(time=date)
            snapshots.append(snap)

        # 构建结果
        eq_df = pd.DataFrame(snapshots)
        if not eq_df.empty and "time" in eq_df.columns:
            eq_df.set_index("time", inplace=True)

        return BacktestResult(
            equity_curve=eq_df,
            trades=self.account.trades.copy(),
            engine_name="BarByBar",
        )

    # ── 辅助 ────────────────────────────────────

    def _should_rebalance(self, date, freq: str, prev_date) -> bool:
        if prev_date is None:
            return True
        if freq == "daily":
            return True
        if freq == "weekly":
            return date.weekday() < prev_date.weekday() or (date - prev_date).days >= 7
        if freq == "monthly":
            return date.month != prev_date.month
        return True

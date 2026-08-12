"""BacktestResult — 统一回测结果

所有三种回测引擎输出统一结果格式。
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd


class BacktestResult:
    """统一回测结果 — 可打印报表、画图、导出"""

    def __init__(
        self,
        equity_curve: pd.DataFrame,
        trades: pd.DataFrame,
        metrics: Optional[Dict[str, Any]] = None,
        engine_name: str = "",
    ):
        self.engine_name = engine_name
        self.equity_curve = equity_curve
        self.trades = trades
        self._metrics = metrics or {}

        # 自动计算核心指标
        if not equity_curve.empty and "equity" in equity_curve.columns:
            self._compute_defaults()

    # ── 指标计算 ────────────────────────────────

    def _compute_defaults(self):
        eq = self.equity_curve["equity"]

        # 收益率
        self._metrics.setdefault("total_return", eq.iloc[-1] / eq.iloc[0] - 1)

        # 回撤
        dd = eq / eq.cummax() - 1
        self._metrics.setdefault("max_drawdown", dd.min())
        self.equity_curve["drawdown"] = dd

        # 夏普
        daily_ret = eq.pct_change().dropna()
        if len(daily_ret) > 1 and daily_ret.std() > 0:
            self._metrics.setdefault("sharpe_ratio", daily_ret.mean() / daily_ret.std() * np.sqrt(252))
        else:
            self._metrics.setdefault("sharpe_ratio", 0.0)

        # 年化收益
        days = (eq.index[-1] - eq.index[0]).days
        if days > 0:
            self._metrics.setdefault("annual_return", (1 + self._metrics["total_return"]) ** (365 / days) - 1)

        # 交易统计
        if not self.trades.empty:
            self._metrics.setdefault("total_trades", len(self.trades))
            if "realized_pnl" in self.trades.columns:
                pnl = self.trades["realized_pnl"]
                self._metrics.setdefault("win_rate", (pnl > 0).sum() / len(pnl) if len(pnl) > 0 else 0)
                self._metrics.setdefault("total_pnl", pnl.sum())
                winners = pnl[pnl > 0]
                losers = pnl[pnl < 0]
                avg_win = winners.mean() if len(winners) > 0 else 0
                avg_loss = abs(losers.mean()) if len(losers) > 0 else 0
                self._metrics.setdefault("avg_win", avg_win)
                self._metrics.setdefault("avg_loss", avg_loss)
                self._metrics.setdefault("profit_factor",
                    winners.sum() / abs(losers.sum()) if losers.sum() != 0 else float("inf"))

    # ── 属性 ────────────────────────────────────

    @property
    def metrics(self) -> Dict[str, Any]:
        return self._metrics

    @property
    def total_return(self) -> float:
        return self._metrics.get("total_return", 0.0)

    @property
    def max_drawdown(self) -> float:
        return self._metrics.get("max_drawdown", 0.0)

    @property
    def sharpe_ratio(self) -> float:
        return self._metrics.get("sharpe_ratio", 0.0)

    # ── 报表 ────────────────────────────────────

    def summary(self) -> str:
        """打印回测报表"""
        m = self._metrics
        lines = [
            "=" * 50,
            f"  Backtest Report ({self.engine_name})",
            "=" * 50,
            f"  Total Return : {m.get('total_return', 0):>8.2%}",
            f"  Annual Return: {m.get('annual_return', 0):>8.2%}",
            f"  Max Drawdown : {m.get('max_drawdown', 0):>8.2%}",
            f"  Sharpe Ratio : {m.get('sharpe_ratio', 0):>8.2f}",
        ]
        if "total_trades" in m:
            lines += [
                f"  Total Trades : {m['total_trades']:>8}",
                f"  Win Rate     : {m.get('win_rate', 0):>8.2%}",
                f"  Total PnL    : {m.get('total_pnl', 0):>8.0f}",
                f"  Profit Factor: {m.get('profit_factor', 0):>8.2f}",
            ]
        lines.append("=" * 50)
        text = "\n".join(lines)
        print(text)
        return text

    def summary_dict(self) -> Dict[str, Any]:
        """返回 JSON-serializable 的指标字典"""
        return {
            k: round(float(v), 6) if isinstance(v, (float, np.floating)) else v
            for k, v in self._metrics.items()
        }

    # ── 画图 ────────────────────────────────────

    def plot(
        self,
        title: str = "Backtest Result",
        figsize: Tuple[int, int] = (14, 8),
    ) -> Tuple[plt.Figure, np.ndarray]:
        """净值曲线 + 回撤双面板"""
        df = self.equity_curve
        if df.empty:
            raise ValueError("无净值数据")

        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=figsize, sharex=True,
            gridspec_kw={"height_ratios": [3, 1], "hspace": 0.05},
        )

        # 净值
        ax1.plot(df.index, df["equity"], color="royalblue", linewidth=1.5, label="Equity")
        ax1.set_ylabel("Equity", fontweight="bold")
        ax1.set_title(title, fontweight="bold")
        ax1.legend(loc="upper left")
        ax1.grid(True, linestyle=":", alpha=0.6)

        # 回撤
        if "drawdown" in df.columns:
            dd = df["drawdown"]
            ax2.fill_between(df.index, dd, 0, color="crimson", alpha=0.35)
            ax2.plot(df.index, dd, color="crimson", linewidth=0.8)
            ax2.axhline(0, color="black", linestyle="--", linewidth=0.6)

            max_dd = dd.min()
            max_dd_date = dd.idxmin()
            ax2.scatter([max_dd_date], [max_dd], color="darkred", s=30, zorder=5)
            ax2.annotate(
                f"Max DD: {max_dd:.2%}",
                xy=(max_dd_date, max_dd),
                xytext=(10, -15), textcoords="offset points",
                arrowprops=dict(arrowstyle="->", color="darkred", lw=1),
                fontsize=8, color="darkred",
            )
            if dd.abs().max() <= 1.0:
                ax2.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))

        ax2.set_ylabel("Drawdown", fontweight="bold")
        ax2.set_xlabel("Date")
        ax2.grid(True, linestyle=":", alpha=0.6)

        for ax in (ax1, ax2):
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

        fig.tight_layout()
        return fig, np.array([ax1, ax2])

    def __repr__(self):
        m = self._metrics
        return (
            f"BacktestResult({self.engine_name}, "
            f"return={m.get('total_return', 0):.2%}, "
            f"sharpe={m.get('sharpe_ratio', 0):.2f}, "
            f"trades={m.get('total_trades', 0)})"
        )

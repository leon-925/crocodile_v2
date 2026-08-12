"""
绩效分析可视化

输出:
  1. 净值曲线 + 回撤
  2. 月度收益率热力图
  3. 收益分布直方图
"""

from typing import Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd


def plot_equity_curve(
    df: pd.DataFrame,
    equity_col: str = "equity",
    drawdown_col: str = "drawdown",
    title: str = "Equity Curve & Drawdown",
    figsize: Tuple[int, int] = (14, 8),
) -> Tuple[plt.Figure, np.ndarray]:
    """净值曲线 + 回撤双面板"""

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=figsize, sharex=True,
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.05},
    )

    # ── 上: 净值曲线 ──
    ax1.plot(df.index, df[equity_col], color="royalblue", linewidth=1.5, label="Equity")
    ax1.set_ylabel("Equity", fontsize=10, fontweight="bold")
    ax1.set_title(title, fontsize=12, fontweight="bold")
    ax1.legend(loc="upper left")
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # ── 下: 回撤 ──
    has_dd = drawdown_col in df.columns
    if has_dd:
        dd = df[drawdown_col]
        ax2.fill_between(df.index, dd, 0, color="crimson", alpha=0.35)
        ax2.plot(df.index, dd, color="crimson", linewidth=0.8)
        ax2.axhline(0, color="black", linestyle="--", linewidth=0.6, alpha=0.5)

        max_dd_val = dd.min()
        max_dd_date = dd.idxmin()
        ax2.scatter([max_dd_date], [max_dd_val], color="darkred", s=30, zorder=5)
        ax2.annotate(
            f"Max DD: {max_dd_val:.2%}",
            xy=(max_dd_date, max_dd_val),
            xytext=(10, -15),
            textcoords="offset points",
            arrowprops=dict(arrowstyle="->", color="darkred", lw=1),
            fontsize=8, color="darkred",
        )

        if dd.abs().max() <= 1.0:
            ax2.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))

    ax2.set_ylabel("Drawdown", fontsize=10, fontweight="bold")
    ax2.set_xlabel("Date", fontsize=10)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.tight_layout()
    return fig, np.array([ax1, ax2])


def plot_monthly_returns(
    df: pd.DataFrame,
    return_col: str = "daily_return",
    title: str = "Monthly Returns Heatmap",
    figsize: Tuple[int, int] = (12, 6),
    cmap: str = "RdYlGn",
) -> Tuple[plt.Figure, plt.Axes]:
    """月度收益热力图"""

    if return_col not in df.columns:
        df["ret"] = df[return_col] if return_col in df.columns else df.iloc[:, 0].pct_change()
        return_col = "ret"

    ret = df[return_col].dropna()
    monthly = ret.resample("ME").apply(lambda x: (1 + x).prod() - 1)
    monthly.index = monthly.index.to_period("M")

    pivot = monthly.to_frame("return")
    pivot["Year"] = pivot.index.year
    pivot["Month"] = pivot.index.month
    heatmap = pivot.pivot_table(values="return", index="Year", columns="Month", aggfunc="sum")

    fig, ax = plt.subplots(figsize=figsize)
    im = ax.imshow(heatmap.values, cmap=cmap, aspect="auto", vmin=-0.15, vmax=0.15)

    for i in range(heatmap.shape[0]):
        for j in range(heatmap.shape[1]):
            val = heatmap.iloc[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.1%}", ha="center", va="center",
                        fontsize=9, fontweight="bold",
                        color="white" if abs(val) > 0.05 else "black")

    ax.set_xticks(range(12))
    ax.set_xticklabels(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])
    ax.set_yticks(range(len(heatmap.index)))
    ax.set_yticklabels(heatmap.index.astype(str))
    ax.set_title(title, fontsize=12, fontweight="bold")
    fig.colorbar(im, ax=ax, format=mtick.PercentFormatter(1.0))
    fig.tight_layout()
    return fig, ax


def plot_return_distribution(
    df: pd.DataFrame,
    return_col: str = "daily_return",
    bins: int = 50,
    title: str = "Daily Return Distribution",
    figsize: Tuple[int, int] = (10, 5),
) -> Tuple[plt.Figure, plt.Axes]:
    """日收益率分布直方图"""

    ret = df[return_col].dropna() if return_col in df.columns else df.pct_change().dropna().iloc[:, 0]

    fig, ax = plt.subplots(figsize=figsize)
    ax.hist(ret, bins=bins, color="steelblue", edgecolor="white", alpha=0.85, density=True)
    ax.axvline(0, color="black", linestyle="--", linewidth=1)

    mean = ret.mean()
    std = ret.std()
    ax.axvline(mean, color="crimson", linestyle="-", linewidth=1.5, label=f"Mean: {mean:.4f}")
    ax.axvline(mean + std, color="gray", linestyle=":", label=f"±1σ: {std:.4f}")
    ax.axvline(mean - std, color="gray", linestyle=":")

    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("Daily Return", fontsize=10)
    ax.set_ylabel("Density", fontsize=10)
    ax.legend(loc="upper right")
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig, ax

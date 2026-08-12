from typing import Optional, Tuple
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_multi_indicator(
    df: pd.DataFrame,
    price_col: str = "close",
    title: str = "Multi-Indicator Quantitative Dashboard",
    figsize: Tuple[int, int] = (12, 9),
) -> Tuple[plt.Figure, np.ndarray]:
    """专业多指标量化仪表盘 (价格 + MACD + RSI)

    参数:
        df: 包含价格及技术指标数据的 DataFrame
        price_col: 价格列名，默认 'close'
        title: 仪表盘全局标题
        figsize: 画布尺寸

    返回:
        (fig, ax): Matplotlib Figure 与 Axes 数组
    """
    df = df.copy()

    # 1. 基础检查
    if price_col not in df.columns:
        raise KeyError(f"DataFrame 缺少价格列 '{price_col}'")

    # 2. 创建 3 行 1 列子图，设置高度比例 3:1:1，收紧垂直间距 (hspace=0.08)
    fig, ax = plt.subplots(
        3,
        1,
        figsize=figsize,
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1, 1], "hspace": 0.08},
    )

    # --------------------------------------------------
    # 面板 1: 主图 - 价格 (可自动叠加布林带)
    # --------------------------------------------------
    ax[0].plot(
        df.index,
        df[price_col],
        label=price_col.capitalize(),
        color="royalblue",
        linewidth=1.5,
    )

    # 自动识别布林带列
    if "boll_upper" in df.columns and "boll_lower" in df.columns:
        ax[0].plot(
            df.index,
            df["boll_upper"],
            label="Boll Upper",
            color="gray",
            linestyle="--",
            alpha=0.6,
        )
        if "boll_middle" in df.columns:
            ax[0].plot(
                df.index,
                df["boll_middle"],
                label="Boll Middle",
                color="orange",
                linestyle=":",
                alpha=0.7,
            )
        ax[0].plot(
            df.index,
            df["boll_lower"],
            label="Boll Lower",
            color="gray",
            linestyle="--",
            alpha=0.6,
        )
        ax[0].fill_between(
            df.index,
            df["boll_lower"],
            df["boll_upper"],
            color="gray",
            alpha=0.05,
        )

    ax[0].set_ylabel("Price", fontsize=10, fontweight="bold")
    ax[0].legend(
        loc="upper left", frameon=True, facecolor="white", framealpha=0.8
    )

    # --------------------------------------------------
    # 面板 2: MACD 指标 (兼容完整的 DIF / DEA / 柱状图)
    # --------------------------------------------------
    macd_col = "MACD" if "MACD" in df.columns else "macd"

    if macd_col in df.columns:
        # 画快线 (DIF)
        ax[1].plot(
            df.index,
            df[macd_col],
            label="DIF (MACD)",
            color="royalblue",
            linewidth=1.2,
        )

        # 检查是否有慢线/信号线 (DEA)
        signal_cols = [
            c
            for c in df.columns
            if c.lower() in ["macd_signal", "dea", "signal"]
        ]
        if signal_cols:
            ax[1].plot(
                df.index,
                df[signal_cols[0]],
                label="DEA (Signal)",
                color="orange",
                linewidth=1.2,
            )

        # 检查是否有柱状图 (Hist / Bar)
        hist_cols = [
            c
            for c in df.columns
            if c.lower() in ["macd_hist", "hist", "bar", "macd_bar"]
        ]
        if hist_cols:
            hist_vals = df[hist_cols[0]]
            # 区分多空红绿柱
            red_bar = hist_vals >= 0
            green_bar = hist_vals < 0
            ax[1].bar(
                df.index[red_bar],
                hist_vals[red_bar],
                color="crimson",
                width=1.0,
                alpha=0.6,
            )
            ax[1].bar(
                df.index[green_bar],
                hist_vals[green_bar],
                color="forestgreen",
                width=1.0,
                alpha=0.6,
            )

        ax[1].axhline(0, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)
        ax[1].legend(
            loc="upper left", frameon=True, facecolor="white", framealpha=0.8
        )
    else:
        ax[1].text(
            0.5,
            0.5,
            "MACD Data Not Found",
            ha="center",
            va="center",
            transform=ax[1].transAxes,
        )

    ax[1].set_ylabel("MACD", fontsize=10, fontweight="bold")

    # --------------------------------------------------
    # 面板 3: RSI 指标 (带 30/70 超买超卖线)
    # --------------------------------------------------
    rsi_col = "RSI" if "RSI" in df.columns else "rsi"

    if rsi_col in df.columns:
        ax[2].plot(
            df.index,
            df[rsi_col],
            label="RSI",
            color="purple",
            linewidth=1.2,
        )
        # 30 和 70 警戒线
        ax[2].axhline(
            70,
            color="crimson",
            linestyle="--",
            linewidth=1,
            alpha=0.7,
            label="Overbought (70)",
        )
        ax[2].axhline(
            30,
            color="forestgreen",
            linestyle="--",
            linewidth=1,
            alpha=0.7,
            label="Oversold (30)",
        )
        # 填充 30-70 之间的正常区间阴影
        ax[2].axhspan(30, 70, color="gray", alpha=0.08)
        ax[2].set_ylim(0, 100)  # RSI 物理区间 0-100
        ax[2].legend(
            loc="upper left", frameon=True, facecolor="white", framealpha=0.8
        )
    else:
        ax[2].text(
            0.5,
            0.5,
            "RSI Data Not Found",
            ha="center",
            va="center",
            transform=ax[2].transAxes,
        )

    ax[2].set_ylabel("RSI", fontsize=10, fontweight="bold")
    ax[2].set_xlabel("Date / Time", fontsize=10)

    # --------------------------------------------------
    # 全局样式修饰
    # --------------------------------------------------
    fig.suptitle(title, fontsize=13, fontweight="bold", y=0.93)

    for a in ax:
        a.grid(True, linestyle=":", alpha=0.6)
        a.spines["top"].set_visible(False)
        a.spines["right"].set_visible(False)

    return fig, ax
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_signal(
    df: pd.DataFrame,
    price_col: str = "close",
    signal_col: str = "signal",
    is_position: bool = False,  # Signal 是动作(1/-1)还是仓位状态(连续1/连续-1)
    cn_style: bool = True,  # True: 红买绿卖(A股风格); False: 绿买红卖(美股外汇风格)
    figsize: tuple[int, int] = (14, 6),
    title: str = "Trading Signals",
    plot_bollinger: bool = True,  # 若包含布林带数据则自动画出
) -> tuple[plt.Figure, plt.Axes]:
    """绘制带有交易信号的价格图表

    参数:
        df: 包含价格和信号的 DataFrame
        price_col: 价格列名，默认 'close'
        signal_col: 信号列名 (0: 持有/无动作, 1: 买入, -1: 卖出)
        is_position: 如果 signal 是连续仓位状态 (如连续多天为 1)，设为 True 会自动只在开平仓切换点画箭头
        cn_style: 是否使用国内红买绿卖配色
        figsize: 图表尺寸
        title: 图表标题
        plot_bollinger: 若 df 包含 boll_upper/boll_lower 列，是否叠加布林带
    """
    df = df.copy()

    # 1. 确定买卖颜色
    if cn_style:
        buy_color, sell_color = "crimson", "forestgreen"  # 红买绿卖
    else:
        buy_color, sell_color = "forestgreen", "crimson"  # 绿买红卖

    # 2. 识别买入点与卖出点
    if is_position:
        # 如果 signal 代表连续持仓状态，通过 diff() 寻找变化点 (切换点)
        pos_diff = df[signal_col].diff().fillna(df[signal_col])
        buy_mask = pos_diff > 0  # 仓位增加 (如 0 -> 1, -1 -> 1)
        sell_mask = pos_diff < 0  # 仓位减少 (如 1 -> 0, 1 -> -1)
    else:
        # 如果 signal 本身就是离散指令 (1: 买入动作, -1: 卖出动作, 0: 无操作)
        buy_mask = df[signal_col] == 1
        sell_mask = df[signal_col] == -1

    buy_df = df[buy_mask]
    sell_df = df[sell_mask]

    # 3. 创建画布
    fig, ax = plt.subplots(figsize=figsize)

    # 4. 绘制价格主线
    ax.plot(
        df.index,
        df[price_col],
        label="Price",
        color="royalblue",
        linewidth=1.5,
        zorder=2,
    )

    # 5. 自动叠加布林带轨道 (如果 DataFrame 中存在)
    if (
        plot_bollinger
        and "boll_upper" in df.columns
        and "boll_lower" in df.columns
    ):
        ax.plot(
            df.index,
            df["boll_upper"],
            label="Upper Band",
            color="gray",
            linestyle="--",
            alpha=0.5,
        )
        if "boll_middle" in df.columns:
            ax.plot(
                df.index,
                df["boll_middle"],
                label="Middle Band",
                color="orange",
                linestyle=":",
                alpha=0.6,
            )
        ax.plot(
            df.index,
            df["boll_lower"],
            label="Lower Band",
            color="gray",
            linestyle="--",
            alpha=0.5,
        )
        ax.fill_between(
            df.index,
            df["boll_lower"],
            df["boll_upper"],
            color="gray",
            alpha=0.06,
        )

    # 6. 计算箭头在 Y 轴的偏移量 (悬挂效果，防止与 K线/折线重叠)
    price_range = df[price_col].max() - df[price_col].min()
    offset = price_range * 0.025 if price_range > 0 else df[price_col].mean() * 0.025

    # 7. 绘制买入信号 (箭头下方悬挂)
    if not buy_df.empty:
        ax.scatter(
            buy_df.index,
            buy_df[price_col] - offset,
            marker="^",
            s=120,
            color=buy_color,
            label="Buy Signal",
            zorder=5,
            edgecolors="black",
            linewidths=0.5,
        )

    # 8. 绘制卖出信号 (箭头上方悬挂)
    if not sell_df.empty:
        ax.scatter(
            sell_df.index,
            sell_df[price_col] + offset,
            marker="v",
            s=120,
            color=sell_color,
            label="Sell Signal",
            zorder=5,
            edgecolors="black",
            linewidths=0.5,
        )

    # 9. 美化图表
    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
    ax.set_ylabel("Price", fontsize=10)
    ax.set_xlabel("Date", fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.6)

    # 隐藏上方和右侧边框
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # 显示图例
    ax.legend(
        loc="best", frameon=True, facecolor="white", framealpha=0.9, fontsize=9
    )

    fig.tight_layout()

    return fig, ax
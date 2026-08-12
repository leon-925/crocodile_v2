import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd


def plot_drawdown(
    df: pd.DataFrame,
    drawdown_col: str = "drawdown",
    title: str = "Portfolio Drawdown",
    width: float = 12,
    height: float = 4,
    show_max_dd: bool = True,
    color: str = "crimson",
    alpha: float = 0.35,
) -> tuple[plt.Figure, plt.Axes]:
    """绘制策略回撤图 (Drawdown Plot)

    参数:
        df: 包含回撤数据的 DataFrame
        drawdown_col: 回撤数据所在的列名 (假设数值为 0 到 -1 之间的负数，或 0 到 -100 的百分数)
        title: 图表标题
        width: 图表宽度
        height: 图表高度
        show_max_dd: 是否高亮标注最大回撤点
        color: 填充颜色，默认深红 (crimson)
        alpha: 填充区域透明度
    """
    
    dd_series = df[drawdown_col]

    # 创建面向对象的 Figure 和 Axes
    fig, ax = plt.subplots(figsize=(width, height))

    # 1. 填充回撤区域
    ax.fill_between(
        df.index,
        dd_series,
        0,
        color=color,
        alpha=alpha,
        label="Drawdown",
    )

    # 2. 绘制上边缘线，使轮廓更清晰
    ax.plot(df.index, dd_series, color=color, linewidth=1)

    # 3. 绘制 0 轴基准线
    ax.axhline(0, color="black", linestyle="--", linewidth=0.8, alpha=0.7)

    # 4. 高亮最大回撤点 (Max Drawdown)
    if show_max_dd and not dd_series.empty:
        # 判断回撤是负数还是正数表示 (通常回撤为负数，极小值即最大回撤)
        max_dd_val = dd_series.min()
        max_dd_date = dd_series.idxmin()

        # 如果回撤数据是正值表示 (如 0.15 代表 15% 回撤)
        if max_dd_val > 0:
            max_dd_val = dd_series.max()
            max_dd_date = dd_series.idxmax()

        # 格式化文本
        val_str = f"{max_dd_val:.2%}" if abs(max_dd_val) <= 1 else f"{max_dd_val:.2f}%"

        # 绘制最大回撤散点
        ax.scatter(
            [max_dd_date],
            [max_dd_val],
            color="darkred",
            s=40,
            zorder=5,
            label=f"Max DD: {val_str}",
        )

        # 添加标注文本
        ax.annotate(
            f"Max DD: {val_str}\n({pd.to_datetime(max_dd_date).strftime('%Y-%m-%d')})",
            xy=(max_dd_date, max_dd_val),
            xytext=(15, -15 if max_dd_val < 0 else 15),
            textcoords="offset points",
            arrowprops=dict(arrowstyle="->", color="darkred", lw=1),
            fontsize=9,
            fontweight="bold",
            color="darkred",
        )

    # 5. 坐标轴与格式美化
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.set_ylabel("Drawdown", fontsize=10)
    ax.set_xlabel("Date", fontsize=10)

    # Y 轴智能转为百分比格式 (如果数值在 [-1, 1] 之间)
    if dd_series.abs().max() <= 1.0:
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))

    # 网格线与美化
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.set_xlim(df.index[0], df.index[-1])  # 紧凑 x 轴边缘

    # 隐藏上方和右侧边框 (Spines)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # 显示图例
    ax.legend(loc="lower left", frameon=True, facecolor="white", framealpha=0.8)

    # 自动调整布局防止标签截断
    fig.tight_layout()

    return fig, ax
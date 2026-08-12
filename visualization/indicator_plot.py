from typing import List, Optional, Union
import matplotlib.pyplot as plt
import pandas as pd


def plot_indicator(
    df: pd.DataFrame,
    column: Union[str, List[str]],
    title: Optional[str] = None,
    figsize: tuple[int, int] = (12, 4),
    ref_lines: Optional[List[float]] = None,
    ylabel: Optional[str] = None,
) -> tuple[plt.Figure, plt.Axes]:
    """通用金融技术指标绘制函数

    参数:
        df: 包含指标数据的 DataFrame
        column: 单个指标列名 (如 'rsi') 或多列列表 (如 ['macd', 'macd_signal'])
        title: 图表标题，默认自动使用列名组合
        figsize: 画布尺寸，默认 (12, 4)
        ref_lines: 参考基准线数值列表 (例如 RSI 超买超卖线 [30, 70]，或 MACD 0轴 [0])
        ylabel: Y 轴标签

    返回:
        fig, ax: Matplotlib 的 Figure 和 Axes 对象，方便外部继续自定义或保存
    """
    # 统一将 column 转化为列表处理
    cols = [column] if isinstance(column, str) else column

    # 1. 安全检查：校验列是否存在
    for col in cols:
        if col not in df.columns:
            raise KeyError(f"列名 '{col}' 不存在于 DataFrame 中")

    # 2. 创建面向对象画布
    fig, ax = plt.subplots(figsize=figsize)

    # 3. 绘制指标折线
    for col in cols:
        ax.plot(df.index, df[col], label=col, linewidth=1.5)

    # 多列时自动开启图例
    if len(cols) > 1:
        ax.legend(
            loc="best", frameon=True, facecolor="white", framealpha=0.8, fontsize=9
        )

    # 4. 绘制参考基准线 (例如 RSI 30/70 线, MACD 0 轴等)
    if ref_lines:
        for val in ref_lines:
            ax.axhline(
                val,
                color="gray",
                linestyle="--",
                linewidth=1,
                alpha=0.7,
                zorder=1,
            )

    # 5. 标题与坐标轴设置
    default_title = (
        title if title else (cols[0] if len(cols) == 1 else " / ".join(cols))
    )
    ax.set_title(default_title, fontsize=11, fontweight="bold", pad=10)
    ax.set_ylabel(
        ylabel or (cols[0] if len(cols) == 1 else "Value"), fontsize=9
    )
    ax.set_xlabel("Date/Time", fontsize=9)

    # 6. 图形外观美化
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()

    return fig, ax
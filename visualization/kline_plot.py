from typing import Optional, Tuple
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd


def plot_kline(
    df: pd.DataFrame,
    title: str = "Stock Kline",
    mav: Tuple[int, ...] = (5, 20, 60),
    cn_style: bool = True,  # True: 红涨绿跌(A股); False: 绿涨红跌(美股/外汇)
    show_bollinger: bool = True,  # 若包含布林带列，是否自动叠加
    savefig: Optional[str] = None,  # 保存路径，如 'kline.png'
) -> Tuple[plt.Figure, list]:
    """工业级 K线图绘制函数 (基于 mplfinance)

    参数:
        df: Pandas DataFrame，包含 OHLCV 数据 (支持大小写列名)
        title: K线图标题 (支持中文)
        mav: 移动平均线周期，例如 (5, 20, 60)
        cn_style: 是否开启国内 A 股习惯配色 (红涨绿跌)
        show_bollinger: 如果 df 包含 boll_upper/boll_lower 列，是否自动叠加
        savefig: 图片保存路径

    返回:
        (fig, axes): Matplotlib 的 Figure 与 Axes 列表
    """
    df = df.copy()

    # 1. 自动映射列名 (兼容全小写: open, high, low, close, volume)
    col_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
        "vol": "Volume",
    }
    df.rename(columns=lambda c: col_map.get(str(c).lower(), c), inplace=True)

    required_cols = ["Open", "High", "Low", "Close"]
    for col in required_cols:
        if col not in df.columns:
            raise KeyError(
                f"DataFrame 缺少必要 OHLC 列: '{col}' (当前列: {list(df.columns)})"
            )

    # 2. 自动转换并校验 DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        # 尝试寻找包含 date / time 的列
        date_cols = [
            c
            for c in df.columns
            if str(c).lower() in ["date", "datetime", "time", "trade_date"]
        ]
        if date_cols:
            df.index = pd.to_datetime(df[date_cols[0]])
            df.drop(columns=[date_cols[0]], inplace=True)
        else:
            try:
                df.index = pd.to_datetime(df.index)
            except Exception as e:
                raise TypeError(
                    "mplfinance 要求 DataFrame 索引必须为 DatetimeIndex，请检查日期列！"
                ) from e

    # 3. 字体配置 (防范中文乱码) 与颜色风格配置
    font_rc = {
        "font.sans-serif": [
            "SimHei",
            "Microsoft YaHei",
            "Arial Unicode MS",
            "DejaVu Sans",
        ],
        "axes.unicode_minus": False,  # 正常显示负号
    }

    if cn_style:
        # A 股配色: 涨=红 (crimson), 跌=绿 (forestgreen)
        market_colors = mpf.make_marketcolors(
            up="crimson",
            down="forestgreen",
            edge="inherit",
            wick="inherit",
            volume="inherit",
        )
    else:
        # 外盘配色: 涨=绿 (forestgreen), 跌=红 (crimson)
        market_colors = mpf.make_marketcolors(
            up="forestgreen",
            down="crimson",
            edge="inherit",
            wick="inherit",
            volume="inherit",
        )

    # 创建自定义 MPF Style
    mpf_style = mpf.make_mpf_style(
        base_mpf_style="classic" if cn_style else "binance",
        marketcolors=market_colors,
        gridstyle=":",
        gridcolor="#E0E0E0",
        rc=font_rc,
    )

    # 4. 辅助指标叠加 (如布林带)
    add_plots = []
    if (
        show_bollinger
        and "boll_upper" in df.columns
        and "boll_lower" in df.columns
    ):
        add_plots.append(
            mpf.make_addplot(
                df["boll_upper"], color="gray", linestyle="--", width=0.8
            )
        )
        if "boll_middle" in df.columns:
            add_plots.append(
                mpf.make_addplot(
                    df["boll_middle"], color="orange", linestyle=":", width=0.8
                )
            )
        add_plots.append(
            mpf.make_addplot(
                df["boll_lower"], color="gray", linestyle="--", width=0.8
            )
        )

    # 5. 构建绘图参数字典
    plot_kwargs = {
        "type": "candle",
        "volume": "Volume" in df.columns,  # 只有存在 Volume 列时才画成交量
        "mav": mav,
        "style": mpf_style,
        "title": title,
        "figsize": (12, 7),
        "returnfig": True,  # 返回 fig 和 axes 对象，不直接强行 show()
        "warn_too_much_data": 2000,
    }

    if add_plots:
        plot_kwargs["addplot"] = add_plots

    if savefig:
        plot_kwargs["savefig"] = savefig

    # 6. 执行绘制
    fig, axes = mpf.plot(df, **plot_kwargs)

    return fig, axes
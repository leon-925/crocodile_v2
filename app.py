"""Crocodile v2 — 量化交易系统面板

运行: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import os
import sys

# 确保项目根目录在 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── 页面配置 ──
st.set_page_config(
    page_title="Crocodile v2",
    page_icon="🐊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 自定义 CSS ──
st.markdown("""
<style>
    /* 隐藏 Streamlit 默认元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {background-color: transparent;}

    /* 封面 */
    .cover-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 2rem 0;
    }
    .cover-title {
        font-size: 3.5rem;
        font-weight: 900;
        background: linear-gradient(135deg, #1a5c2a, #3cb371, #228b22);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .cover-subtitle {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .cover-image {
        border-radius: 20px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.15);
        max-width: 400px;
    }

    /* 卡片 */
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa, #e4e8ec);
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1a5c2a;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #666;
        margin-top: 0.2rem;
    }

    /* 盈利/亏损色 */
    .positive {color: #e74c3c;}
    .negative {color: #27ae60;}

    /* 分割线 */
    .section-divider {
        margin: 2rem 0 1rem 0;
        border-top: 2px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)


# ── Session State 初始化 ──
if "page" not in st.session_state:
    st.session_state.page = "cover"
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "backtest_result" not in st.session_state:
    st.session_state.backtest_result = None
if "df" not in st.session_state:
    st.session_state.df = None


# ── 数据生成（Mock — 真实环境用 DataSource） ──
@st.cache_data
def load_mock_data():
    dates = pd.date_range("2024-01-01", "2024-12-31", freq="B")
    np.random.seed(42)
    close = 100 * (1 + np.cumsum(np.random.randn(len(dates)) * 0.015))
    df = pd.DataFrame(
        {
            "open": close * 0.998,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": np.random.randint(5000, 50000, len(dates)),
        },
        index=dates,
    )
    return df


def compute_indicators_df(df):
    from data import IndicatorCalculator
    calc = IndicatorCalculator(df)
    return calc.full().turtle(20, 10, 20).result()


# ── 侧边栏导航 ──
with st.sidebar:
    st.image(
        "crocodile.jpg" if os.path.exists("crocodile.jpg") else None,
        width=120,
    )
    st.markdown("## 🐊 Crocodile v2")
    st.markdown("---")

    page = st.radio(
        "导航",
        ["🏠 首页", "📊 数据中心", "📈 策略工坊", "⚡ 回测引擎", "📋 结果报告"],
        index=["🏠 首页", "📊 数据中心", "📈 策略工坊", "⚡ 回测引擎", "📋 结果报告"].index(
            "🏠 首页" if st.session_state.page == "cover" else
            "📊 数据中心" if st.session_state.page == "data" else
            "📈 策略工坊" if st.session_state.page == "strategy" else
            "⚡ 回测引擎" if st.session_state.page == "backtest" else
            "📋 结果报告"
        ) if st.session_state.page != "cover" else 0,
        label_visibility="collapsed",
    )

    # Map radio to page
    page_map = {
        "🏠 首页": "cover",
        "📊 数据中心": "data",
        "📈 策略工坊": "strategy",
        "⚡ 回测引擎": "backtest",
        "📋 结果报告": "results",
    }
    st.session_state.page = page_map[page]

    st.markdown("---")
    st.caption(f"v2.0 | {date.today()}")
    st.caption("Built with 🐊 by Crocodile")


# ╔══════════════════════════════════════════════════╗
# ║               🏠 COVER PAGE                      ║
# ╚══════════════════════════════════════════════════╝

if st.session_state.page == "cover":
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="cover-container">', unsafe_allow_html=True)

        # 封面图
        if os.path.exists("crocodile.jpg"):
            st.image("crocodile.jpg", width=400)

        st.markdown('<div class="cover-title">Crocodile v2</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="cover-subtitle">量化交易系统 · Data → Strategy → Backtest</div>',
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # 功能卡片
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("📊 数据引擎", "SQLite + 实时", "akshare")
        with c2:
            st.metric("📈 策略库", "4+ 策略", "SMA/Boll/MT/海龟")
        with c3:
            st.metric("⚡ 回测引擎", "3 模式", "向量/逐K线/事件")
        with c4:
            st.metric("📋 绩效报表", "10+ 指标", "夏普/回撤/胜率")

        st.markdown("---")

        # 快速入口
        st.markdown("### 🚀 快速开始")
        q1, q2, q3 = st.columns(3)
        with q1:
            if st.button("📊 加载数据", use_container_width=True, type="primary"):
                st.session_state.df = load_mock_data()
                st.session_state.data_loaded = True
                st.session_state.page = "data"
                st.rerun()
        with q2:
            if st.button("📈 策略工坊", use_container_width=True):
                if not st.session_state.data_loaded:
                    st.session_state.df = load_mock_data()
                    st.session_state.data_loaded = True
                st.session_state.page = "strategy"
                st.rerun()
        with q3:
            if st.button("⚡ 跑回测", use_container_width=True):
                if not st.session_state.data_loaded:
                    st.session_state.df = load_mock_data()
                    st.session_state.data_loaded = True
                st.session_state.page = "backtest"
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


# ╔══════════════════════════════════════════════════╗
# ║            📊 DATA CENTER                        ║
# ╚══════════════════════════════════════════════════╝

elif st.session_state.page == "data":
    st.markdown("## 📊 数据中心")
    st.markdown("管理本地数据库、拉取历史数据、查看行情")

    if not st.session_state.data_loaded:
        df = load_mock_data()
        st.session_state.df = df
        st.session_state.data_loaded = True

    df = st.session_state.df

    # 数据概览
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{len(df)}</div><div class="metric-label">K 线条数</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{df.index[0].strftime("%Y-%m-%d")}</div><div class="metric-label">起始日期</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{df.index[-1].strftime("%Y-%m-%d")}</div><div class="metric-label">结束日期</div></div>', unsafe_allow_html=True)
    with c4:
        ret = (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100
        color = "#e74c3c" if ret > 0 else "#27ae60"
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:{color}">{ret:+.2f}%</div><div class="metric-label">区间涨跌</div></div>', unsafe_allow_html=True)

    # 数据表格 + K线图
    tab1, tab2, tab3 = st.tabs(["📋 数据表", "📈 K线图", "🔢 指标预览"])

    with tab1:
        st.dataframe(df.tail(20), use_container_width=True, height=400)
        csv = df.to_csv().encode("utf-8")
        st.download_button("⬇️ 下载 CSV", csv, "ohlcv.csv", "text/csv")

    with tab2:
        from visualization import plot_kline
        try:
            fig, ax = plot_kline(df.iloc[-120:], title="Price Chart", cn_style=True)
            st.pyplot(fig)
        except Exception:
            st.line_chart(df["close"].iloc[-120:], height=400)

    with tab3:
        dfi = compute_indicators_df(df)
        st.dataframe(dfi.tail(10), use_container_width=True, height=300)
        cols = st.columns(2)
        with cols[0]:
            st.metric("指标总数", len([c for c in dfi.columns if c not in ("open","high","low","close","volume")]))
        with cols[1]:
            st.metric("有效行数", len(dfi))


# ╔══════════════════════════════════════════════════╗
# ║            📈 STRATEGY WORKSHOP                  ║
# ╚══════════════════════════════════════════════════╝

elif st.session_state.page == "strategy":
    st.markdown("## 📈 策略工坊")
    st.markdown("像搭乐高一样拼策略：入场 + 过滤 + 出场 + 止损 + 止盈")

    if not st.session_state.data_loaded:
        df = load_mock_data()
        st.session_state.df = df
        st.session_state.data_loaded = True

    df = st.session_state.df

    from data import compute_indicators
    from strategies import StrategyBuilder
    from backtest import VectorizedBacktest

    # ── 标签页：预设 / 自定义 / YAML ──
    tab_preset, tab_custom, tab_yaml = st.tabs(["🎯 一键预设", "🧱 搭乐高", "📝 YAML 配置"])

    # ═══════════════════════════════════
    # TAB 1: 预设
    # ═══════════════════════════════════
    with tab_preset:
        c1, c2 = st.columns([1, 2])
        with c1:
            preset = st.selectbox("选择预设策略", StrategyBuilder.list_presets(),
                format_func=lambda x: {
                    'dual_ma':'双均线交叉','bollinger_band':'布林带','momentum':'动量轮动',
                    'turtle':'海龟交易','trend_following':'趋势跟随'
                }.get(x, x))
            st.caption("💡 预设策略自带最优参数，一键可用")

            with st.expander("📖 策略说明"):
                descriptions = {
                    'dual_ma': '短均线上穿长均线 → 买入\n短均线下穿长均线 → 卖出\n经典趋势跟踪策略',
                    'bollinger_band': '价格跌破下轨 → 买入\n价格突破上轨 → 卖出\n震荡反转策略',
                    'momentum': '动量由负转正 → 买入\n动量由正转负 → 卖出\n动量轮动策略',
                    'turtle': '突破20日最高 → 买入\n跌破10日最低 → 卖出\nATR 2倍止损\n经典海龟交易系统',
                    'trend_following': '5/60金叉 → 买入\n价格>120日均线 + 放量\n移动止损8% + 止盈30%\n稳定趋势策略',
                }
                st.text(descriptions.get(preset, ''))

            if st.button("🚀 运行预设", type="primary", use_container_width=True, key="preset_run"):
                with st.spinner("计算指标 & 生成信号..."):
                    strat = StrategyBuilder.preset(preset)
                    dfi = compute_indicators(df, 'full')
                    sig = strat.generate_signal_with_state(dfi)
                    st.session_state.strategy_signal = sig
                    st.session_state.strategy_built = strat

        with c2:
            if "strategy_built" in st.session_state and "strategy_signal" in st.session_state:
                sig = st.session_state.strategy_signal
                strat = st.session_state.strategy_built
                buys = (sig['signal']==1).sum()
                sells = (sig['signal']==-1).sum()

                c1a, c2a, c3a, c4a = st.columns(4)
                c1a.metric("买入信号", buys)
                c2a.metric("卖出信号", sells)
                c3a.metric("信号总数", buys+sells)
                c4a.metric("策略", preset)

                try:
                    from visualization import plot_signal
                    fig, ax = plot_signal(sig.iloc[-200:].copy())
                    st.pyplot(fig)
                except Exception:
                    st.line_chart(sig[["close"]].iloc[-200:])

                st.caption(str(strat))
            else:
                st.info("👈 选择预设策略并点击运行")
                st.line_chart(df["close"].iloc[-200:])

    # ═══════════════════════════════════
    # TAB 2: 搭乐高
    # ═══════════════════════════════════
    with tab_custom:
        c_left, c_right = st.columns([1, 2])

        with c_left:
            st.markdown("#### 🟢 入场规则")
            entry_type = st.selectbox("入场方式",
                ["ma_cross", "boll_lower", "momentum_turn", "turtle_breakout", "price_break"],
                format_func=lambda x: {'ma_cross':'均线金叉','boll_lower':'布林下轨','momentum_turn':'动量转正','turtle_breakout':'海龟突破','price_break':'价格突破'}.get(x,x),
                key="entry_type")
            entry_params = {}
            if entry_type == "ma_cross":
                entry_params["short"] = st.slider("短期", 3, 30, 5, key="entry_short")
                entry_params["long"] = st.slider("长期", 10, 120, 20, key="entry_long")
            elif entry_type in ("momentum_turn", "turtle_breakout", "price_break"):
                entry_params["period"] = st.slider("周期", 5, 60, 20, key="entry_p")

            st.markdown("#### 🛡️ 过滤器 (可选)")
            use_rsi = st.checkbox("RSI 过滤", key="f_rsi")
            filter_list = []
            filter_params = {}
            if use_rsi:
                filter_list.append("rsi")
                filter_params["rsi"] = {"max": st.slider("RSI 上限", 50, 90, 70, key="rsi_max")}
            use_vol = st.checkbox("成交量过滤", key="f_vol")
            if use_vol:
                filter_list.append("volume")
                filter_params["volume"] = {"min_ratio": st.slider("最小量比", 0.5, 3.0, 1.0, 0.1, key="vol_r")}
            use_trend = st.checkbox("趋势过滤", key="f_trend")
            if use_trend:
                filter_list.append("trend")
                filter_params["trend"] = {"period": st.slider("趋势均线", 20, 250, 60, key="trend_p")}

            st.markdown("#### 🔴 出场规则")
            exit_type = st.selectbox("出场方式",
                ["ma_cross", "boll_upper", "momentum_turn", "turtle_exit", "time_exit"],
                format_func=lambda x: {'ma_cross':'均线死叉','boll_upper':'布林上轨','momentum_turn':'动量转负','turtle_exit':'海龟出场','time_exit':'持仓天数'}.get(x,x),
                key="exit_type")
            exit_params = {}
            if exit_type == "ma_cross":
                exit_params["short"] = st.slider("短期", 3, 30, 5, key="exit_short")
                exit_params["long"] = st.slider("长期", 10, 120, 20, key="exit_long")
            elif exit_type in ("momentum_turn", "turtle_exit"):
                exit_params["period"] = st.slider("周期", 5, 60, 20, key="exit_p")
            elif exit_type == "time_exit":
                exit_params["days"] = st.slider("持仓天数", 3, 60, 20, key="exit_d")

            st.markdown("#### ⛔ 止损 / 🎯 止盈")
            use_sl = st.checkbox("启用止损", value=True, key="use_sl")
            sl_type = "atr"
            sl_params = {}
            if use_sl:
                sl_type = st.selectbox("止损方式", ["atr", "fixed_pct", "trailing"],
                    format_func=lambda x: {'atr':'ATR止损','fixed_pct':'固定比例','trailing':'移动止损'}.get(x,x),
                    key="sl_type")
                if sl_type == "atr":
                    sl_params["multiplier"] = st.slider("ATR倍数", 1.0, 5.0, 2.0, 0.5, key="sl_m")
                elif sl_type == "fixed_pct":
                    sl_params["pct"] = st.slider("止损比例%", 1, 20, 5, key="sl_p") / 100
                else:
                    sl_params["pct"] = st.slider("回撤比例%", 1, 20, 8, key="sl_t") / 100

            use_tp = st.checkbox("启用止盈", key="use_tp")
            tp_type = "fixed_pct"
            tp_params = {}
            if use_tp:
                tp_type = st.selectbox("止盈方式", ["fixed_pct", "ma_touch"],
                    format_func=lambda x: {'fixed_pct':'固定比例','ma_touch':'触碰均线'}.get(x,x),
                    key="tp_type")
                if tp_type == "fixed_pct":
                    tp_params["target"] = st.slider("止盈比例%", 5, 50, 15, key="tp_p") / 100
                else:
                    tp_params["period"] = st.slider("均线周期", 3, 20, 5, key="tp_m")

            if st.button("🧱 构建策略", type="primary", use_container_width=True, key="build_btn"):
                with st.spinner("搭建中..."):
                    builder = StrategyBuilder("自定义组合")
                    builder.entry(entry_type, **entry_params)
                    for ft in filter_list:
                        builder.filter(ft, **filter_params.get(ft, {}))
                    builder.exit(exit_type, **exit_params)
                    if use_sl:
                        builder.stop_loss(sl_type, **sl_params)
                    if use_tp:
                        builder.take_profit(tp_type, **tp_params)
                    strat = builder.build()
                    dfi = compute_indicators(df, 'full')
                    sig = strat.generate_signal_with_state(dfi)
                    st.session_state.strategy_signal = sig
                    st.session_state.strategy_built = strat
                    st.session_state.strategy_yaml = builder.to_yaml()

        with c_right:
            if "strategy_built" in st.session_state and "strategy_signal" in st.session_state:
                sig = st.session_state.strategy_signal
                strat = st.session_state.strategy_built
                buys = (sig['signal']==1).sum()
                sells = (sig['signal']==-1).sum()

                c1b, c2b, c3b = st.columns(3)
                c1b.metric("买入信号", buys)
                c2b.metric("卖出信号", sells)
                c3b.metric("信号总数", buys+sells)

                st.markdown(f"**策略配置**: {strat.component_summary}")

                try:
                    from visualization import plot_signal
                    fig, ax = plot_signal(sig.iloc[-200:].copy())
                    st.pyplot(fig)
                except Exception:
                    st.line_chart(sig[["close"]].iloc[-200:])

                # YAML 预览
                with st.expander("📝 YAML 配置预览"):
                    st.code(st.session_state.get("strategy_yaml", ""), language="yaml")
            else:
                st.info("👈 配置入场/出场/过滤/止损/止盈后点击「构建策略」")
                st.line_chart(df["close"].iloc[-200:])

    # ═══════════════════════════════════
    # TAB 3: YAML 配置
    # ═══════════════════════════════════
    with tab_yaml:
        c_y1, c_y2 = st.columns([1, 1])
        with c_y1:
            st.markdown("#### 📝 粘贴 YAML 配置")
            default_yaml = """name: 我的策略
entry:
  type: ma_cross
  short: 5
  long: 20
filters:
  - type: rsi
    max: 70
exit:
  type: ma_cross
  short: 5
  long: 20
stop_loss:
  - type: atr
    multiplier: 2
take_profit:
  - type: fixed_pct
    target: 0.15"""
            yaml_input = st.text_area("YAML", default_yaml, height=300, key="yaml_input")

            if st.button("🚀 从 YAML 加载", type="primary", use_container_width=True, key="yaml_load"):
                with st.spinner("解析 YAML..."):
                    try:
                        import tempfile, os
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
                            f.write(yaml_input)
                            yaml_path = f.name
                        strat = StrategyBuilder.from_yaml(yaml_path)
                        os.unlink(yaml_path)
                        dfi = compute_indicators(df, 'full')
                        sig = strat.generate_signal_with_state(dfi)
                        st.session_state.strategy_signal = sig
                        st.session_state.strategy_built = strat
                        st.success("✅ YAML 加载成功")
                    except Exception as e:
                        st.error(f"❌ 解析失败: {e}")

        with c_y2:
            if "strategy_built" in st.session_state and "strategy_signal" in st.session_state:
                sig = st.session_state.strategy_signal
                strat = st.session_state.strategy_built
                buys = (sig['signal']==1).sum()
                sells = (sig['signal']==-1).sum()

                c1c, c2c, c3c = st.columns(3)
                c1c.metric("买入信号", buys)
                c2c.metric("卖出信号", sells)
                c3c.metric("信号总数", buys+sells)

                st.markdown(f"**策略**: {strat.component_summary}")

                try:
                    from visualization import plot_signal
                    fig, ax = plot_signal(sig.iloc[-200:].copy())
                    st.pyplot(fig)
                except Exception:
                    st.line_chart(sig[["close"]].iloc[-200:])
            else:
                st.info("👈 粘贴 YAML 配置并加载")


# ╔══════════════════════════════════════════════════╗
# ║            ⚡ BACKTEST ENGINE                    ║
# ╚══════════════════════════════════════════════════╝

elif st.session_state.page == "backtest":
    st.markdown("## ⚡ 回测引擎")
    st.markdown("选择回测模式、配置参数、运行回测")

    if not st.session_state.data_loaded:
        df = load_mock_data()
        st.session_state.df = df
        st.session_state.data_loaded = True

    df = st.session_state.df

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### ⚙️ 回测配置")

        mode = st.selectbox("回测模式", ["vectorized", "bar_by_bar", "event_driven"])

        # 策略来源
        strategy_source = st.radio("策略来源", ["🧱 策略工坊(已构建)", "📋 内置策略"], key="bt_strat_source")

        if strategy_source == "🧱 策略工坊(已构建)":
            if "strategy_built" not in st.session_state:
                st.warning("⚠️ 先去策略工坊构建策略")
                strategy_sel = None
            else:
                st.success(f"✅ 已加载: {st.session_state.strategy_built.component_summary}")
                strategy_sel = "workshop"
        else:
            strategy_sel = st.selectbox("策略", ["双均线(5,20)", "布林带", "动量(20)", "海龟(20/10)", "趋势跟随"])

        initial_cash = st.number_input("初始资金", 10000, 10000000, 500000, 10000)
        commission = st.number_input("手续费率", 0.0001, 0.01, 0.0003, 0.0001, format="%.4f")
        slippage = st.number_input("滑点", 0.0, 0.01, 0.0, 0.0001, format="%.4f")

        st.markdown("---")
        run_btn = st.button("⚡ 运行回测", type="primary", use_container_width=True)

        st.markdown("---")
        st.markdown("### 📖 模式说明")
        st.caption("**向量化**: 极速，纯信号列计算")
        st.caption("**逐K线**: 标准，完整 Account/Broker 链路")
        st.caption("**事件驱动**: 高仿真，事件队列撮合")

    with col2:
        if run_btn:
            with st.spinner("回测运行中..."):
                from data import compute_indicators
                from strategies import DualMAStrategy, BollingerStrategy, MomentumStrategy, TurtleStrategy, StrategyBuilder
                from backtest import VectorizedBacktest, BarByBarBacktest, EventDrivenBacktest
                from portfolio import Account, PortfolioManager
                from execution import Broker

                # 选策略
                if strategy_sel == "workshop":
                    strategy = st.session_state.strategy_built
                else:
                    strategy_map = {
                        "双均线(5,20)": lambda: DualMAStrategy(5, 20),
                        "布林带": lambda: BollingerStrategy(),
                        "动量(20)": lambda: MomentumStrategy(20),
                        "海龟(20/10)": lambda: TurtleStrategy(20, 10, 20),
                        "趋势跟随": lambda: StrategyBuilder.preset("trend_following"),
                    }
                    strategy = strategy_map[strategy_sel]()

                # 计算指标
                dfi = compute_indicators(df, "full")

                if mode == "vectorized":
                    sig = strategy.generate_signal(dfi)
                    engine = VectorizedBacktest(initial_cash, commission, slippage=slippage)
                    result = engine.run(sig)
                else:
                    acc = Account(initial_cash)
                    broker = Broker(acc, slippage=slippage)
                    pm = PortfolioManager(acc)

                    if mode == "bar_by_bar":
                        engine = BarByBarBacktest(acc, broker, pm)
                        result = engine.run(dfi, strategy, symbol="600519.SH")
                    else:
                        engine = EventDrivenBacktest(acc, broker, pm)
                        result = engine.run(dfi)

                st.session_state.backtest_result = result
                st.session_state.backtest_mode = mode

        if st.session_state.backtest_result is not None:
            result = st.session_state.backtest_result
            mode = st.session_state.backtest_mode

            # 指标卡片
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("总收益率", f"{result.total_return:.2%}")
            c2.metric("最大回撤", f"{result.max_drawdown:.2%}")
            c3.metric("夏普比率", f"{result.sharpe_ratio:.2f}")
            c4.metric("交易次数", result.metrics.get("total_trades", 0))

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("胜率", f"{result.metrics.get('win_rate', 0):.1%}")
            c6.metric("盈亏比", f"{result.metrics.get('profit_factor', 0):.2f}")
            c7.metric("总盈亏", f"{result.metrics.get('total_pnl', 0):,.0f}")
            c8.metric("回测模式", mode)

            st.markdown("---")
            st.markdown("### 📈 净值曲线")
            try:
                fig, ax = result.plot()
                st.pyplot(fig)
            except Exception:
                st.line_chart(result.equity_curve["equity"])

            with st.expander("📋 详细数据"):
                st.dataframe(result.equity_curve, use_container_width=True)
        else:
            st.info("👈 配置参数后点击「运行回测」")

            # 先画个 K 线占位
            st.markdown("### 📈 数据预览")
            st.line_chart(df["close"].iloc[-200:])


# ╔══════════════════════════════════════════════════╗
# ║            📋 RESULTS REPORT                     ║
# ╚══════════════════════════════════════════════════╝

elif st.session_state.page == "results":
    st.markdown("## 📋 结果报告")

    if st.session_state.backtest_result is None:
        st.info("还没有回测结果。先去「回测引擎」跑一次。")
        if st.button("⚡ 去跑回测"):
            st.session_state.page = "backtest"
            st.rerun()
    else:
        result = st.session_state.backtest_result

        st.markdown("### 📊 绩效摘要")
        m = result.summary_dict()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("#### 收益指标")
            st.metric("总收益率", f"{m.get('total_return', 0):.2%}")
            st.metric("年化收益", f"{m.get('annual_return', 0):.2%}")
            st.metric("总盈亏", f"{m.get('total_pnl', 0):,.0f}")

        with col2:
            st.markdown("#### 风险指标")
            st.metric("最大回撤", f"{m.get('max_drawdown', 0):.2%}")
            st.metric("夏普比率", f"{m.get('sharpe_ratio', 0):.2f}")

        with col3:
            st.markdown("#### 交易统计")
            st.metric("总交易", m.get("total_trades", 0))
            st.metric("胜率", f"{m.get('win_rate', 0):.1%}")
            st.metric("盈亏比", f"{m.get('profit_factor', 0):.2f}")

        st.markdown("---")
        st.markdown("### 📈 净值 + 回撤")
        fig, ax = result.plot()
        st.pyplot(fig)

        st.markdown("---")
        tab1, tab2 = st.tabs(["📋 净值数据", "📜 交易记录"])
        with tab1:
            st.dataframe(result.equity_curve, use_container_width=True)
        with tab2:
            st.dataframe(result.trades, use_container_width=True)

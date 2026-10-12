import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime

from data_loader import DEFAULT_TICKERS, fetch_ticker_data, normalize_ticker
from strategy import calculate_indicators, evaluate_signals, get_latest_signal_summary
from backtest import run_backtest

# Configure page
st.set_page_config(
    page_title="台股 ETF 智能追蹤與買賣決策系統",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        flex-wrap: wrap !important;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        font-weight: 600;
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.title("🎯 標的與策略設定")

# Category filter & Preset selector
categories = ["全部熱門標的 (All)", "🔥 核心指定標的", "🚀 科技半導體個股", "🏦 金融權值存股", "🚢 航運重電人氣股", "💰 熱門高股息 ETF", "🇺🇸 美股科技巨頭"]
selected_category = st.sidebar.selectbox("📂 標的族群分類：", options=categories, index=0)

if selected_category == "全部熱門標的 (All)":
    filtered_keys = list(DEFAULT_TICKERS.keys())
else:
    filtered_keys = [k for k in DEFAULT_TICKERS if DEFAULT_TICKERS[k].get("category") == selected_category]
    if not filtered_keys:
        filtered_keys = list(DEFAULT_TICKERS.keys())

selected_preset = st.sidebar.selectbox(
    "選擇追蹤標的：",
    options=filtered_keys,
    format_func=lambda k: f"{k} - {DEFAULT_TICKERS[k]['name']} ({DEFAULT_TICKERS[k]['type']})",
    index=0
)

# Custom ticker input option
custom_input = st.sidebar.text_input("🔍 或輸入自訂代碼 (如 2317, 2454, AAPL)：", "").strip()
active_symbol = custom_input if custom_input else selected_preset

# Strategy mode
strategy_mode = st.sidebar.selectbox(
    "🧭 交易策略模式：",
    options=["綜合評分模式", "波段操作模式", "中長線趨勢模式", "存股低接模式"],
    index=0,
    help="針對您不確定持有週期的情況：\n- 綜合評分：整合趨勢、動能與擺盪指標，最平衡穩健\n- 波段操作：關注 KD 交叉與月線進出\n- 中長線趨勢：月季線多頭排列時持有\n- 存股低接：逢拉回與超賣分批加碼"
)

# Period selection
period_option = st.sidebar.radio(
    "歷史數據週期：",
    options=["6mo", "1y", "2y", "5y"],
    format_func=lambda x: {"6mo": "6 個月", "1y": "1 年", "2y": "2 年", "5y": "5 年"}[x],
    index=2,
    horizontal=True
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 💡 使用說明")
st.sidebar.info(
    "1. 本系統支援台股代碼 (自動補齊 `.TW`) 與美股代碼。\n"
    "2. 買賣訊號結合 **均線 (MA20/60)**、**日KD**、**RSI**、**MACD** 與 **乖離率** 綜合評估。\n"
    "3. 點選上方分頁可檢視『決策分析』、『技術線圖』、『歷史回測』及『多檔橫向比對』。"
)

# Fetch Data
with st.spinner(f"正在載入 {active_symbol} 市場行情數據..."):
    raw_df, meta, err = fetch_ticker_data(active_symbol, period=period_option)

if err or raw_df is None or raw_df.empty:
    st.error(f"❌ {err or '無法取得該標的行情數據，請確認代碼是否正確。'}")
    st.stop()

# Process strategy
df_with_ind = calculate_indicators(raw_df)
df_scored = evaluate_signals(df_with_ind, strategy_type=strategy_mode)
summary = get_latest_signal_summary(df_scored, meta, strategy_type=strategy_mode)

# Main Title & Top Bar
col_title, col_stat = st.columns([2, 1])
with col_title:
    st.title(f"{meta['name']} (`{meta['symbol']}`)")
    st.caption(f"{meta['type']} ｜ {meta['desc']} ｜ 最後更新日期: {meta['last_date']}")

with col_stat:
    chg_color = "red" if meta['change'] > 0 else "green" if meta['change'] < 0 else "gray" # Taiwan market: Red is UP, Green is DOWN
    chg_arrow = "▲" if meta['change'] > 0 else "▼" if meta['change'] < 0 else "―"
    st.metric(
        label=f"當前價格 (NT$ / USD)",
        value=f"{meta['current_price']:.2f}",
        delta=f"{chg_arrow} {meta['change']:+.2f} ({meta['change_pct']:+.2f}%)",
        delta_color="inverse" # Flip for Taiwan red-up green-down perception
    )

# Key Decision Banner
st.markdown("---")
score = summary['score']
col_b1, col_b2, col_b3 = st.columns([1.5, 1.5, 1])

with col_b1:
    st.subheader("🎯 當前系統決策")
    st.markdown(f"### {summary['label']}")
    st.write(summary['action_text'])

with col_b2:
    st.subheader("📊 綜合多空評分")
    norm_score = max(0.0, min(1.0, (float(score) + 100.0) / 200.0))
    st.progress(norm_score)
    score_int = int(round(float(score)))
    score_desc = "極度偏空" if score_int <= -50 else "偏空" if score_int <= -20 else "中立觀望" if score_int < 20 else "偏多" if score_int < 50 else "極度偏多"
    st.markdown(f"**評分：`{score_int:+d} 分`** (區間 -100 到 +100，目前屬 **{score_desc}**)")

with col_b3:
    st.subheader("🛡️ 參考操作價位")
    st.markdown(f"- **防守停損點**：`{summary['stop_loss']:.2f}`")
    st.markdown(f"- **波段停利點**：`{summary['take_profit']:.2f}`")

# Asset-specific warnings
if summary['risk_warnings']:
    for w in summary['risk_warnings']:
        st.warning(w)

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💡 買賣決策",
    "📈 技術線圖",
    "📊 策略回測",
    "🔍 標的盤點",
    "📖 新手看盤指南"
])

# ================= TAB 1: Signal & Factors Breakdown =================
with tab1:
    st.subheader("📋 技術面六大多空因子檢核表")
    
    factor_cols = st.columns(3)
    for i, f in enumerate(summary['factors']):
        with factor_cols[i % 3]:
            with st.container(border=True):
                st.caption(f['category'])
                st.markdown(f"### {f['value']}")
                badge = "🟢 多方" if f['is_bullish'] else "🔴 偏空/警戒"
                st.markdown(f"狀態：**{f['status']}** ({badge})")
            
    st.markdown("---")
    st.subheader("💡 投資策略建議 (針對新手 / 不確定週期的配置心法)")
    
    col_strat1, col_strat2 = st.columns(2)
    with col_strat1:
        st.markdown("#### 🔹 情況一：偏好穩健、不想天天盯盤 (長期存股 / DCA)")
        st.markdown(
            "- **買進條件**：當月線乖離率 `BIAS20 < -3%` 或 `RSI < 40` 時，代表進入波段超跌或逢低拉回區，可分批進場加碼。\n"
            "- **持有條件**：只要股價在半年線 (MA120) 或季線 (MA60) 之上，大趨勢維持多頭，請堅定持有或定期定額。\n"
            "- **調節條件**：當 RSI 破 80 或乖離率過高時，只停利不停損，適度收割部分利潤。"
        )
    with col_strat2:
        st.markdown("#### 🔹 情況二：希望跟隨動能、掌握波段行情 (波段交易 / Swing)")
        st.markdown(
            "- **進場時機**：日 KD 出現低檔黃金交叉 (K 往上穿過 D)，且股價帶量站上 20 日月線時試單。\n"
            "- **出場停損**：嚴守紀律！跌破 20 日月線或前低停損點立即減碼；日 KD 於高檔 (>80) 出現死亡交叉時分批停利。\n"
            "- **槓桿特別提醒**：若操作 `00631L` (正2)，務必以波段操作為主，切勿在大盤處於空頭或盤整時長抱！"
        )

# ================= TAB 2: Interactive Charts =================
with tab2:
    st.subheader("📈 K線與技術指標圖 (含歷史買賣訊號標記)")
    
    # Create interactive chart with 3 rows: Candlestick, KD, MACD
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=(f"{meta['symbol']} K線圖、均線 (MA20/60/120) 與買賣訊號", "日 KD 指標 (9, 3, 3)", "MACD (12, 26, 9)")
    )
    
    # 1. Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df_scored.index,
            open=df_scored['Open'],
            high=df_scored['High'],
            low=df_scored['Low'],
            close=df_scored['Close'],
            name="K線",
            increasing_line_color="#ef4444", # Red for UP in TW market
            decreasing_line_color="#22c55e" # Green for DOWN in TW market
        ),
        row=1, col=1
    )
    
    # Moving Averages
    fig.add_trace(go.Scatter(x=df_scored.index, y=df_scored['MA20'], name="月線 (MA20)", line=dict(color="#f59e0b", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_scored.index, y=df_scored['MA60'], name="季線 (MA60)", line=dict(color="#3b82f6", width=1.8)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_scored.index, y=df_scored['MA120'], name="半年線 (MA120)", line=dict(color="#8b5cf6", width=1.5)), row=1, col=1)
    
    # Buy / Sell Marker points
    # Buy signals
    buy_signals = df_scored[(df_scored['SIGNAL'] == 1) & (df_scored['SIGNAL_CHANGE'] != 0)]
    sell_signals = df_scored[(df_scored['SIGNAL'] == -1) & (df_scored['SIGNAL_CHANGE'] != 0)]
    
    fig.add_trace(
        go.Scatter(
            x=buy_signals.index,
            y=buy_signals['Low'] * 0.98,
            mode="markers",
            marker=dict(symbol="triangle-up", size=11, color="#16a34a"),
            name="買進訊號 (BUY)",
            hovertext=[f"買進訊號<br>日期: {idx.strftime('%Y-%m-%d')}<br>收盤價: {row['Close']:.2f}" for idx, row in buy_signals.iterrows()],
            hoverinfo="text"
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=sell_signals.index,
            y=sell_signals['High'] * 1.02,
            mode="markers",
            marker=dict(symbol="triangle-down", size=11, color="#dc2626"),
            name="賣出訊號 (SELL)",
            hovertext=[f"賣出訊號<br>日期: {idx.strftime('%Y-%m-%d')}<br>收盤價: {row['Close']:.2f}" for idx, row in sell_signals.iterrows()],
            hoverinfo="text"
        ),
        row=1, col=1
    )
    
    # 2. KD Subplot
    fig.add_trace(go.Scatter(x=df_scored.index, y=df_scored['K'], name="K 值", line=dict(color="#ec4899", width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df_scored.index, y=df_scored['D'], name="D 值", line=dict(color="#06b6d4", width=1.5)), row=2, col=1)
    # 80/20 reference lines
    fig.add_hline(y=80, line_dash="dash", line_color="gray", line_width=1, row=2, col=1)
    fig.add_hline(y=20, line_dash="dash", line_color="gray", line_width=1, row=2, col=1)
    
    # 3. MACD Subplot
    macd_colors = np.where(df_scored['MACD_HIST'] >= 0, '#ef4444', '#22c55e')
    fig.add_trace(
        go.Bar(x=df_scored.index, y=df_scored['MACD_HIST'], name="MACD 柱狀體 (OSC)", marker_color=macd_colors),
        row=3, col=1
    )
    fig.add_trace(go.Scatter(x=df_scored.index, y=df_scored['DIF'], name="DIF (快線)", line=dict(color="#f97316", width=1.2)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_scored.index, y=df_scored['MACD_SIGNAL'], name="MACD (慢線)", line=dict(color="#6366f1", width=1.2)), row=3, col=1)
    
    fig.update_layout(
        height=850,
        xaxis_rangeslider_visible=False,
        margin=dict(l=30, r=30, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)

# ================= TAB 3: Backtest =================
with tab3:
    st.subheader(f"📊 策略歷史回測模擬 ({strategy_mode})")
    st.caption("模擬起始資金 100,000 元，根據策略訊號進行買進賣出，並與單純『買入持有 (Buy & Hold)』基準進行比較。")
    
    bt_res = run_backtest(df_scored, initial_capital=100000.0)
    
    if bt_res:
        # Scoreboard
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("策略總報酬率", f"{bt_res['strat_return']:+.2f}%", delta=f"{bt_res['alpha']:+.2f}% 超額報酬")
        c2.metric("買入持有基準報酬", f"{bt_res['bench_return']:+.2f}%")
        c3.metric("策略年化報酬 (CAGR)", f"{bt_res['strat_cagr']:+.2f}%")
        c4.metric("最大回撤 (MDD)", f"{bt_res['max_dd']:.2f}%", help="資產從最高點回檔的最大跌幅，越小越安全")
        c5.metric("交易勝率", f"{bt_res['win_rate']:.1f}%", help=f"共執行 {bt_res['total_trades']} 筆平倉交易")
        
        # Equity Curve Chart
        eq_df = bt_res['equity_df']
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=eq_df.index, y=eq_df['Strategy_Equity'], name=f"本系統策略 ({strategy_mode})", line=dict(color="#2563eb", width=2.5)))
        fig_bt.add_trace(go.Scatter(x=eq_df.index, y=eq_df['Benchmark_Equity'], name="單純買進持有 (Benchmark)", line=dict(color="#94a3b8", width=1.8, dash="dot")))
        fig_bt.update_layout(
            title="資產淨值曲線 (Equity Curve) 比較",
            yaxis_title="帳戶資產總值 (NTD)",
            height=400,
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_bt, use_container_width=True)
        
        # Trade Log
        if bt_res['trade_history']:
            with st.expander("📝 檢視歷史交易紀錄明細"):
                trade_df = pd.DataFrame(bt_res['trade_history'])
                st.dataframe(trade_df, use_container_width=True)
    else:
        st.info("數據長度不足以產生回測統計，請拉長歷史週期設定。")

# ================= TAB 4: Multi-Stock Watchlist =================
# ================= TAB 4: Multi-Stock Watchlist =================
with tab4:
    st.subheader("🔍 熱門個股與 ETF 橫向大盤點 (一鍵評比)")
    st.caption("同時追蹤半導體、AI 伺服器、金融金控、高股息與核心 ETF，即時掌握資金輪動與多空動能。")
    
    col_t4_1, col_t4_2 = st.columns([1.2, 2.5])
    with col_t4_1:
        tab4_group = st.selectbox(
            "選擇盤點族群：",
            options=["🔥 核心指定標的", "🚀 科技半導體個股", "🏦 金融權值存股", "💰 熱門高股息 ETF", "🚢 航運重電人氣股", "⭐ 精選熱門綜合 (12檔)", "🛠️ 自訂選擇標的"],
            index=0
        )
        
    if tab4_group == "🔥 核心指定標的":
        watchlist_symbols = ["0050.TW", "009800.TW", "2330.TW", "00631L.TW"]
    elif tab4_group == "🚀 科技半導體個股":
        watchlist_symbols = ["2330.TW", "2454.TW", "2317.TW", "2382.TW", "2308.TW", "3231.TW", "2303.TW", "3443.TW"]
    elif tab4_group == "🏦 金融權值存股":
        watchlist_symbols = ["2881.TW", "2882.TW", "2886.TW", "2891.TW", "2884.TW"]
    elif tab4_group == "💰 熱門高股息 ETF":
        watchlist_symbols = ["00878.TW", "00919.TW", "00929.TW", "0056.TW"]
    elif tab4_group == "🚢 航運重電人氣股":
        watchlist_symbols = ["2603.TW", "1519.TW"]
    elif tab4_group == "⭐ 精選熱門綜合 (12檔)":
        watchlist_symbols = ["0050.TW", "2330.TW", "2454.TW", "2317.TW", "2382.TW", "2308.TW", "2881.TW", "2886.TW", "2603.TW", "00878.TW", "00919.TW", "00631L.TW"]
    else: # 自訂選擇標的
        with col_t4_2:
            all_opts = list(DEFAULT_TICKERS.keys())
            def_t4 = [s for s in ["0050.TW", "2330.TW", "2454.TW", "2317.TW", "2881.TW"] if s in all_opts]
            watchlist_symbols = st.multiselect(
                "勾選欲盤點之標的：",
                options=all_opts,
                default=def_t4
            )
            
    if st.button("🔄 刷新盤點清單最新訊號"):
        st.cache_data.clear()
        st.rerun()
        
    overview_data = []
    
    progress_bar = st.progress(0.0)
    for idx, sym in enumerate(watchlist_symbols):
        progress_bar.progress((idx + 1) / len(watchlist_symbols))
        d_raw, m_info, _ = fetch_ticker_data(sym, period="1y")
        if d_raw is not None and not d_raw.empty:
            d_ind = calculate_indicators(d_raw)
            d_sc = evaluate_signals(d_ind, strategy_type=strategy_mode)
            s_sum = get_latest_signal_summary(d_sc, m_info, strategy_type=strategy_mode)
            row_last = d_sc.iloc[-1]
            
            overview_data.append({
                "代碼": sym,
                "標的名稱": m_info['name'],
                "族群類型": m_info.get('type', '個股/ETF'),
                "最新收盤價": f"{m_info['current_price']:.2f}",
                "今日漲跌幅": f"{m_info['change_pct']:+.2f}%",
                "決策訊號": s_sum['label'].split('(')[0].strip(),
                "多空評分": f"{int(round(float(s_sum['score']))):+d}",
                "站上月線": "✅ 是" if row_last['Close'] > row_last['MA20'] else "❌ 否",
                "站上季線": "✅ 是" if row_last['Close'] > row_last['MA60'] else "❌ 否",
                "日 KD": f"{row_last['K']:.0f} / {row_last['D']:.0f}",
                "RSI(14)": f"{row_last['RSI']:.1f}",
                "月線乖離率": f"{row_last['BIAS20']:+.1f}%"
            })
    progress_bar.empty()
    
    if overview_data:
        df_overview = pd.DataFrame(overview_data)
        st.dataframe(df_overview, width="stretch", hide_index=True)
        st.info("💡 觀察小技巧：若標的『多空評分 > +20』且『同時站上月線與季線』，代表該族群處於多方強勢控盤波段。")

# ================= TAB 5: Beginner Guide =================
with tab5:
    st.subheader("📖 投資新手看盤指南（白話大字典）")
    st.caption("把複雜的數學公式全部換成生活化比喻，讓您 3 秒鐘看懂訊號與專有名詞！")
    
    # 1. 3秒判讀法
    st.markdown("### 🚀 第一步：收到 LINE 訊息或看盤的「3 秒判讀法」")
    st.markdown("每次看到標的資訊，只需照著這個順序看三件事：")
    
    st.code("""🟢 【適合買進】 台積電 (2330.TW) 
  • 現價: $1050.00 (+2.44%)
  • 訊號: 偏多買進 / 分批進場 (評分: +35)   <--- 1. 先看燈號與分數（決定能不能買）
  • 建議價位: 停損 $1010.00 ｜ 停利 $1120.00 <--- 2. 再看防守價（先算風險，再算賺多少）
  • 策略建議: KD黃金交叉、站上月線...       <--- 3. 最後看理由（了解為什麼漲）""", language="text")
  
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info("1️⃣ **看顏色與訊號**\n\n綠燈（買進）還是紅燈（賣出/避險）？掌握大方向。")
    with c2:
        st.warning("2️⃣ **看停損價**\n\n若買進後跌破停損價必須果斷出場。能承受該風險才進場。")
    with c3:
        st.success("3️⃣ **看停利價**\n\n漲到停利價附近代表波段肉差不多了，可分批入袋為安。")
        
    st.markdown("---")
    
    # 2. 多空評分表格
    st.markdown("### 📊 第二步：多空評分（Score）是什麼意思？")
    st.markdown("系統分數範圍為 **`-100 分` 至 `+100 分`**，就像為標的的健康狀況進行體檢打分數：")
    
    score_guide_data = [
        {"分數區間": "+50 以上", "燈號訊號": "🟢 強烈買進", "白話解釋": "「順風順水，油門踩到底」多頭全面共振", "新手建議動作": "可積極進場或分批加碼"},
        {"分數區間": "+20 ~ +49", "燈號訊號": "🟢 偏多買進", "白話解釋": "「天氣放晴，可以出門」多方勝率佔優", "新手建議動作": "逢拉回分批建倉，不追高"},
        {"分數區間": "-19 ~ +19", "燈號訊號": "🟡 觀望中立", "白話解釋": "「多空拔河，原地打轉」盤整震盪無趨勢", "新手建議動作": "空手者觀望勿動；持股者續抱"},
        {"分數區間": "-20 ~ -49", "燈號訊號": "🔴 偏空調節", "白話解釋": "「變天轉陰，小心淋雨」短線過熱或轉弱", "新手建議動作": "分批獲利了結或部分停損減碼"},
        {"分數區間": "-50 以下", "燈號訊號": "🔴 強烈賣出", "白話解釋": "「暴風雨來襲，快躲起來」空頭破位加速", "新手建議動作": "嚴格停損出場，切勿盲目抄底"}
    ]
    st.dataframe(pd.DataFrame(score_guide_data), hide_index=True, width="stretch")

    st.markdown("---")
    
    # 3. 專有名詞大字典
    st.markdown("### 💡 第三步：關鍵專有名詞「生活化比喻」大字典")
    
    with st.expander("1. 均線（MA, Moving Average）——【行情的防護罩與跑道】", expanded=True):
        st.markdown("""
        * **白話意思**：過去這段時間「大家的平均買進成本」。
          * **月線（MA20）＝ 20天的平均成本（短期防守線）**：
            * **站上月線**：代表這一個月買進的人都在賺錢，市場氛圍樂觀、大家抱得住，容易繼續漲。
            * **跌破月線**：代表這一個月買進的人開始虧損，容易引發失望拋售賣壓。
          * **季線（MA60）＝ 60天的平均成本（中期生命線）**：
            * 股價在季線之上稱為**中長多頭格局**；在季線之下代表中期偏弱。
        """)
        
    with st.expander("2. KD 指標（9, 3, 3）——【短跑選手的轉向方向燈】", expanded=True):
        st.markdown("""
        * **白話意思**：判斷短線有沒有「衝太快」或「摔太慘」，由 **K 值（快線）** 與 **D 值（慢線）** 組成。
          * **黃金交叉（K 往上穿過 D）**：選手開始往前衝了！為**短線買進訊號**。
          * **死亡交叉（K 往下穿過 D）**：選手沒力轉頭往下跑了！為**短線回檔或賣出訊號**。
          * **超賣區（KD < 20）**：大家賣過頭了，隨時可能像皮球觸底反彈。
          * **超買區（KD > 80）**：大家搶過頭了，小心隨時有人獲利了結回跌。
        """)

    with st.expander("3. RSI 相對強弱指標（14）——【人氣熱度計】"):
        st.markdown("""
        * **白話意思**：量測現在市場是「買氣旺」還是「沒人要」，數值在 0 ~ 100 之間。
          * **RSI > 50**：買方力量強於賣方，處於強勢多頭格局。
          * **RSI > 75**：人氣過熱、發高燒了！容易拉回，切忌盲目追高。
          * **RSI < 30**：打入冷宮、超跌了！容易出現逢低買盤進場搶反彈。
        """)

    with st.expander("4. MACD 柱狀體（OSC）——【火車的引擎推力】"):
        st.markdown("""
        * **白話意思**：判斷大趨勢的加速與減速。
          * **紅柱出現且變長**：引擎猛力噴火，多頭推力越來越強！
          * **紅柱縮小**：車子還在往前，但司機已經放開油門了（要注意隨時準備下車）。
          * **綠柱出現**：火車正在倒退，空方掌控局勢。
        """)

    with st.expander("5. 乖離率（BIAS）——【橡皮筋原理】"):
        st.markdown("""
        * **白話意思**：現在股價和平均成本（月線）拉開了多遠的距離。
          * **正乖離過大（如 > +5%）**：橡皮筋拉得太緊，隨時會被彈回月線（容易拉回修正）。
          * **負乖離過大（如 < -4%）**：股價跌得離月線太遠，橡皮筋隨時會把它彈回正常水位（容易反彈）。
        """)

    with st.expander("6. 布林通道（Bollinger Bands）——【股價行駛的高速公路】"):
        st.markdown("""
        * **白話意思**：用統計學畫出股價 95% 會在裡面跑的「上軌道」、「中軌道（月線）」與「下軌道」。
          * **碰到下軌**：車子開到路肩了，容易被拉回車道內（低接機會）。
          * **碰到上軌**：車子頂到最高天花板了，容易回檔（短線停利點）。
        """)

    with st.expander("7. 停損價與停利價——【保命降落傘與提款密碼】"):
        st.markdown("""
        * **停損參考價（Stop Loss）**：
          * **保命第一條鐵則**。系統設在跌破月線或一定波動度之下。若收盤跌破此價格，代表當初買進的理由已消失，必須果斷認賠賣出，避免小賠變大賠。
        * **停利目標價（Take Profit）**：
          * 系統預設的短波段滿足點。漲到這裡建議可**分批賣一半先賺落袋**，剩下的一半讓獲利繼續奔跑！
        """)

    st.markdown("---")
    st.info("🌟 **新手實戰金句**：『先看紅綠燈，再看停損點；不熟不亂買，跌破就出場。』平常顯示觀望中立時就安心生活，讓量化系統為您把關！")


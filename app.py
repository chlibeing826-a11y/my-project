import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from stock import (
    get_fundamentals,
    get_financials_history,
    get_long_history,
    get_stock_price,
    search_ticker,
)

# ── Page config ───────────────────────────────────────────────────
st.set_page_config(page_title="长期价值投资分析仪", page_icon="📈", layout="wide")
st.title("📈 长期价值投资分析仪")
st.caption("专为价值投资新手设计 · 看公司基本面，不看短线涨跌")


# ── Helper functions ──────────────────────────────────────────────

def fmt_num(n):
    if n is None:
        return "N/A"
    if abs(n) >= 1e12:
        return f"${n/1e12:.2f}T"
    elif abs(n) >= 1e9:
        return f"${n/1e9:.2f}B"
    elif abs(n) >= 1e6:
        return f"${n/1e6:.2f}M"
    return f"${n:,.0f}"


def traffic_light(key, value):
    """Return (emoji, label) for a metric based on value investing thresholds."""
    if value is None:
        return "⚪", "暂无数据"

    # Lower is better
    low_better = {
        "pe_ratio": [
            (15, "🟢", "价格便宜"),
            (25, "🟡", "估值合理"),
            (float("inf"), "🔴", "价格偏贵"),
        ],
        "pb_ratio": [
            (1.5, "🟢", "低于净资产"),
            (3.0, "🟡", "估值合理"),
            (float("inf"), "🔴", "价格偏贵"),
        ],
        "debt_to_equity": [
            (50, "🟢", "负债健康"),
            (150, "🟡", "负债适中"),
            (float("inf"), "🔴", "负债偏高"),
        ],
    }
    # Higher is better
    high_better = {
        "roe": [
            (0.15, "🟢", "盈利能力强"),
            (0.08, "🟡", "盈利能力一般"),
            (0.0, "🔴", "盈利能力弱"),
        ],
        "profit_margin": [
            (0.15, "🟢", "利润率优秀"),
            (0.05, "🟡", "利润率一般"),
            (0.0, "🔴", "利润率偏低"),
        ],
        "gross_margin": [
            (0.40, "🟢", "护城河宽"),
            (0.20, "🟡", "护城河一般"),
            (0.0, "🔴", "护城河窄"),
        ],
    }

    if key == "free_cashflow":
        return ("🟢", "现金流健康") if value > 0 else ("🔴", "现金流为负")

    if key in low_better:
        for thresh, emoji, label in low_better[key]:
            if value <= thresh:
                return emoji, label

    if key in high_better:
        for thresh, emoji, label in high_better[key]:
            if value >= thresh:
                return emoji, label
        return "🔴", "数值为负"

    return "⚪", "暂无数据"


# (label, format_fn, plain-language explanation)
METRIC_INFO = {
    "pe_ratio":       ("市盈率 (P/E)",      lambda v: f"{v:.1f}x",     "你花多少钱买公司每年1元利润，越低越便宜。"),
    "pb_ratio":       ("市净率 (P/B)",      lambda v: f"{v:.2f}x",     "股价相对公司净资产的倍数，低于1说明可能被低估。"),
    "roe":            ("净资产回报率 (ROE)", lambda v: f"{v*100:.1f}%", "公司用股东的钱每年赚多少回来，巴菲特要求长期 > 15%。"),
    "debt_to_equity": ("负债率 (D/E)",      lambda v: f"{v/100:.2f}",  "公司借了多少钱相对自己有多少钱，越低越稳健。"),
    "profit_margin":  ("净利率",            lambda v: f"{v*100:.1f}%", "每赚100元收入最终留下多少净利润，越高代表定价权越强。"),
    "gross_margin":   ("毛利率（护城河）",   lambda v: f"{v*100:.1f}%", "扣除直接成本后的利润率，高毛利往往意味着竞争优势。"),
    "free_cashflow":  ("自由现金流",         fmt_num,                   "公司真实赚到手的钱（扣除资本支出），正数才算真赚钱。"),
}


def buffett_checks(fund):
    """Return a list of Buffett-style checklist items with pass/fail status."""
    checks = []

    roe = fund.get("roe")
    checks.append({
        "name": "ROE 持续盈利能力强（> 15%）",
        "passed": roe is not None and roe > 0.15,
        "detail": f"当前 ROE: {roe*100:.1f}%" if roe is not None else "数据不足",
        "tip": "巴菲特偏好 ROE 长期超过15%的公司，说明管理层善用股东资金持续创造价值。",
    })

    de = fund.get("debt_to_equity")
    checks.append({
        "name": "负债率低（D/E < 0.5）",
        "passed": de is not None and de < 50,
        "detail": f"当前 D/E: {de/100:.2f}" if de is not None else "数据不足",
        "tip": "低负债让公司在经济下行时也能存活，不依赖借钱运营，抗风险能力更强。",
    })

    pm = fund.get("profit_margin")
    checks.append({
        "name": "净利率健康（> 10%）",
        "passed": pm is not None and pm > 0.10,
        "detail": f"当前净利率: {pm*100:.1f}%" if pm is not None else "数据不足",
        "tip": "健康的净利率说明公司有定价权，不只是在赚吆喝，真正有利润留下来。",
    })

    gm = fund.get("gross_margin")
    checks.append({
        "name": "高毛利率，护城河宽（> 40%）",
        "passed": gm is not None and gm > 0.40,
        "detail": f"当前毛利率: {gm*100:.1f}%" if gm is not None else "数据不足",
        "tip": "高毛利通常意味着品牌、技术或规模优势，让竞争对手很难抢走客户。",
    })

    fcf = fund.get("free_cashflow")
    checks.append({
        "name": "自由现金流为正",
        "passed": fcf is not None and fcf > 0,
        "detail": f"当前自由现金流: {fmt_num(fcf)}" if fcf is not None else "数据不足",
        "tip": "利润数字可以被会计粉饰，但现金流很难造假。巴菲特最重视这个指标。",
    })

    pe = fund.get("pe_ratio")
    checks.append({
        "name": "估值合理（P/E < 25）",
        "passed": pe is not None and 0 < pe < 25,
        "detail": f"当前 P/E: {pe:.1f}x" if pe is not None else "数据不足",
        "tip": "即使是好公司，买贵了也很难赚钱。巴菲特说：「以合理价格买入优秀公司」。",
    })

    return checks


def build_ai_prompt(ticker, fund, checks):
    score = sum(1 for c in checks if c["passed"])

    def safe(key, fmt):
        v = fund.get(key)
        return fmt(v) if v is not None else "N/A"

    metrics = "\n".join([
        f"  - 市值: {fmt_num(fund.get('market_cap'))}",
        f"  - 市盈率 P/E: {safe('pe_ratio', lambda v: f'{v:.1f}x')}",
        f"  - 市净率 P/B: {safe('pb_ratio', lambda v: f'{v:.2f}x')}",
        f"  - ROE: {safe('roe', lambda v: f'{v*100:.1f}%')}",
        f"  - 负债率 D/E: {safe('debt_to_equity', lambda v: f'{v/100:.2f}')}",
        f"  - 净利率: {safe('profit_margin', lambda v: f'{v*100:.1f}%')}",
        f"  - 毛利率: {safe('gross_margin', lambda v: f'{v*100:.1f}%')}",
        f"  - 自由现金流: {fmt_num(fund.get('free_cashflow'))}",
        f"  - 巴菲特六项评分: {score}/6",
    ])

    desc = fund.get("description", "")
    desc_line = f"\n公司描述：{desc[:400]}..." if desc else ""

    return f"""你是一位专业的价值投资顾问，请用简单易懂的中文（面向完全没有金融背景的新手投资者）分析以下美股：

股票代码：{ticker}
公司名称：{fund.get('name', ticker)}
行业：{fund.get('sector', 'N/A')} / {fund.get('industry', 'N/A')}{desc_line}

基本面数据：
{metrics}

请按以下结构作答（每点2-3句话，遇到专业术语时请在括号内附上通俗解释）：

**1. 公司简介**
这是什么公司，主要做什么业务？普通人生活中会接触到它吗？

**2. 财务健康状况**
综合各项数据，这家公司财务上健不健康？有没有什么需要注意的地方？

**3. 护城河分析**
这家公司凭什么让竞争对手很难抢走它的客户？护城河宽不宽？

**4. 当前估值判断**
现在这个价格买入贵不贵？是捡到便宜了，还是需要等等再看？

**5. 适合人群**
这只股票适合什么类型的投资者？（例如：稳健保守型/追求成长型/不适合新手等）

**6. 一句话建议**
如果只能说一句话，你会对想买这只股票的新手说什么？

最后给出综合评级（只选一个）：
⭐⭐⭐⭐⭐ 极佳  /  ⭐⭐⭐⭐ 良好  /  ⭐⭐⭐ 一般  /  ⭐⭐ 较差  /  ⭐ 不推荐

---
⚠️ 免责声明：此分析仅供教育参考，不构成投资建议。投资有风险，入市需谨慎。"""


# ── Session state init ────────────────────────────────────────────
for key, default in [
    ("selected_ticker", "AAPL"),
    ("search_matches", []),
    ("data_loaded", False),
    ("price_data", None),
    ("fund", None),
    ("long_hist", None),
    ("fin_hist", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Search section ────────────────────────────────────────────────
st.subheader("🔍 搜索股票")
col_input, col_btn = st.columns([5, 1])
with col_input:
    query = st.text_input(
        "search",
        placeholder="输入股票代码或公司名称（如 Tesla、NVDA、苹果）",
        label_visibility="collapsed",
    )
with col_btn:
    search_clicked = st.button("搜索", use_container_width=True)

if search_clicked:
    if query.strip():
        with st.spinner("搜索中..."):
            st.session_state.search_matches = search_ticker(query.strip())
        if not st.session_state.search_matches:
            st.warning(f"未找到「{query}」的结果，请尝试其他名称或代码。")
    else:
        st.warning("请输入搜索关键词。")

if st.session_state.search_matches:
    options = {
        f"{m['ticker']} — {m['name']} ({m['exchange']})": m["ticker"]
        for m in st.session_state.search_matches
    }
    choice = st.selectbox("选择股票", list(options.keys()))
    st.session_state.selected_ticker = options[choice]

ticker = st.session_state.selected_ticker
st.markdown(f"**当前选中：** `{ticker}`")

# ── Analyze button ────────────────────────────────────────────────
if st.button("📊 开始分析", type="primary"):
    with st.spinner(f"正在获取 {ticker} 的数据，请稍候..."):
        st.session_state.price_data = get_stock_price(ticker)
        st.session_state.fund = get_fundamentals(ticker)
        st.session_state.long_hist = get_long_history(ticker)
        st.session_state.fin_hist = get_financials_history(ticker)
        st.session_state.data_loaded = True

# ── Main content ──────────────────────────────────────────────────
if st.session_state.data_loaded:
    fund = st.session_state.fund
    price_data = st.session_state.price_data
    long_hist = st.session_state.long_hist
    fin_hist = st.session_state.fin_hist
    checks = buffett_checks(fund)
    buffett_score = sum(1 for c in checks if c["passed"])

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📋 公司概览",
        "🚦 基本面健康",
        "📊 财务趋势",
        "✅ 巴菲特清单",
        "💰 历史回报模拟",
        "🤖 AI 分析",
    ])

    # ── Tab 1: 公司概览 ──────────────────────────────────────────
    with tab1:
        st.subheader(fund.get("name", ticker))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("当前股价", f"${price_data['price']}" if price_data["price"] else "N/A")
        c2.metric("市值", fmt_num(fund.get("market_cap")))
        c3.metric("行业", fund.get("sector", "N/A"))
        score_label = "⭐" * buffett_score if buffett_score > 0 else "—"
        c4.metric("巴菲特评分", f"{buffett_score}/6  {score_label}")

        desc = fund.get("description", "")
        if desc:
            with st.expander("公司简介", expanded=True):
                st.write(desc)

    # ── Tab 2: 基本面健康 ────────────────────────────────────────
    with tab2:
        st.subheader("🚦 基本面健康指标")
        st.caption("🟢 优秀  ·  🟡 一般  ·  🔴 需注意  ·  ⚪ 数据暂缺")
        st.divider()

        metric_keys = list(METRIC_INFO.keys())
        for i in range(0, len(metric_keys), 2):
            cols = st.columns(2)
            for j, key in enumerate(metric_keys[i : i + 2]):
                with cols[j]:
                    label, fmt_fn, explain = METRIC_INFO[key]
                    value = fund.get(key)
                    emoji, sig_label = traffic_light(key, value)
                    display_val = fmt_fn(value) if value is not None else "暂无数据"
                    st.markdown(f"**{emoji} {label}**")
                    st.markdown(f"## {display_val}")
                    st.caption(f"**{sig_label}** — {explain}")
                    st.write("")

    # ── Tab 3: 财务趋势 ──────────────────────────────────────────
    with tab3:
        st.subheader("📊 多年财务趋势")
        st.caption("只看股价涨跌不够——看公司多年能赚多少钱，才是价值投资的核心。")

        rev = fin_hist.get("revenue")
        ni = fin_hist.get("net_income")

        if rev is not None and not rev.empty:
            col_r, col_n = st.columns(2)

            with col_r:
                st.markdown("**年营收趋势**")
                dates = [str(d.year) if hasattr(d, "year") else str(d) for d in rev.index]
                fig = go.Figure(go.Bar(
                    x=dates,
                    y=rev.values / 1e9,
                    marker_color="#2196F3",
                    text=[f"${v/1e9:.1f}B" for v in rev.values],
                    textposition="auto",
                ))
                fig.update_layout(
                    title="年营收（十亿美元）",
                    yaxis_title="$B",
                    height=340,
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)

            if ni is not None and not ni.empty:
                with col_n:
                    st.markdown("**年净利润趋势**")
                    dates_ni = [str(d.year) if hasattr(d, "year") else str(d) for d in ni.index]
                    colors = ["#4CAF50" if v >= 0 else "#F44336" for v in ni.values]
                    fig2 = go.Figure(go.Bar(
                        x=dates_ni,
                        y=ni.values / 1e9,
                        marker_color=colors,
                        text=[f"${v/1e9:.1f}B" for v in ni.values],
                        textposition="auto",
                    ))
                    fig2.update_layout(
                        title="年净利润（十亿美元）",
                        yaxis_title="$B",
                        height=340,
                        showlegend=False,
                    )
                    st.plotly_chart(fig2, use_container_width=True)

            rg = fund.get("revenue_growth")
            if rg is not None:
                direction = "📈" if rg > 0 else "📉"
                st.info(f"{direction} 最近一年营收同比增长：**{rg*100:+.1f}%**")
        else:
            st.info("暂时无法获取该公司的历史财务数据。")

    # ── Tab 4: 巴菲特清单 ────────────────────────────────────────
    with tab4:
        st.subheader("✅ 巴菲特式投资检查清单")

        score_emoji = "🟢" if buffett_score >= 5 else ("🟡" if buffett_score >= 3 else "🔴")
        score_desc = {
            6: "极佳 — 高度符合价值投资标准",
            5: "良好 — 基本符合价值投资标准",
            4: "一般 — 有亮点也有明显缺陷",
            3: "偏弱 — 需要谨慎评估",
            2: "较差 — 大部分标准不达标",
            1: "不推荐 — 几乎不符合价值投资要求",
            0: "不推荐 — 完全不符合价值投资标准",
        }
        st.markdown(f"### {score_emoji} 综合得分：{buffett_score} / 6")
        st.caption(score_desc.get(buffett_score, ""))
        st.divider()

        for c in checks:
            icon = "✅" if c["passed"] else "❌"
            with st.expander(f"{icon} {c['name']}  —  {c['detail']}"):
                st.caption(f"💡 {c['tip']}")

    # ── Tab 5: 历史回报模拟 ──────────────────────────────────────
    with tab5:
        st.subheader("💰 如果当年买入……")
        st.caption("用真实历史数据感受长期持有的复利力量。")

        if long_hist is None or long_hist.empty:
            st.info("暂时无法获取该股票的长期历史数据。")
        else:
            years_available = max(1, int((long_hist.index[-1] - long_hist.index[0]).days / 365))
            max_years = min(10, years_available)

            col_ctrl, col_chart = st.columns([1, 2])
            with col_ctrl:
                amount = st.number_input(
                    "投资金额 (USD)",
                    min_value=100,
                    max_value=1_000_000,
                    value=1000,
                    step=500,
                )
                years = st.slider(
                    "N 年前买入",
                    min_value=1,
                    max_value=max_years,
                    value=min(5, max_years),
                )

            cutoff = long_hist.index[-1] - pd.DateOffset(years=years)
            past_data = long_hist[long_hist.index >= cutoff]

            if not past_data.empty:
                buy_price = past_data["Close"].iloc[0]
                current_price = long_hist["Close"].iloc[-1]
                shares = amount / buy_price
                current_value = shares * current_price
                total_return = (current_value - amount) / amount * 100
                annualized = ((current_value / amount) ** (1 / years) - 1) * 100

                with col_ctrl:
                    st.divider()
                    st.metric("当时买入价", f"${buy_price:.2f}")
                    st.metric(
                        "今日市值",
                        f"${current_value:,.0f}",
                        delta=f"{total_return:+.1f}%",
                    )
                    st.metric("年化回报率", f"{annualized:.1f}%")

                with col_chart:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=past_data.index,
                        y=past_data["Close"],
                        mode="lines",
                        name="股价",
                        fill="tozeroy",
                        line=dict(color="#2196F3"),
                    ))
                    fig.add_hline(
                        y=buy_price,
                        line_dash="dash",
                        line_color="green",
                        annotation_text=f"买入价 ${buy_price:.2f}",
                    )
                    fig.update_layout(
                        title=f"{ticker} 近 {years} 年股价走势",
                        xaxis_title="日期",
                        yaxis_title="价格 (USD)",
                        height=380,
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True)

    # ── Tab 6: AI 分析 ───────────────────────────────────────────
    with tab6:
        st.subheader("🤖 AI 价值投资分析报告")
        st.caption("由 Claude AI 生成，结合所有基本面数据，用新手友好的语言解读这只股票。")

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            st.warning("需要设置环境变量 `ANTHROPIC_API_KEY` 才能使用此功能。")
            st.code("export ANTHROPIC_API_KEY=your_api_key_here", language="bash")
            st.info("💡 还没有 API Key？前往 [console.anthropic.com](https://console.anthropic.com) 免费申请。")
        else:
            if st.button("✨ 生成 AI 分析报告", type="primary"):
                with st.spinner("Claude 正在分析中，请稍候（约10-20秒）..."):
                    try:
                        import anthropic
                        client = anthropic.Anthropic(api_key=api_key)
                        prompt = build_ai_prompt(ticker, fund, checks)
                        message = client.messages.create(
                            model="claude-opus-4-6",
                            max_tokens=1500,
                            messages=[{"role": "user", "content": prompt}],
                        )
                        st.markdown(message.content[0].text)
                    except Exception as e:
                        st.error(f"AI 分析生成失败：{e}")

st.divider()
st.caption("📈 Built with Claude + Python  ·  数据来源：Yahoo Finance  ·  仅供学习参考，不构成投资建议")

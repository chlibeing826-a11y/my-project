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
st.set_page_config(page_title="Long-Term Value Investing Analyzer", page_icon="📈", layout="wide")
st.title("📈 Long-Term Value Investing Analyzer")
st.caption("Designed for value investing beginners · Focus on fundamentals, not short-term price movements")


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
        return "⚪", "No data"

    # Lower is better
    low_better = {
        "pe_ratio": [
            (15, "🟢", "Cheap valuation"),
            (25, "🟡", "Fair valuation"),
            (float("inf"), "🔴", "Expensive"),
        ],
        "pb_ratio": [
            (1.5, "🟢", "Below book value"),
            (3.0, "🟡", "Fair valuation"),
            (float("inf"), "🔴", "Expensive"),
        ],
        "debt_to_equity": [
            (50, "🟢", "Healthy debt"),
            (150, "🟡", "Moderate debt"),
            (float("inf"), "🔴", "High debt"),
        ],
    }
    # Higher is better
    high_better = {
        "roe": [
            (0.15, "🟢", "Strong profitability"),
            (0.08, "🟡", "Average profitability"),
            (0.0, "🔴", "Weak profitability"),
        ],
        "profit_margin": [
            (0.15, "🟢", "Excellent margin"),
            (0.05, "🟡", "Average margin"),
            (0.0, "🔴", "Low margin"),
        ],
        "gross_margin": [
            (0.40, "🟢", "Wide moat"),
            (0.20, "🟡", "Narrow moat"),
            (0.0, "🔴", "No moat"),
        ],
    }

    if key == "free_cashflow":
        return ("🟢", "Healthy cash flow") if value > 0 else ("🔴", "Negative cash flow")

    if key in low_better:
        for thresh, emoji, label in low_better[key]:
            if value <= thresh:
                return emoji, label

    if key in high_better:
        for thresh, emoji, label in high_better[key]:
            if value >= thresh:
                return emoji, label
        return "🔴", "Negative value"

    return "⚪", "No data"


# (label, format_fn, plain-language explanation)
METRIC_INFO = {
    "pe_ratio":       ("P/E Ratio",          lambda v: f"{v:.1f}x",     "How much you pay for $1 of annual earnings. Lower means cheaper."),
    "pb_ratio":       ("P/B Ratio",          lambda v: f"{v:.2f}x",     "Price relative to net assets. Below 1 may indicate undervaluation."),
    "roe":            ("Return on Equity",   lambda v: f"{v*100:.1f}%", "How much profit the company generates from shareholders' money. Buffett wants > 15%."),
    "debt_to_equity": ("Debt/Equity Ratio",  lambda v: f"{v/100:.2f}",  "How much debt the company carries relative to equity. Lower is safer."),
    "profit_margin":  ("Net Profit Margin",  lambda v: f"{v*100:.1f}%", "How much net profit is kept from each dollar of revenue. Higher means stronger pricing power."),
    "gross_margin":   ("Gross Margin (Moat)", lambda v: f"{v*100:.1f}%", "Profit after direct costs. High gross margin often signals a competitive advantage."),
    "free_cashflow":  ("Free Cash Flow",     fmt_num,                   "Real cash generated after capital expenditures. Positive means the business truly makes money."),
}


def buffett_checks(fund):
    """Return a list of Buffett-style checklist items with pass/fail status."""
    checks = []

    roe = fund.get("roe")
    checks.append({
        "name": "Strong ROE (> 15%)",
        "passed": roe is not None and roe > 0.15,
        "detail": f"Current ROE: {roe*100:.1f}%" if roe is not None else "Insufficient data",
        "tip": "Buffett favors companies with ROE consistently above 15%, indicating management uses shareholder capital effectively.",
    })

    de = fund.get("debt_to_equity")
    checks.append({
        "name": "Low Debt (D/E < 0.5)",
        "passed": de is not None and de < 50,
        "detail": f"Current D/E: {de/100:.2f}" if de is not None else "Insufficient data",
        "tip": "Low debt allows a company to survive economic downturns without relying on borrowing to operate.",
    })

    pm = fund.get("profit_margin")
    checks.append({
        "name": "Healthy Net Margin (> 10%)",
        "passed": pm is not None and pm > 0.10,
        "detail": f"Current margin: {pm*100:.1f}%" if pm is not None else "Insufficient data",
        "tip": "A healthy net margin shows the company has real pricing power and retains meaningful profit.",
    })

    gm = fund.get("gross_margin")
    checks.append({
        "name": "Wide Moat — High Gross Margin (> 40%)",
        "passed": gm is not None and gm > 0.40,
        "detail": f"Current gross margin: {gm*100:.1f}%" if gm is not None else "Insufficient data",
        "tip": "High gross margin usually means brand, technology, or scale advantages that are hard for competitors to replicate.",
    })

    fcf = fund.get("free_cashflow")
    checks.append({
        "name": "Positive Free Cash Flow",
        "passed": fcf is not None and fcf > 0,
        "detail": f"Current FCF: {fmt_num(fcf)}" if fcf is not None else "Insufficient data",
        "tip": "Earnings can be manipulated by accounting, but cash flow is hard to fake. Buffett considers this the most important metric.",
    })

    pe = fund.get("pe_ratio")
    checks.append({
        "name": "Reasonable Valuation (P/E < 25)",
        "passed": pe is not None and 0 < pe < 25,
        "detail": f"Current P/E: {pe:.1f}x" if pe is not None else "Insufficient data",
        "tip": "Even great companies are hard to profit from if bought at too high a price. Buffett says: 'Buy a wonderful company at a fair price.'",
    })

    return checks


def build_ai_prompt(ticker, fund, checks):
    score = sum(1 for c in checks if c["passed"])

    def safe(key, fmt):
        v = fund.get(key)
        return fmt(v) if v is not None else "N/A"

    metrics = "\n".join([
        f"  - Market Cap: {fmt_num(fund.get('market_cap'))}",
        f"  - P/E Ratio: {safe('pe_ratio', lambda v: f'{v:.1f}x')}",
        f"  - P/B Ratio: {safe('pb_ratio', lambda v: f'{v:.2f}x')}",
        f"  - ROE: {safe('roe', lambda v: f'{v*100:.1f}%')}",
        f"  - Debt/Equity: {safe('debt_to_equity', lambda v: f'{v/100:.2f}')}",
        f"  - Net Margin: {safe('profit_margin', lambda v: f'{v*100:.1f}%')}",
        f"  - Gross Margin: {safe('gross_margin', lambda v: f'{v*100:.1f}%')}",
        f"  - Free Cash Flow: {fmt_num(fund.get('free_cashflow'))}",
        f"  - Buffett Score: {score}/6",
    ])

    desc = fund.get("description", "")
    desc_line = f"\nCompany Description: {desc[:400]}..." if desc else ""

    return f"""You are a professional value investing advisor. Please analyze the following US stock in simple, beginner-friendly English for someone with no financial background:

Ticker: {ticker}
Company: {fund.get('name', ticker)}
Sector: {fund.get('sector', 'N/A')} / {fund.get('industry', 'N/A')}{desc_line}

Fundamental Data:
{metrics}

Please structure your response as follows (2-3 sentences per point, explain any jargon in plain terms):

**1. Company Overview**
What does this company do? Would an average person encounter it in daily life?

**2. Financial Health**
Based on the data, is this company financially healthy? Any red flags to watch out for?

**3. Competitive Moat**
What makes this company hard to compete against? How wide is its moat?

**4. Current Valuation**
Is the current price expensive or cheap? Is now a good time to buy, or is it better to wait?

**5. Who Is This For?**
What type of investor suits this stock? (e.g., conservative/growth-oriented/not for beginners)

**6. One-Sentence Advice**
If you could say just one thing to a beginner considering this stock, what would it be?

Finally, give an overall rating (choose one):
⭐⭐⭐⭐⭐ Excellent  /  ⭐⭐⭐⭐ Good  /  ⭐⭐⭐ Average  /  ⭐⭐ Poor  /  ⭐ Not Recommended

---
⚠️ Disclaimer: This analysis is for educational purposes only and does not constitute investment advice. Investing involves risk."""


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
st.subheader("🔍 Search Stocks")
col_input, col_btn = st.columns([5, 1])
with col_input:
    query = st.text_input(
        "search",
        placeholder="Enter ticker or company name (e.g. Tesla, NVDA, Apple)",
        label_visibility="collapsed",
    )
with col_btn:
    search_clicked = st.button("Search", use_container_width=True)

if search_clicked:
    if query.strip():
        with st.spinner("Searching..."):
            st.session_state.search_matches = search_ticker(query.strip())
        if not st.session_state.search_matches:
            st.warning(f"No results found for \"{query}\". Try a different name or ticker.")
    else:
        st.warning("Please enter a search term.")

if st.session_state.search_matches:
    options = {
        f"{m['ticker']} — {m['name']} ({m['exchange']})": m["ticker"]
        for m in st.session_state.search_matches
    }
    choice = st.selectbox("Select a stock", list(options.keys()))
    st.session_state.selected_ticker = options[choice]

ticker = st.session_state.selected_ticker
st.markdown(f"**Selected:** `{ticker}`")

# ── Analyze button ────────────────────────────────────────────────
if st.button("📊 Analyze", type="primary"):
    with st.spinner(f"Fetching data for {ticker}, please wait..."):
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
        "📋 Overview",
        "🚦 Fundamentals",
        "📊 Financial Trends",
        "✅ Buffett Checklist",
        "💰 Return Simulator",
        "🤖 AI Analysis",
    ])

    # ── Tab 1: Overview ──────────────────────────────────────────
    with tab1:
        logo_url = fund.get("logo_url", "")
        if not logo_url:
            website = fund.get("website", "")
            if website:
                domain = website.replace("https://", "").replace("http://", "").split("/")[0]
                logo_url = f"https://logo.clearbit.com/{domain}"

        if logo_url:
            col_logo, col_name = st.columns([1, 8])
            with col_logo:
                st.image(logo_url, width=64)
            with col_name:
                st.subheader(fund.get("name", ticker))
        else:
            st.subheader(fund.get("name", ticker))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current Price", f"${price_data['price']}" if price_data["price"] else "N/A")
        c2.metric("Market Cap", fmt_num(fund.get("market_cap")))
        c3.metric("Sector", fund.get("sector", "N/A"))
        score_label = "⭐" * buffett_score if buffett_score > 0 else "—"
        c4.metric("Buffett Score", f"{buffett_score}/6  {score_label}")

        desc = fund.get("description", "")
        if desc:
            with st.expander("Company Description", expanded=True):
                sentences = [s.strip() for s in desc.replace("  ", " ").split(". ") if s.strip()]
                paragraphs = [". ".join(sentences[i:i+3]) for i in range(0, len(sentences), 3)]
                for para in paragraphs:
                    if not para.endswith("."):
                        para += "."
                    st.write(para)

    # ── Tab 2: Fundamentals ──────────────────────────────────────
    with tab2:
        st.subheader("🚦 Fundamental Health Indicators")
        st.caption("🟢 Excellent  ·  🟡 Average  ·  🔴 Caution  ·  ⚪ No data")
        st.divider()

        metric_keys = list(METRIC_INFO.keys())
        for i in range(0, len(metric_keys), 2):
            cols = st.columns(2)
            for j, key in enumerate(metric_keys[i : i + 2]):
                with cols[j]:
                    label, fmt_fn, explain = METRIC_INFO[key]
                    value = fund.get(key)
                    emoji, sig_label = traffic_light(key, value)
                    display_val = fmt_fn(value) if value is not None else "No data"
                    st.markdown(f"**{emoji} {label}**")
                    st.markdown(f"## {display_val}")
                    st.caption(f"**{sig_label}** — {explain}")
                    st.write("")

    # ── Tab 3: Financial Trends ──────────────────────────────────
    with tab3:
        st.subheader("📊 Multi-Year Financial Trends")
        st.caption("Stock price alone isn't enough — seeing how much a company earns over time is the core of value investing.")

        rev = fin_hist.get("revenue")
        ni = fin_hist.get("net_income")

        if rev is not None and not rev.empty:
            col_r, col_n = st.columns(2)

            with col_r:
                st.markdown("**Annual Revenue**")
                dates = [str(d.year) if hasattr(d, "year") else str(d) for d in rev.index]
                fig = go.Figure(go.Bar(
                    x=dates,
                    y=rev.values / 1e9,
                    marker_color="#2196F3",
                    text=[f"${v/1e9:.1f}B" for v in rev.values],
                    textposition="auto",
                ))
                fig.update_layout(
                    title="Annual Revenue (Billions USD)",
                    yaxis_title="$B",
                    height=340,
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)

            if ni is not None and not ni.empty:
                with col_n:
                    st.markdown("**Annual Net Income**")
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
                        title="Annual Net Income (Billions USD)",
                        yaxis_title="$B",
                        height=340,
                        showlegend=False,
                    )
                    st.plotly_chart(fig2, use_container_width=True)

            rg = fund.get("revenue_growth")
            if rg is not None:
                direction = "📈" if rg > 0 else "📉"
                st.info(f"{direction} Year-over-year revenue growth: **{rg*100:+.1f}%**")
        else:
            st.info("Historical financial data is not available for this company.")

    # ── Tab 4: Buffett Checklist ──────────────────────────────────
    with tab4:
        st.subheader("✅ Buffett-Style Investment Checklist")

        score_emoji = "🟢" if buffett_score >= 5 else ("🟡" if buffett_score >= 3 else "🔴")
        score_desc = {
            6: "Excellent — Highly meets value investing standards",
            5: "Good — Mostly meets value investing standards",
            4: "Average — Some strengths but notable weaknesses",
            3: "Below Average — Needs careful evaluation",
            2: "Poor — Fails most criteria",
            1: "Not Recommended — Barely meets value investing requirements",
            0: "Not Recommended — Does not meet value investing standards",
        }
        st.markdown(f"### {score_emoji} Overall Score: {buffett_score} / 6")
        st.caption(score_desc.get(buffett_score, ""))
        st.divider()

        for c in checks:
            icon = "✅" if c["passed"] else "❌"
            with st.expander(f"{icon} {c['name']}  —  {c['detail']}"):
                st.caption(f"💡 {c['tip']}")

    # ── Tab 5: Return Simulator ───────────────────────────────────
    with tab5:
        st.subheader("💰 What If You Had Bought...")
        st.caption("Use real historical data to feel the power of compounding over the long term.")

        if long_hist is None or long_hist.empty:
            st.info("Long-term historical data is not available for this stock.")
        else:
            years_available = max(1, int((long_hist.index[-1] - long_hist.index[0]).days / 365))
            max_years = min(10, years_available)

            col_ctrl, col_chart = st.columns([1, 2])
            with col_ctrl:
                amount = st.number_input(
                    "Investment Amount (USD)",
                    min_value=100,
                    max_value=1_000_000,
                    value=1000,
                    step=500,
                )
                years = st.slider(
                    "Years Ago",
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
                    st.metric("Purchase Price", f"${buy_price:.2f}")
                    st.metric(
                        "Current Value",
                        f"${current_value:,.0f}",
                        delta=f"{total_return:+.1f}%",
                    )
                    st.metric("Annualized Return", f"{annualized:.1f}%")

                with col_chart:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=past_data.index,
                        y=past_data["Close"],
                        mode="lines",
                        name="Price",
                        fill="tozeroy",
                        line=dict(color="#2196F3"),
                    ))
                    fig.add_hline(
                        y=buy_price,
                        line_dash="dash",
                        line_color="green",
                        annotation_text=f"Buy price ${buy_price:.2f}",
                    )
                    fig.update_layout(
                        title=f"{ticker} Price — Last {years} Year(s)",
                        xaxis_title="Date",
                        yaxis_title="Price (USD)",
                        height=380,
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True)

    # ── Tab 6: AI Analysis ────────────────────────────────────────
    with tab6:
        st.subheader("🤖 AI Value Investing Report")
        st.caption("Generated by Claude AI — combines all fundamental data into a beginner-friendly stock analysis.")

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            st.warning("Set the `ANTHROPIC_API_KEY` environment variable to use this feature.")
            st.code("export ANTHROPIC_API_KEY=your_api_key_here", language="bash")
            st.info("💡 Don't have an API key? Get one free at [console.anthropic.com](https://console.anthropic.com).")
        else:
            if st.button("✨ Generate AI Report", type="primary"):
                with st.spinner("Claude is analyzing... please wait (~10-20 seconds)..."):
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
                        st.error(f"Failed to generate AI report: {e}")

st.divider()
st.caption("📈 Built with Claude + Python  ·  Data from Yahoo Finance  ·  For educational purposes only, not investment advice")

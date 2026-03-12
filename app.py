import os
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from stock import (
    get_fundamentals,
    get_financials_history,
    get_long_history,
    get_spy_history,
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


# (label, format_fn, tooltip explanation)
METRIC_INFO = {
    "pe_ratio":       ("P/E Ratio",           lambda v: f"{v:.1f}x",     "Price-to-Earnings ratio. How much you pay for $1 of annual profit. Think of it like buying a lemonade stand: if it earns $1/year and you pay $15, P/E = 15. Lower means cheaper. Buffett looks for P/E under 15-25."),
    "pb_ratio":       ("P/B Ratio",           lambda v: f"{v:.2f}x",     "Price-to-Book ratio. Compares stock price to the company's net assets. If a company owns $100 in assets and has $50 in debts, book value = $50. A P/B below 1 means you're buying $1 of assets for less than $1."),
    "roe":            ("Return on Equity",    lambda v: f"{v*100:.1f}%", "How much profit the company earns for every $1 of shareholders' money. Like a savings account rate — 20% ROE means the company turns $100 of equity into $120. Buffett wants this above 15% consistently."),
    "debt_to_equity": ("Debt/Equity Ratio",   lambda v: f"{v/100:.2f}",  "How much the company borrows vs. what it owns. A D/E of 0.5 means for every $1 owned, it owes $0.50. High debt is risky — like a household with a huge mortgage. Buffett prefers D/E below 0.5."),
    "profit_margin":  ("Net Profit Margin",   lambda v: f"{v*100:.1f}%", "Of every $1 in revenue, how much becomes profit after all expenses. A 20% margin means earning $0.20 net on each $1 sale. Higher margin = stronger pricing power = harder for competitors to undercut."),
    "gross_margin":   ("Gross Margin (Moat)", lambda v: f"{v*100:.1f}%", "Profit after only direct production costs (before overhead). A 60% gross margin means $0.60 of every $1 sale is kept before paying staff, rent, etc. High gross margin often signals a wide competitive moat — like a brand or patent others can't easily copy."),
    "free_cashflow":  ("Free Cash Flow",      fmt_num,                   "Real cash left over after running the business and investing in equipment. This is the money a company could pay to shareholders or reinvest. Buffett calls this 'owner earnings' — profits can be faked, but cash is hard to fake."),
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
        "watch": "Check ROE in each quarterly earnings report. A consistent ROE above 15% over 5+ years is more meaningful than a single good year. Watch for declining trends — they often signal rising competition or shrinking pricing power.",
    })

    de = fund.get("debt_to_equity")
    checks.append({
        "name": "Low Debt (D/E < 0.5)",
        "passed": de is not None and de < 50,
        "detail": f"Current D/E: {de/100:.2f}" if de is not None else "Insufficient data",
        "tip": "Low debt allows a company to survive economic downturns without relying on borrowing to operate.",
        "watch": "Monitor the balance sheet each quarter. Watch for total debt growing faster than equity. In earnings calls, listen for mentions of debt reduction plans or new credit facilities — these signal management's debt strategy.",
    })

    pm = fund.get("profit_margin")
    checks.append({
        "name": "Healthy Net Margin (> 10%)",
        "passed": pm is not None and pm > 0.10,
        "detail": f"Current margin: {pm*100:.1f}%" if pm is not None else "Insufficient data",
        "tip": "A healthy net margin shows the company has real pricing power and retains meaningful profit.",
        "watch": "Track margin trends over multiple years in the Financial Trends tab. Compressing margins (e.g. 15% → 10% → 7%) often warn of rising costs or pricing pressure before the stock reacts.",
    })

    gm = fund.get("gross_margin")
    checks.append({
        "name": "Wide Moat — High Gross Margin (> 40%)",
        "passed": gm is not None and gm > 0.40,
        "detail": f"Current gross margin: {gm*100:.1f}%" if gm is not None else "Insufficient data",
        "tip": "High gross margin usually means brand, technology, or scale advantages that are hard for competitors to replicate.",
        "watch": "Gross margin is one of the most stable moat indicators. A sudden drop (e.g. 50% → 42%) could mean a new competitor is forcing price cuts or input costs have risen. Compare to industry peers.",
    })

    fcf = fund.get("free_cashflow")
    checks.append({
        "name": "Positive Free Cash Flow",
        "passed": fcf is not None and fcf > 0,
        "detail": f"Current FCF: {fmt_num(fcf)}" if fcf is not None else "Insufficient data",
        "tip": "Earnings can be manipulated by accounting, but cash flow is hard to fake. Buffett considers this the most important metric.",
        "watch": "Compare FCF to net income each year. If net income is growing but FCF is shrinking, that's a red flag — it may mean earnings are being inflated by accounting rather than real cash generation.",
    })

    pe = fund.get("pe_ratio")
    checks.append({
        "name": "Reasonable Valuation (P/E < 25)",
        "passed": pe is not None and 0 < pe < 25,
        "detail": f"Current P/E: {pe:.1f}x" if pe is not None else "Insufficient data",
        "tip": "Even great companies are hard to profit from if bought at too high a price. Buffett says: 'Buy a wonderful company at a fair price.'",
        "watch": "Track the P/E alongside earnings growth. A high P/E is only justified if earnings grow fast enough to 'grow into' the valuation. If P/E stays high but earnings growth slows, the stock is increasingly risky.",
    })

    return checks


def generate_lessons(ticker, fund, checks):
    """Generate 2-3 educational lessons based on the stock's actual metrics."""
    lessons = []

    pe = fund.get("pe_ratio")
    if pe and pe > 30:
        lessons.append(f"**Lesson: Growth premium.** {ticker}'s P/E of {pe:.1f}x shows investors are paying a large premium expecting strong future growth. This teaches us that high-P/E stocks carry more risk — if growth disappoints, the stock can fall sharply even if the company is profitable.")
    elif pe and pe < 15:
        lessons.append(f"**Lesson: Margin of safety.** {ticker}'s low P/E of {pe:.1f}x illustrates a core value investing principle — buying below fair value creates a 'margin of safety.' You're paying less than $15 for every $1 of annual profit, which limits your downside risk.")

    gm = fund.get("gross_margin")
    roe = fund.get("roe")
    if gm and gm > 0.50:
        lessons.append(f"**Lesson: The power of a moat.** With a {gm*100:.0f}% gross margin, {ticker} demonstrates what Warren Buffett calls an 'economic moat' — a durable competitive advantage. Companies with wide moats can maintain high prices without losing customers, compounding returns over decades.")
    elif gm and gm < 0.20:
        lessons.append(f"**Lesson: Commodity businesses are hard.** {ticker}'s low {gm*100:.0f}% gross margin shows it operates in a competitive industry where price is everything. These businesses often struggle to raise prices and are vulnerable to cost increases — a key reason Buffett avoids them.")

    if roe and roe > 0.20:
        lessons.append(f"**Lesson: Compounding machine.** {ticker}'s {roe*100:.0f}% ROE means for every $100 of shareholder equity, it generates ${roe*100:.0f} in profit annually. Reinvested at this rate, money doubles roughly every {72//(roe*100)} years — this is why Buffett calls high-ROE companies 'compounding machines.'")

    fcf = fund.get("free_cashflow")
    de = fund.get("debt_to_equity")
    if fcf and fcf > 0 and de and de > 150:
        lessons.append(f"**Lesson: Cash flow vs. debt risk.** {ticker} generates positive free cash flow ({fmt_num(fcf)}) but carries significant debt (D/E: {de/100:.2f}). This teaches us to look at both sides — strong cash generation can service debt, but high leverage amplifies risk in downturns.")

    return lessons[:3]


def generate_quiz_questions(ticker, fund, checks):
    """Generate 4 multiple-choice questions from the stock's actual data."""
    questions = []

    # Q1: P/E ratio
    pe = fund.get("pe_ratio")
    if pe:
        if pe < 15:
            correct = "The stock is cheaply valued — you pay less than $15 per $1 of annual profit"
            options = [
                correct,
                "The stock has grown 15% this year",
                "The company has $15 billion in assets",
                "The stock pays a 15% dividend",
            ]
            explanation = f"P/E ratio means Price-to-Earnings. A P/E of {pe:.1f}x means you pay ${pe:.1f} for every $1 of annual earnings. Below 15 is generally considered cheap by value investors."
        elif pe > 30:
            correct = "Investors expect strong future growth to justify the high price"
            options = [
                correct,
                "The company earned $30 profit last year",
                "The stock dropped 30% recently",
                "The company has 30 years of history",
            ]
            explanation = f"A P/E of {pe:.1f}x means you're paying ${pe:.1f} per $1 of earnings — a high premium. This only makes sense if earnings grow fast enough to 'grow into' the valuation."
        else:
            correct = "How much you pay per $1 of annual company profit"
            options = [
                correct,
                "The company's annual profit in billions",
                "The percentage the stock gained this year",
                "The number of years the company has been public",
            ]
            explanation = f"P/E = Price ÷ Earnings per share. {ticker}'s P/E of {pe:.1f}x means you pay ${pe:.1f} for each $1 of annual profit the company generates."
        questions.append({
            "question": f"{ticker}'s P/E ratio is {pe:.1f}x. What does this best indicate?",
            "options": options,
            "answer_index": 0,
            "explanation": explanation,
        })

    # Q2: ROE pass/fail
    passed_checks = [c["name"] for c in checks if c["passed"]]
    failed_checks = [c["name"] for c in checks if not c["passed"]]
    if passed_checks and failed_checks:
        correct = passed_checks[0]
        wrong_options = failed_checks[:3]
        while len(wrong_options) < 3:
            wrong_options.append("Dividend yield above 5%")
        questions.append({
            "question": f"Which of these Buffett criteria does {ticker} currently PASS?",
            "options": [correct] + wrong_options[:3],
            "answer_index": 0,
            "explanation": f"{ticker} passes '{correct}'. Buffett's checklist helps identify companies with durable financial strength — passing more criteria generally means lower risk.",
        })

    # Q3: Free cash flow
    fcf = fund.get("free_cashflow")
    if fcf is not None:
        if fcf > 0:
            correct = "The company generates real cash after all expenses — a positive sign"
            options = [
                correct,
                "The company borrowed money this year",
                "The stock price increased this quarter",
                "The company paid out dividends",
            ]
            explanation = "Positive free cash flow means the company actually generates more cash than it spends running the business. Buffett prioritizes this because cash is harder to manipulate than accounting profits."
        else:
            correct = "The company is spending more cash than it generates — needs monitoring"
            options = [
                correct,
                "The company is very profitable this year",
                "The stock is a great buy right now",
                "The company has no debt",
            ]
            explanation = "Negative free cash flow means cash outflows exceed inflows. This isn't always bad (e.g. heavy investment phase), but sustained negative FCF means the company depends on external financing to survive."
        questions.append({
            "question": f"{ticker}'s Free Cash Flow is {fmt_num(fcf)}. What does this tell you?",
            "options": options,
            "answer_index": 0,
            "explanation": explanation,
        })

    # Q4: Gross margin / moat
    gm = fund.get("gross_margin")
    if gm:
        if gm > 0.40:
            correct = "A wide competitive moat — competitors find it hard to undercut on price"
            options = [
                correct,
                "The company sells very expensive products",
                "The company has high employee costs",
                "The stock has outperformed the market",
            ]
            explanation = f"A {gm*100:.0f}% gross margin means {ticker} keeps ${gm:.2f} of every $1 in revenue after direct costs. High gross margins typically signal strong brand, patents, or switching costs — all forms of competitive moat."
        else:
            correct = "A competitive industry where pricing power is limited"
            options = [
                correct,
                "The company is highly profitable",
                "The stock is undervalued",
                "The company has a strong brand advantage",
            ]
            explanation = f"A {gm*100:.0f}% gross margin means thin pricing power. In low-margin industries, small cost increases can eliminate all profit — making these businesses more vulnerable."
        questions.append({
            "question": f"{ticker} has a gross margin of {gm*100:.0f}%. What does this suggest about its competitive position?",
            "options": options,
            "answer_index": 0,
            "explanation": explanation,
        })

    return questions[:4]


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


# ── Glossary data ─────────────────────────────────────────────────
GLOSSARY = [
    {"term": "P/E Ratio (Price-to-Earnings)", "definition": "How much investors pay for $1 of a company's annual profit. A P/E of 20 means paying $20 per $1 of earnings.", "analogy": "Like buying a lemonade stand that earns $1/year. If you pay $20 for it, your P/E is 20. Lower is generally cheaper."},
    {"term": "P/B Ratio (Price-to-Book)", "definition": "Compares the stock price to the company's net assets (assets minus liabilities). Below 1 means you're buying assets for less than their stated value.", "analogy": "If a store owns $100K of inventory and equipment but owes $40K, book value = $60K. If you can buy the whole store for $50K, P/B < 1 — a potential bargain."},
    {"term": "ROE (Return on Equity)", "definition": "How much profit a company earns relative to shareholders' investment. 20% ROE means for every $100 invested by shareholders, the company earns $20.", "analogy": "Like a savings account. A 20% ROE is like earning 20% interest on your deposit — much better than a bank's 2%."},
    {"term": "Debt-to-Equity Ratio (D/E)", "definition": "Compares how much a company borrows vs. how much it owns. A D/E of 0.5 means for every $1 of equity, the company has borrowed $0.50.", "analogy": "Like buying a house. If the house is worth $400K and you borrowed $200K, your D/E is 0.5. High D/E = heavy mortgage = more financial risk."},
    {"term": "Free Cash Flow (FCF)", "definition": "The actual cash left over after a company pays its operating costs and capital expenditures. This is real money — harder to manipulate than accounting profits.", "analogy": "Your monthly salary minus rent, food, and loan payments. What's left is your free cash flow — the money you can actually spend or save."},
    {"term": "Gross Margin", "definition": "Profit remaining after subtracting the direct cost of making/delivering a product, before other expenses like salaries or rent.", "analogy": "If a coffee shop sells a latte for $5 and the ingredients cost $1, gross margin = 80%. High gross margin means lots of room to cover other costs and still profit."},
    {"term": "Net Profit Margin", "definition": "The percentage of revenue that becomes final profit after ALL expenses (including taxes, salaries, rent, interest).", "analogy": "If the coffee shop made $500K in sales but after paying everything kept $50K, net margin = 10%. This is the 'real' profitability number."},
    {"term": "Market Cap (Market Capitalization)", "definition": "The total market value of all a company's shares. Stock price × total shares outstanding.", "analogy": "If a pizza place has 100 ownership slices and each is worth $10, the market cap is $1,000 — that's what it would cost to buy the whole business at today's price."},
    {"term": "Economic Moat", "definition": "A durable competitive advantage that protects a company from competitors — like a castle moat. Wide moats sustain profits for decades.", "analogy": "Coca-Cola's brand is a moat — even if a competitor makes an identical drink cheaper, most people still buy Coke. The brand is the moat."},
    {"term": "Compounding", "definition": "Earning returns on your returns over time. The longer you hold, the more powerful it becomes — small annual gains become huge over decades.", "analogy": "A snowball rolling downhill: starts small but gets bigger and faster. $10,000 at 10%/year becomes $67,000 in 20 years — without adding a dollar."},
    {"term": "Value Investing", "definition": "A strategy of buying stocks trading below their intrinsic (true) value, creating a 'margin of safety.' Pioneered by Benjamin Graham and practiced by Warren Buffett.", "analogy": "Shopping during a sale. If a $100 jacket is marked down to $60, you have a $40 margin of safety. Value investing applies this to stocks."},
    {"term": "Margin of Safety", "definition": "Buying an asset at a significant discount to its estimated true value, so even if your estimate is wrong, you're protected from a large loss.", "analogy": "If you think a house is worth $300K but only pay $200K, you have a $100K margin of safety. Even if the house is only worth $250K, you still made money."},
    {"term": "Dividend", "definition": "A portion of a company's profit paid directly to shareholders, usually quarterly. Not all companies pay dividends — growth companies often reinvest profits instead.", "analogy": "Like rent from a property you own. Even if the house value stays flat, you still get paid regularly just for owning it."},
    {"term": "Dollar-Cost Averaging (DCA)", "definition": "Investing a fixed dollar amount at regular intervals (e.g. $200/month) regardless of the stock price. Reduces the risk of investing a lump sum at the wrong time.", "analogy": "Buying groceries weekly instead of monthly. Sometimes prices are high, sometimes low — but your average cost evens out over time."},
    {"term": "Bull Market / Bear Market", "definition": "A bull market is a period of rising prices (generally 20%+ gains). A bear market is a period of falling prices (generally 20%+ decline). Both are normal parts of market cycles.", "analogy": "Like seasons — bull markets are summer (growth, optimism), bear markets are winter (decline, fear). Long-term investors know both always pass."},
]


# ── Session state init ────────────────────────────────────────────
for key, default in [
    ("selected_ticker", "AAPL"),
    ("search_matches", []),
    ("data_loaded", False),
    ("price_data", None),
    ("fund", None),
    ("long_hist", None),
    ("fin_hist", None),
    ("spy_hist", None),
    ("watchlist", []),
    ("journal", {}),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Sidebar: Watchlist ────────────────────────────────────────────
with st.sidebar:
    st.header("⭐ My Watchlist")
    if st.session_state.watchlist:
        for t in list(st.session_state.watchlist):
            col_t, col_rm = st.columns([3, 1])
            with col_t:
                if st.button(t, key=f"wl_select_{t}", use_container_width=True):
                    st.session_state.selected_ticker = t
                    st.session_state.data_loaded = False
                    st.rerun()
            with col_rm:
                if st.button("✕", key=f"wl_rm_{t}"):
                    st.session_state.watchlist = [x for x in st.session_state.watchlist if x != t]
                    st.rerun()
    else:
        st.caption("No stocks added yet. Analyze a stock and click ⭐ Add to Watchlist.")
    st.divider()
    st.caption("📖 Tip: Use the Glossary tab to look up any investing term.")


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
        st.session_state.spy_hist = get_spy_history()
        st.session_state.data_loaded = True

# ── Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab_quiz, tab_journal, tab_glossary = st.tabs([
    "📋 Overview",
    "🚦 Fundamentals",
    "📊 Financial Trends",
    "✅ Buffett Checklist",
    "💰 Return Simulator",
    "🤖 AI Analysis",
    "🧠 Quiz",
    "📝 Journal",
    "📖 Glossary",
])

# ── Glossary tab (always visible) ────────────────────────────────
with tab_glossary:
    st.subheader("📖 Investing Glossary")
    st.caption("Plain-English definitions with real-world analogies — no finance degree required.")
    filter_term = st.text_input("Search terms", placeholder="e.g. P/E, moat, dividend...")
    for entry in GLOSSARY:
        if not filter_term or filter_term.lower() in entry["term"].lower() or filter_term.lower() in entry["definition"].lower():
            with st.expander(f"**{entry['term']}**"):
                st.write(entry["definition"])
                st.info(f"💡 **Analogy:** {entry['analogy']}")

# ── Main content (requires data) ─────────────────────────────────
if st.session_state.data_loaded:
    fund = st.session_state.fund
    price_data = st.session_state.price_data
    long_hist = st.session_state.long_hist
    fin_hist = st.session_state.fin_hist
    spy_hist = st.session_state.spy_hist
    checks = buffett_checks(fund)
    buffett_score = sum(1 for c in checks if c["passed"])

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
        c1.metric("Current Price", f"${price_data['price']}" if price_data["price"] else "N/A",
                  help="The latest closing price of the stock in USD.")
        c2.metric("Market Cap", fmt_num(fund.get("market_cap")),
                  help="Total market value of all shares (price × shares outstanding). A rough measure of company size.")
        c3.metric("Sector", fund.get("sector", "N/A"),
                  help="The broad industry category this company belongs to (e.g. Technology, Healthcare, Consumer Staples).")
        score_label = "⭐" * buffett_score if buffett_score > 0 else "—"
        c4.metric("Buffett Score", f"{buffett_score}/6  {score_label}",
                  help="How many of Buffett's 6 key criteria this stock passes: ROE > 15%, D/E < 0.5, Net Margin > 10%, Gross Margin > 40%, Positive FCF, P/E < 25.")

        # Watchlist button
        st.write("")
        if ticker not in st.session_state.watchlist:
            if st.button("⭐ Add to Watchlist"):
                st.session_state.watchlist.append(ticker)
                st.success(f"{ticker} added to your watchlist!")
                st.rerun()
        else:
            if st.button("★ Remove from Watchlist"):
                st.session_state.watchlist = [x for x in st.session_state.watchlist if x != ticker]
                st.rerun()

        desc = fund.get("description", "")
        if desc:
            with st.expander("Company Description", expanded=True):
                sentences = [s.strip() for s in desc.replace("  ", " ").split(". ") if s.strip()]
                paragraphs = [". ".join(sentences[i:i+3]) for i in range(0, len(sentences), 3)]
                for para in paragraphs:
                    if not para.endswith("."):
                        para += "."
                    st.write(para)

        # Learn from this stock
        lessons = generate_lessons(ticker, fund, checks)
        if lessons:
            st.divider()
            st.subheader("🎓 Learn From This Stock")
            st.caption("Key investing lessons illustrated by this company's actual data.")
            for lesson in lessons:
                st.info(lesson)

    # ── Tab 2: Fundamentals ──────────────────────────────────────
    with tab2:
        st.subheader("🚦 Fundamental Health Indicators")
        st.caption("🟢 Excellent  ·  🟡 Average  ·  🔴 Caution  ·  ⚪ No data  —  Hover the metric name for a detailed explanation.")
        st.divider()

        metric_keys = list(METRIC_INFO.keys())
        for i in range(0, len(metric_keys), 2):
            cols = st.columns(2)
            for j, key in enumerate(metric_keys[i : i + 2]):
                with cols[j]:
                    label, fmt_fn, tooltip = METRIC_INFO[key]
                    value = fund.get(key)
                    emoji, sig_label = traffic_light(key, value)
                    display_val = fmt_fn(value) if value is not None else "No data"
                    st.metric(
                        label=f"{emoji} {label}",
                        value=display_val,
                        delta=sig_label,
                        help=tooltip,
                    )

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
                if not c["passed"] and c.get("watch"):
                    st.warning(f"**📡 What to Watch:** {c['watch']}")

    # ── Tab 5: Return Simulator ───────────────────────────────────
    with tab5:
        st.subheader("💰 What If You Had Bought...")
        st.caption("Use real historical data to feel the power of compounding over the long term.")

        if long_hist is None or long_hist.empty:
            st.info("Long-term historical data is not available for this stock.")
        else:
            years_available = max(1, round((long_hist.index[-1] - long_hist.index[0]).days / 365))
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

                # S&P 500 comparison
                spy_return_pct = None
                spy_final = None
                if spy_hist is not None and not spy_hist.empty:
                    spy_past = spy_hist[spy_hist.index >= cutoff]
                    if not spy_past.empty:
                        spy_start_price = spy_past["Close"].iloc[0]
                        spy_current_price = spy_hist["Close"].iloc[-1]
                        spy_final = (spy_current_price / spy_start_price) * amount
                        spy_return_pct = (spy_final - amount) / amount * 100

                with col_ctrl:
                    st.divider()
                    st.metric("Purchase Price", f"${buy_price:.2f}")
                    st.metric(
                        f"{ticker} Current Value",
                        f"${current_value:,.0f}",
                        delta=f"{total_return:+.1f}%",
                    )
                    st.metric("Annualized Return", f"{annualized:.1f}%")
                    if spy_final is not None:
                        st.divider()
                        diff = total_return - spy_return_pct
                        st.metric(
                            "S&P 500 (same period)",
                            f"${spy_final:,.0f}",
                            delta=f"{spy_return_pct:+.1f}%",
                            help="What the same investment in SPY (S&P 500 ETF) would be worth today.",
                        )
                        if diff > 0:
                            st.success(f"✅ {ticker} beat the S&P 500 by {diff:.1f}% over this period.")
                        else:
                            st.warning(f"⚠️ {ticker} underperformed the S&P 500 by {abs(diff):.1f}% over this period.")

                with col_chart:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=past_data.index,
                        y=(past_data["Close"] / buy_price) * amount,
                        mode="lines",
                        name=ticker,
                        fill="tozeroy",
                        line=dict(color="#2196F3"),
                    ))
                    if spy_hist is not None and not spy_hist.empty:
                        spy_past = spy_hist[spy_hist.index >= cutoff]
                        if not spy_past.empty:
                            spy_start_price = spy_past["Close"].iloc[0]
                            fig.add_trace(go.Scatter(
                                x=spy_past.index,
                                y=(spy_past["Close"] / spy_start_price) * amount,
                                mode="lines",
                                name="S&P 500 (SPY)",
                                line=dict(color="#FF9800", dash="dot"),
                            ))
                    fig.add_hline(
                        y=amount,
                        line_dash="dash",
                        line_color="gray",
                        annotation_text=f"Initial ${amount:,.0f}",
                    )
                    fig.update_layout(
                        title=f"{ticker} vs S&P 500 — Last {years} Year(s)",
                        xaxis_title="Date",
                        yaxis_title="Portfolio Value (USD)",
                        height=380,
                        showlegend=True,
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

    # ── Tab 7: Quiz ───────────────────────────────────────────────
    with tab_quiz:
        st.subheader("🧠 Quiz: Test Your Understanding")
        st.caption(f"Questions generated from {ticker}'s actual data — no guessing, real numbers.")

        questions = generate_quiz_questions(ticker, fund, checks)
        if not questions:
            st.info("Not enough data to generate quiz questions for this stock.")
        else:
            score_count = 0
            answered_count = 0
            for i, q in enumerate(questions):
                st.markdown(f"**Q{i+1}. {q['question']}**")
                answer = st.radio("Choose your answer:", q["options"], key=f"quiz_{ticker}_q{i}", index=None)
                if answer is not None:
                    answered_count += 1
                    chosen_idx = q["options"].index(answer)
                    if chosen_idx == q["answer_index"]:
                        st.success("✅ Correct!")
                        score_count += 1
                    else:
                        st.error(f"❌ Not quite. {q['explanation']}")
                st.write("")

            if answered_count == len(questions):
                st.divider()
                pct = int(score_count / len(questions) * 100)
                if pct == 100:
                    st.balloons()
                    st.success(f"🎉 Perfect score! {score_count}/{len(questions)} — You really understand {ticker}!")
                elif pct >= 50:
                    st.info(f"📚 Good effort! {score_count}/{len(questions)} correct. Review the explanations above to strengthen your understanding.")
                else:
                    st.warning(f"📖 {score_count}/{len(questions)} correct. Don't worry — check the Glossary tab and re-read the Fundamentals tab for this stock.")

    # ── Tab 8: Journal ────────────────────────────────────────────
    with tab_journal:
        st.subheader("📝 Investment Journal")
        st.caption("Write notes on stocks you've researched. Great investors keep records of their thinking.")

        st.markdown(f"**Notes for {ticker}:**")
        existing_note = st.session_state.journal.get(ticker, {}).get("notes", "")
        notes_input = st.text_area(
            "Your notes",
            value=existing_note,
            height=200,
            placeholder="What did you learn about this company? What concerns you? What would make you buy or avoid it? At what price would you consider buying?",
            label_visibility="collapsed",
        )
        col_save, col_del = st.columns([1, 1])
        with col_save:
            if st.button("💾 Save Notes", type="primary"):
                st.session_state.journal[ticker] = {
                    "notes": notes_input,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                st.success("Notes saved!")
        with col_del:
            if ticker in st.session_state.journal:
                if st.button("🗑 Delete Notes"):
                    del st.session_state.journal[ticker]
                    st.rerun()

        if st.session_state.journal:
            st.divider()
            st.markdown("**All Journal Entries:**")
            for t, entry in st.session_state.journal.items():
                with st.expander(f"**{t}** — {entry['timestamp']}"):
                    st.write(entry["notes"])

else:
    with tab_quiz:
        st.info("Analyze a stock first to generate quiz questions.")
    with tab_journal:
        st.subheader("📝 Investment Journal")
        st.caption("Analyze a stock first to add journal notes.")
        if st.session_state.journal:
            st.markdown("**Saved Entries:**")
            for t, entry in st.session_state.journal.items():
                with st.expander(f"**{t}** — {entry['timestamp']}"):
                    st.write(entry["notes"])

st.divider()
st.caption("📈 Built with Claude + Python  ·  Data from Yahoo Finance  ·  For educational purposes only, not investment advice")

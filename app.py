import numpy as np
import plotly.graph_objects as go
import streamlit as st

from stock import get_historical_prices, get_stock_price, search_ticker


def advanced_analysis(hist):
    close = hist["Close"]

    change_5d = (close.iloc[-1] - close.iloc[-6]) / close.iloc[-6] * 100

    ma20 = close.rolling(20).mean().iloc[-1]
    vs_ma = (close.iloc[-1] - ma20) / ma20 * 100
    ma_position = "above" if close.iloc[-1] > ma20 else "below"

    volatility = close.pct_change().std() * np.sqrt(252) * 100

    # Momentum assessment
    if change_5d > 5:
        momentum = "surging with strong short-term momentum"
    elif change_5d > 2:
        momentum = "showing positive short-term momentum"
    elif change_5d >= 0:
        momentum = "slightly positive over the past 5 days"
    elif change_5d > -2:
        momentum = "slightly negative over the past 5 days"
    elif change_5d > -5:
        momentum = "declining with moderate short-term weakness"
    else:
        momentum = "under significant selling pressure"

    # Trend vs MA
    if vs_ma > 10:
        trend = "trading well above its 20-day average — potentially overbought"
    elif vs_ma > 3:
        trend = "trading above its 20-day average, indicating bullish momentum"
    elif vs_ma >= 0:
        trend = "trading just above its 20-day average, near equilibrium"
    elif vs_ma > -3:
        trend = "trading just below its 20-day average, showing mild weakness"
    elif vs_ma > -10:
        trend = "trading below its 20-day average — bearish signal"
    else:
        trend = "trading well below its 20-day average — potentially oversold"

    # Volatility label
    if volatility < 15:
        vol_label = "very stable"
    elif volatility < 25:
        vol_label = "relatively stable"
    elif volatility < 40:
        vol_label = "moderately volatile"
    elif volatility < 60:
        vol_label = "highly volatile"
    else:
        vol_label = "extremely volatile"

    ticker = hist.index.name or "This stock"
    summary = (
        f"The stock is {momentum} and {trend}.\n"
        f"At {volatility:.1f}% annualized volatility, it is {vol_label}."
    )

    return {
        "change_5d": change_5d,
        "ma20": ma20,
        "vs_ma": vs_ma,
        "ma_position": ma_position,
        "volatility": volatility,
        "vol_label": vol_label,
        "summary": summary,
    }


st.title("Chen Li's AI Stock Analyzer")

# --- Stock search ---
query = st.text_input("Search by ticker or company name (e.g. Tesla, NVDA)", value="")

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "AAPL"

if st.button("Search"):
    if query.strip():
        with st.spinner("Searching..."):
            matches = search_ticker(query.strip())
        if matches:
            options = {
                f"{m['ticker']} — {m['name']} ({m['exchange']})": m["ticker"]
                for m in matches
            }
            choice = st.selectbox("Select a stock", list(options.keys()))
            st.session_state.selected_ticker = options[choice]
        else:
            st.warning(f"No results found for '{query}'. Try a different name or ticker.")

ticker = st.session_state.selected_ticker
st.caption(f"Selected: **{ticker}**")

period = st.selectbox(
    "Historical period",
    ["1wk", "1mo", "3mo", "6mo", "1y"],
    index=1,
)

if st.button("Fetch"):
    with st.spinner("Fetching data..."):
        data = get_stock_price(ticker)
        hist = get_historical_prices(ticker, period=period)

    if data["price"] is None:
        st.error(f"Could not fetch price for {ticker}.")
    else:
        st.metric(label=f"{data['ticker']} Current Price", value=f"${data['price']}")

        if not hist.empty:
            analysis = advanced_analysis(hist)

            col1, col2, col3 = st.columns(3)
            change = analysis["change_5d"]
            col1.metric(
                "5-Day Change",
                f"{change:+.2f}%",
                delta=f"{change:+.2f}%",
            )
            col2.metric(
                "vs 20-Day MA",
                f"${analysis['ma20']:.2f}",
                delta=f"{analysis['vs_ma']:+.2f}% {analysis['ma_position']}",
            )
            col3.metric(
                "Annualized Volatility",
                f"{analysis['volatility']:.1f}%",
                delta=analysis["vol_label"],
                delta_color="off",
            )

            st.subheader("Analysis Summary")
            st.info(analysis["summary"])

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(x=hist.index, y=hist["Close"], mode="lines", name="Close")
            )
            ma_series = hist["Close"].rolling(20).mean()
            fig.add_trace(
                go.Scatter(
                    x=hist.index,
                    y=ma_series,
                    mode="lines",
                    name="20-Day MA",
                    line=dict(dash="dash", color="orange"),
                )
            )
            fig.update_layout(
                title=f"{ticker} Price History",
                xaxis_title="Date",
                yaxis_title="Price (USD)",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("Raw data"):
                st.dataframe(hist[["Open", "High", "Low", "Close", "Volume"]])

st.caption("Built with AI (Claude + Python)")

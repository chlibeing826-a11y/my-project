import streamlit as st
import plotly.graph_objects as go
from stock import get_stock_price, get_historical_prices

st.title("Stock Price Viewer")

ticker = st.text_input("Enter ticker symbol", value="AAPL").upper()

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
            closes = hist["Close"]
            trend = "up" if closes.iloc[-1] > closes.iloc[0] else "down"
            st.caption(f"Trend over period: {trend}")

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], mode="lines", name="Close"))
            fig.update_layout(
                title=f"{ticker} Price History",
                xaxis_title="Date",
                yaxis_title="Price (USD)",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("Raw data"):
                st.dataframe(hist[["Open", "High", "Low", "Close", "Volume"]])

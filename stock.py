import yfinance as yf


def search_ticker(query: str) -> list:
    """Search by company name or ticker symbol, return up to 6 matches."""
    results = yf.Search(query, max_results=6)
    matches = []
    for q in results.quotes:
        symbol = q.get("symbol", "")
        name = q.get("longname") or q.get("shortname", "")
        exchange = q.get("exchange", "")
        if symbol:
            matches.append({"ticker": symbol, "name": name, "exchange": exchange})
    return matches


def get_stock_price(ticker: str) -> dict:
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1d")
    price = hist["Close"].iloc[-1] if not hist.empty else None
    return {
        "ticker": ticker.upper(),
        "price": round(price, 2) if price is not None else None,
    }


def get_historical_prices(ticker: str, period: str = "1mo", interval: str = "1d"):
    stock = yf.Ticker(ticker)
    return stock.history(period=period, interval=interval)


def get_fundamentals(ticker: str) -> dict:
    """Fetch key fundamental metrics for value investing analysis."""
    stock = yf.Ticker(ticker)
    info = stock.info
    return {
        "name": info.get("longName") or info.get("shortName", ticker),
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "pb_ratio": info.get("priceToBook"),
        "roe": info.get("returnOnEquity"),           # decimal, e.g. 0.25 = 25%
        "debt_to_equity": info.get("debtToEquity"),  # yfinance scale: 50 means D/E=0.5
        "free_cashflow": info.get("freeCashflow"),
        "profit_margin": info.get("profitMargins"),  # decimal
        "gross_margin": info.get("grossMargins"),    # decimal
        "revenue_growth": info.get("revenueGrowth"), # decimal YoY
        "description": info.get("longBusinessSummary", ""),
    }


def get_financials_history(ticker: str) -> dict:
    """Fetch multi-year annual revenue and net income."""
    stock = yf.Ticker(ticker)
    result = {"revenue": None, "net_income": None}
    try:
        fin = stock.financials  # rows=items, cols=dates
        if fin is None or fin.empty:
            return result
        for key in ["Total Revenue", "Revenue"]:
            if key in fin.index:
                result["revenue"] = fin.loc[key].dropna().sort_index()
                break
        for key in ["Net Income", "Net Income Common Stockholders", "NetIncome"]:
            if key in fin.index:
                result["net_income"] = fin.loc[key].dropna().sort_index()
                break
    except Exception:
        pass
    return result


def get_long_history(ticker: str, period: str = "10y"):
    """Fetch long-term price history for investment simulation."""
    stock = yf.Ticker(ticker)
    return stock.history(period=period)


def analyze_trend(ticker: str) -> None:
    stock = yf.Ticker(ticker)
    hist = stock.history(period="5d", interval="1d")
    closes = hist["Close"].tolist()
    if len(closes) < 2:
        print("Not enough data to determine trend.")
        return
    trend = "up" if closes[-1] > closes[0] else "down"
    print(f"Trend for {ticker.upper()} over last {len(closes)} closes: {trend}")


if __name__ == "__main__":
    import sys

    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"Fetching price for {ticker}...")
    data = get_stock_price(ticker)
    print(f"Ticker: {data['ticker']}")
    print(f"Price:  {data['price']} USD")

    print(f"\nLast 5 days of historical data for {ticker}:")
    hist = get_historical_prices(ticker, period="5d")
    print(hist[["Open", "High", "Low", "Close", "Volume"]])

    print()
    analyze_trend(ticker)

import yfinance as yf


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

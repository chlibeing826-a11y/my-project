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


if __name__ == "__main__":
    ticker = "AAPL"
    print(f"Fetching price for {ticker}...")
    data = get_stock_price(ticker)
    print(f"Ticker: {data['ticker']}")
    print(f"Price:  {data['price']} USD")

    print(f"\nLast 5 days of historical data for {ticker}:")
    hist = get_historical_prices(ticker, period="5d")
    print(hist[["Open", "High", "Low", "Close", "Volume"]])

import requests
import pandas as pd
import os

BASE_URL = "https://api.kraken.com/0/public"

def fetch_order_book(symbol="XBTUSD", depth=50):
    """
    Fetch current order book snapshot from Kraken.
    """
    url = f"{BASE_URL}/Depth"
    params = {"pair": symbol, "count": depth}
    r = requests.get(url, params=params)
    data = r.json()

    result = list(data["result"].values())[0]
    bids = pd.DataFrame(result["bids"], columns=["price", "quantity", "timestamp"]).astype(float)
    asks = pd.DataFrame(result["asks"], columns=["price", "quantity", "timestamp"]).astype(float)

    bids["side"] = "bid"
    asks["side"] = "ask"

    return bids, asks


def fetch_recent_trades(symbol="XBTUSD", limit=500):
    """
    Fetch recent trades from Kraken.
    """
    url = f"{BASE_URL}/Trades"
    params = {"pair": symbol}
    r = requests.get(url, params=params)
    data = r.json()

    result = list(data["result"].values())[0]
    df = pd.DataFrame(result, columns=["price", "qty", "time", "side", "order_type", "misc", "trade_id"])
    df["price"] = df["price"].astype(float)
    df["qty"] = df["qty"].astype(float)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df["side"] = df["side"].apply(lambda x: "buy" if x == "b" else "sell")

    return df[["time", "price", "qty", "side"]].tail(limit)


def fetch_klines(symbol="XBTUSD", interval=1, limit=500):
    """
    Fetch OHLCV candlestick data from Kraken.
    interval in minutes: 1, 5, 15, 30, 60, 240, 1440
    """
    url = f"{BASE_URL}/OHLC"
    params = {"pair": symbol, "interval": interval}
    r = requests.get(url, params=params)
    data = r.json()

    result = list(data["result"].values())[0]
    df = pd.DataFrame(result, columns=[
        "open_time", "open", "high", "low", "close", "vwap", "volume", "trades"
    ])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="s")
    for col in ["open", "high", "low", "close", "vwap", "volume"]:
        df[col] = df[col].astype(float)

    return df.tail(limit)


def fetch_ticker_stats(symbol="XBTUSD"):
    """
    Fetch 24hr ticker statistics from Kraken.
    """
    url = f"{BASE_URL}/Ticker"
    params = {"pair": symbol}
    r = requests.get(url, params=params)
    data = r.json()
    result = list(data["result"].values())[0]

    return {
        "bid": float(result["b"][0]),
        "ask": float(result["a"][0]),
        "last": float(result["c"][0]),
        "volume_24h": float(result["v"][1]),
        "high_24h": float(result["h"][1]),
        "low_24h": float(result["l"][1]),
        "vwap_24h": float(result["p"][1]),
        "trades_24h": int(result["t"][1]),
    }


def save_snapshot(symbol="XBTUSD"):
    """
    Save a full market snapshot to disk.
    """
    os.makedirs("data", exist_ok=True)

    print(f"Fetching order book...")
    bids, asks = fetch_order_book(symbol, depth=50)

    print(f"Fetching recent trades...")
    trades = fetch_recent_trades(symbol, limit=500)

    print(f"Fetching klines...")
    klines = fetch_klines(symbol, interval=1, limit=500)

    print(f"Fetching ticker stats...")
    stats = fetch_ticker_stats(symbol)

    bids.to_csv(f"data/{symbol}_bids.csv", index=False)
    asks.to_csv(f"data/{symbol}_asks.csv", index=False)
    trades.to_csv(f"data/{symbol}_trades.csv", index=False)
    klines.to_csv(f"data/{symbol}_klines.csv", index=False)

    print(f"\nSnapshot saved for {symbol}")
    print(f"  Bids:   {len(bids)} levels")
    print(f"  Asks:   {len(asks)} levels")
    print(f"  Trades: {len(trades)}")
    print(f"  Klines: {len(klines)}")
    print(f"  Spread: ${stats['ask'] - stats['bid']:.2f}")
    print(f"  Last:   ${stats['last']:,.2f}")
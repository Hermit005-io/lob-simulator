# Limit Order Book Simulator

A market microstructure simulator built on real tick data from Kraken's API, featuring a full price-time priority matching engine and Hawkes process order flow simulation.

**Live Dashboard:** https://lob-simulator-ai8tcbttqydgl62wxz28mb.streamlit.app/

**GitHub:** https://github.com/Hermit005-io/lob-simulator

## What it does

- Fetches **live order book and trade data** from Kraken (BTC/USD, ETH/USD, SOL/USD)
- Seeds a full **price-time priority matching engine** with real prices and quantities
- Simulates realistic order flow using a **Hawkes process** — orders cluster in bursts rather than arriving randomly, mimicking actual market microstructure
- Supports **limit orders, market orders, partial fills, and cancellations**
- Tracks **market microstructure metrics** including spread dynamics, order flow imbalance, and volatility
- Interactive dashboard to **place your own orders** and watch them execute

## Core Components

**Matching Engine (`orderbook.py`)**
- Heap-based bid/ask book with O(log n) insertion and matching
- Price-time priority — same price orders matched in order of arrival
- Partial fills — large orders consume multiple price levels
- Real-time spread and depth tracking

**Order Flow Simulation (`simulator.py`)**
- Hawkes process — self-exciting point process where each order increases the probability of subsequent orders, creating realistic clustering
- Seeded from real Kraken snapshots so prices are grounded in actual market conditions
- Order flow imbalance tracked as a price predictor

**Data Layer (`fetch.py`)**
- Live order book snapshots (50 levels deep)
- Recent trade history (500 trades)
- OHLCV candlestick data (500 bars)
- 24hr ticker statistics

## Key Findings

**Spread dynamics:** Starting spread of $0.10 (real Kraken spread) widens to $19.40 under simulated order flow as liquidity is consumed and replenished.

**Order flow imbalance:** Buy volume minus sell volume tracked continuously as a leading indicator of price direction.

**Hawkes process vs Poisson:** Real markets show order clustering — the Hawkes process captures this self-exciting behavior far better than a naive random arrival model.

## Running Locally
```bash
git clone https://github.com/Hermit005-io/lob-simulator
cd lob-simulator
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
streamlit run src/dashboard.py
```

## Tech Stack

Python, Pandas, NumPy, Plotly, Streamlit, Kraken API
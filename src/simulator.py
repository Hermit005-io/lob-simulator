import sys
import os
import time
import random
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from order import Order, Side, OrderType
from orderbook import OrderBook

class MarketSimulator:
    def __init__(self, symbol="XBTUSD"):
        self.symbol = symbol
        self.book = OrderBook(symbol)
        self.metrics = {
            "spreads": [],
            "mid_prices": [],
            "timestamps": [],
            "trade_prices": [],
            "trade_quantities": [],
            "trade_sides": [],
            "order_flow_imbalance": [],
        }
        self.buy_volume = 0.0
        self.sell_volume = 0.0

    def seed_from_snapshot(self):
        """
        Seed the order book with real Kraken snapshot data.
        """
        bids_path = f"data/{self.symbol}_bids.csv"
        asks_path = f"data/{self.symbol}_asks.csv"

        if not os.path.exists(bids_path):
            raise FileNotFoundError(f"No snapshot found. Run fetch.py first.")

        bids = pd.read_csv(bids_path)
        asks = pd.read_csv(asks_path)

        print(f"Seeding order book with real {self.symbol} snapshot...")

        for _, row in bids.iterrows():
            order = Order(Side.BUY, OrderType.LIMIT, row["quantity"], row["price"], "market_maker")
            self.book.add_order(order)

        for _, row in asks.iterrows():
            order = Order(Side.SELL, OrderType.LIMIT, row["quantity"], row["price"], "market_maker")
            self.book.add_order(order)

        print(f"  Seeded {len(bids)} bid levels and {len(asks)} ask levels")
        print(f"  Best bid: ${self.book.best_bid():,.2f}")
        print(f"  Best ask: ${self.book.best_ask():,.2f}")
        print(f"  Spread:   ${self.book.spread():.2f}")

    def replay_trades(self, speed=1.0):
        """
        Replay real historical trades through the order book.
        Speed: 1.0 = real time, 10.0 = 10x faster
        """
        trades_path = f"data/{self.symbol}_trades.csv"
        if not os.path.exists(trades_path):
            raise FileNotFoundError("No trades data found. Run fetch.py first.")

        trades = pd.read_csv(trades_path)
        trades["time"] = pd.to_datetime(trades["time"])
        trades = trades.sort_values("time").reset_index(drop=True)

        print(f"\nReplaying {len(trades)} real trades...")
        print(f"Time range: {trades['time'].iloc[0]} -> {trades['time'].iloc[-1]}")

        prev_time = None

        for _, row in trades.iterrows():
            # simulate time delay between trades
            if prev_time is not None:
                delay = (row["time"] - prev_time).total_seconds() / speed
                if 0 < delay < 5:
                    time.sleep(delay)

            side = Side.BUY if row["side"] == "buy" else Side.SELL
            order = Order(side, OrderType.MARKET, row["qty"], trader_id="replayer")
            executed = self.book.add_order(order)

            # track volume imbalance
            if side == Side.BUY:
                self.buy_volume += row["qty"]
            else:
                self.sell_volume += row["qty"]

            # record metrics
            mid = self.book.mid_price()
            spread = self.book.spread()
            ofi = self.buy_volume - self.sell_volume

            if mid and spread:
                self.metrics["spreads"].append(spread)
                self.metrics["mid_prices"].append(mid)
                self.metrics["timestamps"].append(row["time"])
                self.metrics["order_flow_imbalance"].append(ofi)

            for t in executed:
                self.metrics["trade_prices"].append(t.price)
                self.metrics["trade_quantities"].append(t.quantity)
                self.metrics["trade_sides"].append(side.value)

            prev_time = row["time"]

    def simulate_hawkes_orders(self, n_events=500, mid_price=68000.0):
        """
        Simulate realistic order flow using a Hawkes process.
        Orders cluster together — bursts of activity followed by quiet periods.
        This mimics real market microstructure far better than a Poisson process.
        """
        print(f"\nSimulating {n_events} orders via Hawkes process...")

        # Hawkes process parameters
        mu = 0.5       # base arrival rate
        alpha = 0.8    # self-excitation factor
        beta = 1.0     # decay rate

        events = []
        t = 0.0
        lam = mu  # current intensity

        while len(events) < n_events:
            # time to next event
            dt = np.random.exponential(1.0 / lam)
            t += dt
            events.append(t)
            # intensity jumps on each event
            lam = mu + alpha * sum(np.exp(-beta * (t - s)) for s in events[-20:])
            lam = max(lam, mu)

        print(f"  Generated {len(events)} Hawkes events")

        # place orders at each event time
        spread = 10.0
        volatility = 50.0

        for i, t in enumerate(events):
            # random walk mid price
            mid_price += np.random.normal(0, volatility * 0.01)

            side = Side.BUY if random.random() > 0.5 else Side.SELL
            order_type = OrderType.MARKET if random.random() < 0.3 else OrderType.LIMIT

            qty = abs(np.random.lognormal(mean=-2, sigma=1))
            qty = max(0.001, round(qty, 4))

            if order_type == OrderType.LIMIT:
                if side == Side.BUY:
                    price = round(mid_price - random.uniform(0, spread * 2), 1)
                else:
                    price = round(mid_price + random.uniform(0, spread * 2), 1)
                order = Order(side, order_type, qty, price, f"trader_{i%20}")
            else:
                order = Order(side, order_type, qty, trader_id=f"trader_{i%20}")

            executed = self.book.add_order(order)

            # track metrics
            mid = self.book.mid_price()
            spread_val = self.book.spread()
            ofi = self.buy_volume - self.sell_volume

            if mid and spread_val:
                self.metrics["spreads"].append(spread_val)
                self.metrics["mid_prices"].append(mid)
                self.metrics["timestamps"].append(t)
                self.metrics["order_flow_imbalance"].append(ofi)

            for tr in executed:
                self.metrics["trade_prices"].append(tr.price)
                self.metrics["trade_quantities"].append(tr.quantity)
                self.metrics["trade_sides"].append(side.value)

            if side == Side.BUY:
                self.buy_volume += qty
            else:
                self.sell_volume += qty

    def compute_analytics(self):
        """
        Compute market microstructure analytics.
        """
        print("\n" + "=" * 50)
        print("MARKET MICROSTRUCTURE ANALYTICS")
        print("=" * 50)

        prices = self.metrics["mid_prices"]
        spreads = self.metrics["spreads"]
        ofi = self.metrics["order_flow_imbalance"]
        trade_prices = self.metrics["trade_prices"]

        if not prices:
            print("No data yet.")
            return

        print(f"Total orders processed: {self.book.total_trades + len(self.book._orders)}")
        print(f"Total trades executed:  {self.book.total_trades}")
        print(f"Total volume traded:    {self.book.total_volume:.4f} BTC")
        print(f"\nPrice Statistics:")
        print(f"  Starting mid price:  ${prices[0]:,.2f}")
        print(f"  Ending mid price:    ${prices[-1]:,.2f}")
        print(f"  Price range:         ${min(prices):,.2f} - ${max(prices):,.2f}")
        print(f"  Price volatility:    ${np.std(prices):,.2f}")
        print(f"\nSpread Statistics:")
        print(f"  Mean spread:         ${np.mean(spreads):.2f}")
        print(f"  Min spread:          ${min(spreads):.2f}")
        print(f"  Max spread:          ${max(spreads):.2f}")
        print(f"\nOrder Flow:")
        print(f"  Buy volume:          {self.buy_volume:.4f} BTC")
        print(f"  Sell volume:         {self.sell_volume:.4f} BTC")
        print(f"  Net imbalance:       {self.buy_volume - self.sell_volume:+.4f} BTC")

        # OFI as price predictor
        if len(ofi) > 10 and len(prices) > 10:
            min_len = min(len(ofi), len(prices) - 1)
            price_changes = np.diff(prices[:min_len + 1])
            ofi_arr = np.array(ofi[:min_len])
            if np.std(ofi_arr) > 0:
                corr = np.corrcoef(ofi_arr, price_changes)[0, 1]
                print(f"\nOrder Flow Imbalance → Price correlation: {corr:.4f}")
                print(f"  (Positive = buy pressure predicts price rises)")

        print("=" * 50)

    def get_metrics_df(self):
        """Return metrics as a DataFrame for the dashboard."""
        n = min(
            len(self.metrics["timestamps"]),
            len(self.metrics["mid_prices"]),
            len(self.metrics["spreads"]),
            len(self.metrics["order_flow_imbalance"])
        )
        return pd.DataFrame({
            "timestamp": self.metrics["timestamps"][:n],
            "mid_price": self.metrics["mid_prices"][:n],
            "spread": self.metrics["spreads"][:n],
            "order_flow_imbalance": self.metrics["order_flow_imbalance"][:n],
        })


if __name__ == "__main__":
    sim = MarketSimulator("XBTUSD")
    sim.seed_from_snapshot()
    sim.simulate_hawkes_orders(n_events=300)
    sim.compute_analytics()
    sim.book.summary()
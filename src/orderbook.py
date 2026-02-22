import heapq
import time
from collections import defaultdict
from order import Order, Side, OrderType

class Trade:
    def __init__(self, buy_order_id, sell_order_id, price, quantity, timestamp=None):
        self.buy_order_id = buy_order_id
        self.sell_order_id = sell_order_id
        self.price = price
        self.quantity = quantity
        self.timestamp = timestamp or time.time()

    def __repr__(self):
        return (f"Trade(buy={self.buy_order_id}, sell={self.sell_order_id}, "
                f"price={self.price:.2f}, qty={self.quantity:.4f})")


class PriceLevel:
    """All orders at a single price level."""
    def __init__(self, price):
        self.price = price
        self.orders = []  # queue of orders, FIFO
        self.total_quantity = 0.0

    def add_order(self, order):
        self.orders.append(order)
        self.total_quantity += order.remaining

    def remove_filled(self):
        before = sum(o.remaining for o in self.orders)
        self.orders = [o for o in self.orders if o.remaining > 0 and o.status not in ("cancelled", "filled")]
        self.total_quantity = sum(o.remaining for o in self.orders)

    def is_empty(self):
        return len(self.orders) == 0 or self.total_quantity == 0

    def __repr__(self):
        return f"PriceLevel(price={self.price}, qty={self.total_quantity:.4f}, orders={len(self.orders)})"


class OrderBook:
    def __init__(self, symbol="XBTUSD"):
        self.symbol = symbol

        # bids: max heap (negate price for max behavior)
        self._bid_heap = []  # (-price, timestamp, order)
        self._ask_heap = []  # (price, timestamp, order)

        # price level lookup
        self._bid_levels = {}  # price -> PriceLevel
        self._ask_levels = {}  # price -> PriceLevel

        # order lookup
        self._orders = {}  # order_id -> order

        # trade history
        self.trades = []

        # metrics
        self.total_volume = 0.0
        self.total_trades = 0

    def add_order(self, order):
        """Add a limit or market order to the book."""
        self._orders[order.id] = order

        if order.order_type == OrderType.MARKET:
            trades = self._match_market_order(order)
        else:
            trades = self._match_limit_order(order)

        self.trades.extend(trades)
        self.total_trades += len(trades)
        self.total_volume += sum(t.quantity for t in trades)

        return trades

    def cancel_order(self, order_id):
        """Cancel an open order."""
        if order_id in self._orders:
            order = self._orders[order_id]
            order.cancel()
            # remove from price level
            if order.side == Side.BUY and order.price in self._bid_levels:
                self._bid_levels[order.price].remove_filled()
            elif order.side == Side.SELL and order.price in self._ask_levels:
                self._ask_levels[order.price].remove_filled()
            return True
        return False

    def _match_market_order(self, order):
        """Match a market order against the best available prices."""
        trades = []
        if order.side == Side.BUY:
            # buy market order matches against asks (lowest first)
            while order.remaining > 0 and self._ask_heap:
                trades.extend(self._fill_from_asks(order))
                if not self._ask_heap:
                    break
        else:
            # sell market order matches against bids (highest first)
            while order.remaining > 0 and self._bid_heap:
                trades.extend(self._fill_from_bids(order))
                if not self._bid_heap:
                    break

        if order.remaining > 0:
            order.status = "partial"

        return trades

    def _match_limit_order(self, order):
        """Match a limit order, then place remainder in book."""
        trades = []

        if order.side == Side.BUY:
            # match against asks where ask price <= bid price
            while (order.remaining > 0 and self._ask_heap and
                   self._ask_heap[0][0] <= order.price):
                trades.extend(self._fill_from_asks(order))

            # place remainder in bid book
            if order.remaining > 0 and order.status != "filled":
                self._add_to_bids(order)

        else:
            # match against bids where bid price >= ask price
            while (order.remaining > 0 and self._bid_heap and
                   -self._bid_heap[0][0] >= order.price):
                trades.extend(self._fill_from_bids(order))

            # place remainder in ask book
            if order.remaining > 0 and order.status != "filled":
                self._add_to_asks(order)

        return trades

    def _fill_from_asks(self, aggressive_order):
        """Fill aggressive buy order from ask side."""
        trades = []
        while aggressive_order.remaining > 0 and self._ask_heap:
            best_price, ts, passive_order = self._ask_heap[0]

            if passive_order.status in ("filled", "cancelled"):
                heapq.heappop(self._ask_heap)
                continue

            if aggressive_order.order_type == OrderType.LIMIT and best_price > aggressive_order.price:
                break

            fill_qty = min(aggressive_order.remaining, passive_order.remaining)
            aggressive_order.fill(fill_qty)
            passive_order.fill(fill_qty)

            trade = Trade(
                buy_order_id=aggressive_order.id,
                sell_order_id=passive_order.id,
                price=best_price,
                quantity=fill_qty
            )
            trades.append(trade)

            if passive_order.remaining == 0:
                heapq.heappop(self._ask_heap)
                if best_price in self._ask_levels:
                    self._ask_levels[best_price].remove_filled()

        return trades

    def _fill_from_bids(self, aggressive_order):
        """Fill aggressive sell order from bid side."""
        trades = []
        while aggressive_order.remaining > 0 and self._bid_heap:
            neg_price, ts, passive_order = self._bid_heap[0]
            best_price = -neg_price

            if passive_order.status in ("filled", "cancelled"):
                heapq.heappop(self._bid_heap)
                continue

            if aggressive_order.order_type == OrderType.LIMIT and best_price < aggressive_order.price:
                break

            fill_qty = min(aggressive_order.remaining, passive_order.remaining)
            aggressive_order.fill(fill_qty)
            passive_order.fill(fill_qty)

            trade = Trade(
                buy_order_id=passive_order.id,
                sell_order_id=aggressive_order.id,
                price=best_price,
                quantity=fill_qty
            )
            trades.append(trade)

            if passive_order.remaining == 0:
                heapq.heappop(self._bid_heap)
                if best_price in self._bid_levels:
                    self._bid_levels[best_price].remove_filled()

        return trades

    def _add_to_bids(self, order):
        price = order.price
        if price not in self._bid_levels:
            self._bid_levels[price] = PriceLevel(price)
        self._bid_levels[price].add_order(order)
        heapq.heappush(self._bid_heap, (-price, order.timestamp, order))

    def _add_to_asks(self, order):
        price = order.price
        if price not in self._ask_levels:
            self._ask_levels[price] = PriceLevel(price)
        self._ask_levels[price].add_order(order)
        heapq.heappush(self._ask_heap, (price, order.timestamp, order))

    def best_bid(self):
        """Return best bid price."""
        while self._bid_heap:
            neg_price, ts, order = self._bid_heap[0]
            if order.status not in ("filled", "cancelled") and order.remaining > 0:
                return -neg_price
            heapq.heappop(self._bid_heap)
        return None

    def best_ask(self):
        """Return best ask price."""
        while self._ask_heap:
            price, ts, order = self._ask_heap[0]
            if order.status not in ("filled", "cancelled") and order.remaining > 0:
                return price
            heapq.heappop(self._ask_heap)
        return None

    def spread(self):
        """Return bid-ask spread."""
        bid = self.best_bid()
        ask = self.best_ask()
        if bid and ask:
            return round(ask - bid, 2)
        return None

    def mid_price(self):
        """Return mid price."""
        bid = self.best_bid()
        ask = self.best_ask()
        if bid and ask:
            return (bid + ask) / 2
        return None

    def get_depth(self, levels=10):
        """
        Return order book depth as two lists of (price, quantity) tuples.
        Bids sorted descending, asks sorted ascending.
        """
        # aggregate by price level
        bid_depth = {}
        for neg_price, ts, order in self._bid_heap:
            if order.status not in ("filled", "cancelled") and order.remaining > 0:
                price = -neg_price
                bid_depth[price] = bid_depth.get(price, 0) + order.remaining

        ask_depth = {}
        for price, ts, order in self._ask_heap:
            if order.status not in ("filled", "cancelled") and order.remaining > 0:
                ask_depth[price] = ask_depth.get(price, 0) + order.remaining

        bids = sorted(bid_depth.items(), key=lambda x: -x[0])[:levels]
        asks = sorted(ask_depth.items(), key=lambda x: x[0])[:levels]

        return bids, asks

    def get_trade_history(self, n=50):
        """Return last n trades."""
        return self.trades[-n:]

    def summary(self):
        bids, asks = self.get_depth(5)
        print(f"\n{'='*45}")
        print(f"Order Book: {self.symbol}")
        print(f"{'='*45}")
        print(f"{'ASKS':>40}")
        for price, qty in reversed(asks):
            print(f"  {price:>12.2f}  |  {qty:>10.4f}")
        print(f"  {'--- SPREAD: $' + str(self.spread()):^20} ---")
        for price, qty in bids:
            print(f"  {price:>12.2f}  |  {qty:>10.4f}")
        print(f"{'BIDS':>40}")
        print(f"{'='*45}")
        print(f"Total trades: {self.total_trades}")
        print(f"Total volume: {self.total_volume:.4f}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "src")

    book = OrderBook("XBTUSD")

    # seed with some limit orders
    orders = [
        Order(Side.BUY,  OrderType.LIMIT, 0.5,  68000.0),
        Order(Side.BUY,  OrderType.LIMIT, 1.0,  67990.0),
        Order(Side.BUY,  OrderType.LIMIT, 0.75, 67980.0),
        Order(Side.SELL, OrderType.LIMIT, 0.5,  68010.0),
        Order(Side.SELL, OrderType.LIMIT, 1.0,  68020.0),
        Order(Side.SELL, OrderType.LIMIT, 0.75, 68030.0),
    ]

    for o in orders:
        book.add_order(o)

    book.summary()

    # place a market buy that crosses the spread
    print("\nPlacing market buy order for 0.6 BTC...")
    market_buy = Order(Side.BUY, OrderType.MARKET, 0.6)
    trades = book.add_order(market_buy)
    for t in trades:
        print(f"  Executed: {t}")

    book.summary()
import time
from enum import Enum

class Side(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    LIMIT = "limit"
    MARKET = "market"

class Order:
    _id_counter = 0

    def __init__(self, side, order_type, quantity, price=None, trader_id="anonymous"):
        Order._id_counter += 1
        self.id = Order._id_counter
        self.side = side
        self.order_type = order_type
        self.quantity = quantity
        self.price = price          # None for market orders
        self.timestamp = time.time()
        self.remaining = quantity   # quantity not yet filled
        self.filled = 0.0
        self.trader_id = trader_id
        self.status = "open"        # open, partial, filled, cancelled

    def fill(self, quantity):
        """Apply a fill to this order."""
        quantity = min(quantity, self.remaining)
        self.filled += quantity
        self.remaining -= quantity
        if self.remaining == 0:
            self.status = "filled"
        else:
            self.status = "partial"
        return quantity

    def cancel(self):
        self.status = "cancelled"

    def fill_pct(self):
        return (self.filled / self.quantity) * 100 if self.quantity > 0 else 0

    def __repr__(self):
        return (f"Order(id={self.id}, side={self.side.value}, "
                f"type={self.order_type.value}, qty={self.quantity:.4f}, "
                f"price={self.price}, filled={self.filled:.4f}, "
                f"status={self.status})")
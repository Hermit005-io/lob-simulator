import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import time

from order import Order, Side, OrderType
from orderbook import OrderBook
from simulator import MarketSimulator

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="LOB Simulator",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #0f1117; }
    [data-testid="stSidebar"] { background-color: #1a1d27; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    .stApp p, .stApp span, .stApp label, .stApp div { color: #e2e8f0; }
    .stApp h1 { color: #7c9ef5 !important; }
    .stApp h2 { color: #a0b4f7 !important; }
    .stApp h3 { color: #c3d0fa !important; }
    [data-testid="stMetric"] {
        background-color: #1a1d27;
        border: 1px solid #2d3748;
        border-radius: 8px;
        padding: 16px;
    }
    [data-testid="stMetricValue"] { color: #ffffff !important; }
    [data-testid="stMetricLabel"] { color: #a0aec0 !important; }
    .stRadio label { color: #e2e8f0 !important; }
    .stSelectbox label { color: #e2e8f0 !important; }
    .stTextInput input {
        background-color: #1a1d27 !important;
        color: #ffffff !important;
        border-color: #2d3748 !important;
    }
    hr { border-color: #2d3748; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────
if "sim" not in st.session_state:
    st.session_state.sim = None
if "initialized" not in st.session_state:
    st.session_state.initialized = False
if "trade_log" not in st.session_state:
    st.session_state.trade_log = []

# ── Sidebar ───────────────────────────────────────────────────
st.sidebar.title("📈 LOB Simulator")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigate", [
    "Overview",
    "Order Book",
    "Place Order",
    "Simulation",
    "Analytics",
])

st.sidebar.markdown("---")
st.sidebar.subheader("Market")
symbol = st.sidebar.selectbox("Symbol", ["XBTUSD", "ETHUSD", "SOLUSD"])

if st.sidebar.button("🔄 Load Real Market Data"):
    with st.spinner("Fetching live data from Kraken..."):
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from fetch import save_snapshot
            save_snapshot(symbol)
            sim = MarketSimulator(symbol)
            sim.seed_from_snapshot()
            st.session_state.sim = sim
            st.session_state.initialized = True
            st.session_state.trade_log = []
            st.sidebar.success(f"Loaded {symbol} data!")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")

# ── Helper functions ──────────────────────────────────────────
def get_sim():
    if st.session_state.sim is None:
        st.warning("Load market data first using the sidebar.")
        st.stop()
    return st.session_state.sim

def depth_chart(sim):
    bids, asks = sim.book.get_depth(levels=20)
    if not bids or not asks:
        return None

    bid_prices = [b[0] for b in bids]
    bid_qtys = [b[1] for b in bids]
    ask_prices = [a[0] for a in asks]
    ask_qtys = [a[1] for a in asks]

    # cumulative depth
    bid_cum = np.cumsum(bid_qtys)
    ask_cum = np.cumsum(ask_qtys)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=bid_prices, y=bid_cum,
        fill="tozeroy", name="Bids",
        line=dict(color="#00cc88", width=2),
        fillcolor="rgba(0,204,136,0.15)"
    ))
    fig.add_trace(go.Scatter(
        x=ask_prices, y=ask_cum,
        fill="tozeroy", name="Asks",
        line=dict(color="#ff4466", width=2),
        fillcolor="rgba(255,68,102,0.15)"
    ))
    fig.update_layout(
        title="Order Book Depth",
        xaxis_title="Price (USD)",
        yaxis_title="Cumulative Quantity (BTC)",
        plot_bgcolor="#0f1117",
        paper_bgcolor="#0f1117",
        font=dict(color="#e2e8f0"),
        legend=dict(bgcolor="#1a1d27"),
        height=400
    )
    return fig

def order_book_table(sim):
    bids, asks = sim.book.get_depth(levels=15)
    bid_df = pd.DataFrame(bids, columns=["Price", "Quantity"])
    ask_df = pd.DataFrame(asks, columns=["Price", "Quantity"])
    bid_df["Price"] = bid_df["Price"].apply(lambda x: f"${x:,.2f}")
    ask_df["Price"] = ask_df["Price"].apply(lambda x: f"${x:,.2f}")
    bid_df["Quantity"] = bid_df["Quantity"].apply(lambda x: f"{x:.4f}")
    ask_df["Quantity"] = ask_df["Quantity"].apply(lambda x: f"{x:.4f}")
    return bid_df, ask_df

# ── Pages ─────────────────────────────────────────────────────

# OVERVIEW
if page == "Overview":
    st.title("Limit Order Book Simulator")
    st.markdown("*Real market data from Kraken · Hawkes process order flow · Full matching engine*")
    st.markdown("---")

    if not st.session_state.initialized:
        st.info("👈 Click **Load Real Market Data** in the sidebar to begin.")
        st.markdown("""
        ### What this simulator does
        - Fetches **live order book and trade data** from Kraken
        - Seeds a full **price-time priority matching engine** with real prices
        - Simulates realistic order flow using a **Hawkes process**
        - Lets you **place your own orders** and watch them execute
        - Tracks **market microstructure metrics** in real time
        """)
    else:
        sim = get_sim()
        bid = sim.book.best_bid()
        ask = sim.book.best_ask()
        spread = sim.book.spread()
        mid = sim.book.mid_price()

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Best Bid", f"${bid:,.2f}" if bid else "N/A")
        col2.metric("Best Ask", f"${ask:,.2f}" if ask else "N/A")
        col3.metric("Spread", f"${spread:.2f}" if spread else "N/A")
        col4.metric("Mid Price", f"${mid:,.2f}" if mid else "N/A")
        col5.metric("Trades Executed", sim.book.total_trades)

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            fig = depth_chart(sim)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            trades = sim.book.get_trade_history(20)
            if trades:
                trade_data = [{
                    "Price": f"${t.price:,.2f}",
                    "Quantity": f"{t.quantity:.4f}",
                    "Buy ID": t.buy_order_id,
                    "Sell ID": t.sell_order_id,
                } for t in reversed(trades)]
                st.subheader("Recent Trades")
                st.dataframe(pd.DataFrame(trade_data), use_container_width=True)
            else:
                st.info("No trades yet.")

# ORDER BOOK
elif page == "Order Book":
    st.title("Live Order Book")
    sim = get_sim()

    bid = sim.book.best_bid()
    ask = sim.book.best_ask()
    spread = sim.book.spread()

    col1, col2, col3 = st.columns(3)
    col1.metric("Best Bid", f"${bid:,.2f}" if bid else "N/A")
    col2.metric("Best Ask", f"${ask:,.2f}" if ask else "N/A")
    col3.metric("Spread", f"${spread:.2f}" if spread else "N/A")

    st.markdown("---")

    col1, col2 = st.columns(2)
    bid_df, ask_df = order_book_table(sim)

    with col1:
        st.subheader("🟢 Bids")
        st.dataframe(bid_df, use_container_width=True, hide_index=True)
    with col2:
        st.subheader("🔴 Asks")
        st.dataframe(ask_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    fig = depth_chart(sim)
    if fig:
        st.plotly_chart(fig, use_container_width=True)

# PLACE ORDER
elif page == "Place Order":
    st.title("Place Order")
    sim = get_sim()

    st.markdown(f"**Current mid price: ${sim.book.mid_price():,.2f}**")
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        side = st.selectbox("Side", ["Buy", "Sell"])
        order_type = st.selectbox("Order Type", ["Limit", "Market"])
        quantity = st.number_input("Quantity (BTC)", min_value=0.001, value=0.1, step=0.001, format="%.4f")

    with col2:
        if order_type == "Limit":
            default_price = sim.book.best_bid() if side == "Buy" else sim.book.best_ask()
            price = st.number_input("Price (USD)", min_value=1.0,
                                     value=float(default_price) if default_price else 68000.0,
                                     step=0.1, format="%.2f")
        else:
            st.info("Market orders execute immediately at best available price.")
            price = None

    if st.button(f"Place {side} {order_type} Order", type="primary"):
        side_enum = Side.BUY if side == "Buy" else Side.SELL
        type_enum = OrderType.LIMIT if order_type == "Limit" else OrderType.MARKET
        order = Order(side_enum, type_enum, quantity, price, trader_id="user")
        trades = sim.book.add_order(order)

        if trades:
            st.success(f"✅ Order filled! {len(trades)} trade(s) executed.")
            for t in trades:
                st.write(f"  → {t.quantity:.4f} BTC @ ${t.price:,.2f}")
                st.session_state.trade_log.append({
                    "Side": side,
                    "Qty": t.quantity,
                    "Price": t.price,
                    "Type": order_type
                })
        elif order_type == "Limit":
            st.info(f"📋 Limit order placed in book @ ${price:,.2f}")
        else:
            st.warning("⚠️ No liquidity available for market order.")

    st.markdown("---")
    if st.session_state.trade_log:
        st.subheader("Your Trade History")
        df = pd.DataFrame(st.session_state.trade_log)
        df["Price"] = df["Price"].apply(lambda x: f"${x:,.2f}")
        df["Qty"] = df["Qty"].apply(lambda x: f"{x:.4f}")
        st.dataframe(df, use_container_width=True, hide_index=True)

# SIMULATION
elif page == "Simulation":
    st.title("Market Simulation")
    sim = get_sim()

    st.markdown("""
    Run a Hawkes process simulation — orders cluster realistically,
    mimicking actual market microstructure behavior.
    """)

    col1, col2 = st.columns(2)
    with col1:
        n_events = st.slider("Number of orders", 100, 2000, 500, step=100)
    with col2:
        mid_price = sim.book.mid_price() or 68000.0
        st.metric("Current mid price", f"${mid_price:,.2f}")

    if st.button("▶ Run Simulation", type="primary"):
        with st.spinner(f"Simulating {n_events} orders..."):
            sim.simulate_hawkes_orders(n_events=n_events, mid_price=mid_price)
        st.success(f"Done! {sim.book.total_trades} total trades executed.")
        st.rerun()

    st.markdown("---")
    metrics_df = sim.get_metrics_df()
    if not metrics_df.empty:
        col1, col2 = st.columns(2)

        with col1:
            fig = px.line(metrics_df, x=metrics_df.index, y="mid_price",
                         title="Mid Price Over Time",
                         color_discrete_sequence=["#7c9ef5"])
            fig.update_layout(plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
                             font=dict(color="#e2e8f0"), height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.line(metrics_df, x=metrics_df.index, y="spread",
                         title="Spread Over Time",
                         color_discrete_sequence=["#ff9944"])
            fig.update_layout(plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
                             font=dict(color="#e2e8f0"), height=300)
            st.plotly_chart(fig, use_container_width=True)

        fig = px.line(metrics_df, x=metrics_df.index, y="order_flow_imbalance",
                     title="Order Flow Imbalance (Buy Volume - Sell Volume)",
                     color_discrete_sequence=["#00cc88"])
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.3)
        fig.update_layout(plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
                         font=dict(color="#e2e8f0"), height=300)
        st.plotly_chart(fig, use_container_width=True)

# ANALYTICS
elif page == "Analytics":
    st.title("Market Microstructure Analytics")
    sim = get_sim()

    metrics_df = sim.get_metrics_df()
    trades = sim.book.get_trade_history(1000)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Trades", sim.book.total_trades)
    col2.metric("Total Volume", f"{sim.book.total_volume:.4f} BTC")
    col3.metric("Buy Volume", f"{sim.buy_volume:.4f} BTC")
    col4.metric("Sell Volume", f"{sim.sell_volume:.4f} BTC")

    st.markdown("---")

    if not metrics_df.empty:
        prices = metrics_df["mid_price"].values
        spreads = metrics_df["spread"].values
        ofi = metrics_df["order_flow_imbalance"].values

        col1, col2, col3 = st.columns(3)
        col1.metric("Mean Spread", f"${np.mean(spreads):.2f}")
        col2.metric("Price Volatility", f"${np.std(prices):.2f}")
        col3.metric("Net OFI", f"{sim.buy_volume - sim.sell_volume:+.4f} BTC")

        st.markdown("---")

        # price distribution
        if trades:
            trade_prices = [t.price for t in trades]
            fig = px.histogram(x=trade_prices, nbins=50,
                              title="Trade Price Distribution",
                              color_discrete_sequence=["#7c9ef5"])
            fig.update_layout(plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
                             font=dict(color="#e2e8f0"), height=350,
                             xaxis_title="Price (USD)", yaxis_title="Count")
            st.plotly_chart(fig, use_container_width=True)

        # OFI vs price change
        if len(ofi) > 10:
            min_len = min(len(ofi), len(prices) - 1)
            price_changes = np.diff(prices[:min_len + 1])
            ofi_trimmed = ofi[:min_len]
            corr = np.corrcoef(ofi_trimmed, price_changes)[0, 1]

            fig = px.scatter(x=ofi_trimmed, y=price_changes,
                           title=f"Order Flow Imbalance vs Price Change (corr={corr:.4f})",
                           color_discrete_sequence=["#00cc88"],
                           opacity=0.5)
            fig.update_layout(plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
                             font=dict(color="#e2e8f0"), height=350,
                             xaxis_title="Order Flow Imbalance",
                             yaxis_title="Price Change")
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Run a simulation first to see analytics.")
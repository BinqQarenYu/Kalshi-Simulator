"""Unit tests for OrderSimulator institutional realism upgrades.

Validates:
1. Strict FIFO queue priority (no instant touch-fill while queue_ahead > 0).
2. Clean market sweeps through limit level filling immediately.
3. Wire latency arrival delay gating.
4. Quote cancellation discount on initial queue depth.
5. High-velocity adverse selection drift in realistic mode.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest

from kalshi_sim.order_simulator import OrderSimulator
from kalshi_sim.schemas import L2BookState, OrderSide, OrderStatus, Timeframe, TradeEvent


def test_fifo_queue_blocks_instant_fill_on_mere_touch() -> None:
    """Test that with strict_queue_matching=True, a resting limit order does NOT fill on a mere touch if queue_ahead > 0."""
    sim = OrderSimulator(strict_queue_matching=True, wire_latency_ms=0.0)

    book = L2BookState(market_ticker="KXBTC15M-TEST-01")
    book.yes_book = {Decimal("0.52"): Decimal("50")}
    book.no_book = {Decimal("0.47"): Decimal("50")}

    order = sim.place_resting_limit_order(
        book=book,
        side=OrderSide.YES,
        size=1,
        limit_price=Decimal("0.52"),
        timeframe=Timeframe.FIFTEEN_MIN,
    )

    assert order.queue_ahead == 50
    assert order.status == OrderStatus.RESTING


    book.no_book = {Decimal("0.48"): Decimal("50")}
    assert book.best_yes_ask == Decimal("0.52")


    filled = sim.process_resting_orders(book=book, latest_trades=[])
    assert len(filled) == 0
    assert order.status == OrderStatus.RESTING


def test_sweep_through_level_fills_immediately() -> None:
    """Test that if the market sweeps strictly through our limit level (best_ask < limit_price), it fills immediately."""
    sim = OrderSimulator(strict_queue_matching=True, wire_latency_ms=0.0)

    book = L2BookState(market_ticker="KXBTC15M-TEST-02")
    book.yes_book = {Decimal("0.52"): Decimal("50")}
    book.no_book = {Decimal("0.47"): Decimal("50")}

    order = sim.place_resting_limit_order(
        book=book,
        side=OrderSide.YES,
        size=1,
        limit_price=Decimal("0.52"),
        timeframe=Timeframe.FIFTEEN_MIN,
    )
    assert order.queue_ahead == 50


    book.no_book = {Decimal("0.50"): Decimal("50")}
    assert book.best_yes_ask == Decimal("0.50")


    filled = sim.process_resting_orders(book=book, latest_trades=[])
    assert len(filled) == 1
    filled_ord, fill = filled[0]
    assert filled_ord.status == OrderStatus.FILLED
    assert fill.fill_price == Decimal("0.50")


def test_wire_latency_arrival_delay() -> None:
    """Test that orders in-flight before wire latency arrives!are not processed."""
    sim = OrderSimulator(wire_latency_ms=250.0)

    book = L2BookState(market_ticker="KXBTC15M-TEST-03")
    book.yes_book = {Decimal("0.52"): Decimal("50")}
    book.no_book = {Decimal("0.50"): Decimal("50")}

    order = sim.place_resting_limit_order(
        book=book,
        side=OrderSide.YES,
        size=1,
        limit_price=Decimal("0.52"),
        timeframe=Timeframe.FIFTEEN_MIN,
    )
    filled = sim.process_resting_orders(book=book)
    assert len(filled) == 0

    order.created_at = datetime.now(timezone.utc) - timedelta(milliseconds=300)
    filled_after = sim.process_resting_orders(book=book)
    assert len(filled_after) == 1
    assert filled_after[0][0].status == OrderStatus.FILLED


def test_quote_cancellation_discount() -> None:
    """Test that quote_cancel_rate reduces effective queue ahead to model maker cancellations."""
    sim = OrderSimulator(quote_cancel_rate=0.45)

    book = L2BookState(market_ticker="KXBTC15M-TEST-04")
    book.yes_book = {Decimal("0.52"): Decimal("100")}
    book.no_book = {Decimal("0.47"): Decimal("50")}

    order = sim.place_resting_limit_order(
        book=book,
        side=OrderSide.YES,
        size=1,
        limit_price=Decimal("0.52"),
        timeframe=Timeframe.FIFTEEN_MIN,
    )
    assert order.queue_ahead == 55


def test_realistic_mode_adverse_drift() -> None:
    """Test that realistic_mode applies enhanced adverse drift on extreme spot velocity."""
    sim_realistic = OrderSimulator(realistic_mode=True)
    sim_standard = OrderSimulator(realistic_mode=False)

    book_side = {Decimal("0.48"): Decimal("100")}

    vwap_std, _, _ = sim_standard._walk_book(
        book_side=book_side,
        size=1,
        order_side=OrderSide.YES,
        timeframe=Timeframe.FIFTEEN_MIN,
        spot_velocity=35.0,
        asset_or_ticker="BTC",
    )
    assert vwap_std == Decimal("0.5300")

    vwap_real, _, _ = sim_realistic._walk_book(
        book_side=book_side,
        size=1,
        order_side=OrderSide.YES,
        timeframe=Timeframe.FIFTEEN_MIN,
        spot_velocity=35.0,
        asset_or_ticker="BTC",
    )
    assert vwap_real == Decimal("0.5400")

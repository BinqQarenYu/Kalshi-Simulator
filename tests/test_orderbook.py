from datetime import datetime
from decimal import Decimal
import time

from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.schemas import OrderBookDelta, OrderBookLevel, OrderBookSnapshot


def test_orderbook_manager_snapshot_and_getters():
    obm = OrderBookManager()
    snapshot = OrderBookSnapshot(
        market_ticker="TEST-TICKER",
        seq=100,
        yes_levels=[OrderBookLevel(price=Decimal("0.50"), quantity=Decimal("10"))],
        no_levels=[OrderBookLevel(price=Decimal("0.40"), quantity=Decimal("20"))],
        timestamp=datetime.now(),
    )
    book = obm.apply_snapshot(snapshot)
    assert book.market_ticker == "TEST-TICKER"
    assert obm.get_book("TEST-TICKER") is not None

    bids, asks = obm.get_depth_levels("TEST-TICKER", n=5)
    assert len(bids) == 1
    assert len(asks) == 1

    best_bid, best_ask, spread = obm.get_top_of_book("TEST-TICKER")
    assert best_bid == Decimal("0.50")
    assert best_ask == Decimal("0.60")  # 1 - 0.40

    stale = obm.get_stale_tickers()
    assert stale == []

    obm.remove_book("TEST-TICKER")
    assert obm.get_book("TEST-TICKER") is None


def test_orderbook_manager_delta():
    obm = OrderBookManager(enforce_consecutive_seq=False)
    delta = OrderBookDelta(
        market_ticker="TEST-TICKER",
        seq=10,
        side="yes",
        price=Decimal("0.55"),
        delta=Decimal("5"),
        timestamp=datetime.now(),
    )
    book = obm.apply_delta(delta)
    assert book is not None
    assert obm.get_book("TEST-TICKER").yes_book[Decimal("0.55")] == Decimal("5")


def test_get_depth_float_tuples_caching_and_invalidation():
    obm = OrderBookManager(enforce_consecutive_seq=False)
    snapshot = OrderBookSnapshot(
        market_ticker="TEST-FLOAT-CACHE",
        seq=100,
        yes_levels=[OrderBookLevel(price=Decimal("0.50"), quantity=Decimal("10.5"))],
        no_levels=[OrderBookLevel(price=Decimal("0.40"), quantity=Decimal("20.25"))],
        timestamp=datetime.now(),
    )
    book = obm.apply_snapshot(snapshot)

    # 1. Fetch float tuples and verify types & values
    yes_floats, no_floats = book.get_depth_float_tuples(n=5)
    assert isinstance(yes_floats[0][0], float)
    assert isinstance(yes_floats[0][1], float)
    assert yes_floats == [(0.50, 10.5)]
    assert no_floats == [(0.40, 20.25)]

    # 2. Verify O(1) cache identity on second call (exact same object returned)
    yes_floats_cached, no_floats_cached = book.get_depth_float_tuples(n=5)
    assert yes_floats_cached is yes_floats
    assert no_floats_cached is no_floats

    # 3. Apply delta to modify order book and verify cache invalidation
    delta = OrderBookDelta(
        market_ticker="TEST-FLOAT-CACHE",
        seq=101,
        side="yes",
        price=Decimal("0.55"),
        delta=Decimal("15.0"),
        timestamp=datetime.now(),
    )
    obm.apply_delta(delta)

    yes_floats_updated, no_floats_updated = book.get_depth_float_tuples(n=5)
    assert yes_floats_updated is not yes_floats
    assert yes_floats_updated == [(0.55, 15.0), (0.50, 10.5)]

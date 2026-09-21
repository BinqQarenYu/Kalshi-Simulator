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


def test_fastbook_top_of_book_tracking_after_pop():
    from kalshi_sim.schemas import FastBook

    fb = FastBook({
        Decimal("0.50"): Decimal("10"),
        Decimal("0.40"): Decimal("20"),
        Decimal("0.30"): Decimal("15"),
    })
    assert fb.best_bid == Decimal("0.50")

    # Remove top price level
    fb.pop(Decimal("0.50"))

    # Insertion or update of an existing lower price level should NOT corrupt _best
    fb[Decimal("0.30")] = Decimal("25")
    assert fb.best_bid == Decimal("0.40")

    # Inserting a new top price level should update _best
    fb[Decimal("0.60")] = Decimal("5")
    assert fb.best_bid == Decimal("0.60")

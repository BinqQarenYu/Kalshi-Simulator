"""Unit tests for the Rolling OHLCV Candlestick Aggregator."""

from decimal import Decimal
import time
import pytest

from kalshi_sim.ohlcv_aggregator import OHLCVAggregator
from kalshi_sim.schemas import CandleInterval, OHLCVCandle


def test_aggregator_single_tick_creation():
    """A single tick creates a valid 1m bar with open=high=low=close."""
    agg = OHLCVAggregator(max_bars=100)
    now = 1700000000

    agg.add_tick("BTC", price=Decimal("78000.00"), volume=Decimal("2.0"), timestamp=now)
    bars_1m = agg.get_candles("BTC", interval=CandleInterval.ONE_MIN)

    assert len(bars_1m) == 1
    bar = bars_1m[0]
    assert bar.timestamp == 1700000000 // 60 * 60
    assert bar.open == Decimal("78000.00")
    assert bar.high == Decimal("78000.00")
    assert bar.low == Decimal("78000.00")
    assert bar.close == Decimal("78000.00")
    assert bar.volume == Decimal("2.0")
    assert bar.trades_count == 1


def test_aggregator_multi_tick_update_within_bucket():
    """Multiple ticks within the same minute update high, low, close, volume, and count."""
    agg = OHLCVAggregator(max_bars=100)
    base_ts = 1700000000

    # 1st tick
    agg.add_tick("BTC", price=Decimal("78000"), volume=Decimal("1"), timestamp=base_ts)
    # 2nd tick (higher)
    agg.add_tick("BTC", price=Decimal("78200"), volume=Decimal("3"), timestamp=base_ts + 10)
    # 3rd tick (lower)
    agg.add_tick("BTC", price=Decimal("77900"), volume=Decimal("2"), timestamp=base_ts + 20)
    # 4th tick (close)
    agg.add_tick("BTC", price=Decimal("78150"), volume=Decimal("4"), timestamp=base_ts + 30)

    bars_1m = agg.get_candles("BTC", interval=CandleInterval.ONE_MIN)
    assert len(bars_1m) == 1
    bar = bars_1m[0]
    assert bar.open == Decimal("78000")
    assert bar.high == Decimal("78200")
    assert bar.low == Decimal("77900")
    assert bar.close == Decimal("78150")
    assert bar.volume == Decimal("10")
    assert bar.trades_count == 4


def test_aggregator_multi_timeframe_simultaneous_aggregation():
    """Ticks are simultaneously aggregated into 1m, 5m, 15m, and 1h bars."""
    agg = OHLCVAggregator(max_bars=100)
    base_ts = 1700000000  # epoch

    # Ingest 10 ticks spanning 10 minutes (600 seconds)
    for i in range(10):
        agg.add_tick(
            "BTC",
            price=Decimal(str(78000 + (i * 10))),
            volume=Decimal("1"),
            timestamp=base_ts + (i * 60),
        )

    # 1m should have 10 bars
    bars_1m = agg.get_candles("BTC", interval=CandleInterval.ONE_MIN)
    assert len(bars_1m) == 10

    # 5m should have 2 or 3 bars depending on boundary
    bars_5m = agg.get_candles("BTC", interval=CandleInterval.FIVE_MIN)
    assert len(bars_5m) >= 2

    # 1h should have 1 bar containing all 10 ticks
    bars_1h = agg.get_candles("BTC", interval=CandleInterval.ONE_HOUR)
    assert len(bars_1h) == 1
    assert bars_1h[0].volume == Decimal("10")
    assert bars_1h[0].trades_count == 10


def test_aggregator_synthetic_seeding():
    """Synthetic history generates valid sequential bars with non-zero metrics."""
    agg = OHLCVAggregator(max_bars=100)
    agg.seed_synthetic_history("BTC", start_price=Decimal("78500"), bars_count=30)

    bars_1m = agg.get_candles("BTC", interval="1m", limit=30)
    assert len(bars_1m) == 30
    for bar in bars_1m:
        assert bar.high >= bar.low
        assert bar.high >= bar.open
        assert bar.high >= bar.close
        assert bar.low <= bar.open
        assert bar.low <= bar.close
        assert bar.volume > 0
        assert bar.trades_count > 0

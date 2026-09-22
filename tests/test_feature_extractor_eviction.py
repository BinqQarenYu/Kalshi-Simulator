"""Unit tests for feature extractor rolling window eviction and sorting invariants."""

from datetime import datetime, timezone
from decimal import Decimal
import numpy as np

from app_2_execution_bot.ml.feature_extractor import KalshiOrderflowFeatureExtractor
from app_2_execution_bot.ml.gold_feature_extractor import GoldOrderflowFeatureExtractor
from shared.schemas import L2BookState, TradeEvent


def test_kalshi_feature_extractor_trade_eviction() -> None:
    """Test that KalshiOrderflowFeatureExtractor rolling trade eviction maintains sorting."""
    extractor = KalshiOrderflowFeatureExtractor()

    # Push 150 trades to force multiple 100-item eviction cycles
    for i in range(150):
        # Quantity alternates between 1.0 and 100.0 with variation
        qty = Decimal(str(float((i % 10) + 1)))
        trade = TradeEvent(
            trade_id=f"t_{i}",
            market_ticker="KXBTC15M-T78650",
            yes_price=Decimal("0.50"),
            no_price=Decimal("0.50"),
            count=qty,
            taker_side="yes",
            timestamp=datetime.now(timezone.utc),
        )
        extractor.process_trade(trade)

    # Check bounds and sorting invariant
    assert len(extractor.rolling_trade_quantities) == 100
    assert len(extractor.sorted_rolling_trade_quantities) == 100
    # Verify array is sorted
    qs = extractor.sorted_rolling_trade_quantities
    assert all(qs[i] <= qs[i + 1] for i in range(len(qs) - 1))


def test_kalshi_feature_extractor_volume_eviction() -> None:
    """Test that KalshiOrderflowFeatureExtractor rolling volume eviction maintains sorting."""
    extractor = KalshiOrderflowFeatureExtractor()
    book = L2BookState("KXBTC15M-T78650")
    book.yes_book[Decimal("0.50")] = Decimal("10.0")
    book.no_book[Decimal("0.50")] = Decimal("10.0")

    # Push 150 feature extraction calls to trigger 100-item volume eviction
    for i in range(150):
        # Mutate book to change volume
        book.yes_book[Decimal("0.50")] = Decimal(str(float(i + 1)))
        vec = extractor.extract_features_from_book(book)
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (28,)

    # Check bounds and sorting invariant
    assert len(extractor.rolling_volumes) == 100
    assert len(extractor.sorted_rolling_volumes) == 100
    vols = extractor.sorted_rolling_volumes
    assert all(vols[i] <= vols[i + 1] for i in range(len(vols) - 1))


def test_gold_feature_extractor_eviction() -> None:
    """Test GoldOrderflowFeatureExtractor trade and volume eviction maintenance."""
    extractor = GoldOrderflowFeatureExtractor()

    # 1. Trade eviction test
    for i in range(150):
        trade = TradeEvent(
            trade_id=f"gt_{i}",
            market_ticker="KXGOLD15M-T2000",
            yes_price=Decimal("0.50"),
            no_price=Decimal("0.50"),
            count=Decimal(str(float((i % 15) + 1))),
            taker_side="buy",
            timestamp=datetime.now(timezone.utc),
        )
        extractor.process_trade(trade)

    assert len(extractor.rolling_trade_quantities) == 100
    assert len(extractor.sorted_rolling_trade_quantities) == 100
    qs = extractor.sorted_rolling_trade_quantities
    assert all(qs[i] <= qs[i + 1] for i in range(len(qs) - 1))

    # 2. Volume eviction test
    book = L2BookState("KXGOLD15M-T2000", is_spot=True)
    book.yes_book[Decimal("2000.00")] = Decimal("5.0")
    book.no_book[Decimal("2001.00")] = Decimal("5.0")

    for i in range(150):
        book.yes_book[Decimal("2000.00")] = Decimal(str(float(i + 5)))
        vec = extractor.extract_features(
            book,
            target_strike=Decimal("2000.00"),
            current_spot=Decimal("2000.50"),
            time_to_expiry_s=300.0,
        )
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (32,)

    assert len(extractor.rolling_volumes) == 100
    assert len(extractor.sorted_rolling_volumes) == 100
    vols = extractor.sorted_rolling_volumes
    assert all(vols[i] <= vols[i + 1] for i in range(len(vols) - 1))

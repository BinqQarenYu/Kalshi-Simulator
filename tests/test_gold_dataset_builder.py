"""Unit tests for GoldDatasetBuilder (32-D Feature & Target Extraction)."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path

import numpy as np
import pytest

from kalshi_sim.ml.gold_dataset_builder import GoldDatasetBuilder


def test_parse_tick_line_and_book_building() -> None:
    """Verify that tick json lines are parsed and converted to valid L2BookState."""
    builder = GoldDatasetBuilder()
    raw_json = json.dumps({
        "market_ticker": "KXGOLD15M-T2500",
        "yes_levels": [{"price": "0.48", "quantity": "100"}, {"price": "0.46", "quantity": "200"}],
        "no_levels": [{"price": "0.52", "quantity": "150"}, {"price": "0.54", "quantity": "250"}],
        "spot_price": "2502.50",
        "time_remaining_s": 350,
    })

    record = builder.parse_tick_line(raw_json)
    assert record is not None
    assert record["market_ticker"] == "KXGOLD15M-T2500"

    book = builder.build_book_from_snapshot(record)
    assert Decimal("0.48") in book.yes_book
    assert book.yes_book[Decimal("0.48")] == Decimal("100")
    assert Decimal("0.52") in book.no_book
    assert book.no_book[Decimal("0.52")] == Decimal("150")


def test_build_dataset_from_records_dimensions_and_labels() -> None:
    """Verify (M, 32) feature matrix and labels in {0, 1, 2}."""
    builder = GoldDatasetBuilder(dead_zone_threshold=Decimal("0.50"))

    records = []
    # Create 30 sequential ticks where spot drifts upwards
    for i in range(30):
        records.append({
            "market_ticker": "KXGOLD15M-T2500",
            "yes_levels": [{"price": "0.48", "quantity": "100"}],
            "no_levels": [{"price": "0.52", "quantity": "100"}],
            "spot_price": str(2500.0 + i * 0.10),
            "time_remaining_s": 400 - i * 5,
        })

    X, y = builder.build_dataset_from_records(records, forward_horizon=10, target_strike=Decimal("2500.00"))

    assert isinstance(X, np.ndarray)
    assert isinstance(y, np.ndarray)
    assert X.shape == (20, 32)
    assert y.shape == (20,)
    assert X.dtype == np.float32
    assert y.dtype == np.int64

    # With spot drifting +$0.10/tick over 10 ticks (+1.00 > +0.50 threshold), label should be UP (0)
    assert (y == GoldDatasetBuilder.CLASS_UP).all()


def test_generate_synthetic_samples_distribution() -> None:
    """Verify synthetic generator generates balanced 32-D features."""
    builder = GoldDatasetBuilder()
    X, y = builder.generate_synthetic_samples(num_samples=300, seed=123)

    assert X.shape == (300, 32)
    assert y.shape == (300,)

    classes, counts = np.unique(y, return_counts=True)
    assert set(classes) == {0, 1, 2}
    # Check each class has reasonable representation
    for cnt in counts:
        assert cnt >= 30


def test_train_val_split_stratification() -> None:
    """Verify that train_val_split maintains class balance across partitions."""
    builder = GoldDatasetBuilder()
    X, y = builder.generate_synthetic_samples(num_samples=200, seed=42)

    X_train, X_val, y_train, y_val = builder.train_val_split(X, y, val_ratio=0.25, stratified=True)

    assert len(X_train) + len(X_val) == 200
    assert len(y_train) + len(y_val) == 200

    # Ensure all 3 classes exist in both splits
    assert set(np.unique(y_train)) == {0, 1, 2}
    assert set(np.unique(y_val)) == {0, 1, 2}

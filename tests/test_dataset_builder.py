"""Unit and integration tests for tick log parsing and training dataset builder."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import tempfile

import numpy as np
import orjson
import pytest

from kalshi_sim.ml.dataset_builder import DatasetBuilder, TickFrame


@pytest.fixture
def sample_jsonl_file(tmp_path: Path) -> Path:
    """Create a temporary JSONL tick file containing orderbook snapshots and deltas."""
    file_path = tmp_path / "ticks_test.jsonl"

    lines = []
    # 1. Snapshot
    lines.append({
        "_type": "OrderBookSnapshot",
        "ticker": "KXBTC15M-T78650",
        "yes_levels": [{"price": "0.48", "volume": 100}, {"price": "0.47", "volume": 200}],
        "no_levels": [{"price": "0.52", "volume": 150}, {"price": "0.53", "volume": 250}],
        "timestamp": 1724600000.0,
    })

    # 2. Sequential deltas and trades
    for i in range(30):
        # alternate buy and sell deltas
        price = "0.49" if i > 15 else "0.48"
        lines.append({
            "_type": "OrderBookDelta",
            "ticker": "KXBTC15M-T78650",
            "side": "yes",
            "price": price,
            "delta": 10,
            "seq": i + 1,
            "timestamp": 1724600000.0 + i,
        })
        lines.append({
            "_type": "TradeEvent",
            "ticker": "KXBTC15M-T78650",
            "side": "yes",
            "price": price,
            "count": 5,
            "timestamp": 1724600000.0 + i,
        })

    with open(file_path, "wb") as f:
        for item in lines:
            f.write(orjson.dumps(item) + b"\n")

    return file_path


def test_parse_synthetic_tick_file(sample_jsonl_file: Path) -> None:
    """Test parsing JSONL tick recording into valid TickFrames."""
    builder = DatasetBuilder(horizon_steps=5, price_diff_threshold=0.01)
    frames = builder.parse_tick_file(sample_jsonl_file)

    assert len(frames) > 0
    first_frame = frames[0]
    assert isinstance(first_frame, TickFrame)
    assert first_frame.features.shape == (28,)
    assert np.all(np.isfinite(first_frame.features))
    assert first_frame.mid_price > 0.0


def test_build_dataset_labeling_logic() -> None:
    """Test future return horizon labeling (0=UP, 1=DOWN, 2=WAIT)."""
    builder = DatasetBuilder(horizon_steps=2, price_diff_threshold=0.02)

    frames = [
        TickFrame(timestamp=1.0, ticker="TEST", features=np.zeros(28, dtype=np.float32), mid_price=0.50),
        TickFrame(timestamp=2.0, ticker="TEST", features=np.zeros(28, dtype=np.float32), mid_price=0.50),
        TickFrame(timestamp=3.0, ticker="TEST", features=np.zeros(28, dtype=np.float32), mid_price=0.55),  # 0.55 - 0.50 = +0.05 -> UP (0)
        TickFrame(timestamp=4.0, ticker="TEST", features=np.zeros(28, dtype=np.float32), mid_price=0.45),  # 0.45 - 0.50 = -0.05 -> DOWN (1)
        TickFrame(timestamp=5.0, ticker="TEST", features=np.zeros(28, dtype=np.float32), mid_price=0.55),  # 0.55 - 0.55 = 0.00 -> WAIT (2)
    ]

    X, y = builder.build_dataset_from_frames(frames)
    assert len(X) == 3
    assert len(y) == 3
    assert y[0] == 0  # UP (0.50 -> 0.55)
    assert y[1] == 1  # DOWN (0.50 -> 0.45)
    assert y[2] == 2  # WAIT (0.55 -> 0.55)


def test_build_from_directory_and_save_npz(tmp_path: Path, sample_jsonl_file: Path) -> None:
    """Test directory batch building and .npz archive persistence."""
    builder = DatasetBuilder(horizon_steps=3, price_diff_threshold=0.01)

    # 1. Build from directory
    X, y = builder.build_from_directory(tmp_path, file_pattern="ticks_*.jsonl")
    assert len(X) > 0
    assert len(y) == len(X)
    assert X.shape[1] == 28

    # 2. Save .npz and load back
    npz_path = tmp_path / "models" / "dataset.npz"
    builder.save_dataset_npz(X, y, npz_path, val_split=0.25)
    assert npz_path.exists()

    loaded = np.load(npz_path)
    assert "X_train" in loaded
    assert "y_train" in loaded
    assert "X_val" in loaded
    assert "y_val" in loaded
    assert loaded["X_train"].shape[1] == 28
    assert len(loaded["X_train"]) + len(loaded["X_val"]) == len(X)

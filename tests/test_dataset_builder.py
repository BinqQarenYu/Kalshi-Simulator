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
    builder = DatasetBuilder(horizon_steps=2, price_diff_threshold=0.02, horizon_seconds=2.0)

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


def test_time_anchored_horizon_windowing_and_stale_skip() -> None:
    """Test time-anchored frame matching, stale data gap skipping (> 10.0s), and step fallback."""
    builder = DatasetBuilder(horizon_steps=2, horizon_seconds=3.0, price_diff_threshold=0.02)

    # Non-uniform timestamps with horizon_seconds=3.0:
    # t=1.0 -> target 4.0, closest is t=4.1 (mid 0.55 -> +0.05 => UP 0)
    # t=2.0 -> target 5.0, closest is t=5.0 (mid 0.45 -> -0.05 => DOWN 1)
    # t=4.1 -> target 7.1, closest is t=7.0 (mid 0.55 -> 0.00 => WAIT 2)
    # t=5.0 -> target 8.0, closest is t=7.0 (mid 0.55 -> +0.10 => UP 0)
    # t=7.0 -> target 10.0, closest is t=25.0 -> gap 18.0s > 10.0s (STALE DATA! Skipped!)
    # t=25.0 -> target 28.0, closest is t=28.0 (mid 0.60 -> 0.00 => WAIT 2)
    frames = [
        TickFrame(timestamp=1.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.50),
        TickFrame(timestamp=2.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.50),
        TickFrame(timestamp=4.1, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.55),
        TickFrame(timestamp=5.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.45),
        TickFrame(timestamp=7.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.55),
        TickFrame(timestamp=25.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.60),
        TickFrame(timestamp=28.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.60),
    ]
    X, y = builder.build_dataset_from_frames(frames, max_wait_ratio=None)
    # 5 pairs matched; t=7.0 skipped due to 18.0s gap to t=25.0
    assert len(X) == 5
    assert y[0] == 0
    assert y[1] == 1
    assert y[2] == 2
    assert y[3] == 0
    assert y[4] == 2


def test_stale_data_gap_skipped() -> None:
    """Explicitly verify that frame pairs with timestamp gap > 10.0s are skipped."""
    builder = DatasetBuilder(horizon_seconds=3.0, price_diff_threshold=0.02)
    # Frame 0 at 1.0, Frame 1 at 16.0 (gap = 15.0s > 10.0s)
    frames = [
        TickFrame(timestamp=1.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.50),
        TickFrame(timestamp=16.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.55),
    ]
    X, y = builder.build_dataset_from_frames(frames, max_wait_ratio=None)
    assert len(X) == 0  # Skipped due to gap > 10.0s


def test_timestamp_fallback_to_horizon_steps() -> None:
    """Verify that absent/non-positive/identical timestamps gracefully fall back to horizon_steps."""
    builder = DatasetBuilder(horizon_steps=2, horizon_seconds=3.0, price_diff_threshold=0.02)

    # All timestamps 0.0 (non-positive / absent)
    frames_zero_ts = [
        TickFrame(timestamp=0.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.50),
        TickFrame(timestamp=0.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.50),
        TickFrame(timestamp=0.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.55),
        TickFrame(timestamp=0.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.45),
    ]
    X, y = builder.build_dataset_from_frames(frames_zero_ts, max_wait_ratio=None)
    assert len(X) == 2  # 4 - horizon_steps(2) = 2
    assert y[0] == 0  # 0.55 - 0.50 = +0.05 -> UP
    assert y[1] == 1  # 0.45 - 0.50 = -0.05 -> DOWN

    # Identical timestamps
    frames_identical_ts = [
        TickFrame(timestamp=100.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.50),
        TickFrame(timestamp=100.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.50),
        TickFrame(timestamp=100.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.55),
        TickFrame(timestamp=100.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.45),
    ]
    X_id, y_id = builder.build_dataset_from_frames(frames_identical_ts, max_wait_ratio=None)
    assert len(X_id) == 2
    assert y_id[0] == 0
    assert y_id[1] == 1


def test_micro_price_directional_labeling() -> None:
    """Test spread-aware micro-price vs mid-price label assignment."""
    builder = DatasetBuilder(horizon_steps=1, horizon_seconds=1.0, price_diff_threshold=0.02)

    # Both have valid micro_price: micro_price diff is used
    # Frame 0: mid=0.50, micro=0.50
    # Frame 1: mid=0.50, micro=0.53 (diff = +0.03 >= 0.02 -> UP 0, even though mid diff is 0.00!)
    frames_micro = [
        TickFrame(timestamp=1.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.50, micro_price=0.50),
        TickFrame(timestamp=2.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.50, micro_price=0.53),
    ]
    X_m, y_m = builder.build_dataset_from_frames(frames_micro, max_wait_ratio=None)
    assert len(y_m) == 1
    assert y_m[0] == 0  # UP due to micro-price shift

    # Fallback to mid_price when micro_price is None
    frames_fallback = [
        TickFrame(timestamp=1.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.50, micro_price=None),
        TickFrame(timestamp=2.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.53, micro_price=None),
    ]
    X_fb, y_fb = builder.build_dataset_from_frames(frames_fallback, max_wait_ratio=None)
    assert len(y_fb) == 1
    assert y_fb[0] == 0


def test_dynamic_wait_undersampling() -> None:
    """Test dynamic WAIT undersampling respecting max_wait_ratio."""
    builder = DatasetBuilder(horizon_steps=1, horizon_seconds=1.0, price_diff_threshold=0.02)

    # Generate 2 non-wait frames (1 UP, 1 DOWN) and 20 WAIT frames
    frames = [
        TickFrame(timestamp=1.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.50),
        TickFrame(timestamp=2.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.55),  # 0->1: UP (0)
        TickFrame(timestamp=3.0, ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.45),  # 1->2: DOWN (1)
    ]
    # Add 20 identical mid_price frames resulting in WAIT (2)
    for i in range(4, 24):
        frames.append(TickFrame(timestamp=float(i), ticker="T", features=np.zeros(28, dtype=np.float32), mid_price=0.45))

    # With max_wait_ratio=0.50: N_non_wait = 2 -> max_wait_samples = 2
    # Total samples should be 2 + 2 = 4 (WAIT ratio <= 50%)
    X_sub, y_sub = builder.build_dataset_from_frames(frames, max_wait_ratio=0.50)
    assert len(X_sub) == 4
    assert np.sum(y_sub == 2) == 2
    assert np.sum(y_sub != 2) == 2
    assert np.sum(y_sub == 2) / len(y_sub) <= 0.50

    # With max_wait_ratio=None: all WAIT frames are preserved
    X_all, y_all = builder.build_dataset_from_frames(frames, max_wait_ratio=None)
    assert len(X_all) > 4
    assert np.sum(y_all == 2) > 2


def test_parse_gzip_tick_file(sample_jsonl_file: Path, tmp_path: Path) -> None:
    """Test transparent parsing of gzip-compressed .jsonl.gz tick files."""
    import gzip

    gz_file = tmp_path / "ticks_test.jsonl.gz"
    with open(sample_jsonl_file, "rb") as f_in, gzip.open(gz_file, "wb") as f_out:
        f_out.write(f_in.read())

    builder = DatasetBuilder(horizon_steps=5, price_diff_threshold=0.01)
    frames_raw = builder.parse_tick_file(sample_jsonl_file)
    frames_gz = builder.parse_tick_file(gz_file)

    assert len(frames_gz) == len(frames_raw)
    assert len(frames_gz) > 0
    # Verify exact feature equality
    for f_r, f_g in zip(frames_raw, frames_gz):
        assert f_r.timestamp == f_g.timestamp
        assert f_r.mid_price == f_g.mid_price
        np.testing.assert_allclose(f_r.features, f_g.features)

    # Test build_from_directory with .gz pattern
    X_gz, y_gz = builder.build_from_directory(tmp_path, file_pattern="ticks_test.jsonl.gz")
    assert len(X_gz) > 0


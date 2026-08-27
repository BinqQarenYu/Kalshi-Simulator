"""Offline JSONL Tick Dataset Parser & Feature Matrix Builder.

Parses recorded tick data files (containing OrderBookSnapshot, OrderBookDelta, TradeEvent, TickerUpdate),
reconstructs chronological L2 CLOB book states, extracts 28-dimensional feature vectors via
KalshiOrderflowFeatureExtractor, and labels future directional returns (UP=0, DOWN=1, WAIT=2).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterator, List, Optional, Tuple, Union

import numpy as np
import orjson

from kalshi_sim.ml.feature_extractor import KalshiOrderflowFeatureExtractor
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.schemas import (
    L2BookState,
    OrderBookDelta,
    OrderBookLevel,
    OrderBookSnapshot,
    OrderSide,
    TickerUpdate,
    TradeEvent,
)

logger = logging.getLogger(__name__)


@dataclass
class TickFrame:
    """Extracted snapshot of orderflow feature vector and corresponding market mid-price at time t."""
    timestamp: float
    ticker: str
    features: np.ndarray  # Shape: (28,)
    mid_price: float


class DatasetBuilder:
    """Processes recorded JSONL tick logs into aligned (N, 28) feature matrices and forward-return labels."""

    def __init__(
        self,
        horizon_steps: int = 15,
        price_diff_threshold: float = 0.01,
        target_depth: int = 15,
        spatial_alpha: float = 0.425,
    ) -> None:
        self.horizon_steps = horizon_steps
        self.price_diff_threshold = price_diff_threshold
        self.target_depth = target_depth
        self.spatial_alpha = spatial_alpha

    def parse_tick_file(self, file_path: Union[str, Path]) -> List[TickFrame]:
        """Stream and parse a single JSONL tick recording file."""
        file_path = Path(file_path)
        if not file_path.exists() or file_path.stat().st_size == 0:
            logger.warning("Tick file %s is empty or does not exist.", file_path)
            return []

        book_mgr = OrderBookManager()
        extractor = KalshiOrderflowFeatureExtractor(
            target_depth=self.target_depth,
            spatial_alpha=self.spatial_alpha,
        )

        frames: List[TickFrame] = []
        current_ticker = "KXBTC15M"

        with open(file_path, "rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = orjson.loads(line)
                except Exception:
                    continue

                record_type = data.get("_type")
                ts = 0.0
                if "timestamp" in data:
                    raw_ts = data["timestamp"]
                    if isinstance(raw_ts, (int, float)):
                        ts = float(raw_ts)
                    elif isinstance(raw_ts, str):
                        try:
                            ts = datetime.fromisoformat(raw_ts).timestamp()
                        except Exception:
                            ts = 0.0

                ticker_str = str(data.get("market_ticker") or data.get("ticker") or current_ticker)
                current_ticker = ticker_str

                # Process event type
                if record_type == "OrderBookSnapshot":
                    try:
                        yes_raw = data.get("yes_levels", [])
                        no_raw = data.get("no_levels", [])
                        yes_levels = [
                            OrderBookLevel(
                                price=Decimal(str(lvl.get("price", "0"))),
                                quantity=Decimal(str(lvl.get("quantity") or lvl.get("volume") or "1")),
                            )
                            for lvl in yes_raw
                        ]
                        no_levels = [
                            OrderBookLevel(
                                price=Decimal(str(lvl.get("price", "0"))),
                                quantity=Decimal(str(lvl.get("quantity") or lvl.get("volume") or "1")),
                            )
                            for lvl in no_raw
                        ]
                        snapshot = OrderBookSnapshot(
                            market_ticker=ticker_str,
                            seq=int(data.get("seq", 0)),
                            yes_levels=yes_levels,
                            no_levels=no_levels,
                        )
                        book_mgr.apply_snapshot(snapshot)
                    except Exception as e:
                        logger.debug("Failed parsing snapshot: %s", e)
                        continue

                elif record_type == "OrderBookDelta":
                    try:
                        delta = OrderBookDelta(
                            market_ticker=ticker_str,
                            side=data.get("side", "yes"),
                            price=Decimal(str(data.get("price", "0"))),
                            delta=Decimal(str(data.get("delta", 0))),
                            seq=int(data.get("seq", 0)),
                            timestamp=datetime.now(timezone.utc),
                        )
                        book_mgr.apply_delta(delta)
                    except Exception as e:
                        logger.debug("Failed parsing delta: %s", e)
                        continue

                elif record_type == "TradeEvent":
                    try:
                        yes_p = Decimal(str(data.get("yes_price") or data.get("price") or "0.50"))
                        no_p = Decimal(str(data.get("no_price") or str(Decimal("1.0") - yes_p)))
                        trade = TradeEvent(
                            trade_id=str(data.get("trade_id", "t_sim")),
                            market_ticker=ticker_str,
                            yes_price=yes_p,
                            no_price=no_p,
                            count=Decimal(str(data.get("count", 1))),
                            taker_side=data.get("taker_side") or data.get("side") or "yes",
                            timestamp=datetime.now(timezone.utc),
                        )
                        extractor.process_trade(trade)
                    except Exception as e:
                        logger.debug("Failed parsing trade: %s", e)
                        continue

                # Build current L2 book state and extract features
                l2_state = book_mgr.get_book(current_ticker)
                if not l2_state:
                    continue

                mid_p = l2_state.mid_price or 0.50
                features = extractor.extract_features_from_book(l2_state)
                if not np.all(np.isfinite(features)):
                    continue

                frames.append(
                    TickFrame(
                        timestamp=ts,
                        ticker=current_ticker,
                        features=features,
                        mid_price=float(mid_p),
                    )
                )

        return frames

    def build_dataset_from_frames(
        self, frames: List[TickFrame]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Align features and future target labels from sequential tick frames.

        Target labeling rule:
          - UP (0): mid_price(t + horizon) - mid_price(t) >= price_diff_threshold
          - DOWN (1): mid_price(t + horizon) - mid_price(t) <= -price_diff_threshold
          - WAIT (2): |mid_price(t + horizon) - mid_price(t)| < price_diff_threshold
        """
        n = len(frames)
        if n <= self.horizon_steps:
            return np.empty((0, 28), dtype=np.float32), np.empty((0,), dtype=np.int64)

        x_list: List[np.ndarray] = []
        y_list: List[int] = []

        for i in range(n - self.horizon_steps):
            current = frames[i]
            future = frames[i + self.horizon_steps]

            diff = future.mid_price - current.mid_price

            if diff >= self.price_diff_threshold:
                label = 0  # UP
            elif diff <= -self.price_diff_threshold:
                label = 1  # DOWN
            else:
                label = 2  # WAIT

            x_list.append(current.features)
            y_list.append(label)

        X = np.array(x_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.int64)
        return X, y

    def build_from_directory(
        self, data_dir: Union[str, Path], file_pattern: str = "ticks_*.jsonl"
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Iterate over all matching tick files in a directory and concatenate into feature tensors."""
        data_dir = Path(data_dir)
        all_x: List[np.ndarray] = []
        all_y: List[np.ndarray] = []

        files = sorted(list(data_dir.glob(file_pattern)))
        logger.info("Found %d tick files matching %s in %s", len(files), file_pattern, data_dir)

        for file_path in files:
            frames = self.parse_tick_file(file_path)
            if len(frames) > self.horizon_steps:
                X_f, y_f = self.build_dataset_from_frames(frames)
                if len(X_f) > 0:
                    all_x.append(X_f)
                    all_y.append(y_f)

        if not all_x:
            return np.empty((0, 28), dtype=np.float32), np.empty((0,), dtype=np.int64)

        X = np.concatenate(all_x, axis=0)
        y = np.concatenate(all_y, axis=0)
        return X, y

    def save_dataset_npz(
        self,
        X: np.ndarray,
        y: np.ndarray,
        output_path: Union[str, Path],
        val_split: float = 0.2,
    ) -> None:
        """Split into train/validation sets and save to compressed NumPy .npz file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        n_samples = len(X)
        if n_samples == 0:
            raise ValueError("Cannot save empty dataset")

        n_val = int(n_samples * val_split)
        n_train = n_samples - n_val

        X_train, y_train = X[:n_train], y[:n_train]
        X_val, y_val = X[n_train:], y[n_train:]

        np.savez_compressed(
            output_path,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            feature_dim=28,
            num_classes=3,
        )
        logger.info("Saved compiled dataset with %d samples to %s", n_samples, output_path)

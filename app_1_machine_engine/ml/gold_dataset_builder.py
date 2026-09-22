"""Gold Orderflow & Spacetime 32-D Dataset Builder.

Reconstructs chronological L2 CLOB book states and spacetime physics from
tick logs (JSONL) and synthetic jump-diffusion feeds to construct normalized
feature matrices (N, 32) and classification targets (N,) for QuoLasGoldMicroscopeNet.

Target Classes:
- 0: UP (BUY_YES conviction)
- 1: DOWN (BUY_NO conviction)
- 2: WAIT (Chop / Dead-zone / High toxicity)
"""

from __future__ import annotations

from decimal import Decimal
import json
import logging
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np

from app_2_execution_bot.ml.gold_feature_extractor import GoldOrderflowFeatureExtractor
from shared.schemas import L2BookState, OrderSide, TradeEvent

logger = logging.getLogger(__name__)


class GoldDatasetBuilder:
    """Extracts 32-D feature vectors and directional labels for model training."""

    FEATURE_DIM: int = 32
    CLASS_UP: int = 0
    CLASS_DOWN: int = 1
    CLASS_WAIT: int = 2

    def __init__(
        self,
        extractor: Optional[GoldOrderflowFeatureExtractor] = None,
        default_strike: Decimal = Decimal("2500.00"),
        dead_zone_threshold: Decimal = Decimal("0.75"),
        volatility: float = 2.50,
    ) -> None:
        self.extractor = extractor or GoldOrderflowFeatureExtractor(
            target_depth=15,
            default_gold_volatility=volatility,
        )
        self.default_strike = default_strike
        self.dead_zone_threshold = dead_zone_threshold
        self.volatility = volatility

    def parse_tick_line(self, line: Union[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Safely parse a line of JSON tick data."""
        if isinstance(line, dict):
            return line
        line = line.strip()
        if not line:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    def build_book_from_snapshot(self, record: Dict[str, Any]) -> L2BookState:
        """Construct an L2BookState from parsed tick dictionary."""
        ticker = record.get("market_ticker") or record.get("ticker") or "KXGOLD15M-SAMPLE"
        book = L2BookState(market_ticker=ticker)

        # Populate yes_book
        yes_levels = record.get("yes_levels") or record.get("bids") or []
        for item in yes_levels:
            if isinstance(item, dict):
                p = Decimal(str(item.get("price", "0.00")))
                q = Decimal(str(item.get("quantity", item.get("count", "0"))))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                p = Decimal(str(item[0]))
                q = Decimal(str(item[1]))
            else:
                continue
            if p > 0:
                book.yes_book[p] = q

        # Populate no_book
        no_levels = record.get("no_levels") or record.get("asks") or []
        for item in no_levels:
            if isinstance(item, dict):
                p = Decimal(str(item.get("price", "0.00")))
                q = Decimal(str(item.get("quantity", item.get("count", "0"))))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                p = Decimal(str(item[0]))
                q = Decimal(str(item[1]))
            else:
                continue
            if p > 0:
                book.no_book[p] = q

        return book

    def build_dataset_from_records(
        self,
        records: Sequence[Dict[str, Any]],
        forward_horizon: int = 10,
        target_strike: Optional[Decimal] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Extract 32-D features and forward labels from a chronological sequence of ticks.

        Args:
            records: Chronological sequence of tick/orderbook snapshot dictionaries.
            forward_horizon: Number of ticks forward to evaluate price movement for label.
            target_strike: Option strike price for moneyness calculation.

        Returns:
            X: np.ndarray of shape (M, 32), float32.
            y: np.ndarray of shape (M,), int64 in {0, 1, 2}.
        """
        strike = target_strike or self.default_strike
        n = len(records)
        if n <= forward_horizon:
            return np.empty((0, self.FEATURE_DIM), dtype=np.float32), np.empty((0,), dtype=np.int64)

        features_list: List[np.ndarray] = []
        labels_list: List[int] = []

        # First pass: collect books, spots, and time parameters
        spots: List[Decimal] = []
        books: List[L2BookState] = []
        taus: List[float] = []

        for i, rec in enumerate(records):
            book = self.build_book_from_snapshot(rec)
            books.append(book)

            # Spot derivation
            raw_spot = rec.get("spot_price") or rec.get("spot")
            if raw_spot is not None:
                spot = Decimal(str(raw_spot))
            else:
                # Approximate spot from binary price midpoint if not explicit
                best_bid = max(book.yes_book.keys()) if book.yes_book else Decimal("0.50")
                best_ask = Decimal("1.00") - max(book.no_book.keys()) if book.no_book else Decimal("0.52")
                mid_bin = (best_bid + best_ask) / Decimal("2")
                # Offset relative to strike
                spot = strike + (mid_bin - Decimal("0.50")) * Decimal("5.00")
            spots.append(spot)

            tau = float(rec.get("time_remaining_s", max(10, 900 - i * 5)))
            taus.append(tau)

        # Second pass: compute features and forward labels
        rolling_twap: List[Decimal] = []
        for i in range(n - forward_horizon):
            book = books[i]
            cur_spot = spots[i]
            tau = taus[i]

            rolling_twap.append(cur_spot)
            if len(rolling_twap) > 60:
                rolling_twap.pop(0)
            twap_60s = sum(rolling_twap) / Decimal(str(len(rolling_twap)))

            # Feature extraction
            feat = self.extractor.extract_features(
                book=book,
                target_strike=strike,
                current_spot=cur_spot,
                time_to_expiry_s=tau,
                twap_60s=twap_60s,
                spot_volatility=self.volatility,
            )

            # Forward outcome label calculation
            forward_spot = spots[i + forward_horizon]
            spot_diff = forward_spot - cur_spot

            # Classification rules with dead-zone noise filter
            if spot_diff >= self.dead_zone_threshold:
                label = self.CLASS_UP
            elif spot_diff <= -self.dead_zone_threshold:
                label = self.CLASS_DOWN
            else:
                label = self.CLASS_WAIT

            features_list.append(feat)
            labels_list.append(label)

        X = np.array(features_list, dtype=np.float32)
        y = np.array(labels_list, dtype=np.int64)
        return X, y

    def load_from_file(
        self,
        file_path: Union[str, Path],
        forward_horizon: int = 10,
        target_strike: Optional[Decimal] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Load and extract dataset from a JSONL tick file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        records = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                rec = self.parse_tick_line(line)
                if rec:
                    records.append(rec)

        return self.build_dataset_from_records(
            records=records,
            forward_horizon=forward_horizon,
            target_strike=target_strike,
        )

    def generate_synthetic_samples(
        self,
        num_samples: int = 1200,
        seed: int = 42,
        base_strike: Decimal = Decimal("2500.00"),
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Generate high-fidelity synthetic orderflow & spacetime samples.

        Used for model pre-training, test gauntlets, and cold-start training
        under jump-diffusion orderbook dynamics.
        """
        rng = np.random.RandomState(seed)
        features: List[np.ndarray] = []
        labels: List[int] = []

        # Split roughly equally across classes: 40% UP, 40% DOWN, 20% WAIT
        for i in range(num_samples):
            # Pick intended target class
            r = rng.rand()
            if r < 0.40:
                intended_class = self.CLASS_UP
                drift = rng.uniform(0.80, 2.50)
                ofi_bias = rng.uniform(0.35, 0.90)
                z_bias = rng.uniform(0.50, 2.50)
            elif r < 0.80:
                intended_class = self.CLASS_DOWN
                drift = -rng.uniform(0.80, 2.50)
                ofi_bias = -rng.uniform(0.35, 0.90)
                z_bias = -rng.uniform(0.50, 2.50)
            else:
                intended_class = self.CLASS_WAIT
                drift = rng.uniform(-0.40, 0.40)
                ofi_bias = rng.uniform(-0.20, 0.20)
                z_bias = rng.uniform(-0.40, 0.40)

            # Construct synthetic 32-D vector matching physics
            feat = np.zeros(self.FEATURE_DIM, dtype=np.float32)
            # Microstructure
            feat[0] = float(rng.uniform(0.01, 0.04))  # spread
            feat[1] = float(np.clip(ofi_bias + rng.normal(0, 0.1), -1.0, 1.0))  # ofi_l1
            feat[2] = float(np.clip(ofi_bias * 0.85 + rng.normal(0, 0.1), -1.0, 1.0))  # ofi_l5
            feat[3] = float(np.clip(ofi_bias * 0.70 + rng.normal(0, 0.1), -1.0, 1.0))  # ofi_l15
            feat[4] = float(drift * 1.5 + rng.normal(0, 0.2))  # cvd
            feat[5] = float(rng.uniform(1.2, 3.8))  # entropy
            feat[6] = float(rng.uniform(0.20, 0.55))  # vpin
            feat[7] = float(rng.uniform(0.0, 0.15))  # spoof bid
            feat[8] = float(rng.uniform(0.0, 0.15))  # spoof ask
            feat[9] = float(rng.uniform(0.0, 0.10))  # bid absorption
            feat[10] = float(rng.uniform(0.0, 0.10))  # ask absorption
            feat[11] = float(rng.poisson(1.0))  # whale count
            feat[12] = float(rng.uniform(0.5, 2.0))  # layering

            # 15 Spatial decay layers
            decay = np.exp(-0.425 * np.arange(15))
            spatial_noise = rng.normal(0, 0.05, 15)
            feat[13:28] = (decay * ofi_bias + spatial_noise).astype(np.float32)

            # Spacetime features
            tau = float(rng.uniform(60.0, 850.0))
            feat[28] = float(z_bias + rng.normal(0, 0.15))  # moneyness z-score
            feat[29] = float(tau / 900.0)  # tau norm
            feat[30] = float(ofi_bias * 0.5 + rng.normal(0, 0.1))  # ofi accel
            feat[31] = float(drift * 0.4 + rng.normal(0, 0.1))  # twap delta

            features.append(feat)
            labels.append(intended_class)

        X = np.array(features, dtype=np.float32)
        y = np.array(labels, dtype=np.int64)
        return X, y

    def train_val_split(
        self,
        X: np.ndarray,
        y: np.ndarray,
        val_ratio: float = 0.20,
        stratified: bool = True,
        seed: int = 42,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Split dataset into train and validation sets with optional stratification."""
        n = len(y)
        if n == 0:
            return (
                np.empty((0, self.FEATURE_DIM), dtype=np.float32),
                np.empty((0, self.FEATURE_DIM), dtype=np.float32),
                np.empty((0,), dtype=np.int64),
                np.empty((0,), dtype=np.int64),
            )

        rng = np.random.RandomState(seed)

        if stratified:
            train_indices: List[int] = []
            val_indices: List[int] = []
            for c in np.unique(y):
                idx = np.where(y == c)[0]
                rng.shuffle(idx)
                n_val_c = max(1, int(len(idx) * val_ratio)) if len(idx) > 1 else 0
                val_indices.extend(idx[:n_val_c])
                train_indices.extend(idx[n_val_c:])
            train_idx = np.array(train_indices)
            val_idx = np.array(val_indices)
            rng.shuffle(train_idx)
            rng.shuffle(val_idx)
        else:
            indices = np.arange(n)
            rng.shuffle(indices)
            n_val = int(n * val_ratio)
            val_idx = indices[:n_val]
            train_idx = indices[n_val:]

        return X[train_idx], X[val_idx], y[train_idx], y[val_idx]

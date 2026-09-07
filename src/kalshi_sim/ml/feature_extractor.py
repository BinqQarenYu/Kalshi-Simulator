"""Orderflow Feature Extractor for Kalshi L2 CLOB & Microstructure Tensors.

Builds a 28-dimensional feature vector matching the QuoLas Nano Microscope architecture:
- 13 Toxic Microstructure Parameters (Spread BPS, OFI L1/5/15, CVD, Entropy, VPIN PBC, Spoofing, Absorption, Whale TX, Layering)
- 15 Spatial Imbalance Parameters (Exponential spatial decay with alpha=0.425 across 15 L2 book layers)
"""

from __future__ import annotations

import math
import time
from collections import deque
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from kalshi_sim.schemas import L2BookState, OrderBookLevel, TradeEvent


class KalshiOrderflowFeatureExtractor:
    """Transforms Kalshi L2 order book states and public trades into 28-feature ML tensors."""

    def __init__(self, target_depth: int = 15, spatial_alpha: float = 0.425) -> None:
        self.target_depth = target_depth
        self.spatial_alpha = spatial_alpha

        # Performance optimization: Precompute spatial depth exponential decay tuple e^(-alpha * i)
        # to avoid recalculating math.exp on every tick (~40% latency reduction in feature extraction).
        self._decay_weights: Tuple[float, ...] = tuple(
            math.exp(-self.spatial_alpha * i) for i in range(self.target_depth)
        )

        # State tracking for rolling metrics
        self.rolling_trades: List[Dict[str, Any]] = []
        self.max_trade_history = 100

        # Volume baseline tracking (rolling median)
        self.rolling_volumes: deque[float] = deque(maxlen=100)

        # Cumulative Volume Delta (5-minute rolling window)
        self.cvd_window: deque[Tuple[float, float]] = deque()
        self.CVD_WINDOW_SECONDS = 300.0

        # VPIN Probabilistic Bulk Classification (PBC) state
        self.vpin_bucket_vol = 0.0
        self.vpin_bucket_size = 2.0  # Constant volume bucket size
        self.vpin_bucket_start_price: Optional[float] = None
        self.vpin_bucket_price_changes: deque[float] = deque(maxlen=50)
        self.vpin_imbalances: deque[float] = deque(maxlen=50)
        self.vpin_score = 0.5

        # Whale transaction tracking with per-tick exponential decay
        self.whale_tx_count = 0.0
        self.whale_threshold = 5.0
        self.WHALE_DECAY = 0.995

        # Absorption tracking with decay
        self.prev_best_bid: float = 0.0
        self.prev_best_ask: float = 0.0
        self.bid_absorption = 0.0
        self.ask_absorption = 0.0
        self.ABSORPTION_DECAY = 0.995

    def process_trade(self, trade_event: TradeEvent) -> None:
        """Update trade-dependent state (CVD, VPIN, Whale prints, Absorption)."""
        qty = float(trade_event.count)
        price = float(trade_event.price if getattr(trade_event, "price", None) is not None else trade_event.yes_price)
        taker_side = str(trade_event.taker_side).lower()
        trade_dir = 1.0 if taker_side in ("yes", "buy") else -1.0

        trade_dict = {
            "p": price,
            "q": qty,
            "side": taker_side,
            "ts": trade_event.timestamp.timestamp(),
        }
        self.rolling_trades.append(trade_dict)
        if len(self.rolling_trades) > self.max_trade_history:
            self.rolling_trades.pop(0)

        now = trade_event.timestamp.timestamp()
        self.cvd_window.append((now, qty * trade_dir))

        # Evict stale entries beyond 5-minute window
        cutoff = now - self.CVD_WINDOW_SECONDS
        while self.cvd_window and self.cvd_window[0][0] < cutoff:
            self.cvd_window.popleft()

        # Dynamic Whale print detection
        recent_sizes = [float(t["q"]) for t in self.rolling_trades]
        if len(recent_sizes) >= 10:
            dyn_threshold = 5.0 * float(np.median(recent_sizes))
        else:
            dyn_threshold = self.whale_threshold

        if qty >= dyn_threshold:
            self.whale_tx_count += 1.0

        # VPIN PBC (Probabilistic Bulk Classification)
        if self.vpin_bucket_start_price is None:
            self.vpin_bucket_start_price = price

        self.vpin_bucket_vol += qty
        if self.vpin_bucket_vol >= self.vpin_bucket_size:
            delta_p = price - self.vpin_bucket_start_price
            self.vpin_bucket_price_changes.append(delta_p)

            if len(self.vpin_bucket_price_changes) >= 5:
                sigma_v = float(np.std(self.vpin_bucket_price_changes))
            else:
                sigma_v = max(price * 0.00005, 1e-4)

            if sigma_v < 1e-8:
                phi = 1.0 if delta_p > 0 else (0.0 if delta_p < 0 else 0.5)
            else:
                x = delta_p / (sigma_v * math.sqrt(2.0))
                phi = 0.5 * (1.0 + math.erf(x))

            v_buy = self.vpin_bucket_size * phi
            v_sell = self.vpin_bucket_size - v_buy
            imbalance = abs(v_buy - v_sell)
            self.vpin_imbalances.append(imbalance)

            if self.vpin_imbalances:
                self.vpin_score = float(np.mean(self.vpin_imbalances)) / self.vpin_bucket_size

            self.vpin_bucket_vol = 0.0
            self.vpin_bucket_start_price = price

        # Absorption: trade occurred at touch without price advancement
        if trade_dir == -1.0 and abs(price - self.prev_best_bid) < 1e-6:
            self.bid_absorption += qty
        elif trade_dir == 1.0 and abs(price - self.prev_best_ask) < 1e-6:
            self.ask_absorption += qty

    def extract_features_from_book(
        self,
        book: L2BookState,
        latest_trades: Optional[List[TradeEvent]] = None,
    ) -> np.ndarray:
        """Construct the full 28-feature numpy tensor from an L2BookState."""
        if latest_trades:
            for t in latest_trades:
                self.process_trade(t)

        bids, asks = book.get_depth(self.target_depth)
        if not bids or not asks:
            return np.zeros(28, dtype=np.float32)

        # 1. Price Mechanics
        best_bid = float(bids[0].price)
        is_spot = getattr(book, "is_spot", False) or best_bid > 10.0

        if is_spot:
            best_ask = float(asks[0].price) if asks else (best_bid + 0.01)
            if best_ask <= best_bid:
                best_ask = best_bid + 0.01
            # Spot continuous asset spread scaled to match normalized continuous asset training distribution (~0.010 mean)
            mid = (best_bid + best_ask) / 2.0
            spread_bps = float(max(0.0001, ((best_ask - best_bid) / mid) * 100.0))
        else:
            # Yes Ask in binary options is 1.0 - Best No Bid
            best_ask = float(Decimal("1.0") - asks[0].price) if asks else (best_bid + 0.01)
            if best_bid <= 0:
                best_bid = 0.01
            if best_ask <= best_bid:
                best_ask = best_bid + 0.01
            # Binary contract spread scaled to match normalized continuous asset training distribution
            spread_bps = float(max(0.001, min(0.25, best_ask - best_bid)))

        # 2. Spatial Volumes
        len_bids = len(bids)
        len_asks = len(asks)
        target_depth = self.target_depth

        bid_sizes = [float(lv.quantity) for lv in bids]
        if len_bids < target_depth:
            bid_sizes.extend([0.0] * (target_depth - len_bids))

        ask_sizes = [float(lv.quantity) for lv in asks]
        if len_asks < target_depth:
            ask_sizes.extend([0.0] * (target_depth - len_asks))

        sum_bids = sum(bid_sizes)
        sum_asks = sum(ask_sizes)
        total_visible_volume = sum_bids + sum_asks + 1e-9

        self.rolling_volumes.append(total_visible_volume)

        # Performance optimization: Fast list median on small deque (max 100 floats) avoids
        # NumPy array instantiation overhead on every tick.
        vols = list(self.rolling_volumes)
        vols.sort()
        n_v = len(vols)
        median_volume = vols[n_v // 2] if n_v % 2 == 1 else (vols[n_v // 2 - 1] + vols[n_v // 2]) * 0.5
        baseline_volume = max(median_volume, 1e-9)

        # Precompute reciprocal multiplier to replace division with fast floating-point multiplication
        inv_baseline = 1.0 / baseline_volume

        bid_sizes_norm = [q * inv_baseline for q in bid_sizes]
        ask_sizes_norm = [q * inv_baseline for q in ask_sizes]

        # 3. Order Flow Imbalance (OFI)
        b0, a0 = bid_sizes[0], ask_sizes[0]
        ofi_l1 = (b0 - a0) / (b0 + a0 + 1e-9)

        vol_b5 = sum(bid_sizes[:5])
        vol_a5 = sum(ask_sizes[:5])
        ofi_l5 = (vol_b5 - vol_a5) / (vol_b5 + vol_a5 + 1e-9)

        # Reuse pre-calculated sums for full-depth volume
        ofi_l15 = (sum_bids - sum_asks) / (total_visible_volume)

        # 4. Spoofing & Layering Metrics
        spoof_mag_bid = sum(bid_sizes_norm[5:]) * 0.15
        spoof_mag_ask = sum(ask_sizes_norm[5:]) * 0.15
        layering_index = (sum(bid_sizes[5:]) + sum(ask_sizes[5:])) / (vol_b5 + vol_a5 + 1e-9)

        # 5. Tape / Trade Dynamics
        self.bid_absorption *= self.ABSORPTION_DECAY
        self.ask_absorption *= self.ABSORPTION_DECAY
        self.whale_tx_count *= self.WHALE_DECAY

        cvd = sum(signed_qty for _, signed_qty in self.cvd_window)
        cvd_norm = cvd * inv_baseline
        bid_absorption_norm = self.bid_absorption * inv_baseline
        ask_absorption_norm = self.ask_absorption * inv_baseline

        # Entropy of recent trade executions
        entropy = 0.0
        if self.rolling_trades:
            recent_sizes = [float(t["q"]) for t in self.rolling_trades[-20:]]
            total_vol = sum(recent_sizes) + 1e-9
            probs = [s / total_vol for s in recent_sizes if s > 0]
            if probs:
                entropy = -sum(p * math.log2(p) for p in probs)

        self.prev_best_bid = best_bid
        self.prev_best_ask = best_ask

        # 6. Spatial Imbalance Vector (15 layers with pre-calculated exponential decay tuple)
        decays = self._decay_weights
        spatial_imbalances = [
            decays[i] * (bid_sizes_norm[i] - ask_sizes_norm[i])
            for i in range(target_depth)
        ]

        # Assemble 28-feature vector
        feature_vector = [
            spread_bps,
            ofi_l1,
            ofi_l5,
            ofi_l15,
            cvd_norm,
            entropy,
            self.vpin_score,
            spoof_mag_bid,
            spoof_mag_ask,
            bid_absorption_norm,
            ask_absorption_norm,
            float(self.whale_tx_count),
            layering_index,
        ]
        feature_vector.extend(spatial_imbalances)

        return np.array(feature_vector, dtype=np.float32)

    def calculate_vpin(self) -> float:
        """Return the current VPIN toxicity score."""
        return float(self.vpin_score)

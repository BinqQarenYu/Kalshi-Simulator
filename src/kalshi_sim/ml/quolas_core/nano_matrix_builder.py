"""Nano Microscope Matrix Tensor Builder (Transplanted from QuoLas Core).

Transforms raw Binance @depth20 and @trade ticks into a normalized
Machine Learning Tensor for the Orderflow AI (models/nano_microscope_overhauled.onnx).
Produces the exact 28-feature tensor:
- 13 Toxic Vector Parameters
- 15 Spatial Order Book Decayed Imbalance Parameters (alpha = 0.425)
"""

from __future__ import annotations

import logging
import math
import time
from collections import deque
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger("kalshi_sim.ml.quolas_core.nano_matrix_builder")


class NanoMatrixBuilder:
    """AI Expert Builder Module: Nano Microscope Matrix.

    Transforms raw Binance @depth20 / @trade ticks into a normalized
    Machine Learning Tensor for the Orderflow AI.
    """

    def __init__(self, target_depth: int = 15) -> None:
        self.target_depth = target_depth

        # State tracking for rolling metrics
        self.rolling_trades: List[Dict] = []
        self.max_trade_history = 100

        # Volume tracking for rolling median normalization
        self.rolling_volumes: deque = deque(maxlen=100)

        # CVD: rolling 5-minute window instead of unbounded accumulator
        self.cvd_window: deque = deque()  # (timestamp, signed_qty) pairs
        self.CVD_WINDOW_SECONDS = 300  # 5 minutes

        # Microstructure specific state (VPIN PBC)
        self.vpin_bucket_vol = 0.0
        self.vpin_bucket_size = 2.0  # 2 BTC per bucket
        self.vpin_bucket_start_price: Optional[float] = None
        self.vpin_bucket_price_changes: deque = deque(maxlen=50)
        self.vpin_imbalances: deque = deque(maxlen=50)
        self.vpin_score = 0.5

        # Whale TX: exponential decay instead of unbounded counter
        self.whale_tx_count = 0.0  # float for decay
        self.whale_threshold = 5.0  # BTC
        self.WHALE_DECAY = 0.995  # Per-tick decay factor

        self.prev_best_bid = 0.0
        self.prev_best_ask = 0.0

        # Absorption tracking — slower decay
        self.bid_absorption = 0.0
        self.ask_absorption = 0.0
        self.ABSORPTION_DECAY = 0.995

        # Cached last tensor for non-blocking retrieval
        self._last_tensor: np.ndarray = np.zeros(28, dtype=np.float32)

    def _process_trade(self, trade: Dict, best_bid: float, best_ask: float) -> None:
        """Process a single trade tick and update all trade-dependent state."""
        self.rolling_trades.append(trade)
        if len(self.rolling_trades) > self.max_trade_history:
            self.rolling_trades.pop(0)

        qty = float(trade.get("q", 0.0))
        price = float(trade.get("p", 0.0))
        is_buyer_maker = trade.get("m", False)
        trade_dir = -1 if is_buyer_maker else 1

        # CVD — rolling window
        ts = trade.get("E", trade.get("T", 0))
        if ts > 0:
            now = ts / 1000.0
        else:
            now = time.time()

        self.cvd_window.append((now, qty * trade_dir))
        cutoff = now - self.CVD_WINDOW_SECONDS
        while self.cvd_window and self.cvd_window[0][0] < cutoff:
            self.cvd_window.popleft()

        # Whale TX — dynamic threshold based on rolling trades median
        recent_sizes = [float(t.get("q", 0.0)) for t in self.rolling_trades]
        if len(recent_sizes) >= 10:
            dynamic_whale_threshold = 5.0 * float(np.median(recent_sizes))
        else:
            dynamic_whale_threshold = self.whale_threshold

        if qty >= dynamic_whale_threshold:
            self.whale_tx_count += 1.0

        # VPIN Bucket Tracking using Probabilistic Bulk Classification (PBC)
        if self.vpin_bucket_start_price is None:
            self.vpin_bucket_start_price = price

        self.vpin_bucket_vol += qty

        if self.vpin_bucket_vol >= self.vpin_bucket_size:
            delta_p = price - self.vpin_bucket_start_price
            self.vpin_bucket_price_changes.append(delta_p)

            if len(self.vpin_bucket_price_changes) >= 5:
                sigma_v = float(np.std(list(self.vpin_bucket_price_changes)))
            else:
                sigma_v = max(price * 0.00005, 1e-4)  # 0.5 BPS baseline floor

            if sigma_v < 1e-8:
                phi = 1.0 if delta_p > 0 else (0.0 if delta_p < 0 else 0.5)
            else:
                x = delta_p / (sigma_v * math.sqrt(2.0))
                phi = 0.5 * (1.0 + math.erf(x))

            v_buy = self.vpin_bucket_size * phi
            v_sell = self.vpin_bucket_size - v_buy
            imbalance = abs(v_buy - v_sell)
            self.vpin_imbalances.append(imbalance)

            self.vpin_score = float(np.mean(list(self.vpin_imbalances))) / self.vpin_bucket_size

            # Reset bucket
            self.vpin_bucket_vol = 0.0
            self.vpin_bucket_start_price = price

        # Absorption Rate (Trade happened but best price didn't move)
        if trade_dir == -1 and best_bid == self.prev_best_bid:
            self.bid_absorption += qty
        elif trade_dir == 1 and best_ask == self.prev_best_ask:
            self.ask_absorption += qty

    def extract_features(
        self,
        depth_payload: Dict,
        latest_trade: Optional[Dict] = None,
        trade_batch: Optional[List[Dict]] = None,
    ) -> np.ndarray:
        """Build the 28-feature tensor from a depth snapshot and trade data.

        Args:
            depth_payload: Binance @depth20 or REST orderbook snapshot.
            latest_trade: Single trade tick (backward compat).
            trade_batch: List of trade ticks accumulated since last depth tick.

        Returns:
            np.ndarray of shape (28,) and dtype float32.
        """
        bids = (depth_payload.get("b") or depth_payload.get("bids", []))[:self.target_depth]
        asks = (depth_payload.get("a") or depth_payload.get("asks", []))[:self.target_depth]

        if not bids or not asks:
            return np.zeros(28, dtype=np.float32)

        # 1. CORE PRICE MECHANICS
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        if best_bid <= 0 or best_ask <= 0:
            return np.zeros(28, dtype=np.float32)

        spread_bps = math.log(best_ask / best_bid) * 10000.0

        # 2. SPATIAL ORDERBOOK Imbalances and Volumes
        bid_sizes = []
        for i in range(self.target_depth):
            if i < len(bids):
                bid_sizes.append(float(bids[i][1]))
            else:
                bid_sizes.append(0.0)

        ask_sizes = []
        for i in range(self.target_depth):
            if i < len(asks):
                ask_sizes.append(float(asks[i][1]))
            else:
                ask_sizes.append(0.0)

        total_visible_volume = sum(bid_sizes) + sum(ask_sizes) + 1e-9
        self.rolling_volumes.append(total_visible_volume)

        median_volume = float(np.median(list(self.rolling_volumes)))
        baseline_volume = max(median_volume, 1e-9)

        bid_sizes_norm = [q / baseline_volume for q in bid_sizes]
        ask_sizes_norm = [q / baseline_volume for q in ask_sizes]

        # 3. ORDER FLOW IMBALANCE (OFI)
        ofi_l1 = (bid_sizes[0] - ask_sizes[0]) / (bid_sizes[0] + ask_sizes[0] + 1e-9)
        vol_b5, vol_a5 = sum(bid_sizes[:5]), sum(ask_sizes[:5])
        ofi_l5 = (vol_b5 - vol_a5) / (vol_b5 + vol_a5 + 1e-9)
        vol_b15, vol_a15 = sum(bid_sizes), sum(ask_sizes)
        ofi_l15 = (vol_b15 - vol_a15) / (vol_b15 + vol_a15 + 1e-9)

        # 4. SPOOFING & LAYERING (Toxic Metrics)
        spoof_mag_bid = sum(bid_sizes_norm[5:]) * 0.15
        spoof_mag_ask = sum(ask_sizes_norm[5:]) * 0.15
        layering_index = (sum(bid_sizes[5:]) + sum(ask_sizes[5:])) / (sum(bid_sizes[:5]) + sum(ask_sizes[:5]) + 1e-9)

        # 5. TAPE / TRADE DYNAMICS (Toxic Metrics)
        entropy = 0.0
        self.bid_absorption *= self.ABSORPTION_DECAY
        self.ask_absorption *= self.ABSORPTION_DECAY
        self.whale_tx_count *= self.WHALE_DECAY

        trades_to_process = trade_batch if trade_batch else ([latest_trade] if latest_trade else [])
        for trade in trades_to_process:
            self._process_trade(trade, best_bid, best_ask)

        cvd = sum(signed_qty for _, signed_qty in self.cvd_window)

        if self.rolling_trades:
            recent_sizes = [float(t.get("q", 0.0)) for t in self.rolling_trades[-20:]]
            if recent_sizes:
                total_vol = sum(recent_sizes) + 1e-9
                probs = [s / total_vol for s in recent_sizes if s > 0]
                entropy = -sum(p * math.log2(p) for p in probs)

        self.prev_best_bid = best_bid
        self.prev_best_ask = best_ask

        cvd_norm = cvd / baseline_volume
        bid_absorption_norm = self.bid_absorption / baseline_volume
        ask_absorption_norm = self.ask_absorption / baseline_volume

        # 6. SPATIAL ORDERBOOK Imbalance (15 features with alpha = 0.425 spatial decay)
        spatial_imbalances = []
        alpha = 0.425
        for i in range(self.target_depth):
            decay = math.exp(-alpha * i)
            b_norm = bid_sizes_norm[i]
            a_norm = ask_sizes_norm[i]
            spatial_imbalances.append(decay * (b_norm - a_norm))

        feature_vector = [
            # 13 TOXIC PARAMETERS
            spread_bps,                  # 1
            ofi_l1,                      # 2
            ofi_l5,                      # 3
            ofi_l15,                     # 4
            cvd_norm,                    # 5
            entropy,                     # 6
            self.vpin_score,             # 7
            spoof_mag_bid,               # 8
            spoof_mag_ask,               # 9
            bid_absorption_norm,         # 10
            ask_absorption_norm,         # 11
            float(self.whale_tx_count),  # 12
            layering_index,              # 13
        ]
        # 15 SPATIAL IMBALANCE PARAMETERS
        feature_vector.extend(spatial_imbalances)

        tensor = np.array(feature_vector, dtype=np.float32)
        # Sanitization: replace any NaN or Inf with 0.0
        tensor = np.nan_to_num(tensor, nan=0.0, posinf=0.0, neginf=0.0)
        self._last_tensor = tensor
        return tensor

    def get_current_tensor(self) -> np.ndarray:
        """Return the most recently generated 28-feature tensor."""
        return self._last_tensor.copy()

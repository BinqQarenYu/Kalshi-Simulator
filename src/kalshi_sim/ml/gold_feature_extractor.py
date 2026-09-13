"""Gold Orderflow & Spacetime Physics Feature Extractor (32-Dimensional Tensor).

Constructs the 3rd-generation 32-dimensional feature vector (D* = 32) tailored for
Gold (XAU / PAXG) orderflow and digital contract spacetime dynamics:

- 13 Toxic Microstructure Features (Spread BPS, OFI L1/5/15, CVD, Entropy, VPIN PBC, Spoofing, Layering, Whales, Absorption)
- 15 Spatial Imbalance Features (Exponential spatial decay with alpha=0.425 across 15 L2 book levels)
- 4 Spacetime & Contract Physics Features:
    f[28] = Normalized Moneyness: z_t = (S_t - K) / (sigma * sqrt(tau / 60))
    f[29] = Time-to-Expiry Normalized Fraction: tau / 900.0
    f[30] = OFI Acceleration: Delta OFI_L5 = OFI_t - OFI_{t-3}
    f[31] = Settlement TWAP Delta: (S_t - TWAP_60s) / sigma
"""

from __future__ import annotations

from collections import deque
from decimal import Decimal
import itertools
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from kalshi_sim.schemas import L2BookState, TradeEvent


class GoldOrderflowFeatureExtractor:
    """Extracts 32-dimensional orderflow + spacetime physics tensors for Gold (XAU / PAXG)."""

    FEATURE_DIM: int = 32

    def __init__(
        self,
        target_depth: int = 15,
        spatial_alpha: float = 0.425,
        default_gold_volatility: float = 2.50,  # $2.50/oz typical 1-min Gold spot standard deviation
    ) -> None:
        self.target_depth = target_depth
        self.spatial_alpha = spatial_alpha
        self.default_gold_volatility = default_gold_volatility

        # Precompute exponential decay weights: e^(-alpha * i)
        self._decay_weights: Tuple[float, ...] = tuple(
            math.exp(-self.spatial_alpha * i) for i in range(self.target_depth)
        )

        # Rolling state tracking
        self.rolling_trades: deque[Dict[str, Any]] = deque(maxlen=100)
        self.rolling_volumes: deque[float] = deque(maxlen=100)
        self.ofi_l5_history: deque[float] = deque(maxlen=10)

        # Cumulative Volume Delta (5-minute rolling window)
        self.cvd_window: deque[Tuple[float, float]] = deque()
        self._running_cvd: float = 0.0
        self.CVD_WINDOW_SECONDS: float = 300.0

        # VPIN Probabilistic Bulk Classification
        self.vpin_bucket_vol: float = 0.0
        self.vpin_bucket_size: float = 1.5  # Constant volume bucket size for Gold
        self.vpin_bucket_start_price: Optional[float] = None
        self.vpin_bucket_price_changes: deque[float] = deque(maxlen=50)
        self.vpin_imbalances: deque[float] = deque(maxlen=50)
        self.vpin_score: float = 0.5

        # Whale transaction tracking
        self.whale_tx_count: float = 0.0
        self.whale_threshold: float = 5.0
        self.WHALE_DECAY: float = 0.995

        # Absorption tracking
        self.prev_best_bid: float = 0.0
        self.prev_best_ask: float = 0.0
        self.bid_absorption: float = 0.0
        self.ask_absorption: float = 0.0
        self.ABSORPTION_DECAY: float = 0.995

        # Cached entropy & pre-allocated 32-element feature buffer
        self._cached_entropy: float = 0.0
        self._feature_buffer: np.ndarray = np.zeros(self.FEATURE_DIM, dtype=np.float32)

    def _update_cached_entropy(self) -> None:
        """Recalculate trade size entropy whenever trade history updates."""
        if not self.rolling_trades:
            self._cached_entropy = 0.0
            return

        start_idx = max(0, len(self.rolling_trades) - 20)
        recent_sizes = [float(t["q"]) for t in itertools.islice(self.rolling_trades, start_idx, None)]
        total_vol = sum(recent_sizes) + 1e-9
        probs = [s / total_vol for s in recent_sizes if s > 0]
        if probs:
            self._cached_entropy = -sum(p * math.log2(p) for p in probs)
        else:
            self._cached_entropy = 0.0

    def process_trade(self, trade_event: TradeEvent) -> None:
        """Update trade-dependent state (CVD, VPIN, Whales, Absorption)."""
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
        self._update_cached_entropy()

        now = trade_event.timestamp.timestamp()
        signed_qty = qty * trade_dir
        self.cvd_window.append((now, signed_qty))
        self._running_cvd += signed_qty

        # Evict stale entries beyond 5-minute window in O(1)
        cutoff = now - self.CVD_WINDOW_SECONDS
        while self.cvd_window and self.cvd_window[0][0] < cutoff:
            _, evicted_signed = self.cvd_window.popleft()
            self._running_cvd -= evicted_signed

        # Dynamic Whale print detection
        if len(self.rolling_trades) >= 10:
            recent_sizes = [t["q"] for t in self.rolling_trades]
            recent_sizes.sort()
            n_q = len(recent_sizes)
            med_q = recent_sizes[n_q // 2] if n_q % 2 == 1 else (recent_sizes[n_q // 2 - 1] + recent_sizes[n_q // 2]) * 0.5
            dyn_threshold = 4.0 * med_q
        else:
            dyn_threshold = self.whale_threshold

        if qty >= dyn_threshold:
            self.whale_tx_count += 1.0

        # VPIN Probabilistic Bulk Classification
        if self.vpin_bucket_start_price is None:
            self.vpin_bucket_start_price = price

        self.vpin_bucket_vol += qty
        if self.vpin_bucket_vol >= self.vpin_bucket_size:
            delta_p = price - self.vpin_bucket_start_price
            self.vpin_bucket_price_changes.append(delta_p)

            if len(self.vpin_bucket_price_changes) >= 5:
                pcs = list(self.vpin_bucket_price_changes)
                mean_pc = sum(pcs) / len(pcs)
                variance = sum((x - mean_pc) ** 2 for x in pcs) / len(pcs)
                sigma_v = math.sqrt(variance)
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
                self.vpin_score = (sum(self.vpin_imbalances) / len(self.vpin_imbalances)) / self.vpin_bucket_size

            self.vpin_bucket_vol = 0.0
            self.vpin_bucket_start_price = price

        # Absorption tracking
        if trade_dir == -1.0 and abs(price - self.prev_best_bid) < 1e-6:
            self.bid_absorption += qty
        elif trade_dir == 1.0 and abs(price - self.prev_best_ask) < 1e-6:
            self.ask_absorption += qty

    def extract_features(
        self,
        book: L2BookState,
        latest_trades: Optional[List[TradeEvent]] = None,
        target_strike: Optional[Decimal] = None,
        current_spot: Optional[Decimal] = None,
        time_to_expiry_s: Optional[float] = None,
        twap_60s: Optional[Decimal] = None,
        spot_volatility: Optional[float] = None,
    ) -> np.ndarray:
        """Construct the full 32-feature numpy tensor from an L2BookState and spacetime parameters."""
        if latest_trades:
            for t in latest_trades:
                self.process_trade(t)

        # 1. Book Depth Extraction
        if hasattr(book, "get_depth_tuples"):
            top_yes, top_no = book.get_depth_tuples(self.target_depth)
            if not top_yes or not top_no:
                return np.zeros(self.FEATURE_DIM, dtype=np.float32)

            best_bid = float(top_yes[0][0])
            is_spot = getattr(book, "is_spot", False) or best_bid > 10.0

            if is_spot:
                best_ask = float(top_no[0][0]) if top_no else (best_bid + 0.01)
                if best_ask <= best_bid:
                    best_ask = best_bid + 0.01
                mid = (best_bid + best_ask) * 0.5
                spread_bps = max(0.0001, ((best_ask - best_bid) / mid) * 100.0)
            else:
                best_ask = (1.0 - float(top_no[0][0])) if top_no else (best_bid + 0.01)
                if best_bid <= 0:
                    best_bid = 0.01
                if best_ask <= best_bid:
                    best_ask = best_bid + 0.01
                spread_bps = max(0.001, min(0.25, best_ask - best_bid))

            bid_sizes = [float(qty) for _, qty in top_yes]
            ask_sizes = [float(qty) for _, qty in top_no]
        else:
            bids, asks = book.get_depth(self.target_depth)
            if not bids or not asks:
                return np.zeros(self.FEATURE_DIM, dtype=np.float32)

            best_bid = float(bids[0].price)
            is_spot = getattr(book, "is_spot", False) or best_bid > 10.0

            if is_spot:
                best_ask = float(asks[0].price) if asks else (best_bid + 0.01)
                if best_ask <= best_bid:
                    best_ask = best_bid + 0.01
                mid = (best_bid + best_ask) * 0.5
                spread_bps = max(0.0001, ((best_ask - best_bid) / mid) * 100.0)
            else:
                best_ask = (1.0 - float(asks[0].price)) if asks else (best_bid + 0.01)
                if best_bid <= 0:
                    best_bid = 0.01
                if best_ask <= best_bid:
                    best_ask = best_bid + 0.01
                spread_bps = max(0.001, min(0.25, best_ask - best_bid))

            bid_sizes = [float(lv.quantity) for lv in bids]
            ask_sizes = [float(lv.quantity) for lv in asks]

        # 2. Spatial Volumes & Normalization
        len_bids = len(bid_sizes)
        len_asks = len(ask_sizes)
        target_depth = self.target_depth

        if len_bids < target_depth:
            bid_sizes.extend([0.0] * (target_depth - len_bids))
        if len_asks < target_depth:
            ask_sizes.extend([0.0] * (target_depth - len_asks))

        sum_bids = sum(bid_sizes)
        sum_asks = sum(ask_sizes)
        total_visible_volume = sum_bids + sum_asks + 1e-9

        self.rolling_volumes.append(total_visible_volume)
        vols = list(self.rolling_volumes)
        vols.sort()
        n_v = len(vols)
        median_volume = vols[n_v // 2] if n_v % 2 == 1 else (vols[n_v // 2 - 1] + vols[n_v // 2]) * 0.5
        baseline_volume = max(median_volume, 1e-9)
        inv_baseline = 1.0 / baseline_volume

        # 3. Order Flow Imbalance (OFI)
        b0, a0 = bid_sizes[0], ask_sizes[0]
        ofi_l1 = (b0 - a0) / (b0 + a0 + 1e-9)

        vol_b5 = sum(bid_sizes[:5])
        vol_a5 = sum(ask_sizes[:5])
        ofi_l5 = (vol_b5 - vol_a5) / (vol_b5 + vol_a5 + 1e-9)
        self.ofi_l5_history.append(ofi_l5)

        ofi_l15 = (sum_bids - sum_asks) / total_visible_volume

        # 4. Spoofing & Layering Metrics
        vol_b_tail = sum_bids - vol_b5
        vol_a_tail = sum_asks - vol_a5
        spoof_mag_bid = (vol_b_tail * inv_baseline) * 0.15
        spoof_mag_ask = (vol_a_tail * inv_baseline) * 0.15
        layering_index = (vol_b_tail + vol_a_tail) / (vol_b5 + vol_a5 + 1e-9)

        # 5. Tape / Trade Dynamics
        self.bid_absorption *= self.ABSORPTION_DECAY
        self.ask_absorption *= self.ABSORPTION_DECAY
        self.whale_tx_count *= self.WHALE_DECAY

        cvd_norm = self._running_cvd * inv_baseline
        bid_absorption_norm = self.bid_absorption * inv_baseline
        ask_absorption_norm = self.ask_absorption * inv_baseline

        self.prev_best_bid = best_bid
        self.prev_best_ask = best_ask

        # 6. Spacetime & Contract Physics Features
        tau = float(time_to_expiry_s) if time_to_expiry_s is not None else 450.0
        tau = max(1.0, min(900.0, tau))
        tau_norm = tau / 900.0

        sigma = spot_volatility or self.default_gold_volatility
        sigma = max(0.10, sigma)

        # Feature 28: Moneyness Z-score
        if current_spot is not None and target_strike is not None and target_strike > 0:
            diff = float(current_spot - target_strike)
            time_scale = math.sqrt(tau / 60.0)  # minutes remaining sqrt scale
            denom = sigma * max(0.2, time_scale)
            z_score = max(-5.0, min(5.0, diff / denom))
        else:
            z_score = 0.0

        # Feature 30: OFI Acceleration
        if len(self.ofi_l5_history) >= 4:
            ofi_accel = ofi_l5 - self.ofi_l5_history[-4]
        else:
            ofi_accel = 0.0
        ofi_accel = max(-2.0, min(2.0, ofi_accel))

        # Feature 31: Settlement TWAP Delta
        if current_spot is not None and twap_60s is not None:
            twap_diff = float(current_spot - twap_60s)
            twap_delta = max(-3.0, min(3.0, twap_diff / sigma))
        else:
            twap_delta = 0.0

        # 7. Buffer Assembly (32 Dimensions)
        decays = self._decay_weights
        buf = self._feature_buffer
        buf[0] = spread_bps
        buf[1] = ofi_l1
        buf[2] = ofi_l5
        buf[3] = ofi_l15
        buf[4] = cvd_norm
        buf[5] = self._cached_entropy
        buf[6] = self.vpin_score
        buf[7] = spoof_mag_bid
        buf[8] = spoof_mag_ask
        buf[9] = bid_absorption_norm
        buf[10] = ask_absorption_norm
        buf[11] = self.whale_tx_count
        buf[12] = layering_index

        # 15 Spatial decay layers
        end_depth_idx = 13 + target_depth
        buf[13:end_depth_idx] = [decays[i] * (bid_sizes[i] - ask_sizes[i]) * inv_baseline for i in range(target_depth)]

        # 4 Spacetime & Contract Physics features
        buf[28] = z_score
        buf[29] = tau_norm
        buf[30] = ofi_accel
        buf[31] = twap_delta

        return buf.copy()

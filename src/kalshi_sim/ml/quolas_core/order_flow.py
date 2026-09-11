"""Order Flow Integrity — The Truth Layer (Transplanted from QuoLas Core).

Monitors live Binance trade streams for manipulation and toxic flow signals:
  - CVD (Cumulative Volume Delta) Divergence
  - Absorption: Price stalls during volume spikes
  - Spoofing: Rapid order book cancellation
  - VPIN PBC: Volume-Synchronized Probability of Toxicity
  - OFI: Order Flow Imbalance

Acts as an institutional VETO GATE — blocks trades but never initiates them.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Dict, List, Optional

import numpy as np

from kalshi_sim.ml.quolas_core.config import OrderFlowConfig

logger = logging.getLogger("kalshi_sim.ml.quolas_core.order_flow")


class FlowSignal(str, Enum):
    CLEAN = "CLEAN"
    CVD_DIVERGENCE = "CVD_DIVERGENCE"
    ABSORPTION = "ABSORPTION"
    SPOOFING = "SPOOFING"
    TOXIC_FLOW = "TOXIC_FLOW"
    INFORMED_FLOW = "INFORMED_FLOW"
    MANIPULATION = "MANIPULATION"


@dataclass
class TradeEvent:
    timestamp: int
    price: float
    quantity: float
    is_buyer_maker: bool
    symbol: str

    @property
    def side_volume(self) -> float:
        return -self.quantity if self.is_buyer_maker else self.quantity


@dataclass
class DepthSnapshot:
    timestamp: int
    symbol: str
    bids: List[List[float]]
    asks: List[List[float]]
    total_bid_depth: float = 0.0
    total_ask_depth: float = 0.0


@dataclass
class FlowState:
    cvd: float = 0.0
    cvd_history: Deque[float] = field(default_factory=lambda: deque(maxlen=500))
    price_history: Deque[float] = field(default_factory=lambda: deque(maxlen=500))
    volume_history: Deque[float] = field(default_factory=lambda: deque(maxlen=500))
    imbalance: float = 0.0
    whale_buys: int = 0
    whale_sells: int = 0
    liquidations: int = 0

    # ── Microstructure Shield ──
    depth_ages: Dict[float, float] = field(default_factory=dict)  # price -> birth_timestamp
    iceberg_executions: Dict[float, float] = field(default_factory=dict)  # price -> cumulative_vol
    is_iceberg_at_price: Dict[float, bool] = field(default_factory=dict)

    last_depth_snapshot: Optional[DepthSnapshot] = None
    spoof_cooldown_until: float = 0.0
    depth_history: Deque[DepthSnapshot] = field(default_factory=lambda: deque(maxlen=20))

    # ── VPIN Metrics ──
    current_bucket_vol: float = 0.0
    current_bucket_buy_vol: float = 0.0
    current_bucket_high: float = -1.0
    current_bucket_low: float = 1e18
    vpin_history: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    vpin: float = 0.0

    # ── OFI Metrics ──
    ofi: float = 0.0
    ofi_history: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    last_best_bid: float = 0.0
    last_best_ask: float = 0.0
    last_best_bid_size: float = 0.0
    last_best_ask_size: float = 0.0

    last_signal: FlowSignal = FlowSignal.CLEAN
    signal_reason: str = ""


class OrderFlowIntegrity:
    """Order Flow Integrity Engine with CVD, absorption, and spoofing detection."""

    def __init__(self, config: Optional[OrderFlowConfig] = None) -> None:
        self.config = config or OrderFlowConfig()
        self.states: Dict[str, FlowState] = {}
        self.cvd_sigma_threshold = self.config.cvd_divergence_sigma
        self.absorption_vol_mult = self.config.absorption_vol_multiplier
        self.spoof_cancel_pct = self.config.spoof_cancel_pct
        self.spoof_cooldown_secs = self.config.spoof_cooldown_seconds
        self.vpin_threshold = self.config.vpin_threshold
        self.vpin_bucket_size = self.config.vpin_bucket_size
        self.ofi_threshold = self.config.ofi_threshold

    def _get_state(self, symbol: str) -> FlowState:
        if symbol not in self.states:
            self.states[symbol] = FlowState()
        return self.states[symbol]

    def process_trade(self, trade: TradeEvent) -> FlowSignal:
        state = self._get_state(trade.symbol)
        state.cvd += trade.side_volume
        state.cvd_history.append(state.cvd)
        state.price_history.append(trade.price)
        state.volume_history.append(trade.quantity)

        # ── Iceberg Detection ──
        state.iceberg_executions[trade.price] = state.iceberg_executions.get(trade.price, 0.0) + trade.quantity

        # Track Whale Buys / Sells (> $100k)
        notional_value = trade.price * trade.quantity
        if notional_value >= 100000:
            if trade.is_buyer_maker:  # Seller initiated
                state.whale_sells += 1
            else:  # Buyer initiated
                state.whale_buys += 1

        # ── VPIN & Churn Logic ──
        state.current_bucket_vol += trade.quantity
        state.current_bucket_high = max(state.current_bucket_high, trade.price)
        state.current_bucket_low = min(state.current_bucket_low, trade.price)

        if not trade.is_buyer_maker:  # Buyer initiated
            state.current_bucket_buy_vol += trade.quantity

        if state.current_bucket_vol >= self.vpin_bucket_size:
            price_range = state.current_bucket_high - state.current_bucket_low
            churn = state.current_bucket_vol / (price_range + 1e-9)

            if churn > 1000000 and price_range < 0.00001:
                state.last_signal = FlowSignal.MANIPULATION

            sell_vol = state.current_bucket_vol - state.current_bucket_buy_vol
            vpin_val = abs(state.current_bucket_buy_vol - sell_vol) / state.current_bucket_vol
            state.vpin_history.append(vpin_val)
            state.vpin = float(np.mean(list(state.vpin_history)))

            # Reset bucket
            state.current_bucket_vol = 0.0
            state.current_bucket_buy_vol = 0.0
            state.current_bucket_high = -1.0
            state.current_bucket_low = 1e18

        signals = []
        cvd_sig = self._check_cvd_divergence(state)
        if cvd_sig:
            signals.append(cvd_sig)
        abs_sig = self._check_absorption(state)
        if abs_sig:
            signals.append(abs_sig)

        if len(signals) >= 2:
            state.last_signal = FlowSignal.TOXIC_FLOW
        elif signals:
            state.last_signal = signals[0]
        else:
            state.last_signal = FlowSignal.CLEAN

        return state.last_signal

    def process_depth(self, snapshot: DepthSnapshot) -> FlowSignal:
        state = self._get_state(snapshot.symbol)
        now = time.time()

        # ── Age Tracking (Anti-Spoofing) ──
        current_prices = set()
        for p, s in snapshot.bids + snapshot.asks:
            current_prices.add(p)
            if p not in state.depth_ages:
                state.depth_ages[p] = now

        # Cleanup old ages
        state.depth_ages = {p: t for p, t in state.depth_ages.items() if p in current_prices}

        # ── Firm OBI Calculation (Only count liquidity older than 0.5s) ──
        firm_bids = 0.0
        for p, s in snapshot.bids[:10]:
            age = now - state.depth_ages.get(p, now)
            weight = 1.0 if age > 0.5 else 0.3  # Discount transient liquidity
            firm_bids += s * weight

            # Check for Iceberg Exhaustion
            if state.iceberg_executions.get(p, 0) > s * 1.1:
                state.is_iceberg_at_price[p] = True
            else:
                state.is_iceberg_at_price[p] = False

        firm_asks = 0.0
        for p, s in snapshot.asks[:10]:
            age = now - state.depth_ages.get(p, now)
            weight = 1.0 if age > 0.5 else 0.3
            firm_asks += s * weight

            if state.iceberg_executions.get(p, 0) > s * 1.1:
                state.is_iceberg_at_price[p] = True
            else:
                state.is_iceberg_at_price[p] = False

        if len(state.iceberg_executions) > 100:
            state.iceberg_executions.clear()

        # Update OBI with firm liquidity
        total_firm_depth = firm_bids + firm_asks
        if total_firm_depth > 0:
            state.imbalance = (firm_bids - firm_asks) / total_firm_depth
        else:
            state.imbalance = 0.0

        # ── OFI (Order Flow Imbalance) Calculation ──
        if snapshot.bids and snapshot.asks:
            curr_bid = snapshot.bids[0][0]
            curr_bid_size = snapshot.bids[0][1]
            curr_ask = snapshot.asks[0][0]
            curr_ask_size = snapshot.asks[0][1]

            if state.last_best_bid > 0:
                if curr_bid > state.last_best_bid:
                    delta_bid = curr_bid_size
                elif curr_bid < state.last_best_bid:
                    delta_bid = -state.last_best_bid_size
                else:
                    delta_bid = curr_bid_size - state.last_best_bid_size

                if curr_ask < state.last_best_ask:
                    delta_ask = curr_ask_size
                elif curr_ask > state.last_best_ask:
                    delta_ask = -state.last_best_ask_size
                else:
                    delta_ask = curr_ask_size - state.last_best_ask_size

                state.ofi = delta_bid - delta_ask
                state.ofi_history.append(state.ofi)

            state.last_best_bid = curr_bid
            state.last_best_bid_size = curr_bid_size
            state.last_best_ask = curr_ask
            state.last_best_ask_size = curr_ask_size

        if state.last_depth_snapshot is not None:
            spoof = self._check_spoofing(state, snapshot)
            if spoof:
                state.last_signal = FlowSignal.SPOOFING
                state.spoof_cooldown_until = time.time() + self.spoof_cooldown_secs

        state.depth_history.append(snapshot)
        state.last_depth_snapshot = snapshot
        return state.last_signal

    def get_flow_signal(self, symbol: str) -> FlowSignal:
        state = self._get_state(symbol)
        if time.time() < state.spoof_cooldown_until:
            return FlowSignal.SPOOFING
        return state.last_signal

    def is_flow_clean(self, symbol: str) -> bool:
        return self.get_flow_signal(symbol) == FlowSignal.CLEAN

    def _check_cvd_divergence(self, state: FlowState) -> Optional[FlowSignal]:
        if len(state.cvd_history) < 50:
            return None
        cvd_arr = np.array(list(state.cvd_history))
        price_arr = np.array(list(state.price_history))
        window = 20
        if len(cvd_arr) < window:
            return None
        cvd_delta = cvd_arr[-1] - cvd_arr[-window]
        price_delta = price_arr[-1] - price_arr[-window]
        cvd_std = np.std(np.diff(cvd_arr[-100:])) if len(cvd_arr) > 100 else 1.0
        if cvd_std == 0:
            cvd_std = 1.0
        cvd_z = cvd_delta / cvd_std
        price_dir = 1 if price_delta > 0 else -1
        cvd_dir = 1 if cvd_delta > 0 else -1
        if price_dir != cvd_dir and abs(cvd_z) > self.cvd_sigma_threshold:
            return FlowSignal.CVD_DIVERGENCE
        return None

    def _check_absorption(self, state: FlowState) -> Optional[FlowSignal]:
        if len(state.volume_history) < 50:
            return None
        vol_arr = np.array(list(state.volume_history))
        price_arr = np.array(list(state.price_history))
        window = 10
        if len(vol_arr) < window:
            return None
        recent_vol = vol_arr[-window:]
        recent_price = price_arr[-window:]
        avg_vol = np.mean(vol_arr[-100:]) if len(vol_arr) >= 100 else np.mean(vol_arr)
        current_vol = np.mean(recent_vol)
        price_pct = abs(recent_price[-1] - recent_price[0]) / recent_price[0] if recent_price[0] > 0 else 0
        if current_vol > avg_vol * self.absorption_vol_mult and price_pct < 0.0005:
            return FlowSignal.ABSORPTION
        return None

    def _check_spoofing(self, state: FlowState, current: DepthSnapshot) -> Optional[FlowSignal]:
        prev = state.last_depth_snapshot
        if prev is None:
            return None
        time_delta_ms = current.timestamp - prev.timestamp
        if time_delta_ms > 1000:
            return None
        if prev.total_bid_depth > 0:
            bid_cancel = (prev.total_bid_depth - current.total_bid_depth) / prev.total_bid_depth
            if bid_cancel > self.spoof_cancel_pct:
                return FlowSignal.SPOOFING
        if prev.total_ask_depth > 0:
            ask_cancel = (prev.total_ask_depth - current.total_ask_depth) / prev.total_ask_depth
            if ask_cancel > self.spoof_cancel_pct:
                return FlowSignal.SPOOFING
        return None

    def get_status(self, symbol: str) -> Dict:
        state = self._get_state(symbol)
        return {
            "symbol": symbol,
            "signal": state.last_signal.value,
            "cvd": round(state.cvd, 2),
            "is_clean": self.is_flow_clean(symbol),
            "imbalance": round(state.imbalance, 4),
            "vpin": round(state.vpin, 3),
            "ofi": round(state.ofi, 2),
            "whale_buys": state.whale_buys,
            "whale_sells": state.whale_sells,
            "liquidations": state.liquidations,
        }

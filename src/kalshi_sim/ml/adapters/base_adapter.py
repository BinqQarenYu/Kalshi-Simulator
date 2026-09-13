"""Abstract Base Venue Adapter for the 32-D Gold ONNX Engine.

Defines the contract for transforming raw model output probabilities [P(UP), P(DOWN), P(WAIT)]
and market telemetry into venue-specific actionable trading signals and order specifications.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional, Tuple
import numpy as np


class SignalDirection(str, Enum):
    """Actionable prediction direction."""
    BUY_YES = "BUY_YES"    # Expect price to settle above target strike (P(UP) > threshold)
    BUY_NO = "BUY_NO"      # Expect price to settle below target strike (P(DOWN) > threshold)
    HOLD = "HOLD"          # Low conviction or noise regime (P(WAIT) dominant)


@dataclass(frozen=True)
class VenueSignal:
    """Venue-specific trade signal generated from 32-D ONNX model inference."""
    venue_name: str
    symbol: str
    direction: SignalDirection
    confidence: Decimal          # Probability in [0.00, 1.00] as Decimal
    recommended_limit_price: Decimal  # Venue price in Decimal (e.g. 0.48 on Kalshi, 0.48 on Polymarket)
    max_contracts: int           # Hard-capped sizing
    expected_fee: Decimal        # Estimated exchange fee in Decimal
    strike_diff: Decimal         # Spot minus Strike in Decimal
    settlement_offset: Decimal   # Offset to settlement metric (e.g. TWAP delta)
    telemetry: Dict[str, Any]    # Diagnostics payload


class BaseVenueAdapter(ABC):
    """Abstract interface for venue adapters transforming 32-D ONNX probabilities into orders."""

    def __init__(self, venue_name: str, min_conviction: Decimal = Decimal("0.65")) -> None:
        self.venue_name = venue_name
        self.min_conviction = min_conviction

    @abstractmethod
    def evaluate_signal(
        self,
        probabilities: np.ndarray,
        current_spot: Decimal,
        target_strike: Decimal,
        time_to_expiry_s: float,
        best_bid: Decimal,
        best_ask: Decimal,
        bankroll: Decimal,
        **kwargs: Any,
    ) -> VenueSignal:
        """Evaluate raw 3-class model probabilities against venue-specific microstructural rules.

        Args:
            probabilities: Array of shape (3,) with [P(UP), P(DOWN), P(WAIT)].
            current_spot: Current asset spot price in Decimal.
            target_strike: Target strike price (K) in Decimal.
            time_to_expiry_s: Time remaining to expiry in seconds.
            best_bid: Current best bid on venue in Decimal.
            best_ask: Current best ask on venue in Decimal.
            bankroll: Available capital balance in Decimal.
            **kwargs: Venue-specific auxiliary data (e.g. TWAP, orderbook depth).

        Returns:
            VenueSignal: Fully specified and risk-checked trading signal.
        """
        pass

    @abstractmethod
    def calculate_taker_fee(self, price: Decimal, count: int) -> Decimal:
        """Calculate exchange taker fee using exact venue fee schedule."""
        pass

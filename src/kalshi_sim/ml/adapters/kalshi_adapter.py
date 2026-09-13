"""Kalshi Binary Options Venue Adapter for the 32-D Gold ONNX Engine.

Implements CFTC regulatory fee curves, 60s trailing TWAP settlement rules,
micro-bankroll armor (1 contract cap), and dead-zone noise filtering.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import math
from typing import Any, Dict, Optional
import numpy as np

from kalshi_sim.ml.adapters.base_adapter import (
    BaseVenueAdapter,
    SignalDirection,
    VenueSignal,
)


class KalshiVenueAdapter(BaseVenueAdapter):
    """Adapter for routing 32-D Gold ONNX inferences to Kalshi binary options."""

    def __init__(
        self,
        min_conviction: Decimal = Decimal("0.65"),
        dead_zone_gold_usd: Decimal = Decimal("0.75"),  # Minimum $0.75/oz spot distance for Gold
        default_limit_price: Decimal = Decimal("0.48"), # Target Maker discount price ($0.48)
    ) -> None:
        super().__init__(venue_name="Kalshi", min_conviction=min_conviction)
        self.dead_zone_gold_usd = dead_zone_gold_usd
        self.default_limit_price = default_limit_price

    def calculate_taker_fee(self, price: Decimal, count: int) -> Decimal:
        """Calculate exact Kalshi CFTC taker fee with $0.01 floor and $0.02 cap per contract.

        Formula: ceil(0.07 * count * price * (1 - price))
        """
        if count <= 0 or price <= Decimal("0.00") or price >= Decimal("1.00"):
            return Decimal("0.00")

        p = price
        one_minus_p = Decimal("1.00") - p
        raw_fee = Decimal("0.07") * Decimal(count) * p * one_minus_p
        
        # Round up to next cent (ceiling)
        fee = raw_fee.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
        
        # Apply $0.01 floor and $0.02 cap per contract
        min_fee = Decimal("0.01") * Decimal(count)
        max_fee = Decimal("0.02") * Decimal(count)
        return max(min_fee, min(max_fee, fee))

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
        """Evaluate 32-D probabilities with Kalshi-specific microstructural safeguards."""
        p_up = Decimal(str(round(float(probabilities[0]), 4)))
        p_down = Decimal(str(round(float(probabilities[1]), 4)))
        p_wait = Decimal(str(round(float(probabilities[2]), 4)))

        strike_diff = current_spot - target_strike
        twap_60s: Optional[Decimal] = kwargs.get("twap_60s")
        twap_offset = (current_spot - twap_60s) if twap_60s is not None else Decimal("0.00")

        # 1. Micro-bankroll sizing armor: strictly 1 contract for accounts < $75
        max_contracts = 1 if bankroll < Decimal("75.00") else 1

        # 2. Dead-zone noise filter (Lesson 4)
        in_dead_zone = abs(strike_diff) < self.dead_zone_gold_usd

        # 3. Direction determination
        direction = SignalDirection.HOLD
        confidence = p_wait
        recommended_price = self.default_limit_price

        if not in_dead_zone and time_to_expiry_s >= 30.0:
            if p_up >= self.min_conviction and strike_diff > Decimal("0.00"):
                direction = SignalDirection.BUY_YES
                confidence = p_up
                recommended_price = min(self.default_limit_price, best_bid if best_bid > Decimal("0.00") else Decimal("0.48"))
            elif p_down >= self.min_conviction and strike_diff < Decimal("0.00"):
                direction = SignalDirection.BUY_NO
                confidence = p_down
                recommended_price = min(self.default_limit_price, best_bid if best_bid > Decimal("0.00") else Decimal("0.48"))

        expected_fee = self.calculate_taker_fee(recommended_price, max_contracts)

        telemetry = {
            "p_up": str(p_up),
            "p_down": str(p_down),
            "p_wait": str(p_wait),
            "in_dead_zone": in_dead_zone,
            "twap_60s": str(twap_60s) if twap_60s is not None else None,
            "time_to_expiry_s": time_to_expiry_s,
        }

        return VenueSignal(
            venue_name=self.venue_name,
            symbol="KXGOLD15M",
            direction=direction,
            confidence=confidence,
            recommended_limit_price=recommended_price,
            max_contracts=max_contracts,
            expected_fee=expected_fee,
            strike_diff=strike_diff,
            settlement_offset=twap_offset,
            telemetry=telemetry,
        )

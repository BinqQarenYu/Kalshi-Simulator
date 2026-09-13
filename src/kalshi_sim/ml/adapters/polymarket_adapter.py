"""Polymarket Prediction Market Venue Adapter for the 32-D Gold ONNX Engine.

Implements USDC collateralization, point-in-time oracle settlement evaluation (Chainlink/Pyth/UMA),
and CLOB execution mechanics.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional
import numpy as np

from kalshi_sim.ml.adapters.base_adapter import (
    BaseVenueAdapter,
    SignalDirection,
    VenueSignal,
)


class PolymarketVenueAdapter(BaseVenueAdapter):
    """Adapter for routing 32-D Gold ONNX inferences to Polymarket prediction markets."""

    def __init__(
        self,
        min_conviction: Decimal = Decimal("0.65"),
        target_token_price: Decimal = Decimal("0.50"),
    ) -> None:
        super().__init__(venue_name="Polymarket", min_conviction=min_conviction)
        self.target_token_price = target_token_price

    def calculate_taker_fee(self, price: Decimal, count: int) -> Decimal:
        """Polymarket CLOB uses 0% exchange fees for standard prediction markets (relayer gasless)."""
        return Decimal("0.00")

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
        """Evaluate 32-D probabilities against Polymarket CLOB liquidity."""
        p_up = Decimal(str(round(float(probabilities[0]), 4)))
        p_down = Decimal(str(round(float(probabilities[1]), 4)))
        p_wait = Decimal(str(round(float(probabilities[2]), 4)))

        strike_diff = current_spot - target_strike
        oracle_type: str = kwargs.get("oracle_type", "Pyth/Chainlink")

        # Polymarket sizing: 1 share / contract for micro-bankroll armor
        max_contracts = 1 if bankroll < Decimal("75.00") else 1

        direction = SignalDirection.HOLD
        confidence = p_wait
        recommended_price = self.target_token_price

        if time_to_expiry_s >= 20.0:
            if p_up >= self.min_conviction and strike_diff > Decimal("0.00"):
                direction = SignalDirection.BUY_YES
                confidence = p_up
                recommended_price = best_bid if Decimal("0.01") <= best_bid <= Decimal("0.55") else Decimal("0.50")
            elif p_down >= self.min_conviction and strike_diff < Decimal("0.00"):
                direction = SignalDirection.BUY_NO
                confidence = p_down
                recommended_price = best_bid if Decimal("0.01") <= best_bid <= Decimal("0.55") else Decimal("0.50")

        expected_fee = self.calculate_taker_fee(recommended_price, max_contracts)

        telemetry = {
            "p_up": str(p_up),
            "p_down": str(p_down),
            "p_wait": str(p_wait),
            "oracle_type": oracle_type,
            "collateral": "USDC",
            "time_to_expiry_s": time_to_expiry_s,
        }

        return VenueSignal(
            venue_name=self.venue_name,
            symbol="XAU-USD-POLY-15M",
            direction=direction,
            confidence=confidence,
            recommended_limit_price=recommended_price,
            max_contracts=max_contracts,
            expected_fee=expected_fee,
            strike_diff=strike_diff,
            settlement_offset=Decimal("0.00"),  # Point-in-time oracle, no 60s TWAP
            telemetry=telemetry,
        )

"""Binance Options & Predictions Venue Adapter for the 32-D Gold ONNX Engine.

Implements Binance composite index mark pricing, basis-point tiered fee modeling,
and high-frequency execution formatting.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional
import numpy as np

from kalshi_sim.ml.adapters.base_adapter import (
    BaseVenueAdapter,
    SignalDirection,
    VenueSignal,
)


class BinanceVenueAdapter(BaseVenueAdapter):
    """Adapter for routing 32-D Gold ONNX inferences to Binance options & prediction markets."""

    def __init__(
        self,
        min_conviction: Decimal = Decimal("0.65"),
        taker_fee_bps: Decimal = Decimal("0.0004"), # 4 bps taker fee
    ) -> None:
        super().__init__(venue_name="Binance", min_conviction=min_conviction)
        self.taker_fee_bps = taker_fee_bps

    def calculate_taker_fee(self, price: Decimal, count: int) -> Decimal:
        """Calculate Binance basis-point taker fee: price * count * taker_fee_bps."""
        if count <= 0 or price <= Decimal("0.00"):
            return Decimal("0.00")
        raw_fee = price * Decimal(count) * self.taker_fee_bps
        return raw_fee.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

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
        """Evaluate 32-D probabilities against Binance Composite Index mark price."""
        p_up = Decimal(str(round(float(probabilities[0]), 4)))
        p_down = Decimal(str(round(float(probabilities[1]), 4)))
        p_wait = Decimal(str(round(float(probabilities[2]), 4)))

        strike_diff = current_spot - target_strike
        mark_price: Optional[Decimal] = kwargs.get("mark_price", current_spot)
        mark_diff = (current_spot - mark_price) if mark_price is not None else Decimal("0.00")

        # Binance sizing: 1 unit / contract for micro-bankroll armor
        max_contracts = 1 if bankroll < Decimal("75.00") else 1

        direction = SignalDirection.HOLD
        confidence = p_wait
        recommended_price = Decimal("0.50")

        if time_to_expiry_s >= 15.0:
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
            "mark_price": str(mark_price) if mark_price is not None else None,
            "settlement_currency": "USDT",
            "time_to_expiry_s": time_to_expiry_s,
        }

        return VenueSignal(
            venue_name=self.venue_name,
            symbol="PAXGUSDT-15M",
            direction=direction,
            confidence=confidence,
            recommended_limit_price=recommended_price,
            max_contracts=max_contracts,
            expected_fee=expected_fee,
            strike_diff=strike_diff,
            settlement_offset=mark_diff,
            telemetry=telemetry,
        )

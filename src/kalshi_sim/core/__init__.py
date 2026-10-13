"""Core quantitative invariants and zero-float financial math."""

from src.kalshi_sim.core.decimal_math import (
    calculate_kalshi_taker_fee,
    calculate_binary_net_ev,
    decimal_to_cents,
    cents_to_decimal,
)
from src.kalshi_sim.core.invariants import (
    MICRO_BANKROLL_MAX_CONTRACTS,
    MAX_SPREAD_CROSSING,
    BROWNIAN_DEAD_ZONE_USD,
    MIN_EXPIRATION_TIME_SEC,
    IN_FLIGHT_INTENT_LOCK_TTL_SEC,
    RETAIL_INVERSION_MULTIPLIER,
)

__all__ = [
    "calculate_kalshi_taker_fee",
    "calculate_binary_net_ev",
    "decimal_to_cents",
    "cents_to_decimal",
    "MICRO_BANKROLL_MAX_CONTRACTS",
    "MAX_SPREAD_CROSSING",
    "BROWNIAN_DEAD_ZONE_USD",
    "MIN_EXPIRATION_TIME_SEC",
    "IN_FLIGHT_INTENT_LOCK_TTL_SEC",
    "RETAIL_INVERSION_MULTIPLIER",
]

"""Quantitative Trading Invariants and Guardrail Constants.

Enforces system-wide risk limits, anti-kamikaze sizing, and market microstructure bounds.
"""

from decimal import Decimal
from typing import Dict, Any, Tuple
from src.kalshi_sim.core.decimal_math import to_decimal

# Micro-bankroll sizing armor (Law 2: AGENTS.md)
MICRO_BANKROLL_MAX_CONTRACTS: int = 1

# Maximum allowable spread crossing penalty
MAX_SPREAD_CROSSING: Decimal = Decimal("0.05")

# Brownian noise dead-zone boundary (entries within +/- $25 are pure random walk)
BROWNIAN_DEAD_ZONE_USD: Decimal = Decimal("25.00")

# Expiration pinning lock window (no entries allowed under 120 seconds to expiration)
MIN_EXPIRATION_TIME_SEC: int = 120

# In-flight order intent lock TTL to prevent dual-fire race conditions
IN_FLIGHT_INTENT_LOCK_TTL_SEC: int = 15

# Edge multiplier required when taking a trade contrary to retail inversion
RETAIL_INVERSION_MULTIPLIER: Decimal = Decimal("3.0")

# Minimum net EV required after taker fees
MIN_NET_EV: Decimal = Decimal("0.015")


def is_in_brownian_dead_zone(spot: Decimal, strike: Decimal) -> bool:
    """Check if spot price is trapped inside the Brownian dead-zone around strike."""
    diff = abs(to_decimal(spot) - to_decimal(strike))
    return diff <= BROWNIAN_DEAD_ZONE_USD


def validate_order_invariants(
    contracts: int,
    spread: Decimal,
    net_ev: Decimal,
    seconds_to_expiry: int
) -> Tuple[bool, list[str]]:
    """Validate all core invariants prior to order submission.
    
    Returns:
        Tuple of (is_valid: bool, violations: list[str])
    """
    violations = []
    
    if contracts > MICRO_BANKROLL_MAX_CONTRACTS:
        violations.append(
            f"Contract size {contracts} exceeds micro-bankroll cap {MICRO_BANKROLL_MAX_CONTRACTS}."
        )
        
    if to_decimal(spread) > MAX_SPREAD_CROSSING:
        violations.append(
            f"Spread ${spread} exceeds maximum crossing threshold ${MAX_SPREAD_CROSSING}."
        )
        
    if to_decimal(net_ev) < MIN_NET_EV:
        violations.append(
            f"Net EV ${net_ev} is below minimum hurdle rate ${MIN_NET_EV}."
        )
        
    if seconds_to_expiry < MIN_EXPIRATION_TIME_SEC:
        violations.append(
            f"Time to expiry {seconds_to_expiry}s is inside pinning blackout (<{MIN_EXPIRATION_TIME_SEC}s)."
        )
        
    return (len(violations) == 0, violations)

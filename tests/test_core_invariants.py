"""Targeted unit tests for Core financial math and invariants."""

import pytest
from decimal import Decimal
from src.kalshi_sim.core import (
    calculate_kalshi_taker_fee,
    calculate_binary_net_ev,
    decimal_to_cents,
    cents_to_decimal,
    MICRO_BANKROLL_MAX_CONTRACTS,
    MAX_SPREAD_CROSSING,
    BROWNIAN_DEAD_ZONE_USD,
)
from src.kalshi_sim.core.decimal_math import to_decimal
from src.kalshi_sim.core.invariants import (
    is_in_brownian_dead_zone,
    validate_order_invariants,
)


def test_zero_float_enforcement():
    # Str, Int, and Decimal are valid
    assert to_decimal("0.50") == Decimal("0.50")
    assert to_decimal(10) == Decimal("10")
    assert to_decimal(Decimal("1.25")) == Decimal("1.25")

    # IEEE 754 floats must raise TypeError
    with pytest.raises(TypeError):
        to_decimal(0.50)  # type: ignore


def test_kalshi_taker_fee_quadratic():
    # 1 contract at 0.50 price: 0.07 * 1 * 0.50 * 0.50 = 0.0175 -> ceil to $0.02
    fee = calculate_kalshi_taker_fee(1, Decimal("0.50"))
    assert fee == Decimal("0.02")

    # 1 contract at 0.10 price: 0.07 * 1 * 0.10 * 0.90 = 0.0063 -> ceil to $0.01
    fee_otm = calculate_kalshi_taker_fee(1, Decimal("0.10"))
    assert fee_otm == Decimal("0.01")


def test_binary_net_ev_calculation():
    # Buy at $0.48, true win prob 0.60, fee $0.02
    # Gross EV = 0.60 * (1 - 0.48) - 0.40 * 0.48 = 0.60 * 0.52 - 0.192 = 0.312 - 0.192 = 0.120
    # Net EV = 0.120 - 0.02 = 0.100
    net_ev = calculate_binary_net_ev(
        p_win=Decimal("0.60"),
        cost_price=Decimal("0.48"),
        taker_fee=Decimal("0.02")
    )
    assert net_ev == Decimal("0.1000")


def test_cents_conversion():
    assert decimal_to_cents(Decimal("0.54")) == 54
    assert cents_to_decimal(54) == Decimal("0.54")


def test_brownian_dead_zone():
    strike = Decimal("65000.00")
    
    # Trapped inside +/- $25
    assert is_in_brownian_dead_zone(Decimal("65015.00"), strike) is True
    assert is_in_brownian_dead_zone(Decimal("64980.00"), strike) is True

    # Escaped outside dead zone
    assert is_in_brownian_dead_zone(Decimal("65030.00"), strike) is False
    assert is_in_brownian_dead_zone(Decimal("64970.00"), strike) is False


def test_validate_order_invariants_pass():
    is_valid, violations = validate_order_invariants(
        contracts=1,
        spread=Decimal("0.02"),
        net_ev=Decimal("0.05"),
        seconds_to_expiry=300,
    )
    assert is_valid is True
    assert len(violations) == 0


def test_validate_order_invariants_violations():
    is_valid, violations = validate_order_invariants(
        contracts=5,                # Exceeds max 1
        spread=Decimal("0.08"),     # Exceeds max $0.05
        net_ev=Decimal("0.005"),    # Below min $0.015
        seconds_to_expiry=60,       # Below min 120s
    )
    assert is_valid is False
    assert len(violations) == 4

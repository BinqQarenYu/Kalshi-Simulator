"""Unit tests verifying Council 2x and 3x Scaled Sizing Rules, Conviction Filters, and Bankroll Tiers."""

from decimal import Decimal
import pytest
from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.ml.statistical_ev_engine import StatisticalEVEngine


def test_statistical_ev_engine_conviction_tiers():
    """Verify StatisticalEVEngine accurately determines 1x, 2x, and 3x conviction tiers."""
    # 1. Platinum 3x Confluence: Equity $100, P=90%, Price $0.50, VPIN 0.15, T=350s, Moat $55 -> 3x
    tier3 = StatisticalEVEngine.compute_conviction_tier(
        ai_prob=0.90,
        price=Decimal("0.50"),
        vpin=0.15,
        time_to_expiry_s=350.0,
        spot_distance_to_strike=55.0,
        total_equity=Decimal("100.00"),
    )
    assert tier3 == 3

    # 2. High Conviction 2x: Equity $60, P=84%, Price $0.53, VPIN 0.22, T=200s, Moat $35 -> 2x
    tier2 = StatisticalEVEngine.compute_conviction_tier(
        ai_prob=0.84,
        price=Decimal("0.53"),
        vpin=0.22,
        time_to_expiry_s=200.0,
        spot_distance_to_strike=35.0,
        total_equity=Decimal("60.00"),
    )
    assert tier2 == 2

    # 3. Standard 1x Baseline (Price too high for 2x: $0.56) -> 1x
    tier1_price = StatisticalEVEngine.compute_conviction_tier(
        ai_prob=0.85,
        price=Decimal("0.56"),
        vpin=0.15,
        time_to_expiry_s=350.0,
        spot_distance_to_strike=40.0,
        total_equity=Decimal("100.00"),
    )
    assert tier1_price == 1

    # 4. Standard 1x Baseline (Equity too low for 2x: $25) -> 1x
    tier1_equity = StatisticalEVEngine.compute_conviction_tier(
        ai_prob=0.92,
        price=Decimal("0.50"),
        vpin=0.15,
        time_to_expiry_s=350.0,
        spot_distance_to_strike=55.0,
        total_equity=Decimal("25.00"),
    )
    assert tier1_equity == 1


def test_guardrails_approve_3x_when_platinum_criteria_met():
    """Verify AgentGuardrails approves 3 contracts when all Council criteria are met."""
    guard = AgentGuardrails(min_order_interval_seconds=0.0)
    cycle = "KXBTC15M-SCALE-3X"

    ok, reason, size, diag = guard.validate_pre_trade_intent(
        ticker=cycle,
        side="yes",
        requested_size=3,
        est_price=Decimal("0.50"),
        total_equity=Decimal("100.00"),
        vpin=0.15,
        bot_type="3_step_domination_bot",
    )
    assert ok is True, f"Failed: {reason}"
    assert size == 3
    assert diag["approved_size"] == 3


def test_guardrails_approve_2x_when_high_conviction_met():
    """Verify AgentGuardrails approves 2 contracts when 2x criteria are met."""
    guard = AgentGuardrails(min_order_interval_seconds=0.0)
    cycle = "KXBTC15M-SCALE-2X"

    ok, reason, size, diag = guard.validate_pre_trade_intent(
        ticker=cycle,
        side="yes",
        requested_size=2,
        est_price=Decimal("0.53"),
        total_equity=Decimal("60.00"),
        vpin=0.22,
        bot_type="bot1_v4_domination",
    )
    assert ok is True, f"Failed: {reason}"
    assert size == 2


def test_guardrails_safely_taper_3x_to_1x_if_micro_bankroll():
    """Verify 3x request is safely tapered to 1 contract if bankroll is small (< $50)."""
    guard = AgentGuardrails(min_order_interval_seconds=0.0)
    cycle = "KXBTC15M-TAPER-BANKROLL"

    ok, reason, size, diag = guard.validate_pre_trade_intent(
        ticker=cycle,
        side="yes",
        requested_size=3,
        est_price=Decimal("0.50"),
        total_equity=Decimal("25.00"),  # Nano/micro bankroll
        vpin=0.10,
        bot_type="bot1_v4_domination",
    )
    assert ok is True
    assert size == 1  # Safely restricted to 1 contract


def test_guardrails_safely_taper_to_1x_if_price_over_ceiling():
    """Verify 2x or 3x request is safely tapered to 1 contract if price > $0.54."""
    guard = AgentGuardrails(min_order_interval_seconds=0.0)
    cycle = "KXBTC15M-TAPER-PRICE"

    ok, reason, size, diag = guard.validate_pre_trade_intent(
        ticker=cycle,
        side="yes",
        requested_size=3,
        est_price=Decimal("0.56"),  # Over $0.54 ceiling
        total_equity=Decimal("100.00"),
        vpin=0.10,
        bot_type="bot1_v4_domination",
    )
    assert ok is True
    assert size == 1  # Safely tapered


def test_guardrails_safely_taper_to_1x_if_vpin_toxic():
    """Verify 2x or 3x request is safely tapered to 1 contract if VPIN >= 0.30."""
    guard = AgentGuardrails(min_order_interval_seconds=0.0)
    cycle = "KXBTC15M-TAPER-VPIN"

    ok, reason, size, diag = guard.validate_pre_trade_intent(
        ticker=cycle,
        side="yes",
        requested_size=2,
        est_price=Decimal("0.52"),
        total_equity=Decimal("100.00"),
        vpin=0.35,  # Toxic flow
        bot_type="3_step_domination_bot",
    )
    assert ok is True
    assert size == 1  # Safely tapered


def test_loss_streak_forces_size_one_taper():
    """Verify consecutive loss streak forces all sized bets down to 1 contract for self-preservation."""
    guard = AgentGuardrails(min_order_interval_seconds=0.0, consecutive_loss_taper_threshold=2)
    guard.validate_pre_trade_intent("T0", "yes", 1, Decimal("0.50"), total_equity=Decimal("100.00"))

    # Record 2 losses to trigger taper
    guard.record_cycle_settlement("T1", outcome="loss", pnl=Decimal("-2.00"), balance_after=Decimal("98.00"))
    guard.record_cycle_settlement("T2", outcome="loss", pnl=Decimal("-2.00"), balance_after=Decimal("96.00"))

    # Now attempt a 3x bet with $96 equity
    ok, reason, size, diag = guard.validate_pre_trade_intent(
        ticker="KXBTC15M-STREAK-TAPER",
        side="yes",
        requested_size=3,
        est_price=Decimal("0.50"),
        total_equity=Decimal("96.00"),
        vpin=0.10,
        bot_type="3_step_domination_bot",
    )
    assert ok is True
    assert diag["is_tapered"] is True
    assert size == 1  # Self-preservation taper locked to 1

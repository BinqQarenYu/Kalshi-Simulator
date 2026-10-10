"""Unit tests for Dynamic Bet Sizing, Bankroll Stepladders, and Chop Asymmetry."""

from decimal import Decimal
import pytest
from kalshi_sim.ml.statistical_ev_engine import StatisticalEVEngine
from kalshi_sim.ml.bot1_v4_engine import Bot1V4DominationEngine
from kalshi_sim.schemas import L2BookState


def test_tier1_micro_bankroll_defense_at_35_dollars() -> None:
    """At $35.00 equity, sizing must remain strictly 1 contract to defend micro-bankroll."""
    # Even with 95% win probability and $60 strike separation:
    contracts = StatisticalEVEngine.compute_conviction_tier(
        ai_prob=0.95,
        price=Decimal("0.48"),
        vpin=0.15,
        time_to_expiry_s=300.0,
        spot_distance_to_strike=60.0,
        total_equity=Decimal("35.00"),
        regime="STORM",
    )
    assert contracts == 1


def test_tier1b_chop_deep_discount_2x_boost() -> None:
    """At $42.00 equity, Warrior 2 Chop Harvester @ $0.38 unlocks 2 contracts (risk only $0.76)."""
    # 1. In Chop: should boost to 2 contracts
    contracts_chop = StatisticalEVEngine.compute_conviction_tier(
        ai_prob=0.70,
        price=Decimal("0.38"),
        vpin=0.20,
        time_to_expiry_s=300.0,
        spot_distance_to_strike=15.0,
        total_equity=Decimal("42.00"),
        regime="CHOP",
    )
    assert contracts_chop == 2

    # 2. In Storm with same equity ($42.00), Storm defense holds at 1 contract
    contracts_storm = StatisticalEVEngine.compute_conviction_tier(
        ai_prob=0.70,
        price=Decimal("0.48"),
        vpin=0.20,
        time_to_expiry_s=300.0,
        spot_distance_to_strike=15.0,
        total_equity=Decimal("42.00"),
        regime="STORM",
    )
    assert contracts_storm == 1


def test_tier2_emerging_capital_at_50_dollars() -> None:
    """At $55.00 equity, high conviction trades scale to 2 contracts in any regime."""
    contracts = StatisticalEVEngine.compute_conviction_tier(
        ai_prob=0.82,
        price=Decimal("0.52"),
        vpin=0.25,
        time_to_expiry_s=250.0,
        spot_distance_to_strike=35.0,
        total_equity=Decimal("55.00"),
        regime="STORM",
    )
    assert contracts == 2


def test_tier3_growth_capital_at_75_dollars() -> None:
    """At $80.00 equity, ultra high conviction trades scale to 3 contracts."""
    contracts = StatisticalEVEngine.compute_conviction_tier(
        ai_prob=0.86,
        price=Decimal("0.50"),
        vpin=0.20,
        time_to_expiry_s=300.0,
        spot_distance_to_strike=50.0,
        total_equity=Decimal("80.00"),
        regime="STORM",
    )
    assert contracts == 3


def test_tier4_star_player_seal_at_100_dollars() -> None:
    """At $100.00+ equity, 4 contracts requires Seal of Star Player."""
    # Without seal: caps at Tier 3 (3 contracts)
    contracts_no_seal = StatisticalEVEngine.compute_conviction_tier(
        ai_prob=0.90,
        price=Decimal("0.50"),
        vpin=0.15,
        time_to_expiry_s=350.0,
        spot_distance_to_strike=55.0,
        total_equity=Decimal("110.00"),
        regime="STORM",
        has_star_player_seal=False,
    )
    assert contracts_no_seal == 3

    # With Seal of Star Player: unlocks 4 contracts
    contracts_star = StatisticalEVEngine.compute_conviction_tier(
        ai_prob=0.90,
        price=Decimal("0.50"),
        vpin=0.15,
        time_to_expiry_s=350.0,
        spot_distance_to_strike=55.0,
        total_equity=Decimal("110.00"),
        regime="STORM",
        has_star_player_seal=True,
    )
    assert contracts_star == 4


def test_seal_of_the_brave_bypass() -> None:
    """Seal of the Brave bypasses equity limits and allows elite 4-contract sizing immediately."""
    contracts_brave = StatisticalEVEngine.compute_conviction_tier(
        ai_prob=0.92,
        price=Decimal("0.45"),
        vpin=0.15,
        time_to_expiry_s=400.0,
        spot_distance_to_strike=60.0,
        total_equity=Decimal("35.00"),  # micro-bankroll
        regime="STORM",
        has_seal_of_the_brave=True,
    )
    assert contracts_brave == 4


def test_bot1_v4_engine_dynamic_sizing_integration() -> None:
    """Verify Bot1V4DominationEngine propagates total_equity and scales sizing dynamically."""
    engine = Bot1V4DominationEngine()
    l2 = L2BookState("KXBTC15M-TEST")

    # 1. At $35 equity, evaluated contracts must be 1
    d_micro = engine.evaluate_market_opportunity(
        spot_price=85060.0,
        target_strike=85000.0,
        time_to_expiry_s=300.0,
        l2_book=l2,
        total_equity=Decimal("35.00"),
    )
    assert d_micro.recommended_contracts <= 1

    # 2. At $60 equity with massive edge ($60 diff), evaluated contracts should scale to 2
    d_scale2 = engine.evaluate_market_opportunity(
        spot_price=85060.0,
        target_strike=85000.0,
        time_to_expiry_s=300.0,
        l2_book=l2,
        total_equity=Decimal("60.00"),
    )
    if d_scale2.recommended_side != "wait":
        assert d_scale2.recommended_contracts == 2

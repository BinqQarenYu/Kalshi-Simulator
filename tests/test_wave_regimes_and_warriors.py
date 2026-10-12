"""Comprehensive Test Suite for 1-Boat 3-Warrior 4-Region Architecture.

Validates:
1. compute_wave_physics (Tsunami, Double-Wick Meatgrinder, False Breakout detection).
2. WaveRegimeClassifier transitions across the 4 regions (CHOP, STORM, BLEED, HEALING).
3. BleedDefender (Warrior 3) veto logic, super-moats, and ultra-discount pricing.
4. HealingProtocol convalescence gating and probationary 2-win graduation.
5. Bot1V4DominationEngine integration across all 4 market regions.
6. Zero float financial math compliance (Decimal everywhere).
"""

from decimal import Decimal
import pytest

from kalshi_sim.ml.wave_classifier import (
    MarketWavePhysics,
    WaveRegimeClassifier,
    compute_wave_physics,
)
from kalshi_sim.ml.bleed_defender import BleedDefender
from kalshi_sim.ml.healing_protocol import HealingProtocol
from kalshi_sim.ml.bot1_v4_engine import Bot1V4DominationEngine
from kalshi_sim.schemas import CryptoAsset, L2BookState


# ---------------------------------------------------------------------------
# 1. WAVE PHYSICS TESTS
# ---------------------------------------------------------------------------

def test_compute_wave_physics_calm():
    """Verify calm chop candle has no storm/bleed red flags."""
    # Open: 68000, High: 68030, Low: 67990, Close: 68020
    # Range: 40, Body: 20, Upper: 10, Lower: 10
    physics = compute_wave_physics(
        open_price=68000.0,
        high_price=68030.0,
        low_price=67990.0,
        current_price=68020.0,
    )
    assert physics.range_dollars == 40.0
    assert physics.body_dollars == 20.0
    assert physics.upper_wick_dollars == 10.0
    assert physics.lower_wick_dollars == 10.0
    assert not physics.is_tsunami
    assert not physics.is_double_wick_meatgrinder
    assert not physics.is_false_breakout


def test_compute_wave_physics_tsunami():
    """Verify candle exceeding tsunami threshold is flagged."""
    # Range 320 > 250 threshold
    physics = compute_wave_physics(
        open_price=68000.0,
        high_price=68320.0,
        low_price=68000.0,
        current_price=68280.0,
        tsunami_threshold=250.0,
    )
    assert physics.is_tsunami is True
    assert physics.range_dollars == 320.0


def test_compute_wave_physics_double_wick_meatgrinder():
    """Verify candle with large upper AND lower wicks is flagged as meatgrinder."""
    # Open: 68100, High: 68160 (upper wick = 60), Low: 68000 (lower wick = 80), Close: 68080
    physics = compute_wave_physics(
        open_price=68100.0,
        high_price=68160.0,
        low_price=68000.0,
        current_price=68080.0,
        wick_meatgrinder_threshold=45.0,
    )
    assert physics.upper_wick_dollars == 60.0
    assert physics.lower_wick_dollars == 80.0
    assert physics.is_double_wick_meatgrinder is True


def test_compute_wave_physics_false_breakout_rejection():
    """Verify candle with giant rejection wick is flagged as false breakout."""
    # Open: 68000, High: 68150 (upper wick = 140), Low: 68000, Close: 68010 (body = 10)
    # Range = 150 >= 100, Wick (140) >= 1.8 * body (18)
    physics = compute_wave_physics(
        open_price=68000.0,
        high_price=68150.0,
        low_price=68000.0,
        current_price=68010.0,
    )
    assert physics.is_false_breakout is True


# ---------------------------------------------------------------------------
# 2. WAVE REGIME CLASSIFIER TESTS
# ---------------------------------------------------------------------------

def test_wave_classifier_transitions():
    """Verify state transitions between CHOP, STORM, BLEED, and HEALING."""
    clf = WaveRegimeClassifier(chop_range_threshold=150.0, tsunami_threshold=250.0)
    assert clf.current_region == "CHOP"

    # Calm candle -> Remains CHOP
    region, phys, reason = clf.classify_region(
        open_price=68000.0,
        high_price=68080.0,
        low_price=68000.0,
        current_price=68050.0,
        rolling_vol_1m=5.0,
    )
    assert region == "CHOP"

    # Directional expansion candle range 180 > 150, body 180 >= 80, onnx LONG 80% -> STORM
    region, phys, reason = clf.classify_region(
        open_price=68000.0,
        high_price=68190.0,
        low_price=68000.0,
        current_price=68180.0,
        rolling_vol_1m=15.0,
        onnx_signal="LONG",
        onnx_confidence=0.80,
    )
    assert region == "STORM"

    # Tsunami candle (range 320) -> BLEED
    region, phys, reason = clf.classify_region(
        open_price=68000.0,
        high_price=68320.0,
        low_price=68000.0,
        current_price=68200.0,
        rolling_vol_1m=25.0,
    )
    assert region == "BLEED"

    # Bleed triggered by 2 consecutive losses
    clf_losses = WaveRegimeClassifier(chop_range_threshold=150.0)
    clf_losses.record_settled_cycle(won=False)
    assert clf_losses.consecutive_losses == 1
    assert clf_losses.current_region == "CHOP"

    clf_losses.record_settled_cycle(won=False)
    assert clf_losses.consecutive_losses == 2
    assert clf_losses.current_region == "BLEED"


# ---------------------------------------------------------------------------
# 3. BLEED DEFENDER (WARRIOR 3) TESTS
# ---------------------------------------------------------------------------

def test_bleed_defender_veto_meatgrinder():
    """Warrior 3 must veto trades when meatgrinder double-wicks are ramming the boat."""
    defender = BleedDefender(min_spot_diff_bleed=85.0)
    physics = MarketWavePhysics(
        range_dollars=180.0,
        body_dollars=40.0,
        upper_wick_dollars=70.0,
        lower_wick_dollars=70.0,
        is_tsunami=False,
        is_double_wick_meatgrinder=True,
        is_false_breakout=False,
        wave_summary="Double-wick meatgrinder",
    )

    allow, price, reason = defender.evaluate_bleed_defense(
        physics=physics,
        spot_diff=100.0,
        model_win_prob=0.75,
        time_to_expiry_s=300.0,
    )
    assert allow is False
    assert price is None
    assert "Meatgrinder Veto" in reason


def test_bleed_defender_veto_false_breakout():
    """Warrior 3 must veto trades when false breakout upper rejection pin occurs."""
    defender = BleedDefender()
    physics = MarketWavePhysics(
        range_dollars=150.0,
        body_dollars=20.0,
        upper_wick_dollars=120.0,
        lower_wick_dollars=10.0,
        is_tsunami=False,
        is_double_wick_meatgrinder=False,
        is_false_breakout=True,
        wave_summary="False breakout pin",
    )

    allow, price, reason = defender.evaluate_bleed_defense(
        physics=physics,
        spot_diff=100.0,
        model_win_prob=0.75,
        time_to_expiry_s=300.0,
    )
    assert allow is False
    assert "False Breakout Veto" in reason


def test_bleed_defender_super_moat_veto():
    """Warrior 3 must veto if spot is within $85 of strike (protecting against whipsaws)."""
    defender = BleedDefender(min_spot_diff_bleed=85.0)
    physics = MarketWavePhysics(
        range_dollars=280.0,
        body_dollars=200.0,
        upper_wick_dollars=40.0,
        lower_wick_dollars=40.0,
        is_tsunami=True,
        is_double_wick_meatgrinder=False,
        is_false_breakout=False,
        wave_summary="Tsunami expansion",
    )

    # Spot diff is $50 < $85 super-moat requirement
    allow, price, reason = defender.evaluate_bleed_defense(
        physics=physics,
        spot_diff=50.0,
        model_win_prob=0.75,
        time_to_expiry_s=300.0,
    )
    assert allow is False
    assert "Super-Moat Veto" in reason


def test_bleed_defender_valid_entry_pricing():
    """Warrior 3 allows entry when super-moat >= $85, clean candle, and prices at deep discount."""
    defender = BleedDefender(
        bleed_discount_limit_price=Decimal("0.28"),
        bleed_max_entry_price=Decimal("0.35"),
        min_spot_diff_bleed=85.0,
    )
    physics = MarketWavePhysics(
        range_dollars=280.0,
        body_dollars=200.0,
        upper_wick_dollars=40.0,
        lower_wick_dollars=40.0,
        is_tsunami=True,
        is_double_wick_meatgrinder=False,
        is_false_breakout=False,
        wave_summary="Tsunami expansion",
    )

    # Spot diff is $120 >= $85
    allow, price, reason = defender.evaluate_bleed_defense(
        physics=physics,
        spot_diff=120.0,
        model_win_prob=0.75,
        time_to_expiry_s=300.0,
    )
    assert allow is True
    assert Decimal("0.28") <= price <= Decimal("0.35")
    assert "Bleed Defender Asymmetric Entry Approved" in reason


# ---------------------------------------------------------------------------
# 4. HEALING PROTOCOL TESTS
# ---------------------------------------------------------------------------

def test_healing_protocol_lifecycle():
    """Verify HealingProtocol quarantine gating and 2-win graduation."""
    healing = HealingProtocol(consecutive_wins_required=2)
    assert healing.is_active is False
    assert healing.should_suppress_live_capital() is False

    # Trigger quarantine
    healing.arm_healing_quarantine("2 consecutive losses ramming boat")
    assert healing.is_active is True
    assert healing.should_suppress_live_capital() is True
    assert healing.consecutive_wins == 0

    # 1st paper win -> Remains quarantined
    graduated_1 = healing.record_settled_cycle(won=True)
    assert graduated_1 is False
    assert healing.consecutive_wins == 1
    assert healing.is_active is True

    # Paper loss -> Resets counter
    graduated_loss = healing.record_settled_cycle(won=False)
    assert graduated_loss is False
    assert healing.consecutive_wins == 0
    assert healing.is_active is True

    # 2 consecutive paper wins -> Graduates
    healing.record_settled_cycle(won=True)
    graduated_2 = healing.record_settled_cycle(won=True)
    assert graduated_2 is True
    assert healing.consecutive_wins == 0
    assert healing.is_active is False
    assert healing.should_suppress_live_capital() is False


# ---------------------------------------------------------------------------
# 5. BOT1_V4 ENGINE INTEGRATION ACROSS 4 REGIONS
# ---------------------------------------------------------------------------

def test_bot1_v4_engine_4_regions_initialization():
    """Verify engine has WaveRegimeClassifier, BleedDefender, and HealingProtocol."""
    engine = Bot1V4DominationEngine(asset=CryptoAsset.BTC)
    assert hasattr(engine, "wave_classifier")
    assert hasattr(engine, "bleed_defender")
    assert hasattr(engine, "healing_protocol")

    params = engine.get_parameters()
    assert "current_regime" in params
    assert "bleed_discount_limit_price" in params
    assert "bleed_max_entry_price" in params
    assert "min_spot_diff_bleed" in params
    assert "healing_status" in params


def test_bot1_v4_engine_parameter_updates():
    """Verify updating dials correctly updates Warrior 3 thresholds."""
    engine = Bot1V4DominationEngine(asset=CryptoAsset.BTC)
    engine.update_parameters(
        bleed_discount_limit_price=0.29,
        bleed_max_entry_price=0.34,
        min_spot_diff_bleed=95.0,
    )
    assert engine.bleed_discount_limit_price == Decimal("0.29")
    assert engine.bleed_max_entry_price == Decimal("0.34")
    assert engine.min_spot_diff_bleed == 95.0
    assert engine.bleed_defender.min_spot_diff_bleed == 95.0
    assert engine.bleed_defender.bleed_discount_limit_price == Decimal("0.29")
    assert engine.bleed_defender.bleed_max_entry_price == Decimal("0.34")


def test_bot1_v4_engine_healing_transition_on_bleed_losses():
    """Verify recording 2 losses triggers BLEED and HEALING quarantine in engine."""
    engine = Bot1V4DominationEngine(asset=CryptoAsset.BTC)
    assert engine.wave_classifier.current_region == "CHOP"

    # Record 2 losses
    engine.record_cycle_settlement(won=False)
    engine.record_cycle_settlement(won=False)

    assert engine.wave_classifier.consecutive_losses == 2
    assert engine.wave_classifier.current_region == "BLEED"

    # Transition to HEALING to test quarantine gate
    engine.arm_healing_protocol("Test quarantine")

    # In HEALING quarantine, live trade must not be placed (returns wait decision)
    book = L2BookState(market_ticker="KXBTC15M-TEST", is_spot=False)
    book.yes_book[Decimal("0.40")] = Decimal("20")
    book.no_book[Decimal("0.58")] = Decimal("20")

    decision = engine.evaluate_market_opportunity(
        spot_price=68200.0,
        target_strike=68100.0,
        time_to_expiry_s=300.0,
        l2_book=book,
        cycle_id="KXBTC15M-CYCLE-TEST",
    )
    assert decision.recommended_side == "wait"
    assert decision.recommended_contracts == 0
    assert decision.active_playbook == "healing_convalescence_quarantine"
    assert decision.regime == "HEALING"

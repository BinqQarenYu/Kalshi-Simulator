"""tests/test_fast_taker_win_lock.py
Unit tests verifying the Fast Taker Win Lock Engine ("A Win is Truly a Win Even with Fees").
Verifies Scenarios A, B, C, D, Zero Float Decimal math, order_type="market", and fee deductions.
"""

from decimal import Decimal
import pytest

from kalshi_sim.schemas import L2BookState, OrderSide
from kalshi_sim.ml.bot1_v4_engine import Bot1V4DominationEngine
from kalshi_sim.ml.domination_exit_evaluator import DominationExitEvaluator, DominationExitDecision


def _create_mock_l2_book(
    best_yes_bid: str = "0.78",
    best_yes_ask: str = "0.80",
    best_no_bid: str = "0.20",
) -> L2BookState:
    """Create a mock L2 book with exact bid/ask depth."""
    book = L2BookState(market_ticker="KXBTC15M-TEST-FAST")
    book.yes_book = {Decimal(best_yes_bid): Decimal("100")}
    book.no_book = {Decimal(best_no_bid): Decimal("100")}
    return book


@pytest.fixture
def bot1_v4():
    """Create a configured Bot1V4DominationEngine with Fast Win Lock enabled."""
    return Bot1V4DominationEngine(
        enable_fast_win_lock=True,
        fast_lock_asymmetric_bid=Decimal("0.78"),
        min_fast_lock_bid=Decimal("0.68"),
        min_fast_lock_roi=0.35,
        fast_lock_late_cycle_roi=0.20,
        fee_per_contract=Decimal("0.01"),
    )


@pytest.fixture
def exit_eval(bot1_v4):
    """Create exit evaluator bound to bot1_v4."""
    return DominationExitEvaluator(bot1_v4)


def test_scenario_a_asymmetric_rr_inversion(bot1_v4, exit_eval):
    """Scenario A: When bid reaches $0.78+, risking 78c to make 22c is negative EV.
    Exit immediately into the bid via market order and pay the $0.01 fee to lock in win.
    """
    book = _create_mock_l2_book(best_yes_bid="0.78", best_yes_ask="0.80")

    decision = exit_eval.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.45"),
        size=1,
        book=book,
        time_to_expiry_s=300.0,
        spot_price=78700.0,
        target_strike=78650.0,
        spot_velocity_3s=2.0,
    )

    assert decision.should_exit is True
    assert decision.exit_reason in ("FAST_WIN_LOCK_FEE_ADVANTAGE", "ASYMMETRIC_PEAK_HARVEST")
    assert decision.order_type == "market"
    assert decision.exit_price == Decimal("0.78")
    # Gross PnL: 0.78 - 0.45 = 0.33. Net PnL after $0.01 fee: 0.32
    assert decision.unrealized_pnl == Decimal("0.32")
    assert isinstance(decision.exit_price, Decimal)
    assert isinstance(decision.unrealized_pnl, Decimal)


def test_scenario_b_chop_regime_rapid_scalp_lock(bot1_v4, exit_eval):
    """Scenario B: In CHOP/BLEED oscillating regime, exit once ROI >= 35% and bid >= $0.68
    to prevent mean reversion from destroying gains.
    """
    bot1_v4.current_regime = "CHOP"
    book = _create_mock_l2_book(best_yes_bid="0.70", best_yes_ask="0.72")

    decision = exit_eval.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.48"),
        size=1,
        book=book,
        time_to_expiry_s=300.0,  # inside chop window (150s - 450s)
        spot_price=78670.0,
        target_strike=78650.0,
        spot_velocity_3s=0.0,
        rolling_vol_1m=10.0,  # low chop vol
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "FAST_WIN_LOCK_FEE_ADVANTAGE"
    assert decision.order_type == "market"
    assert decision.exit_price == Decimal("0.70")
    # Net PnL: 0.70 - 0.48 - 0.01 = 0.21
    assert decision.unrealized_pnl == Decimal("0.21")


def test_scenario_c_late_cycle_gamma_defense(bot1_v4, exit_eval):
    """Scenario C: Inside the 3-minute death window (15s < T <= 180s), if ROI >= 20%
    and bid >= $0.68, dump into bid immediately with fee to eliminate jump diffusion wipeout.
    """
    book = _create_mock_l2_book(best_yes_bid="0.69", best_yes_ask="0.71")

    decision = exit_eval.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.50"),
        size=1,
        book=book,
        time_to_expiry_s=120.0,  # 2 minutes left (inside 180s cliff)
        spot_price=78660.0,
        target_strike=78650.0,
        spot_velocity_3s=1.0,
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "FAST_WIN_LOCK_FEE_ADVANTAGE"
    assert decision.order_type == "market"
    assert decision.exit_price == Decimal("0.69")
    # Net PnL: 0.69 - 0.50 - 0.01 = 0.18
    assert decision.unrealized_pnl == Decimal("0.18")


def test_scenario_d_kinetic_exhaustion_dump(bot1_v4, exit_eval):
    """Scenario D: In transition zone (T <= 240s), adverse spot velocity of >= 5.0 $/3s
    detected while position is in profit (ROI >= 25%, Bid >= $0.65). Dump into bid immediately
    before orderbook vacuum pulls resting liquidity.
    """
    book = _create_mock_l2_book(best_yes_bid="0.66", best_yes_ask="0.68")

    decision = exit_eval.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.48"),
        size=1,
        book=book,
        time_to_expiry_s=210.0,  # Transition zone
        spot_price=78655.0,
        target_strike=78650.0,  # moneyness is only +$5, not deep ITM
        spot_velocity_3s=-8.0,  # sharp adverse drop (-8.0 $/3s)
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "FAST_WIN_LOCK_FEE_ADVANTAGE"
    assert decision.order_type == "market"
    assert decision.exit_price == Decimal("0.66")
    # Net PnL: 0.66 - 0.48 - 0.01 = 0.17
    assert decision.unrealized_pnl == Decimal("0.17")


def test_fast_win_lock_disabled_honors_flag(bot1_v4, exit_eval):
    """When enable_fast_win_lock=False, fast taker lock does NOT trigger."""
    bot1_v4.enable_fast_win_lock = False
    book = _create_mock_l2_book(best_yes_bid="0.70", best_yes_ask="0.72")

    decision = exit_eval.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.48"),
        size=1,
        book=book,
        time_to_expiry_s=300.0,
        spot_price=78700.0,
        target_strike=78650.0,
        spot_velocity_3s=2.0,
    )

    # At $0.70 with favorable drift and healthy trend, it should hold
    assert decision.should_exit is False


# =========================================================================
# PART 2 TESTS: TAKER CAPITAL SALVAGE (CRASHING / ADVERSE TRADES)
# =========================================================================

def test_part2_valley_ejector_taker_market_salvage(bot1_v4, exit_eval):
    """Part 2: When contract price collapses to $0.35 with >= 70% adverse conviction,
    VALLEY_EJECTOR must exit via an immediate market order (order_type='market')
    to salvage capital ($0.34 net) instead of suffering a 100% expiration loss ($0.00).
    """
    book = _create_mock_l2_book(best_yes_bid="0.35", best_yes_ask="0.37", best_no_bid="0.63")

    decision = exit_eval.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.45"),
        size=1,
        book=book,
        time_to_expiry_s=300.0,
        spot_price=78500.0,  # $150 below strike = strong adverse conviction
        target_strike=78650.0,
        spot_velocity_3s=-5.0,
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "VALLEY_EJECTOR"
    assert decision.order_type == "market"
    assert decision.exit_price == Decimal("0.35")
    # Loss is capped at -(0.45 - 0.35 + 0.01) = -$0.11 instead of -$0.45 total loss!
    assert decision.unrealized_pnl == Decimal("-0.11")


def test_part2_kinetic_crash_salvage_taker_knife_defense(bot1_v4, exit_eval):
    """Part 2: When adverse spot velocity spikes severely (>= 12.0 $/3s) and bid is <= $0.40,
    KINETIC_CRASH_SALVAGE immediately dumps via market order to rescue capital before liquidity vanishes.
    """
    book = _create_mock_l2_book(best_yes_bid="0.39", best_yes_ask="0.41", best_no_bid="0.59")

    decision = exit_eval.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.48"),
        size=1,
        book=book,
        time_to_expiry_s=250.0,
        spot_price=78620.0,  # $30 below strike
        target_strike=78650.0,
        spot_velocity_3s=-16.0,  # violent adverse drop (-16.0 $/3s)
    )

    assert decision.should_exit is True
    assert decision.exit_reason in ("KINETIC_CRASH_SALVAGE", "VALLEY_EJECTOR")
    assert decision.order_type == "market"
    assert decision.exit_price <= Decimal("0.40")


# =========================================================================
# PART 3 TESTS: TAKER DYNAMIC BREAKOUT ENTRY (HIGH-VELOCITY WAVE PENETRATION)
# =========================================================================

def test_part3_taker_breakout_entry_high_velocity():
    """Part 3: In high-velocity breakout waves (|v| >= 15.0 $/3s) with high conviction (>= 78%),
    Bot 1 V4 executes an immediate taker market buy (order_type='market') to penetrate the wave.
    """
    bot = Bot1V4DominationEngine(
        enable_taker_breakout_entry=True,
        taker_breakout_min_velocity=15.0,
        taker_breakout_min_confidence=0.78,
        max_taker_entry_price=Decimal("0.52"),
        min_confidence=0.72,
    )
    book = _create_mock_l2_book(best_yes_bid="0.46", best_yes_ask="0.50", best_no_bid="0.50")

    decision = bot.evaluate(
        book=book,
        spot_price=78750.0,  # Spot is surging $100 above strike
        target_strike=78650.0,
        time_to_expiry_s=400.0,
        total_equity=Decimal("35.00"),
        spot_velocity_3s=22.0,  # Violent positive surge (+22.0 $/3s)
    )

    assert decision.recommended_side == "yes"
    assert decision.active_playbook == "playbook1_breakout"
    assert decision.order_type == "market"
    assert decision.limit_price <= 0.52
    assert "TAKER BREAKOUT ENTRY" in decision.rationale


def test_part3_standard_drift_uses_maker_limit_order():
    """Part 3 Control: When velocity is calm (< 15.0 $/3s), Bot 1 V4 stays passive
    and places a maker limit order (order_type='limit') to avoid paying fees.
    """
    bot = Bot1V4DominationEngine(
        enable_taker_breakout_entry=True,
        taker_breakout_min_velocity=15.0,
        min_confidence=0.72,
    )
    book = _create_mock_l2_book(best_yes_bid="0.44", best_yes_ask="0.46", best_no_bid="0.54")

    decision = bot.evaluate(
        book=book,
        spot_price=78720.0,  # Favorable spot
        target_strike=78650.0,
        time_to_expiry_s=400.0,
        total_equity=Decimal("35.00"),
        spot_velocity_3s=5.0,  # Calm velocity (+5.0 $/3s)
    )

    if decision.recommended_side != "wait":
        assert decision.order_type == "limit"


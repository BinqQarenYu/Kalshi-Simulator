"""tests/test_doubt_harvest.py
Unit tests for the Council-approved 50% Profit + Doubt-Harvest Engine in Bot 1 V4.
"""

from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock
import pytest

from kalshi_sim.schemas import L2BookState, OrderSide
from kalshi_sim.ml.bot1_v4_engine import Bot1V4DominationEngine
from kalshi_sim.ml.domination_exit_evaluator import DominationExitEvaluator, DominationExitDecision


def _create_mock_l2_book(
    best_yes_bid: str = "0.58",
    best_yes_ask: str = "0.60",
    best_no_bid: Optional[str] = None,
) -> L2BookState:
    """Create a valid mock L2 book state."""
    book = L2BookState(market_ticker="KXBTC15M-TEST-00")
    y_bid = Decimal(best_yes_bid)
    n_bid = Decimal("1.00") - Decimal(best_yes_ask) if best_no_bid is None else Decimal(best_no_bid)
    book.yes_book = {y_bid: Decimal("100")}
    book.no_book = {n_bid: Decimal("100")}
    return book


@pytest.fixture
def bot1_v4():
    """Create a configured Bot1V4DominationEngine instance."""
    return Bot1V4DominationEngine(
        enable_doubt_harvest=True,
        doubt_threshold=0.55,
        upside_capture_ratio_threshold=0.50,
        asymmetric_peak_bid=Decimal("0.88"),
    )


@pytest.fixture
def exit_eval(bot1_v4):
    """Create DominationExitEvaluator bound to bot1_v4."""
    return DominationExitEvaluator(bot1_v4)


def test_low_doubt_holds_healthy_trend(bot1_v4, exit_eval):
    """When up 50% profit ($0.75 bid) but market has high confidence & low doubt, HOLD for $1.00."""
    book = _create_mock_l2_book(best_yes_bid="0.75", best_yes_ask="0.77")

    # Mock high conviction in YES (spot $78700 vs strike $78650)
    decision = exit_eval.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.55"),
        size=1,
        book=book,
        time_to_expiry_s=300.0,
        spot_price=78700.0,
        target_strike=78650.0,
        spot_velocity_3s=5.0,  # Favorable upward velocity
    )

    # Under healthy trend without doubt, bot should NOT exit at $0.75; it aims for $1.00
    assert decision.should_exit is False
    assert decision.exit_reason in ("NONE", "HOLD")


def test_doubt_harvest_triggered_on_reversal(bot1_v4, exit_eval):
    """When up 50% profit ($0.75 bid) and direction reverses (Doubt >= 0.55), lock in banked profit."""
    book = _create_mock_l2_book(best_yes_bid="0.75", best_yes_ask="0.77")

    # Spot is declining sharply back toward strike, adverse velocity is -20.0 $/3s
    decision = exit_eval.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.55"),
        size=1,
        book=book,
        time_to_expiry_s=200.0,
        spot_price=78651.0,
        target_strike=78650.0,
        spot_velocity_3s=-20.0,  # Severe adverse dump against our YES position
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "DOUBT_PROFIT_HARVEST"
    assert decision.exit_price == Decimal("0.75")
    assert decision.unrealized_pnl > Decimal("0.10")  # Net profit strictly positive after fees


def test_asymmetric_peak_harvest(bot1_v4, exit_eval):
    """When contract bid reaches $0.88+, take profit unconditionally to eliminate 1:7 downside trap."""
    book = _create_mock_l2_book(best_yes_bid="0.89", best_yes_ask="0.91")

    decision = exit_eval.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.55"),
        size=1,
        book=book,
        time_to_expiry_s=400.0,
        spot_price=78750.0,
        target_strike=78650.0,
        spot_velocity_3s=0.0,
    )

    assert decision.should_exit is True
    assert decision.exit_reason in ("ASYMMETRIC_PEAK_HARVEST", "TAKE_PROFIT_CEILING")
    assert decision.exit_price == Decimal("0.89")
    assert decision.unrealized_pnl >= Decimal("0.30")


def test_silas_twap_invariance_vetoes_exit_near_settlement(bot1_v4, exit_eval):
    """At T <= 30s, if trailing 60s TWAP is deep ITM, veto exit to collect full $1.00 payout."""
    book = _create_mock_l2_book(best_yes_bid="0.78", best_yes_ask="0.80")

    decision = exit_eval.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.55"),
        size=1,
        book=book,
        time_to_expiry_s=18.0,  # Within Silas TWAP window (T <= 30s)
        spot_price=78660.0,
        target_strike=78650.0,
        spot_velocity_3s=-15.0,  # Negative velocity, but TWAP is locked
        twap_60s=78675.0,  # Official 60s TWAP is +$25 ITM
    )

    # Silas TWAP invariance must veto the harvest to avoid paying 2c fee and collect $1.00
    assert decision.should_exit is False


def test_evaluate_exit_with_position_object(exit_eval):
    """Verify that evaluate_exit handles position object without positional argument error."""
    mock_pos = MagicMock()
    mock_pos.side = OrderSide.NO
    mock_pos.entry_price = Decimal("0.52")
    mock_pos.size = 1

    book = _create_mock_l2_book(best_yes_bid="0.10", best_yes_ask="0.12", best_no_bid="0.88")

    decision = exit_eval.evaluate_exit(
        position=mock_pos,
        book=book,
        time_to_expiry_s=150.0,
        spot_price=78600.0,
        target_strike=78650.0,
    )

    assert isinstance(decision, DominationExitDecision)
    assert decision.should_exit is True
    assert decision.exit_price == Decimal("0.88")


def test_nine_minute_minor_noise_does_not_trigger_doubt_exit(bot1_v4, exit_eval):
    """At 9 minutes left (T=540s), a -$10 dip is routine Brownian noise; bot holds winner."""
    book = _create_mock_l2_book(best_yes_bid="0.75", best_yes_ask="0.77")

    # With 9 min left (540s), strike is 78650, spot is 78690 (+40 moat)
    # Adverse velocity is -$10.0
    decision = exit_eval.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.55"),
        size=1,
        book=book,
        time_to_expiry_s=540.0,
        spot_price=78690.0,
        target_strike=78650.0,
        spot_velocity_3s=-10.0,
    )

    # Must NOT panic dump; 9 minutes remaining allows normal breathing
    assert decision.should_exit is False


def test_ninety_second_adverse_velocity_triggers_prompt_doubt_exit(bot1_v4, exit_eval):
    """At 90 seconds left (T=90s), that same -$10 dip is a lethal threat; bot locks in profit."""
    book = _create_mock_l2_book(best_yes_bid="0.75", best_yes_ask="0.77")

    # With only 90s left, that same -$10.0 adverse velocity threatens expiration settlement
    decision = exit_eval.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.55"),
        size=1,
        book=book,
        time_to_expiry_s=90.0,
        spot_price=78660.0,
        target_strike=78650.0,
        spot_velocity_3s=-10.0,
    )

    # Must immediately harvest to protect capital!
    assert decision.should_exit is True
    assert decision.exit_reason == "DOUBT_PROFIT_HARVEST"
    assert decision.exit_price == Decimal("0.75")


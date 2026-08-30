"""Unit tests for the 3-Step Domination Bot strategy engine."""

from decimal import Decimal
import pytest

from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
from kalshi_sim.schemas import L2BookState, OrderBookLevel, OrderSide


def test_domination_bot_playbook3_late_gamma_snub() -> None:
    bot = ThreeStepDominationBot(min_edge_pct=0.05, min_ev_dollars=Decimal("0.02"))

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.75"): Decimal("100"), Decimal("0.72"): Decimal("200")}
    book.no_book = {Decimal("0.25"): Decimal("100"), Decimal("0.28"): Decimal("200")}

    # T = 120s (2 minutes left), spot is +$30 above strike ($78680 vs $78650)
    decision = bot.evaluate(
        book=book,
        spot_price=78680.0,
        target_strike=78650.0,
        time_to_expiry_s=120.0,
        total_equity=Decimal("100.00"),
        max_position_size=10,
        estimated_vpin=0.10,
    )

    assert decision.strategy_id == "3_step_domination_bot"
    assert decision.playbook_stage == "gamma_snub"
    assert "Playbook 3" in decision.active_playbook
    assert decision.p_up > 0.85
    assert decision.vpin_is_safe is True
    assert decision.recommended_side == "yes"
    assert decision.recommended_contracts > 0


def test_domination_bot_playbook2_mid_cycle_ofi_drift() -> None:
    bot = ThreeStepDominationBot(min_edge_pct=0.05, min_ev_dollars=Decimal("0.02"))

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.55"): Decimal("300")}
    book.no_book = {Decimal("0.45"): Decimal("100")}

    # T = 420s (7 minutes left), spot is +$15 above strike
    decision = bot.evaluate(
        book=book,
        spot_price=78665.0,
        target_strike=78650.0,
        time_to_expiry_s=420.0,
        total_equity=Decimal("100.00"),
        max_position_size=10,
        estimated_vpin=0.20,
    )

    assert decision.strategy_id == "3_step_domination_bot"
    assert decision.playbook_stage == "drift"
    assert "Playbook 2" in decision.active_playbook


def test_domination_bot_vpin_toxicity_veto() -> None:
    bot = ThreeStepDominationBot()

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.50"): Decimal("100")}
    book.no_book = {Decimal("0.50"): Decimal("100")}

    # High VPIN = 0.85 > threshold
    decision = bot.evaluate(
        book=book,
        spot_price=78660.0,
        target_strike=78650.0,
        time_to_expiry_s=180.0,
        total_equity=Decimal("100.00"),
        max_position_size=10,
        estimated_vpin=0.85,
    )

    assert decision.vpin_is_safe is False
    assert decision.recommended_side == "wait"
    assert "VPIN Toxicity Veto" in decision.rationale

"""Unit tests for Dominion 2 Bot (Anti-Pin Asymmetric Scalper).

Verifies the mathematical rigor, four playbooks, hard entry ceiling, asymmetric discount hunting,
Kalshi settlement tie exploitation, and anti-pin defense.
"""

from decimal import Decimal
import pytest

from app_1_machine_engine.ml.dominion_2_bot import (
    Dominion2Bot,
    Dominion2Decision,
    Dominion2ExitDecision,
)
from shared.schemas import L2BookState, OrderSide, TradeEvent


@pytest.fixture
def dominion_bot() -> Dominion2Bot:
    """Initialize a fresh Dominion 2 Bot instance."""
    return Dominion2Bot(
        max_entry_price=Decimal("0.55"),
        min_edge_pct=0.04,
        vpin_toxic_threshold=0.45,
        anti_pin_diff_threshold=25.0,
        anti_pin_time_threshold_s=180.0,
        asymmetric_sweet_spot_max=Decimal("0.45"),
    )


def test_hard_entry_price_ceiling_veto(dominion_bot: Dominion2Bot):
    """Test Pillar 1: Dominion 2 strictly rejects buying contracts priced above $0.55."""
    book = L2BookState("KXBTC15M-T78000")
    # In binary CLOB: yes_ask = 1 - max(no_book), no_ask = 1 - max(yes_book)
    # To test expensive asks ($0.75 > $0.55 ceiling), set opposite bids to $0.25
    book.no_book = {Decimal("0.25"): Decimal("500")}   # best_yes_ask = 1.0 - 0.25 = 0.75
    book.yes_book = {Decimal("0.25"): Decimal("500")}  # best_no_ask = 1.0 - 0.25 = 0.75

    decision = dominion_bot.evaluate(
        book=book,
        spot_price=78150.0,  # Spot > Strike, strong upward momentum
        target_strike=78000.0,
        time_to_expiry_s=400.0,
        total_equity=Decimal("100.00"),
        max_position_size=4,
    )

    # Even with high probability, trade MUST be vetoed due to price ceiling
    assert decision.recommended_side == "wait"
    assert decision.max_price_veto is True
    assert "Ceiling Veto" in decision.rationale or "Exceeds Hard Max" in decision.rationale or "exceeds ceiling" in decision.rationale


def test_asymmetric_discount_hunting_playbook_1(dominion_bot: Dominion2Bot):
    """Test Pillar 2: Asymmetric Discount Band ($0.25 - $0.45) triggers Playbook 1 breakout entry."""
    book = L2BookState("KXBTC15M-T78000")
    # YES ask is in sweet-spot ($0.38)
    book.yes_book = {Decimal("0.38"): Decimal("500"), Decimal("0.42"): Decimal("1000")}
    book.no_book = {Decimal("0.65"): Decimal("500")}

    decision = dominion_bot.evaluate(
        book=book,
        spot_price=78080.0,  # Spot > Strike + $80
        target_strike=78000.0,
        time_to_expiry_s=700.0,  # Early stage (11.6m remaining)
        total_equity=Decimal("100.00"),
        max_position_size=4,
    )

    assert decision.recommended_side == "yes"
    assert decision.playbook_stage == "asymmetric_breakout"
    assert decision.edge_pct >= 0.04
    assert decision.recommended_contracts in range(1, 5)
    assert not decision.max_price_veto
    assert not decision.anti_pin_veto


def test_kalshi_tie_rule_no_exploitation_playbook_2(dominion_bot: Dominion2Bot):
    """Test Pillar 3: Kalshi Tie Rule (Spot <= Strike => NO wins) defaults to NO in consolidating markets."""
    book = L2BookState("KXBTC15M-T78000")
    # NO ask is cheap ($0.35)
    book.yes_book = {Decimal("0.68"): Decimal("500")}
    book.no_book = {Decimal("0.35"): Decimal("500"), Decimal("0.40"): Decimal("1000")}

    decision = dominion_bot.evaluate(
        book=book,
        spot_price=77990.0,  # Near strike, slightly below (-$10)
        target_strike=78000.0,
        time_to_expiry_s=450.0,  # Mid stage (7.5m remaining)
        total_equity=Decimal("100.00"),
        max_position_size=4,
    )

    assert decision.recommended_side == "no"
    assert decision.playbook_stage == "tie_exploiter"
    assert "Tie Edge" in decision.active_playbook or "Tie" in decision.active_playbook
    assert decision.recommended_contracts in range(1, 5)


def test_anti_pin_tie_defense_veto_playbook_3(dominion_bot: Dominion2Bot):
    """Test Pillar 4: Anti-Pin Defense strictly vetoes entries within +/-$25 strike pin with < 180s left."""
    book = L2BookState("KXBTC15M-T78000")
    book.yes_book = {Decimal("0.45"): Decimal("500")}
    book.no_book = {Decimal("0.45"): Decimal("500")}

    # Pin condition: Spot is $78005.00 (+5 from strike) and only 120s remaining
    decision = dominion_bot.evaluate(
        book=book,
        spot_price=78005.0,
        target_strike=78000.0,
        time_to_expiry_s=120.0,  # < 180s
        total_equity=Decimal("100.00"),
        max_position_size=4,
    )

    assert decision.recommended_side == "wait"
    assert decision.anti_pin_veto is True
    assert "Anti-Pin" in decision.rationale or "Pin Veto" in decision.rationale


def test_confirmed_moneyness_late_entry(dominion_bot: Dominion2Bot):
    """Test Playbook 3: Confirmed Moneyness allows trade when Spot is deep in the money (|Diff| >= $35)."""
    book = L2BookState("KXBTC15M-T78000")
    book.no_book = {Decimal("0.32"): Decimal("500")}
    book.yes_book = {Decimal("0.70"): Decimal("500")}

    # Confirmed NO moneyness: Spot is $77930.00 (-$70 from strike), 150s remaining
    decision = dominion_bot.evaluate(
        book=book,
        spot_price=77930.0,
        target_strike=78000.0,
        time_to_expiry_s=150.0,
        total_equity=Decimal("100.00"),
        max_position_size=4,
    )

    assert decision.recommended_side == "no"
    assert decision.playbook_stage == "moneyness_snub"
    assert not decision.anti_pin_veto


def test_dynamic_early_harvest_take_profit(dominion_bot: Dominion2Bot):
    """Test Pillar 5: Dynamic Early Harvest takes profit at >= $0.90 bid."""
    book = L2BookState("KXBTC15M-T78000")
    # Best YES bid is $0.92
    book.yes_book = {Decimal("0.92"): Decimal("500")}

    exit_dec = dominion_bot.evaluate_exit(
        holding_side=OrderSide.YES,
        contracts=4,
        entry_price=Decimal("0.35"),
        book=book,
        spot_price=78150.0,
        target_strike=78000.0,
        time_to_expiry_s=200.0,
    )

    assert exit_dec.should_exit is True
    assert exit_dec.exit_reason == "TAKE_PROFIT_CEILING"
    assert exit_dec.exit_price == Decimal("0.92")
    assert exit_dec.profit_pct > 1.0  # > 100% ROI


def test_vpin_toxicity_veto(dominion_bot: Dominion2Bot):
    """Test VPIN shield: Rejects trade if toxic orderflow bursts above 0.45."""
    book = L2BookState("KXBTC15M-T78000")
    book.yes_book = {Decimal("0.35"): Decimal("500")}
    book.no_book = {Decimal("0.65"): Decimal("500")}

    decision = dominion_bot.evaluate(
        book=book,
        spot_price=78080.0,
        target_strike=78000.0,
        time_to_expiry_s=600.0,
        total_equity=Decimal("100.00"),
        max_position_size=4,
        estimated_vpin=0.55,  # Highly toxic
    )

    assert decision.recommended_side == "wait"
    assert decision.vpin_is_safe is False
    assert "Toxic VPIN" in decision.rationale or "VPIN" in decision.rationale

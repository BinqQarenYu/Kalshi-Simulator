"""Unit tests for the 3-Step Domination Bot strategy engine."""

from decimal import Decimal
import pytest

from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
from kalshi_sim.schemas import L2BookState, OrderBookLevel, OrderSide


def test_domination_bot_playbook3_late_gamma_snub() -> None:
    bot = ThreeStepDominationBot(min_edge_pct=0.05, min_ev_dollars=Decimal("0.02"), min_spot_diff=35.0)

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.75"): Decimal("100"), Decimal("0.72"): Decimal("200")}
    book.no_book = {Decimal("0.25"): Decimal("100"), Decimal("0.28"): Decimal("200")}

    # T = 120s (2 minutes left), spot is +$100 above strike ($78750 vs $78650) -> deep ITM harvest
    decision = bot.evaluate(
        book=book,
        spot_price=78750.0,
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


def test_domination_bot_price_cap_veto() -> None:
    bot = ThreeStepDominationBot(max_entry_price=0.62)

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.85"): Decimal("100")}
    book.no_book = {Decimal("0.15"): Decimal("100")}

    # Expensive entry ($0.85 > $0.72) must be vetoed
    decision = bot.evaluate(
        book=book,
        spot_price=78750.0,
        target_strike=78650.0,
        time_to_expiry_s=120.0,
        total_equity=Decimal("100.00"),
        max_position_size=10,
    )

    assert decision.recommended_side == "wait"
    assert "Price Cap Veto" in decision.rationale


def test_domination_bot_playbook2_mid_cycle_ofi_drift() -> None:
    bot = ThreeStepDominationBot(min_edge_pct=0.05, min_ev_dollars=Decimal("0.02"), min_spot_diff=35.0)

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.55"): Decimal("300")}
    book.no_book = {Decimal("0.45"): Decimal("100")}

    # T = 420s (7 minutes left), spot is +$45 above strike
    decision = bot.evaluate(
        book=book,
        spot_price=78695.0,
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


def test_domination_bot_discount_sniper_maker_execution() -> None:
    """Verify that Domination Bot places resting maker limit orders at the user's discount price ($0.35) with $0.00 fee."""
    bot = ThreeStepDominationBot(
        min_edge_pct=0.05,
        min_ev_dollars=Decimal("0.02"),
        min_spot_diff=35.0,
        discount_limit_price=Decimal("0.35"),
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    # Current exchange ask is 0.60 (tradeable, but user demands 35c discount or nothing)
    book.yes_book = {Decimal("0.60"): Decimal("200")}
    book.no_book = {Decimal("0.40"): Decimal("200")}

    # Spot is +$60 above strike, T = 120s
    decision = bot.evaluate(
        book=book,
        spot_price=78710.0,
        target_strike=78650.0,
        time_to_expiry_s=120.0,
        total_equity=Decimal("100.00"),
        max_position_size=10,
        estimated_vpin=0.10,
    )

    assert decision.recommended_side == "yes"
    assert decision.order_type == "limit"
    assert decision.limit_price == 0.35
    assert "Discount Sniper" in decision.rationale
    assert "$0.00 Fee" in decision.rationale
    assert "@ $0.35" in decision.rationale


def test_domination_bot_dynamic_discount_update() -> None:
    """Verify that calling set_discount_limit_price dynamically tunes the sniper ceiling."""
    bot = ThreeStepDominationBot(discount_limit_price=Decimal("0.48"))
    assert bot.discount_limit_price == Decimal("0.48")

    # Tune down to 30 cents
    bot.set_discount_limit_price(0.30)
    assert bot.discount_limit_price == Decimal("0.30")

    # Clamped within safe boundaries [0.10, 0.50]
    bot.set_discount_limit_price(0.05)
    assert bot.discount_limit_price == Decimal("0.10")

    bot.set_discount_limit_price(0.75)
    assert bot.discount_limit_price == Decimal("0.50")


def test_domination_bot_asset_calibration() -> None:
    """Verify that ThreeStepDominationBot dynamically scales min_spot_diff across BTC, ETH, SOL, DOGE."""
    from kalshi_sim.schemas import CryptoAsset

    bot = ThreeStepDominationBot(asset=CryptoAsset.BTC)
    assert bot.asset == CryptoAsset.BTC
    assert bot.min_spot_diff == 35.0

    # Calibrate to ETH ($2.50 threshold)
    bot.set_asset(CryptoAsset.ETH)
    assert bot.asset == CryptoAsset.ETH
    assert bot.min_spot_diff == 2.50
    params = bot.get_parameters()
    assert params["asset"] == "ETH"
    assert params["min_spot_diff"] == 2.50

    # Calibrate to SOL ($0.50 threshold)
    bot.set_asset(CryptoAsset.SOL)
    assert bot.asset == CryptoAsset.SOL
    assert bot.min_spot_diff == 0.50

    # Calibrate to DOGE ($0.0005 threshold)
    bot.set_asset(CryptoAsset.DOGE)
    assert bot.asset == CryptoAsset.DOGE
    assert bot.min_spot_diff == 0.0005


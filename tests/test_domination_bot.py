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

    # T = 420s (7 minutes left), spot is +$110 above strike (must exceed 2x min_spot_diff=$70)
    decision = bot.evaluate(
        book=book,
        spot_price=78760.0,
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

    # Spot is +$110 above strike (must exceed 2x min_spot_diff=$70), T = 120s
    decision = bot.evaluate(
        book=book,
        spot_price=78760.0,
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


def test_domination_bot_asset_volatility_calibration() -> None:
    """Verify that ThreeStepDominationBot calibrates 1m volatility across all crypto assets."""
    from kalshi_sim.schemas import CryptoAsset

    bot = ThreeStepDominationBot(asset=CryptoAsset.BTC)
    assert bot.typical_1m_volatility == 14.0

    bot.set_asset(CryptoAsset.ETH)
    assert bot.typical_1m_volatility == 0.60
    assert bot.get_parameters()["typical_1m_volatility"] == 0.60

    bot.set_asset(CryptoAsset.SOL)
    assert bot.typical_1m_volatility == 0.04

    bot.set_asset(CryptoAsset.DOGE)
    assert bot.typical_1m_volatility == 0.000045


def test_domination_bot_multi_asset_evaluation() -> None:
    """Verify that Domination Bot correctly evaluates and trades ETH, SOL, and DOGE with true statistical edge."""
    from kalshi_sim.schemas import CryptoAsset

    # 1. Ethereum Evaluation
    eth_bot = ThreeStepDominationBot(asset=CryptoAsset.ETH, min_edge_pct=0.05, min_ev_dollars=Decimal("0.02"))
    eth_book = L2BookState(market_ticker="KXETH15M-T2100")
    eth_book.yes_book = {Decimal("0.60"): Decimal("100")}
    eth_book.no_book = {Decimal("0.40"): Decimal("100")}

    eth_decision = eth_bot.evaluate(
        book=eth_book,
        spot_price=2108.0,  # +$8.00 ITM (> 2x $2.50 threshold=$5.00, ~13.3x 1m std dev)
        target_strike=2100.0,
        time_to_expiry_s=120.0,
        total_equity=Decimal("100.00"),
        max_position_size=1,
    )
    assert eth_decision.recommended_side == "yes"
    assert eth_decision.recommended_contracts == 1
    assert eth_decision.p_up > 0.85
    assert "BTC" not in eth_decision.rationale
    assert eth_decision.spot_diff == 8.0

    # 2. Dogecoin Evaluation (Micro-decimal precision test)
    doge_bot = ThreeStepDominationBot(asset=CryptoAsset.DOGE, min_edge_pct=0.05, min_ev_dollars=Decimal("0.02"))
    doge_book = L2BookState(market_ticker="KXDOGE15M-T090000")
    doge_book.yes_book = {Decimal("0.60"): Decimal("100")}
    doge_book.no_book = {Decimal("0.40"): Decimal("100")}

    doge_decision = doge_bot.evaluate(
        book=doge_book,
        spot_price=0.091500,  # +$0.001500 ITM (> 2x $0.0005 threshold=$0.001, ~33x 1m std dev)
        target_strike=0.090000,
        time_to_expiry_s=120.0,
        total_equity=Decimal("100.00"),
        max_position_size=1,
    )
    assert doge_decision.recommended_side == "yes"
    assert doge_decision.recommended_contracts == 1
    assert doge_decision.p_up > 0.85
    assert "BTC" not in doge_decision.rationale
    # Verify DOGE spot_diff is not rounded to 0.00
    assert doge_decision.spot_diff == 0.0015
    assert "+$0.001500" in doge_decision.rationale

    # 3. Solana Evaluation
    sol_bot = ThreeStepDominationBot(asset=CryptoAsset.SOL, min_edge_pct=0.05, min_ev_dollars=Decimal("0.02"))
    sol_book = L2BookState(market_ticker="KXSOL15M-T130")
    sol_book.yes_book = {Decimal("0.60"): Decimal("100")}
    sol_book.no_book = {Decimal("0.40"): Decimal("100")}

    sol_decision = sol_bot.evaluate(
        book=sol_book,
        spot_price=132.00,  # +$2.00 ITM (> 2x $0.50 threshold=$1.00, > 3x marginal=$1.50, 50x 1m std dev)
        target_strike=130.00,
        time_to_expiry_s=120.0,
        total_equity=Decimal("100.00"),
        max_position_size=1,
    )
    assert sol_decision.recommended_side == "yes"
    assert sol_decision.recommended_contracts == 1
    assert sol_decision.p_up > 0.85
    assert "BTC" not in sol_decision.rationale
    assert sol_decision.spot_diff == 2.0


def test_domination_bot_razor_tight_proximity_veto() -> None:
    """Verify that any razor-tight event (|Diff| < 2x min_spot_diff) is vetoed across all crypto assets."""
    from kalshi_sim.schemas import CryptoAsset

    # BTC: min_spot_diff = 35.0, 2x = 70.0. Diff = $40.00 -> VETO
    btc_bot = ThreeStepDominationBot(asset=CryptoAsset.BTC)
    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.55"): Decimal("100")}
    book.no_book = {Decimal("0.45"): Decimal("100")}
    d_btc = btc_bot.evaluate(
        book=book,
        spot_price=78690.0,  # +$40.00 (< $70.00)
        target_strike=78650.0,
        time_to_expiry_s=120.0,
    )
    assert d_btc.recommended_side == "wait"
    assert "Razor-Tight Proximity Veto" in d_btc.rationale

    # ETH: min_spot_diff = 2.50, 2x = 5.00. Diff = $3.00 -> VETO
    eth_bot = ThreeStepDominationBot(asset=CryptoAsset.ETH)
    d_eth = eth_bot.evaluate(
        book=book,
        spot_price=2103.0,  # +$3.00 (< $5.00)
        target_strike=2100.0,
        time_to_expiry_s=120.0,
    )
    assert d_eth.recommended_side == "wait"
    assert "Razor-Tight Proximity Veto" in d_eth.rationale

    # SOL: min_spot_diff = 0.50, 2x = 1.00. Diff = $0.75 -> VETO
    sol_bot = ThreeStepDominationBot(asset=CryptoAsset.SOL)
    d_sol = sol_bot.evaluate(
        book=book,
        spot_price=130.75,  # +$0.75 (< $1.00)
        target_strike=130.00,
        time_to_expiry_s=120.0,
    )
    assert d_sol.recommended_side == "wait"
    assert "Razor-Tight Proximity Veto" in d_sol.rationale

    # DOGE: min_spot_diff = 0.0005, 2x = 0.0010. Diff = $0.0007 -> VETO
    doge_bot = ThreeStepDominationBot(asset=CryptoAsset.DOGE)
    d_doge = doge_bot.evaluate(
        book=book,
        spot_price=0.090700,  # +$0.000700 (< $0.001000)
        target_strike=0.090000,
        time_to_expiry_s=120.0,
    )
    assert d_doge.recommended_side == "wait"
    assert "Razor-Tight Proximity Veto" in d_doge.rationale


def test_domination_bot_extreme_volatility_swing_empty_ask_no_crash() -> None:
    """Verify that during extreme swings (+-$125) with one-sided empty book, evaluate does not crash with TypeError."""
    from kalshi_sim.schemas import CryptoAsset

    bot = ThreeStepDominationBot(asset=CryptoAsset.BTC)

    # 1. Massive upward swing (+125.0): no_book is empty -> best_yes_ask is None, but YES is recommended
    book_up = L2BookState(market_ticker="KXBTC15M-T79000")
    book_up.yes_book = {Decimal("0.95"): Decimal("50")}
    book_up.no_book = {}  # Empty NO book -> best_no_bid is None -> best_yes_ask is None

    for t_rem in [120.0, 350.0, 750.0]:
        decision_up = bot.evaluate(
            book=book_up,
            spot_price=79125.0,  # +$125.00 swing
            target_strike=79000.0,
            time_to_expiry_s=t_rem,
            total_equity=Decimal("25.00"),
            max_position_size=1,
            estimated_vpin=0.15,
        )
        assert decision_up is not None
        assert decision_up.p_up > 0.90

    # 2. Massive downward swing (-125.0): yes_book is empty -> best_no_ask is None, but NO is recommended
    book_down = L2BookState(market_ticker="KXBTC15M-T79000")
    book_down.yes_book = {}  # Empty YES book -> best_yes_bid is None -> best_no_ask is None
    book_down.no_book = {Decimal("0.95"): Decimal("50")}

    for t_rem in [120.0, 350.0, 750.0]:
        decision_down = bot.evaluate(
            book=book_down,
            spot_price=78875.0,  # -$125.00 swing
            target_strike=79000.0,
            time_to_expiry_s=t_rem,
            total_equity=Decimal("25.00"),
            max_position_size=1,
            estimated_vpin=0.15,
        )
        assert decision_down is not None
        assert decision_down.p_down > 0.90



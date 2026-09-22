"""Unit tests for the 3-Step Domination Bot strategy engine."""

from decimal import Decimal
import pytest

from app_1_machine_engine.ml.domination_bot_v4 import ThreeStepDominationBotV4
from shared.schemas import CryptoAsset, L2BookState, OrderBookLevel, OrderSide


def test_domination_bot_playbook3_late_gamma_snub() -> None:
    bot = ThreeStepDominationBotV4(
        min_edge_pct=0.05,
        min_ev_dollars=Decimal("0.02"),
        min_spot_diff=35.0,
        entry_cutoff_seconds=0.0,  # disable V4 freeze for this baseline P3 test
        enable_every_cycle_engagement=False,
    )

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

    assert decision.strategy_id == "bot1_ver_4"
    assert decision.playbook_stage == "gamma_snub"
    assert "Playbook 3" in decision.active_playbook
    assert decision.p_up > 0.85
    assert decision.vpin_is_safe is True
    assert decision.recommended_side == "yes"
    assert decision.recommended_contracts > 0


def test_domination_bot_price_cap_veto() -> None:
    bot = ThreeStepDominationBotV4(
        max_entry_price=0.62,
        entry_cutoff_seconds=0.0,
        enable_every_cycle_engagement=False,
    )

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
    bot = ThreeStepDominationBotV4(min_edge_pct=0.05, min_ev_dollars=Decimal("0.02"), min_spot_diff=35.0)

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

    assert decision.strategy_id == "bot1_ver_4"
    assert decision.playbook_stage == "drift"
    assert "Playbook 2" in decision.active_playbook


def test_domination_bot_vpin_toxicity_veto() -> None:
    bot = ThreeStepDominationBotV4(entry_cutoff_seconds=0.0, enable_every_cycle_engagement=False)

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
    bot = ThreeStepDominationBotV4(
        min_edge_pct=0.05,
        min_ev_dollars=Decimal("0.02"),
        min_spot_diff=35.0,
        discount_limit_price=Decimal("0.35"),
        entry_cutoff_seconds=0.0,
        enable_every_cycle_engagement=False,
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
    bot = ThreeStepDominationBotV4()
    assert bot.discount_limit_price == Decimal("0.52")

    # Tune to 48 cents
    bot.set_discount_limit_price(0.48)
    assert bot.discount_limit_price == Decimal("0.48")

    # Tune down to 30 cents
    bot.set_discount_limit_price(0.30)
    assert bot.discount_limit_price == Decimal("0.30")

    # Clamped within safe boundaries [0.10, 0.65]
    bot.set_discount_limit_price(0.05)
    assert bot.discount_limit_price == Decimal("0.10")

    bot.set_discount_limit_price(0.75)
    assert bot.discount_limit_price == Decimal("0.65")


def test_domination_bot_asset_calibration() -> None:
    """Verify that ThreeStepDominationBotV4 dynamically scales min_spot_diff across BTC, ETH, SOL, DOGE."""
    from shared.schemas import CryptoAsset

    bot = ThreeStepDominationBotV4(asset=CryptoAsset.BTC)
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
    """Verify that ThreeStepDominationBotV4 calibrates 1m volatility across all crypto assets."""
    from shared.schemas import CryptoAsset

    bot = ThreeStepDominationBotV4(asset=CryptoAsset.BTC)
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
    from shared.schemas import CryptoAsset

    # 1. Ethereum Evaluation
    eth_bot = ThreeStepDominationBotV4(
        asset=CryptoAsset.ETH,
        min_edge_pct=0.05,
        min_ev_dollars=Decimal("0.02"),
        entry_cutoff_seconds=0.0,
        enable_every_cycle_engagement=False,
    )
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
    doge_bot = ThreeStepDominationBotV4(
        asset=CryptoAsset.DOGE,
        min_edge_pct=0.05,
        min_ev_dollars=Decimal("0.02"),
        entry_cutoff_seconds=0.0,
        enable_every_cycle_engagement=False,
    )
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
    sol_bot = ThreeStepDominationBotV4(
        asset=CryptoAsset.SOL,
        min_edge_pct=0.05,
        min_ev_dollars=Decimal("0.02"),
        entry_cutoff_seconds=0.0,
        enable_every_cycle_engagement=False,
    )
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


def test_domination_bot_dynamic_proximity_threshold() -> None:
    """Verify Option A: Self-calibrating dynamic proximity threshold across all 4 crypto assets."""
    from shared.schemas import CryptoAsset

    # 1. BTC: min_spot_diff=35.0, typical_1m_vol=14.0
    # Floor = 35.0 * 1.15 = 40.25, Ceiling = 35.0 * 2.15 = 75.25
    btc_bot = ThreeStepDominationBotV4(asset=CryptoAsset.BTC)
    
    # At T=900s (15 mins): reaches ceiling 75.25
    assert btc_bot.get_dynamic_proximity_threshold(900.0) == pytest.approx(75.25, abs=1e-2)

    # At T=600s (10 mins): ~61.44
    assert btc_bot.get_dynamic_proximity_threshold(600.0) == pytest.approx(61.44, abs=0.1)

    # At T=360s (6 mins): sweet spot ~47.60 (1.36x strike step)
    assert btc_bot.get_dynamic_proximity_threshold(360.0) == pytest.approx(47.60, abs=0.1)

    # At T=120s (2 mins): clamped to floor 40.25
    assert btc_bot.get_dynamic_proximity_threshold(120.0) == pytest.approx(40.25, abs=1e-2)

    # At T=30s (0.5 mins): clamped to floor 40.25
    assert btc_bot.get_dynamic_proximity_threshold(30.0) == pytest.approx(40.25, abs=1e-2)

    # 2. ETH: min_spot_diff=2.50, typical_1m_vol=0.60
    # Floor = 2.50 * 1.15 = 2.875, Ceiling = 2.50 * 2.15 = 5.375
    eth_bot = ThreeStepDominationBotV4(asset=CryptoAsset.ETH)
    assert eth_bot.get_dynamic_proximity_threshold(900.0) == pytest.approx(5.375, abs=1e-2)  # Reaches ceiling
    assert eth_bot.get_dynamic_proximity_threshold(600.0) == pytest.approx(4.39, abs=0.1)
    assert eth_bot.get_dynamic_proximity_threshold(360.0) == pytest.approx(3.40, abs=0.1)    # Sweet spot ~3.40 (1.36x)
    assert eth_bot.get_dynamic_proximity_threshold(120.0) == pytest.approx(2.875, abs=1e-2)  # Clamped to floor

    # 3. SOL: min_spot_diff=0.50, typical_1m_vol=0.04
    # Floor = 0.50 * 1.15 = 0.575, Ceiling = 0.50 * 2.15 = 1.075
    sol_bot = ThreeStepDominationBotV4(asset=CryptoAsset.SOL)
    assert sol_bot.get_dynamic_proximity_threshold(900.0) == pytest.approx(1.075, abs=1e-2)  # Reaches ceiling
    assert sol_bot.get_dynamic_proximity_threshold(600.0) == pytest.approx(0.88, abs=0.05)
    assert sol_bot.get_dynamic_proximity_threshold(360.0) == pytest.approx(0.68, abs=0.05)   # Sweet spot ~0.68 (1.36x)
    assert sol_bot.get_dynamic_proximity_threshold(120.0) == pytest.approx(0.575, abs=1e-2)  # Clamped to floor

    # 4. DOGE: min_spot_diff=0.0005, typical_1m_vol=0.000045
    # Floor = 0.0005 * 1.15 = 0.000575, Ceiling = 0.0005 * 2.15 = 0.001075
    doge_bot = ThreeStepDominationBotV4(asset=CryptoAsset.DOGE)
    assert doge_bot.get_dynamic_proximity_threshold(900.0) == pytest.approx(0.001075, abs=1e-6)  # Reaches ceiling
    assert doge_bot.get_dynamic_proximity_threshold(360.0) == pytest.approx(0.000680, abs=1e-5)  # Sweet spot (1.36x)
    assert doge_bot.get_dynamic_proximity_threshold(120.0) == pytest.approx(0.000575, abs=1e-6)  # Clamped to floor

    # 5. Universal Sweet Spot Ratio Invariant at T=6m: exactly 1.36x across ALL assets!
    for bot, expected_min_diff in [(btc_bot, 35.0), (eth_bot, 2.50), (sol_bot, 0.50), (doge_bot, 0.0005)]:
        thresh = bot.get_dynamic_proximity_threshold(360.0)
        ratio = thresh / expected_min_diff
        assert ratio == pytest.approx(1.36, abs=0.02)

    # 6. Elevated Live Volatility Protection: When vol doubles, moat widens
    btc_high_vol = ThreeStepDominationBotV4(asset=CryptoAsset.BTC)
    btc_high_vol.typical_1m_volatility = 28.0  # 2x volatility spike
    # At T=360s, baseline was 47.60, high vol should widen to ceiling 75.25
    assert btc_high_vol.get_dynamic_proximity_threshold(360.0) == pytest.approx(75.25, abs=1e-2)


def test_domination_bot_dynamic_moat_unlocks_mid_cycle_entry() -> None:
    """Demonstrate that dynamic moat unlocks profitable mid-cycle trades ($55 diff) that the static $70 rule killed."""
    from shared.schemas import CryptoAsset

    btc_bot = ThreeStepDominationBotV4(asset=CryptoAsset.BTC)
    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.48"): Decimal("100")}
    book.no_book = {Decimal("0.52"): Decimal("100")}

    # At T=360s (6 mins left), dynamic moat is ~48.01. Spot diff is +$55.00.
    # Under old static $70 rule, this was vetoed as razor-tight.
    # Under dynamic moat, $55 > $48.01 -> NO VETO, order proceeds!
    decision = btc_bot.evaluate(
        book=book,
        spot_price=78705.0,  # +$55.00
        target_strike=78650.0,
        time_to_expiry_s=360.0,
        total_equity=Decimal("100.00"),
        max_position_size=1,
        estimated_vpin=0.15,
    )
    assert decision.recommended_side == "yes"
    assert "Razor-Tight" not in decision.rationale


def test_domination_bot_razor_tight_proximity_veto() -> None:
    """Verify that any razor-tight event (|Diff| < dynamic moat) is vetoed across all crypto assets."""
    from shared.schemas import CryptoAsset

    # BTC: at T=120s, dynamic moat floor is $40.25. Diff = $20.00 (< $40.25) -> VETO
    btc_bot = ThreeStepDominationBotV4(asset=CryptoAsset.BTC, entry_cutoff_seconds=0.0, enable_every_cycle_engagement=False)
    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.55"): Decimal("100")}
    book.no_book = {Decimal("0.45"): Decimal("100")}
    d_btc = btc_bot.evaluate(
        book=book,
        spot_price=78670.0,  # +$20.00 (< $40.25 floor)
        target_strike=78650.0,
        time_to_expiry_s=120.0,
    )
    assert d_btc.recommended_side == "wait"
    assert "Razor-Tight Proximity Veto" in d_btc.rationale

    # ETH: at T=120s, dynamic moat floor is $2.875. Diff = $1.50 (< $2.875) -> VETO
    eth_bot = ThreeStepDominationBotV4(asset=CryptoAsset.ETH, entry_cutoff_seconds=0.0, enable_every_cycle_engagement=False)
    d_eth = eth_bot.evaluate(
        book=book,
        spot_price=2101.50,  # +$1.50 (< $2.875 floor)
        target_strike=2100.0,
        time_to_expiry_s=120.0,
    )
    assert d_eth.recommended_side == "wait"
    assert "Razor-Tight Proximity Veto" in d_eth.rationale

    # SOL: at T=120s, dynamic moat floor is $0.575. Diff = $0.30 (< $0.575) -> VETO
    sol_bot = ThreeStepDominationBotV4(asset=CryptoAsset.SOL, entry_cutoff_seconds=0.0, enable_every_cycle_engagement=False)
    d_sol = sol_bot.evaluate(
        book=book,
        spot_price=130.30,  # +$0.30 (< $0.575 floor)
        target_strike=130.00,
        time_to_expiry_s=120.0,
    )
    assert d_sol.recommended_side == "wait"
    assert "Razor-Tight Proximity Veto" in d_sol.rationale

    # DOGE: at T=120s, dynamic moat floor is $0.000575. Diff = $0.000300 (< $0.000575) -> VETO
    doge_bot = ThreeStepDominationBotV4(asset=CryptoAsset.DOGE, entry_cutoff_seconds=0.0, enable_every_cycle_engagement=False)
    d_doge = doge_bot.evaluate(
        book=book,
        spot_price=0.090300,  # +$0.000300 (< $0.000575 floor)
        target_strike=0.090000,
        time_to_expiry_s=120.0,
    )
    assert d_doge.recommended_side == "wait"
    assert "Razor-Tight Proximity Veto" in d_doge.rationale


def test_domination_bot_extreme_volatility_swing_empty_ask_no_crash() -> None:
    """Verify that during extreme swings (+-$125) with one-sided empty book, evaluate does not crash with TypeError."""
    from shared.schemas import CryptoAsset

    bot = ThreeStepDominationBotV4(asset=CryptoAsset.BTC, entry_cutoff_seconds=0.0, enable_every_cycle_engagement=False)

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


def test_domination_bot_playbook1_opening_quarantine_veto() -> None:
    """Verify that Playbook 1 strictly outputs WAIT when in the opening cycle quarantine window."""
    bot = ThreeStepDominationBotV4(asset=CryptoAsset.BTC, opening_quarantine_seconds=90.0)

    book = L2BookState(market_ticker="KXBTC15M-T79000")
    book.yes_book = {Decimal("0.50"): Decimal("100")}
    book.no_book = {Decimal("0.50"): Decimal("100")}

    # T = 850s > 810s ceiling (Quarantine active during opening 90s of 900s cycle)
    decision = bot.evaluate(
        book=book,
        spot_price=79100.0,  # +$100.00 breakout proposal (clears proximity moat)
        target_strike=79000.0,
        time_to_expiry_s=850.0,
        total_equity=Decimal("25.00"),
        max_position_size=1,
    )

    assert decision.recommended_side == "wait"
    assert "Opening Cycle Quarantine Active" in decision.rationale
    assert "Playbook 1" in decision.rationale


def test_domination_bot_playbook1_post_quarantine_activation() -> None:
    """Verify that Playbook 1 activates normally once the quarantine window has expired."""
    bot = ThreeStepDominationBotV4(asset=CryptoAsset.BTC, opening_quarantine_seconds=90.0)

    book = L2BookState(market_ticker="KXBTC15M-T79000")
    book.yes_book = {Decimal("0.48"): Decimal("100")}
    book.no_book = {Decimal("0.52"): Decimal("100")}

    # T = 750s <= 810s ceiling (Quarantine expired, Playbook 1 active)
    decision = bot.evaluate(
        book=book,
        spot_price=79080.0,  # +$80.00 strong breakout
        target_strike=79000.0,
        time_to_expiry_s=750.0,
        total_equity=Decimal("25.00"),
        max_position_size=1,
    )

    assert "Playbook 1" in decision.active_playbook
    assert decision.playbook_stage == "breakout"
    assert decision.recommended_side == "yes"


def test_domination_bot_playbook1_onnx_microstructure_veto() -> None:
    """Verify that Playbook 1 vetoes a breakout proposal when ONNX signals opposing flow or wait."""
    class MockONNXEngine:
        def __init__(self, signal: str, confidence: float = 0.85, vpin_veto: bool = False):
            self.signal = signal
            self.confidence = confidence
            self.vpin_veto = vpin_veto

        def process_orderbook_tick(self, book):
            return {
                "signal": self.signal,
                "confidence": self.confidence,
                "vpin_veto": self.vpin_veto,
                "vpin_score": 0.50,
                "prob_wait": 0.80 if self.signal == "WAIT" else 0.10,
                "prob_long": 0.85 if self.signal == "LONG" else 0.05,
                "prob_short": 0.85 if self.signal == "SHORT" else 0.05,
            }

    # 1. Opposing signal: Proposing BUY YES on spot diff, but ONNX signals SHORT (downward absorption)
    mock_opposing = MockONNXEngine(signal="SHORT")
    bot_opposing = ThreeStepDominationBotV4(asset=CryptoAsset.BTC, opening_quarantine_seconds=90.0, onnx_engine=mock_opposing)

    book = L2BookState(market_ticker="KXBTC15M-T79000")
    book.yes_book = {Decimal("0.48"): Decimal("100")}
    book.no_book = {Decimal("0.52"): Decimal("100")}

    decision_veto = bot_opposing.evaluate(
        book=book,
        spot_price=79080.0,  # +$80.00 breakout
        target_strike=79000.0,
        time_to_expiry_s=750.0,
        total_equity=Decimal("25.00"),
        max_position_size=1,
    )

    assert decision_veto.recommended_side == "wait"
    assert "ONNX Microstructure Veto" in decision_veto.rationale
    assert "Brain 1 signaled SHORT" in decision_veto.rationale

    # 2. Confirmed signal: ONNX signals LONG -> trade passes!
    mock_agree = MockONNXEngine(signal="LONG")
    bot_agree = ThreeStepDominationBotV4(asset=CryptoAsset.BTC, opening_quarantine_seconds=90.0, onnx_engine=mock_agree)

    decision_pass = bot_agree.evaluate(
        book=book,
        spot_price=79080.0,
        target_strike=79000.0,
        time_to_expiry_s=750.0,
        total_equity=Decimal("25.00"),
        max_position_size=1,
    )
    assert decision_pass.recommended_side == "yes"


def test_domination_bot_clob_spread_corridor_veto() -> None:
    """Test Frontier 3: Vance Max CLOB Spread Corridor Cap vetoes wide/illiquid markets."""
    bot = ThreeStepDominationBotV4(
        max_clob_spread_cents=0.05,  # 5¢ max corridor
        min_spot_diff=35.0,
    )

    book = L2BookState(market_ticker="KXBTC15M-T79000")
    # Best YES bid is 0.40; Best YES ask is 0.52 (via NO bid of 0.48) -> Spread is 12¢ > 5¢
    book.yes_book = {Decimal("0.40"): Decimal("100")}
    book.no_book = {Decimal("0.48"): Decimal("100")}

    decision = bot.evaluate(
        book=book,
        spot_price=79080.0,
        target_strike=79000.0,
        time_to_expiry_s=400.0,
        total_equity=Decimal("50.00"),
        max_position_size=1,
    )

    assert decision.recommended_side == "wait"
    assert "Wide CLOB Spread Veto" in decision.rationale
    assert "corridor cap" in decision.rationale


def test_domination_bot_anti_toxic_queue_depth_veto() -> None:
    """Test Frontier 2: Vance Anti-Toxic Queue Depth Shield vetoes resting behind massive whale walls."""
    bot = ThreeStepDominationBotV4(
        max_queue_depth_ahead=250,  # 250 contracts limit
        discount_limit_price=Decimal("0.52"),
        max_clob_spread_cents=0.10,  # Allow spread to isolate queue test
        min_spot_diff=35.0,
    )

    book = L2BookState(market_ticker="KXBTC15M-T79000")
    # Market ask is 0.58 (> 0.52 discount limit), so order must rest as a maker bid at 0.52
    # 400 contracts already resting at 0.52 (> 250 limit)
    book.yes_book = {Decimal("0.52"): Decimal("400"), Decimal("0.50"): Decimal("100")}
    book.no_book = {Decimal("0.42"): Decimal("100")}  # YES ask = 1 - 0.42 = 0.58

    decision = bot.evaluate(
        book=book,
        spot_price=79080.0,
        target_strike=79000.0,
        time_to_expiry_s=400.0,
        total_equity=Decimal("50.00"),
        max_position_size=1,
    )

    assert decision.recommended_side == "wait"
    assert "Toxic Queue Depth Veto" in decision.rationale
    assert "400 contracts resting ahead" in decision.rationale


def test_domination_bot_playbook4_silas_twap_immutability_sniper() -> None:
    """Test Frontier 1: Silas TWAP Immutability Sniper harvests late-cycle retail panic dumps."""
    bot = ThreeStepDominationBotV4(
        twap_immutability_sniper_cents=0.75,  # 75¢ ceiling
        max_clob_spread_cents=0.06,
        min_spot_diff=35.0,
        entry_cutoff_seconds=0.0,
        enable_every_cycle_engagement=False,
    )

    book = L2BookState(market_ticker="KXBTC15M-T79000")
    # Retail panicking: offering YES at 0.72 (NO bid is 0.28 -> YES ask is 0.72)
    # Best YES bid is 0.69 -> Spread is 3¢ <= 5¢
    book.yes_book = {Decimal("0.69"): Decimal("50")}
    book.no_book = {Decimal("0.28"): Decimal("100")}

    # T = 30s (within [15s, 45s] window). Spot +$60 above strike, TWAP +$55 above strike.
    decision = bot.evaluate(
        book=book,
        spot_price=79060.0,
        target_strike=79000.0,
        time_to_expiry_s=30.0,
        twap_60s=79055.0,
        total_equity=Decimal("50.00"),
        max_position_size=1,
    )

    assert decision.strategy_id == "bot1_ver_4"
    assert decision.playbook_stage == "twap_sniper"
    assert "Playbook 4: Silas TWAP Immutability Sniper" in decision.active_playbook
    assert decision.recommended_side == "yes"
    assert decision.recommended_contracts == 1
    assert decision.limit_price == 0.72
    assert "Endgame Harvest" in decision.rationale


# ===========================================================================
# V4 SPECIFIC TEST SUITE: Every-Cycle Engagement, +45% Harvest, -35% Stop Loss
# ===========================================================================

def test_v4_profit_harvest_at_45_pct() -> None:
    """Verify that when position reaches +45% gain, Step 0 emits immediate profit harvest sell."""
    from shared.schemas import Position, Timeframe

    bot = ThreeStepDominationBotV4(profit_harvest_pct=0.45)
    book = L2BookState(market_ticker="KXBTC15M-T78650")
    # Entry was at 30¢. +45% gain requires bid >= 44¢ (0.30 * 1.45 = 0.435 -> 0.44)
    # Book has YES bid at 0.45, ask at 0.47
    book.yes_book = {Decimal("0.45"): Decimal("100")}
    book.no_book = {Decimal("0.53"): Decimal("100")}

    current_pos = Position(
        ticker="KXBTC15M-T78650",
        side=OrderSide.YES,
        size=1,
        avg_entry_price=Decimal("0.30"),
        timeframe=Timeframe.FIFTEEN_MIN,
    )

    decision = bot.evaluate(
        book=book,
        spot_price=78700.0,
        target_strike=78650.0,
        time_to_expiry_s=500.0,
        current_position=current_pos,
    )

    assert decision.action == "harvest"
    assert decision.recommended_side == "sell_yes"
    assert decision.limit_price == 0.45
    assert "PROFIT HARVEST" in decision.rationale


def test_v4_defensive_stop_loss_at_35_pct() -> None:
    """Verify that when position drops -35% below entry, Step 0 emits defensive stop loss sell."""
    from shared.schemas import Position, Timeframe

    bot = ThreeStepDominationBotV4(enable_stop_loss=True, stop_loss_pct=0.35)
    book = L2BookState(market_ticker="KXBTC15M-T78650")
    # Entry was at 40¢. -35% drop triggers when bid <= 26¢ (0.40 * 0.65 = 0.26)
    # Book has YES bid at 0.25, ask at 0.28
    book.yes_book = {Decimal("0.25"): Decimal("100")}
    book.no_book = {Decimal("0.72"): Decimal("100")}

    current_pos = Position(
        ticker="KXBTC15M-T78650",
        side=OrderSide.YES,
        size=1,
        avg_entry_price=Decimal("0.40"),
        timeframe=Timeframe.FIFTEEN_MIN,
    )

    decision = bot.evaluate(
        book=book,
        spot_price=78600.0,
        target_strike=78650.0,
        time_to_expiry_s=500.0,
        current_position=current_pos,
    )

    assert decision.action == "stop_loss"
    assert decision.recommended_side == "sell_yes"
    assert decision.limit_price == 0.25
    assert "DEFENSIVE STOP LOSS" in decision.rationale


def test_v4_entry_cutoff_freeze_at_240s() -> None:
    """Verify that new entries are strictly frozen when T <= 240s (Playbook 3 gamma risk)."""
    bot = ThreeStepDominationBotV4(entry_cutoff_seconds=240.0)
    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.50"): Decimal("100")}
    book.no_book = {Decimal("0.50"): Decimal("100")}

    decision = bot.evaluate(
        book=book,
        spot_price=78750.0,
        target_strike=78650.0,
        time_to_expiry_s=200.0,  # <= 240s cutoff
    )

    assert decision.recommended_side == "wait"
    assert "V4 Late Cycle Freeze" in decision.rationale
    assert "200s <= 240s cutoff" in decision.rationale


def test_v4_price_corridor_enforcement() -> None:
    """Verify that entries below 18¢ floor or above 48¢ ceiling are strictly vetoed."""
    bot = ThreeStepDominationBotV4(
        min_entry_price=Decimal("0.18"),
        max_entry_price=Decimal("0.48"),
        entry_cutoff_seconds=240.0,
    )

    # 1. Floor test: Ask is 15¢ (< 18¢ floor)
    book_cheap = L2BookState(market_ticker="KXBTC15M-T78650")
    book_cheap.yes_book = {Decimal("0.15"): Decimal("100")}
    book_cheap.no_book = {Decimal("0.85"): Decimal("100")}

    d_floor = bot.evaluate(
        book=book_cheap,
        spot_price=78700.0,
        target_strike=78650.0,
        time_to_expiry_s=500.0,
    )
    assert d_floor.recommended_side == "wait"
    assert "Price Floor Veto" in d_floor.rationale

    # 2. Ceiling test: Ask is 55¢ (> 48¢ ceiling)
    book_expensive = L2BookState(market_ticker="KXBTC15M-T78650")
    book_expensive.yes_book = {Decimal("0.55"): Decimal("100")}
    book_expensive.no_book = {Decimal("0.45"): Decimal("100")}

    d_ceiling = bot.evaluate(
        book=book_expensive,
        spot_price=78700.0,
        target_strike=78650.0,
        time_to_expiry_s=500.0,
    )
    assert d_ceiling.recommended_side == "wait"
    assert "Price Cap Veto" in d_ceiling.rationale


def test_v4_every_cycle_engagement_entry() -> None:
    """Verify that in Every-Cycle Engagement mode, bot enters at cheapest ask within [18¢, 48¢]."""
    bot = ThreeStepDominationBotV4(
        enable_every_cycle_engagement=True,
        min_entry_price=Decimal("0.18"),
        max_entry_price=Decimal("0.48"),
        entry_cutoff_seconds=240.0,
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    # Yes ask is 38¢ (in sweetspot corridor [18¢, 48¢]), spot is above strike
    book.yes_book = {Decimal("0.38"): Decimal("100")}
    book.no_book = {Decimal("0.62"): Decimal("100")}

    decision = bot.evaluate(
        book=book,
        spot_price=78720.0,
        target_strike=78650.0,
        time_to_expiry_s=500.0,
        total_equity=Decimal("50.00"),
        max_position_size=1,
    )

    assert decision.recommended_side == "yes"
    assert decision.limit_price == 0.38
    assert decision.action == "entry"
    assert "V4 Cycle Entry" in decision.rationale
    assert "Harvest Target: +45%" in decision.rationale

"""Comprehensive Unit Tests for Macro Trend Dominion Bot.

Verifies:
1. Rolling macro trend calculation (1h, 15m) and regime classification (BULL, BEAR, CHOP).
2. Strict trend-following direction enforcement (counter-trend NO vetoed in BULL, YES vetoed in BEAR).
3. Playbook 3 late-cycle high-certainty gamma sniper execution.
4. Entry price constraints ($0.30 floor, $0.62 standard cap, $0.72 hard kill).
5. Micro-bankroll 1-contract sizing cap when equity < $50.
6. Dynamic take-profit ceiling and late-cycle cut-loss salvage exits.
"""

from decimal import Decimal
import time
import pytest

from kalshi_sim.ml.macro_trend_dominion_bot import (
    MacroTrendDominionBot,
    MacroTrendDecision,
    MacroTrendExitDecision,
)
from kalshi_sim.schemas import L2BookState, OrderSide


def _create_mock_l2_book(
    best_yes_bid: str = "0.58",
    best_yes_ask: str = "0.60",
    best_no_bid: Optional[str] = None,
    best_no_ask: Optional[str] = None,
) -> L2BookState:
    """Create a valid mock L2 book state."""
    book = L2BookState(market_ticker="KXBTC15M-TEST-00")
    # In Kalshi:
    # best_yes_bid is max(yes_book.keys())
    # best_yes_ask = 1 - max(no_book.keys())
    # so max(no_book.keys()) must equal 1 - Decimal(best_yes_ask)
    y_bid = Decimal(best_yes_bid)
    n_bid = Decimal("1") - Decimal(best_yes_ask)
    book.yes_book = {y_bid: Decimal("100")}
    book.no_book = {n_bid: Decimal("100")}
    return book


def test_macro_trend_calculation_and_regimes():
    """Verify that rolling 1h return correctly categorizes BULL, BEAR, and CHOP regimes."""
    bot = MacroTrendDominionBot()
    base_time = 10000.0

    # 1. Bull trend test: spot increases from $80,000 to $80,500 (+0.625%) over 1 hour
    history_bull = [
        (base_time - 3600.0, 80000.0),
        (base_time - 900.0, 80300.0),
        (base_time, 80500.0),
    ]
    t_1h, t_15m, regime = bot.compute_macro_trend(
        current_spot=80500.0,
        current_time=base_time,
        external_spot_history=history_bull,
    )
    assert regime == "MACRO_BULL"
    assert t_1h > 0.50
    assert t_15m > 0.20

    # 2. Bear trend test: spot drops from $80,000 to $79,500 (-0.625%) over 1 hour
    history_bear = [
        (base_time - 3600.0, 80000.0),
        (base_time - 900.0, 79700.0),
        (base_time, 79500.0),
    ]
    t_1h, t_15m, regime = bot.compute_macro_trend(
        current_spot=79500.0,
        current_time=base_time,
        external_spot_history=history_bear,
    )
    assert regime == "MACRO_BEAR"
    assert t_1h < -0.50
    assert t_15m < -0.20

    # 3. Flat chop test: spot moves $80,000 to $80,010 (+0.0125%)
    history_chop = [
        (base_time - 3600.0, 80000.0),
        (base_time - 900.0, 80005.0),
        (base_time, 80010.0),
    ]
    t_1h, t_15m, regime = bot.compute_macro_trend(
        current_spot=80010.0,
        current_time=base_time,
        external_spot_history=history_chop,
    )
    assert regime == "MACRO_CHOP"


def test_bull_regime_vetoes_no_bet():
    """Verify that in a MACRO_BULL regime, counter-trend NO trades are 100% vetoed."""
    bot = MacroTrendDominionBot()
    base_time = 10000.0
    history_bull = [
        (base_time - 3600.0, 80000.0),
        (base_time - 900.0, 80400.0),
        (base_time, 80600.0),
    ]

    # Set up book where NO ask is cheap/attractive but market is bull
    book = _create_mock_l2_book(
        best_yes_bid="0.65",
        best_yes_ask="0.68",
        best_no_bid="0.30",
        best_no_ask="0.33",
    )

    # Spot is slightly below target strike so raw EV might think NO
    decision = bot.evaluate(
        book=book,
        spot_price=80600.0,
        target_strike=80650.0,  # spot_diff = -50
        time_to_expiry_s=180.0,
        current_time=base_time,
        spot_history=history_bull,
    )

    # In a bull trend, NO trades are strictly vetoed!
    assert decision.recommended_side != "no"
    if decision.recommended_side == "wait":
        assert "Macro Trend Veto" in decision.rationale or "Proximity Veto" in decision.rationale


def test_bear_regime_vetoes_yes_bet():
    """Verify that in a MACRO_BEAR regime, knife-catching YES trades are 100% vetoed."""
    bot = MacroTrendDominionBot()
    base_time = 10000.0
    history_bear = [
        (base_time - 3600.0, 80000.0),
        (base_time - 900.0, 79400.0),
        (base_time, 79200.0),
    ]

    book = _create_mock_l2_book(
        best_yes_bid="0.30",
        best_yes_ask="0.34",
        best_no_bid="0.64",
        best_no_ask="0.68",
    )

    decision = bot.evaluate(
        book=book,
        spot_price=79200.0,
        target_strike=79150.0,  # spot_diff = +50
        time_to_expiry_s=180.0,
        current_time=base_time,
        spot_history=history_bear,
    )

    assert decision.recommended_side != "yes"
    if decision.recommended_side == "wait":
        assert "Macro Trend Veto" in decision.rationale or "Proximity Veto" in decision.rationale


def test_playbook3_late_gamma_sniper():
    """Verify Playbook 3 executes late-cycle gamma harvest when aligned with macro trend."""
    bot = MacroTrendDominionBot()
    base_time = 10000.0
    history_bull = [
        (base_time - 3600.0, 80000.0),
        (base_time - 900.0, 80400.0),
        (base_time, 80700.0),
    ]

    # Spot is $80 above strike, T = 120s remaining, YES ask is $0.60
    book = _create_mock_l2_book(
        best_yes_bid="0.58",
        best_yes_ask="0.60",
        best_no_bid="0.38",
        best_no_ask="0.42",
    )

    decision = bot.evaluate(
        book=book,
        spot_price=80700.0,
        target_strike=80620.0,  # spot_diff = +$80 (deep ITM)
        time_to_expiry_s=120.0,
        total_equity=Decimal("25.00"),
        current_time=base_time,
        spot_history=history_bull,
    )

    assert decision.recommended_side == "yes"
    assert decision.recommended_contracts == 1  # 1-contract micro-bankroll cap
    assert decision.active_playbook == "Playbook 3: Late-Cycle Gamma Sniper"
    assert decision.edge_pct > 0.0


def test_micro_bankroll_sizing_cap():
    """Verify that account equity < $50 strictly caps position to 1 contract."""
    bot = MacroTrendDominionBot()
    base_time = 10000.0
    history_bull = [(base_time - 3600.0, 80000.0), (base_time, 80700.0)]
    book = _create_mock_l2_book("0.58", "0.60", "0.38", "0.42")

    # Equity $25.00 -> should be 1 contract
    dec_small = bot.evaluate(
        book=book,
        spot_price=80700.0,
        target_strike=80620.0,
        time_to_expiry_s=120.0,
        total_equity=Decimal("25.00"),
        max_position_size=4,
        current_time=base_time,
        spot_history=history_bull,
    )
    assert dec_small.recommended_contracts <= 1

    # Equity $100.00 -> can scale to 2 contracts if Kelly permits
    dec_large = bot.evaluate(
        book=book,
        spot_price=80700.0,
        target_strike=80620.0,
        time_to_expiry_s=120.0,
        total_equity=Decimal("100.00"),
        max_position_size=2,
        current_time=base_time,
        spot_history=history_bull,
    )
    assert dec_large.recommended_contracts >= 1


def test_entry_price_caps():
    """Verify entry price boundaries ($0.30 floor, $0.72 hard kill)."""
    bot = MacroTrendDominionBot()
    base_time = 10000.0
    history_bull = [(base_time - 3600.0, 80000.0), (base_time, 80700.0)]

    # 1. Ask > $0.72 -> Hard Kill veto
    book_expensive = _create_mock_l2_book("0.75", "0.78", "0.20", "0.24")
    dec_kill = bot.evaluate(
        book=book_expensive,
        spot_price=80700.0,
        target_strike=80600.0,
        time_to_expiry_s=120.0,
        current_time=base_time,
        spot_history=history_bull,
    )
    assert dec_kill.recommended_side == "wait"
    assert "Price Cap Veto (Hard Kill)" in dec_kill.rationale

    # 2. Ask < $0.30 -> Price Floor veto
    book_cheap = _create_mock_l2_book("0.24", "0.26", "0.72", "0.76")
    dec_floor = bot.evaluate(
        book=book_cheap,
        spot_price=80700.0,
        target_strike=80620.0,
        time_to_expiry_s=120.0,
        current_time=base_time,
        spot_history=history_bull,
    )
    assert dec_floor.recommended_side == "wait"
    assert "Price Floor Veto" in dec_floor.rationale


def test_exit_take_profit_and_salvage():
    """Verify take-profit ceiling and late-cycle cut-loss salvage exits."""
    bot = MacroTrendDominionBot()

    # 1. Take Profit Ceiling: bid >= $0.95
    book_tp = _create_mock_l2_book(best_yes_bid="0.96", best_yes_ask="0.98")
    exit_tp = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.60"),
        size=1,
        book=book_tp,
        time_to_expiry_s=300.0,
    )
    assert exit_tp.should_exit is True
    assert exit_tp.exit_reason == "TAKE_PROFIT_CEILING"
    assert exit_tp.exit_price == Decimal("0.96")

    # 2. Late-Cycle Cut-Loss Salvage: T <= 90s, spot broken -$60 below strike
    book_salvage = _create_mock_l2_book(best_yes_bid="0.14", best_yes_ask="0.18")
    exit_salvage = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.60"),
        size=1,
        book=book_salvage,
        time_to_expiry_s=60.0,  # 60s <= 90s
        spot_price=79940.0,
        target_strike=80000.0,  # spot_diff = -$60 (severely adverse)
    )
    assert exit_salvage.should_exit is True
    assert exit_salvage.exit_reason == "CUT_LOSS_SALVAGE"
    assert exit_salvage.exit_price == Decimal("0.14")
    assert "CUT LOSS SALVAGE" in exit_salvage.rationale

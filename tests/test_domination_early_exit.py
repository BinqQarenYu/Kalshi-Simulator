"""Unit tests for the 3-Step Domination Bot Take-Profit and Early Liquidation Engine."""

from decimal import Decimal
import pytest

from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
from kalshi_sim.schemas import L2BookState, OrderSide


def test_take_profit_ceiling_holds_when_no_reversal() -> None:
    """Core Philosophy: When winning (bid 98c) and NO adverse reversal (<85%),

    continue holding to $1.00 payout at expiration.
    """
    bot = ThreeStepDominationBot(
        take_profit_price_threshold=Decimal("0.95"),
        require_reversal_for_tp_ceiling=True,
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    # Best YES bid is $0.98, NO bid is $0.01 -> prob_no is ~1-2% (no reversal)
    book.yes_book = {Decimal("0.98"): Decimal("500"), Decimal("0.97"): Decimal("200")}
    book.no_book = {Decimal("0.01"): Decimal("100")}

    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.75"),
        size=2,
        book=book,
        time_to_expiry_s=300.0,
        spot_price=78800.0,
        target_strike=78650.0,  # +$150 in the money -> NO reversal
    )

    # Should NOT exit; let winners run to full $1.00 payout
    assert decision.should_exit is False
    assert decision.exit_reason == "HOLD"
    assert "has not hit take-profit criteria" in decision.rationale


def test_take_profit_ceiling_exits_when_85pct_reversal_detected() -> None:
    """User scenario: Bought YES at 75c, market is 98c, but adverse reversal >= 85% is detected.

    Bot exits at 98c to lock in profits before expiration collapse.
    """
    bot = ThreeStepDominationBot(
        take_profit_price_threshold=Decimal("0.95"),
        require_reversal_for_tp_ceiling=True,
        reverse_indicator_threshold=0.85,
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.98"): Decimal("500"), Decimal("0.97"): Decimal("200")}
    book.no_book = {Decimal("0.01"): Decimal("100")}

    # Spot has crashed $250 below strike -> adverse reversal prob >= 85%
    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.75"),
        size=2,
        book=book,
        time_to_expiry_s=300.0,
        spot_price=78400.0,
        target_strike=78650.0,  # -$250 below strike
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "TAKE_PROFIT_CEILING"
    assert decision.exit_price == Decimal("0.98")
    assert decision.profit_pct > 30.0
    # Net PnL = (0.98 - 0.75 - 0.01) * 2 = 0.22 * 2 = 0.44
    assert decision.unrealized_pnl == Decimal("0.44")
    assert "TAKE PROFIT CEILING" in decision.rationale
    assert "reversal" in decision.rationale.lower()


def test_take_profit_ceiling_unconditional_mode() -> None:
    """When require_reversal_for_tp_ceiling is False, exits at ceiling unconditionally."""
    bot = ThreeStepDominationBot(
        take_profit_price_threshold=Decimal("0.95"),
        require_reversal_for_tp_ceiling=False,
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.98"): Decimal("500")}
    book.no_book = {Decimal("0.01"): Decimal("100")}

    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.75"),
        size=2,
        book=book,
        time_to_expiry_s=300.0,
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "TAKE_PROFIT_CEILING"
    assert decision.exit_price == Decimal("0.98")


def test_take_profit_target_roi_holds_when_no_reversal() -> None:
    """Target ROI: Bought at 50c, bid reaches 80c (+60% ROI).

    Without adverse reversal (<85%), position continues holding to $1.00 payout.
    """
    bot = ThreeStepDominationBot(
        min_take_profit_roi=0.20,
        enable_reverse_take_profit_roi=True,
        reverse_indicator_threshold=0.85,
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.80"): Decimal("200")}
    book.no_book = {Decimal("0.19"): Decimal("100")}

    # Spot is well above strike -> prob_no < 85%
    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.50"),
        size=1,
        book=book,
        time_to_expiry_s=400.0,
        spot_price=78800.0,
        target_strike=78650.0,
    )

    # Holds because no reversal detected
    assert decision.should_exit is False
    assert decision.exit_reason == "HOLD"


def test_take_profit_target_roi_harvest_on_85pct_reversal() -> None:
    """Target ROI: Bought at 50c, bid reaches 80c (+60% ROI), adverse reversal >= 85% detected.

    Bot executes early profit harvest.
    """
    bot = ThreeStepDominationBot(
        min_take_profit_roi=0.20,
        enable_reverse_take_profit_roi=True,
        reverse_indicator_threshold=0.85,
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.80"): Decimal("200")}
    book.no_book = {Decimal("0.19"): Decimal("100")}

    # Spot crashes $250 below strike -> reversal >= 85%
    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.50"),
        size=1,
        book=book,
        time_to_expiry_s=400.0,
        spot_price=78400.0,
        target_strike=78650.0,
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "TAKE_PROFIT_ROI"
    assert decision.exit_price == Decimal("0.80")
    assert decision.profit_pct == 60.0
    assert decision.unrealized_pnl == Decimal("0.29")  # 0.80 - 0.50 - 0.01 fee
    assert "REVERSE SIGNAL TAKE-PROFIT" in decision.rationale
    assert "reversal" in decision.rationale.lower()


def test_take_profit_target_roi_disabled() -> None:
    """When enable_reverse_take_profit_roi is False, Rule 3 does not trigger even with reversal."""
    bot = ThreeStepDominationBot(
        min_take_profit_roi=0.20,
        enable_reverse_take_profit_roi=False,
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.80"): Decimal("200")}
    book.no_book = {Decimal("0.19"): Decimal("100")}

    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.50"),
        size=1,
        book=book,
        time_to_expiry_s=400.0,
        spot_price=78400.0,
        target_strike=78650.0,
    )

    # Disabled -> holds
    assert decision.should_exit is False
    assert decision.exit_reason == "HOLD"


def test_late_cycle_harvest_final_two_minutes() -> None:
    """Late cycle: T=85s left (<120s), bid is 86c with +22% ROI -> locks profit before binary settlement."""
    bot = ThreeStepDominationBot(late_cycle_roi=0.15)

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.86"): Decimal("150")}
    book.no_book = {Decimal("0.13"): Decimal("100")}

    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.70"),
        size=1,
        book=book,
        time_to_expiry_s=85.0,  # <= 120s
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "LATE_CYCLE_HARVEST"
    assert decision.exit_price == Decimal("0.86")
    assert "LATE CYCLE HARVEST" in decision.rationale


def test_no_exit_when_still_holding_minor_gain() -> None:
    """Bought at 70c, bid is 72c -> not hit 95c ceiling, not hit 20% ROI -> HOLD."""
    bot = ThreeStepDominationBot()

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.72"): Decimal("100")}
    book.no_book = {Decimal("0.27"): Decimal("100")}

    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.70"),
        size=1,
        book=book,
        time_to_expiry_s=300.0,
    )

    assert decision.should_exit is False
    assert decision.exit_reason == "HOLD"


def test_no_exit_when_in_loss() -> None:
    """Bought at 75c, bid drops to 50c -> does not panic sell on take-profit."""
    bot = ThreeStepDominationBot()

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.50"): Decimal("100")}
    book.no_book = {Decimal("0.49"): Decimal("100")}

    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.75"),
        size=1,
        book=book,
        time_to_expiry_s=300.0,
    )

    assert decision.should_exit is False
    assert decision.exit_reason == "HOLD"


def test_take_profit_for_no_position() -> None:
    """Holding NO position bought at 60c, NO bid hits 96c, spot rallies (adverse reversal >= 85%).

    Triggers ceiling exit.
    """
    bot = ThreeStepDominationBot(take_profit_price_threshold=Decimal("0.95"))

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.03"): Decimal("50")}
    book.no_book = {Decimal("0.96"): Decimal("300")}

    # Spot rallies $250 above strike -> adverse reversal for NO position >= 85%
    decision = bot.evaluate_exit(
        side=OrderSide.NO,
        entry_price=Decimal("0.60"),
        size=2,
        book=book,
        time_to_expiry_s=250.0,
        spot_price=78900.0,
        target_strike=78650.0,
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "TAKE_PROFIT_CEILING"
    assert decision.exit_price == Decimal("0.96")
    # Net PnL = (0.96 - 0.60 - 0.01) * 2 = 0.35 * 2 = 0.70
    assert decision.unrealized_pnl == Decimal("0.70")


def test_take_profit_ceiling_toggle_disabled() -> None:
    """When enable_take_profit_ceiling is False, ceiling exit is suppressed."""
    bot = ThreeStepDominationBot(
        take_profit_price_threshold=Decimal("0.95"),
        enable_take_profit_ceiling=False,
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.98"): Decimal("500")}
    book.no_book = {Decimal("0.01"): Decimal("100")}

    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.85"),  # ROI < 20% so Rule 3 does not trigger
        size=1,
        book=book,
        time_to_expiry_s=300.0,
        spot_price=78400.0,  # reversal present, but ceiling disabled
        target_strike=78650.0,
    )

    # Ceiling is disabled -> should HOLD
    assert decision.should_exit is False
    assert decision.exit_reason == "HOLD"


def test_take_profit_ceiling_parameter_updates() -> None:
    """Test dynamically enabling/disabling take_profit_ceiling and reversal gating via update_parameters."""
    bot = ThreeStepDominationBot()
    assert bot.enable_take_profit_ceiling is True
    assert bot.require_reversal_for_tp_ceiling is True
    assert bot.enable_reverse_take_profit_roi is True
    assert bot.reverse_indicator_threshold == 0.85

    # Update parameters
    res = bot.update_parameters(
        enable_take_profit_ceiling=False,
        require_reversal_for_tp_ceiling=False,
        enable_reverse_take_profit_roi=False,
        reverse_indicator_threshold=90.0,
        min_take_profit_roi=25.0,
    )
    assert bot.enable_take_profit_ceiling is False
    assert bot.require_reversal_for_tp_ceiling is False
    assert bot.enable_reverse_take_profit_roi is False
    assert bot.reverse_indicator_threshold == 0.90
    assert bot.min_take_profit_roi == 0.25
    assert res["require_reversal_for_tp_ceiling"] is False
    assert res["enable_reverse_take_profit_roi"] is False
    assert res["reverse_indicator_threshold"] == 90.0
    assert res["min_take_profit_roi"] == 25.0

    # Re-enable
    res = bot.update_parameters(
        enable_take_profit_ceiling=True,
        require_reversal_for_tp_ceiling=True,
        enable_reverse_take_profit_roi=True,
        reverse_indicator_threshold=85.0,
    )
    assert bot.enable_take_profit_ceiling is True
    assert bot.require_reversal_for_tp_ceiling is True
    assert bot.enable_reverse_take_profit_roi is True
    assert bot.reverse_indicator_threshold == 0.85


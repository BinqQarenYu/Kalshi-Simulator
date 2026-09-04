"""Unit tests for the 3-Step Domination Bot Take-Profit and Early Liquidation Engine."""

from decimal import Decimal
import pytest

from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
from kalshi_sim.schemas import L2BookState, OrderSide


def test_take_profit_ceiling_trigger_98_cents() -> None:
    """User scenario: Bought YES at 75c, market reaches 98c -> locks in profit."""
    bot = ThreeStepDominationBot(take_profit_price_threshold=Decimal("0.95"))

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    # Best YES bid is $0.98, best YES ask is $0.99
    book.yes_book = {Decimal("0.98"): Decimal("500"), Decimal("0.97"): Decimal("200")}
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
    assert decision.profit_pct > 30.0
    # Net PnL = (0.98 - 0.75 - 0.01) * 2 = 0.22 * 2 = 0.44
    assert decision.unrealized_pnl == Decimal("0.44")
    assert "TAKE PROFIT CEILING" in decision.rationale


def test_take_profit_target_roi_harvest() -> None:
    """Target ROI: Bought at 50c, best bid reaches 80c (+60% ROI) -> locks in profit."""
    bot = ThreeStepDominationBot(min_take_profit_roi=0.20)

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.80"): Decimal("200")}
    book.no_book = {Decimal("0.19"): Decimal("100")}

    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.50"),
        size=1,
        book=book,
        time_to_expiry_s=400.0,
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "TAKE_PROFIT_ROI"
    assert decision.exit_price == Decimal("0.80")
    assert decision.profit_pct == 60.0
    assert decision.unrealized_pnl == Decimal("0.29")  # 0.80 - 0.50 - 0.01 fee


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
    """Holding NO position bought at 60c, NO bid hits 96c -> triggers exit."""
    bot = ThreeStepDominationBot(take_profit_price_threshold=Decimal("0.95"))

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.03"): Decimal("50")}
    book.no_book = {Decimal("0.96"): Decimal("300")}

    decision = bot.evaluate_exit(
        side=OrderSide.NO,
        entry_price=Decimal("0.60"),
        size=2,
        book=book,
        time_to_expiry_s=250.0,
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "TAKE_PROFIT_CEILING"
    assert decision.exit_price == Decimal("0.96")
    # Net PnL = (0.96 - 0.60 - 0.01) * 2 = 0.35 * 2 = 0.70
    assert decision.unrealized_pnl == Decimal("0.70")

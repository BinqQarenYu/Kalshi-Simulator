"""Unit tests for Lane 2 Gold Incubator Shadow Runner."""

import json
from decimal import Decimal
import tempfile
from pathlib import Path
import pytest

from kalshi_sim.incubator_manager import IncubatorManager
from kalshi_sim.ml.gold_inversion_bot import GoldInversionBot
from kalshi_sim.schemas import CryptoAsset, L2BookState, MarketInfo, MarketStatus, OrderSide
from kalshi_sim.shadow_gold_runner import Lane2GoldShadowRunner, calculate_kalshi_taker_fee


@pytest.fixture
def temp_incubator():
    """Create an isolated IncubatorManager using a tempfile."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        temp_path = Path(tf.name)
    manager = IncubatorManager(registry_path=temp_path)
    yield manager
    if temp_path.exists():
        temp_path.unlink()


def test_fee_calculation():
    """Verify quadratic taker fee with $0.01 floor and $0.02 cap."""
    # Price = 0.50 -> 0.07 * 1 * 0.5 * 0.5 = 0.0175 -> ceil to 2 cents
    assert calculate_kalshi_taker_fee(Decimal("0.50")) == Decimal("0.02")
    # Price = 0.05 -> 0.07 * 1 * 0.05 * 0.95 = 0.003325 -> floor at 1 cent
    assert calculate_kalshi_taker_fee(Decimal("0.05")) == Decimal("0.01")
    # Price = 0.95 -> floor at 1 cent
    assert calculate_kalshi_taker_fee(Decimal("0.95")) == Decimal("0.01")


def test_step_entry_and_lock(temp_incubator):
    """Verify step generates shadow order and locks subsequent entries for that cycle."""
    bot = GoldInversionBot()
    runner = Lane2GoldShadowRunner(incubator=temp_incubator, bot=bot)

    market = MarketInfo(
        ticker="KXGOLD15M-TEST-001",
        title="Will Gold be above $2900?",
        status=MarketStatus.OPEN,
        floor_strike=Decimal("2900.00"),
        target_strike=Decimal("2900.00"),
        yes_bid=Decimal("0.49"),
        yes_ask=Decimal("0.51"),
    )
    book = L2BookState(market_ticker=market.ticker)
    book.yes_book = {Decimal("0.49"): 100}
    book.no_book = {Decimal("0.49"): 100}

    # First step: Conditions favorable -> Enters BUY NO
    order = runner.step(
        market=market,
        orderbook=book,
        spot_price=Decimal("2899.50"),
        time_remaining_s=240,
        ofi_imbalance=0.75,
    )
    assert order is not None
    assert order["ticker"] == "KXGOLD15M-TEST-001"
    assert order["side"] == "NO"
    assert order["entry_price"] == Decimal("0.51")
    assert runner.in_flight_position is not None

    # Second step on SAME cycle: In-flight lock blocks duplicate entry
    order2 = runner.step(
        market=market,
        orderbook=book,
        spot_price=Decimal("2899.40"),
        time_remaining_s=200,
        ofi_imbalance=0.80,
    )
    assert order2 is None


def test_settle_win_and_loss(temp_incubator):
    """Verify settlement math and fee deduction for WIN and LOSS."""
    runner = Lane2GoldShadowRunner(incubator=temp_incubator)

    market = MarketInfo(
        ticker="KXGOLD15M-TEST-WIN",
        title="Will Gold be above $2900?",
        status=MarketStatus.OPEN,
        floor_strike=Decimal("2900.00"),
        target_strike=Decimal("2900.00"),
    )
    book = L2BookState(market_ticker=market.ticker)
    book.yes_book = {Decimal("0.49"): 50}
    book.no_book = {Decimal("0.49"): 50}

    # 1. Enter NO trade
    runner.step(
        market=market,
        orderbook=book,
        spot_price=Decimal("2899.50"),
        time_remaining_s=300,
        ofi_imbalance=0.70,
    )

    # Settle with Spot = 2898.00 < 2900.00 (NO wins!)
    # Win payout: $1.00 - $0.51 entry - $0.02 fee = +$0.47
    res = runner.settle_position(settlement_spot=Decimal("2898.00"))
    assert res["outcome"] == "WIN"
    assert res["net_pnl"] == 0.47
    assert runner.in_flight_position is None

    # 2. Enter second trade on new ticker
    market2 = MarketInfo(
        ticker="KXGOLD15M-TEST-LOSS",
        title="Will Gold be above $2900?",
        status=MarketStatus.OPEN,
        floor_strike=Decimal("2900.00"),
        target_strike=Decimal("2900.00"),
    )
    runner.step(
        market=market2,
        orderbook=book,
        spot_price=Decimal("2899.50"),
        time_remaining_s=300,
        ofi_imbalance=0.70,
    )

    # Settle with Spot = 2902.00 >= 2900.00 (YES wins, NO loses!)
    # Loss payout: -$0.51
    res2 = runner.settle_position(settlement_spot=Decimal("2902.00"))
    assert res2["outcome"] == "LOSS"
    assert res2["net_pnl"] == -0.51


def test_30_cycle_auto_certification(temp_incubator):
    """Verify 30 test cycles with 70% win rate automatically certifies Gold and unlocks live trading."""
    runner = Lane2GoldShadowRunner(incubator=temp_incubator)

    # Initial state: locked
    assert temp_incubator.is_locked(CryptoAsset.GOLD) is True

    # Run 30 cycles with 22 wins (73.3% WR >= 65%)
    results = runner.run_simulation_batch(num_cycles=30, win_count=22)
    assert len(results) == 30

    # Verify certification
    status = temp_incubator.get_status(CryptoAsset.GOLD)
    assert status["completed_cycles"] == 30
    assert status["wins"] == 22
    assert status["losses"] == 8
    assert status["current_win_rate"] >= 0.65
    assert status["status"] == "CERTIFIED"
    assert status["is_locked"] is False
    assert temp_incubator.is_locked(CryptoAsset.GOLD) is False


def test_failed_win_rate_retains_lock(temp_incubator):
    """Verify that completing 30 cycles with sub-threshold win rate keeps asset locked."""
    runner = Lane2GoldShadowRunner(incubator=temp_incubator)

    # Run 30 cycles with only 12 wins (40.0% WR < 65%)
    results = runner.run_simulation_batch(num_cycles=30, win_count=12)
    assert len(results) == 30

    status = temp_incubator.get_status(CryptoAsset.GOLD)
    assert status["completed_cycles"] == 30
    assert status["wins"] == 12
    assert status["current_win_rate"] == 0.40
    assert status["status"] == "INCUBATOR"
    assert status["is_locked"] is True
    assert temp_incubator.is_locked(CryptoAsset.GOLD) is True


def test_onnx_30_cycle_85_percent_certification(temp_incubator):
    """Verify 30 test cycles with 85% win rate certifies 32-D Gold ONNX Bot."""
    runner = Lane2GoldShadowRunner(incubator=temp_incubator, strategy_mode="ONNX", target_win_rate=0.85)

    assert temp_incubator.is_locked(CryptoAsset.GOLD) is True
    # 26 wins out of 30 = 86.7% >= 85.0%
    results = runner.run_simulation_batch(num_cycles=30, win_count=26)
    assert len(results) == 30

    status = temp_incubator.get_status(CryptoAsset.GOLD)
    assert status["completed_cycles"] == 30
    assert status["wins"] == 26
    assert status["current_win_rate"] >= 0.85
    assert status["status"] == "CERTIFIED"
    assert status["is_locked"] is False
    assert temp_incubator.is_locked(CryptoAsset.GOLD) is False

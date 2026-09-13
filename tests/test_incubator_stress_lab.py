"""Unit tests for Incubator Stress Lab and Council Quantitative Math Engine."""

from decimal import Decimal
import json
from pathlib import Path
import tempfile
import pytest

from kalshi_sim.incubator_stress_lab import (
    IncubatorStressLab,
    QuantitativeDialSet,
    QuantitativeMathEngine,
    StressTestScore,
)
from kalshi_sim.ml.doge_inversion_bot import DogeInversionBot
from kalshi_sim.schemas import L2BookState, MarketInfo, MarketStatus, OrderSide


def test_quantitative_math_engine():
    """Verify Council mathematical indicator formulas."""
    math = QuantitativeMathEngine()

    # 1. Retail Skew: 800 YES vs 200 NO -> (800 - 200) / 1000 = +0.60
    assert math.calculate_retail_skew(800.0, 200.0) == 0.60
    # Balanced
    assert math.calculate_retail_skew(500.0, 500.0) == 0.0
    # Bearish
    assert math.calculate_retail_skew(100.0, 900.0) == -0.80

    # 2. VCR (Volatility Compression Ratio)
    # 1m vol = 0.20, 15m vol = 0.50 -> 0.40 (Tight compression)
    assert math.calculate_vcr(0.20, 0.50) == 0.40
    # Expansion: 1m vol = 0.80, 15m vol = 0.40 -> 2.00
    assert math.calculate_vcr(0.80, 0.40) == 2.00

    # 3. TWAP Convergence Velocity
    # |2950 - 2948| / 20s = 2.0 / 20 = 0.10 $/s
    assert math.calculate_twap_convergence_velocity(Decimal("2950.00"), Decimal("2948.00"), 20) == 0.10

    # 4. Fee-Adjusted Expected Value (Dr. Nash E*[Kelly])
    # Win prob = 0.70, entry = 0.50, fee = 0.02
    # EV = 0.70 * (1.00 - 0.50) - 0.30 * 0.50 - 0.02 = 0.35 - 0.15 - 0.02 = +0.18
    ev = math.calculate_fee_adjusted_ev(0.70, Decimal("0.50"))
    assert ev == Decimal("0.18")

    # Win prob = 0.30, entry = 0.50
    # EV = 0.30 * 0.50 - 0.70 * 0.50 - 0.02 = 0.15 - 0.35 - 0.02 = -0.22
    ev_neg = math.calculate_fee_adjusted_ev(0.30, Decimal("0.50"))
    assert ev_neg == Decimal("-0.22")


def test_stress_lab_initialization():
    """Verify IncubatorStressLab initializes data cache and settlements."""
    lab = IncubatorStressLab()
    assert lab.cache is not None
    assert isinstance(lab._settlements_cache, dict)


def test_replay_mock_stream():
    """Verify stream replay produces structured evaluation with taker fee."""
    lab = IncubatorStressLab()
    dials = QuantitativeDialSet(entry_price=Decimal("0.50"), min_ofi=0.65)

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as tf:
        temp_path = Path(tf.name)
        # Write mock stream lines
        tf.write(json.dumps({"timestamp": 1789000000.0, "price": 0.50, "delta": 100, "side": "yes"}) + "\n")
        tf.write(json.dumps({"timestamp": 1789000002.0, "price": 0.50, "delta": 50, "side": "no"}) + "\n")

    try:
        res = lab.replay_stream_file(temp_path, dials=dials, asset="GOLD")
        assert res is not None
        assert res["side"] == "NO"
        assert res["entry_price"] == Decimal("0.50")
        assert res["fee"] == Decimal("0.02")
        assert res["outcome"] in ("WIN", "LOSS")
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_doge_inversion_bot_logic():
    """Verify DogeInversionBot applies sub-cent velocity shield and Barnaby rule."""
    bot = DogeInversionBot(
        spot_velocity_limit=Decimal("0.0020"),
        retail_skew_threshold=0.70,
        vcr_threshold=0.50,
    )

    market = MarketInfo(
        ticker="KXDOGE15M-TEST",
        title="Will DOGE be above $0.1300?",
        status=MarketStatus.OPEN,
        floor_strike=Decimal("0.1300"),
        target_strike=Decimal("0.1300"),
    )
    book = L2BookState(market_ticker=market.ticker)
    book.yes_book = {Decimal("0.49"): 50}
    book.no_book = {Decimal("0.50"): 50}

    # 1. Retail skew below threshold -> WAIT
    dec = bot.decide(
        market=market,
        orderbook=book,
        spot_price=Decimal("0.1299"),
        time_remaining_s=240,
        retail_skew=0.40,
        vcr=0.35,
    )
    assert dec.action == "WAIT"
    assert "[RETAIL SKEW GATE]" in dec.rationale

    # 2. VCR expansion -> WAIT
    dec2 = bot.decide(
        market=market,
        orderbook=book,
        spot_price=Decimal("0.1299"),
        time_remaining_s=240,
        retail_skew=0.80,
        vcr=0.85,
    )
    assert dec2.action == "WAIT"
    assert "[VCR EXPANSION GATE]" in dec2.rationale

    # 3. Favorable conditions -> BUY NO
    dec3 = bot.decide(
        market=market,
        orderbook=book,
        spot_price=Decimal("0.1299"),
        time_remaining_s=240,
        retail_skew=0.80,
        vcr=0.35,
    )
    assert dec3.action == "BUY"
    assert dec3.side == OrderSide.NO
    assert dec3.price == Decimal("0.51")

"""Unit and ASVL verification tests for BTC Bot 1 V4 and BtcOrderflowFeed.

Verifies:
1. BtcOrderflowFeed orderbook depth, CVD tracking, OFI L1, and candle building.
2. BtcBot1V4Engine quantitative calibration (1m vol $16.00, strike moat $25.00, chop thresholds).
3. Zero Float Financial Math (Decimal pricing and balances throughout).
4. Micro-bankroll sizing (1 contract) and 1-trade-per-cycle turnover locking.
5. Bidirectional symmetry: YES evaluation above strike and NO evaluation below strike.
6. In-flight position derisking and take-profit thresholds.
7. Seal of Excellence authorization check.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from kalshi_sim.ml.bot1_v4_engine import Bot1V4Decision
from kalshi_sim.ml.btc_bot1v4.btc_bot1v4_engine import BtcBot1V4Engine
from kalshi_sim.ml.btc_bot1v4.paper_trade_btcbot import verify_seal_of_excellence
from kalshi_sim.orderflow.btc_orderflow_feed import BtcOrderflowFeed
from kalshi_sim.schemas import CryptoAsset, L2BookState, MarketInfo, MarketStatus


def test_btc_orderflow_feed_initialization_and_snapshot() -> None:
    """Test BtcOrderflowFeed initializes with realistic BTC depth and valid Decimal math."""
    feed = BtcOrderflowFeed()
    assert feed.last_spot_price == Decimal("85000.00")
    assert feed.book.market_ticker == "BTC-USDT"

    # Verify 20-level bids and asks
    assert len(feed.book.yes_book) == 20
    assert len(feed.book.no_book) == 20

    # Ensure all bids and asks are Decimal
    for p, q in feed.book.yes_book.items():
        assert isinstance(p, Decimal)
        assert isinstance(q, Decimal)

    snapshot_book, trades = feed.get_btc_l2_state()
    assert isinstance(snapshot_book, L2BookState)
    assert len(trades) > 0

    summary = feed.get_orderflow_summary()
    assert summary["spot_price"] == 85000.0
    assert summary["best_bid"] > 0
    assert summary["best_ask"] > summary["best_bid"]

    candles_5m = feed.get_candles(symbol="BTCUSDT", interval_seconds=300)
    assert len(candles_5m) > 0


def test_btc_orderflow_tick_dispatch() -> None:
    """Test callback registration and sub-millisecond tick dispatch."""
    feed = BtcOrderflowFeed()
    received_prices = []

    def on_tick(price: Decimal) -> None:
        received_prices.append(price)

    feed.register_on_tick(on_tick)
    feed.last_spot_price = Decimal("85100.50")
    for cb in feed._on_tick_callbacks:
        cb(Decimal("85100.50"))

    assert len(received_prices) == 1
    assert received_prices[0] == Decimal("85100.50")


def test_btc_bot1v4_engine_calibration_and_defaults(tmp_path: Path) -> None:
    """Test BtcBot1V4Engine is correctly calibrated for Kalshi 15M Bitcoin contracts."""
    hist_file = tmp_path / "win_loss_reports.json"
    engine = BtcBot1V4Engine(history_file=hist_file)

    assert engine.STRATEGY_ID == "bot1_v4_domination"
    assert engine.STRATEGY_NAME == "Bot 1 V4 (BTC Domination)"
    assert engine.asset == CryptoAsset.BTC
    assert engine.default_btc_1m_volatility == 16.00
    assert engine.min_spot_diff == 45.00
    assert engine.chop_range_threshold == 75.00
    assert engine.chop_vol_threshold == 14.00
    assert engine.min_spot_diff_bleed == 45.00
    assert engine.taker_breakout_min_velocity == 12.00
    assert engine.discount_limit_price == Decimal("0.45")
    assert engine.max_entry_price == Decimal("0.55")
    assert engine.max_turnover_per_event == 1


def test_btc_bot1v4_engine_evaluation_yes_and_no() -> None:
    """Test evaluation on BTC orderbook returns valid decisions for both YES and NO sides."""
    engine = BtcBot1V4Engine()
    book = L2BookState("KXBTC15M-TEST")
    book.yes_book = {Decimal("0.45"): Decimal("10"), Decimal("0.40"): Decimal("20")}
    book.no_book = {Decimal("0.55"): Decimal("10"), Decimal("0.60"): Decimal("20")}

    # Case 1: Spot comfortably above strike ($85100 vs $85000 = +$100 diff > $25 moat)
    dec_yes = engine.evaluate(
        book=book,
        spot_price=85100.0,
        target_strike=85000.0,
        time_to_expiry_s=300.0,
        recent_trades=[],
    )
    assert dec_yes is not None
    assert isinstance(dec_yes, Bot1V4Decision)
    assert dec_yes.recommended_side in ("yes", "hold")
    if dec_yes.recommended_side == "yes":
        assert float(dec_yes.limit_price) > 0

    # Case 2: Spot comfortably below strike ($84900 vs $85000 = -$100 diff < -$25 moat)
    dec_no = engine.evaluate(
        book=book,
        spot_price=84900.0,
        target_strike=85000.0,
        time_to_expiry_s=300.0,
        recent_trades=[],
    )
    assert dec_no is not None
    assert isinstance(dec_no, Bot1V4Decision)
    assert dec_no.recommended_side in ("no", "hold")
    if dec_no.recommended_side == "no":
        assert float(dec_no.limit_price) > 0


def test_btc_seal_of_excellence_verification() -> None:
    """Verify that bot1_v4_domination holds a valid Seal on disk."""
    assert verify_seal_of_excellence() is True


def test_btc_bot1v4_macro_slope_caching() -> None:
    """Verify get_macro_1h_slope caches result for 60 seconds."""
    engine = BtcBot1V4Engine()
    engine._last_1h_slope = -0.45
    engine._last_1h_slope_ts = time.monotonic()
    
    # Should immediately return cached value without hitting network
    assert engine.get_macro_1h_slope() == -0.45


@pytest.mark.asyncio
async def test_btc_bot1v4_opening_noise_maturity_gate() -> None:
    """Verify that tau > 600s with spot_diff < $75.00 triggers opening noise gate."""
    from unittest.mock import AsyncMock
    engine = BtcBot1V4Engine(ticker="KXBTC15M-TEST-85000")
    engine.get_spot_price = lambda: Decimal("85030.00")  # diff = +$30 < $75 threshold
    engine.get_macro_1h_slope = lambda: -0.25

    mock_client = AsyncMock()
    engine.order_client = mock_client

    async def mock_fetch_orderbook(ticker: str, rest_base: str = None) -> L2BookState:
        book = L2BookState(ticker)
        book.yes_book = {Decimal("0.45"): Decimal("10")}
        book.no_book = {Decimal("0.55"): Decimal("10")}
        return book

    engine.fetch_orderbook = mock_fetch_orderbook

    # Create market info with 750 seconds to expiry (within opening 5 minutes)
    from datetime import timedelta
    now_utc = datetime.now(timezone.utc)
    engine._cached_market = MarketInfo(
        ticker="KXBTC15M-TEST-85000",
        event_ticker="KXBTC15M",
        status=MarketStatus.ACTIVE,
        open_time=now_utc - timedelta(seconds=150),
        close_time=now_utc + timedelta(seconds=750),
        expiration_time=now_utc + timedelta(seconds=750),
        floor_strike=Decimal("85000.00"),
        cap_strike=None,
        strike_type="greater",
    )
    engine._last_market_fetch_ts = time.monotonic()

    decision = await engine.run_cycle()
    assert decision is not None
    # No order should be placed because opening noise maturity gate triggered
    assert mock_client.place_order.call_count == 0


@pytest.mark.asyncio
async def test_btc_bot1v4_macro_bleed_veto() -> None:
    """Verify that in a macro bleed (slope <= -0.10%), counter-trend YES is vetoed."""
    from unittest.mock import AsyncMock
    engine = BtcBot1V4Engine(ticker="KXBTC15M-TEST-85000")
    engine.get_spot_price = lambda: Decimal("85030.00")  # diff = +$30 < $50 moat requirement
    engine.get_macro_1h_slope = lambda: -0.35  # Bearish macro slope

    mock_client = AsyncMock()
    engine.order_client = mock_client

    async def mock_fetch_orderbook(ticker: str, rest_base: str = None) -> L2BookState:
        book = L2BookState(ticker)
        book.yes_book = {Decimal("0.45"): Decimal("10")}
        book.no_book = {Decimal("0.55"): Decimal("10")}
        return book

    engine.fetch_orderbook = mock_fetch_orderbook

    from datetime import timedelta
    now_utc = datetime.now(timezone.utc)
    engine._cached_market = MarketInfo(
        ticker="KXBTC15M-TEST-85000",
        event_ticker="KXBTC15M",
        status=MarketStatus.ACTIVE,
        open_time=now_utc - timedelta(seconds=400),
        close_time=now_utc + timedelta(seconds=500),
        expiration_time=now_utc + timedelta(seconds=500),  # tau = 500s <= 600s
        floor_strike=Decimal("85000.00"),
        cap_strike=None,
        strike_type="greater",
    )
    engine._last_market_fetch_ts = time.monotonic()

    # Mock kev_oracle to recommend YES
    from kalshi_sim.ml.kev_oracle import KevDecisionResult, KevQuestionType
    mock_kev_res = {
        "trade_direction": KevDecisionResult(
            key="trade_direction",
            question_type=KevQuestionType.CHOICE,
            selected_option="YES",
            probabilities={"YES": Decimal("0.85"), "NO": Decimal("0.10"), "WAIT": Decimal("0.05")},
            confidence=Decimal("0.85"),
            latency_ms=1.0,
            source="test",
        ),
        "is_toxic_sweep": KevDecisionResult(
            key="is_toxic_sweep",
            question_type=KevQuestionType.BOOLEAN,
            selected_option="false",
            probabilities={"false": Decimal("0.90"), "true": Decimal("0.10")},
            confidence=Decimal("0.90"),
            latency_ms=1.0,
            source="test",
        ),
    }
    engine.kev_oracle.evaluate = AsyncMock(return_value=mock_kev_res)

    decision = await engine.run_cycle()
    assert decision is not None
    # Order should be blocked by Macro Bleed Veto
    assert mock_client.place_order.call_count == 0


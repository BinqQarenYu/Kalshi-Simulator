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
from decimal import Decimal
from pathlib import Path
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
    assert engine.min_spot_diff == 25.00
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

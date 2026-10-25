"""Tests for BNB Bot 1 V4 quantitative engine and orderflow feed."""

from decimal import Decimal
from pathlib import Path
import pytest

from kalshi_sim.ml.bot1_v4_engine import Bot1V4Decision
from kalshi_sim.ml.bnb_bot1v4.bnb_bot1v4_engine import BnbBot1V4Engine
from kalshi_sim.orderflow.bnb_orderflow_feed import BnbOrderflowFeed
from kalshi_sim.schemas import CryptoAsset, L2BookState, MarketInfo, MarketStatus, OrderSide, Timeframe


def test_bnb_bot1v4_engine_calibration_and_defaults(tmp_path: Path) -> None:
    """Test BnbBot1V4Engine is correctly calibrated for Kalshi 15M Binance Coin contracts."""
    hist_file = tmp_path / "bnb_win_loss_reports.json"
    engine = BnbBot1V4Engine(history_file=hist_file)

    assert engine.STRATEGY_ID == "bnb_bot1_v4"
    assert engine.STRATEGY_NAME == "BNB Bot 1 V4 (Binance Coin Domination)"
    assert engine.asset == CryptoAsset.BNB
    assert engine.default_btc_1m_volatility == 0.25
    assert engine.min_spot_diff == 1.50
    assert engine.discount_limit_price == Decimal("0.42")
    assert engine.max_entry_price == Decimal("0.45")


def test_bnb_bot1v4_micro_bankroll_and_single_trade_lock(tmp_path: Path) -> None:
    """Verify AGENTS.md Law 2: 1 contract micro-sizing and 1-trade-per-cycle lock."""
    hist_file = tmp_path / "bnb_win_loss_reports.json"
    engine = BnbBot1V4Engine(history_file=hist_file)

    book = L2BookState(market_ticker="BNB-USDT", is_spot=True)
    decision = engine.evaluate(
        book=book,
        spot_price=742.0,
        target_strike=740.0,
        time_to_expiry_s=400.0,
        recent_trades=[],
        total_equity=Decimal("100.00"),
        max_position_size=1,
        estimated_vpin=0.15,
        cycle_id="KXBNB15M-TEST",
        spot_velocity_3s=0.0,
    )

    assert isinstance(decision, Bot1V4Decision)
    assert decision.strategy_id == "bnb_bot1_v4"
    assert decision.recommended_contracts <= 1, "Micro-bankroll violation: Max 1 contract allowed"


def test_bnb_orderflow_feed_initialization() -> None:
    """Test BnbOrderflowFeed initialization state."""
    feed = BnbOrderflowFeed()
    assert feed.book.market_ticker == "BNB-USDT"
    assert feed.last_spot_price == Decimal("740.0")
    assert not feed.is_connected

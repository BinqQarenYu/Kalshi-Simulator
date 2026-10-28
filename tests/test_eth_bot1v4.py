"""Unit and ASVL verification tests for ETH Bot 1 V4 and EthOrderflowFeed.

Verifies:
1. EthOrderflowFeed orderbook depth, CVD tracking, OFI L1, and candle building.
2. EthBot1V4Engine quantitative calibration (1m vol $0.60, strike step $2.50, chop thresholds).
3. Zero Float Financial Math (Decimal pricing and balances throughout).
4. Micro-bankroll sizing (1 contract) and 1-trade-per-cycle turnover locking.
5. LangGraph Council Orchestrator ratification for ETH 15-minute contracts.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from kalshi_sim.council.orchestrator import CouncilOrchestrator
from kalshi_sim.ml.bot1_v4_engine import Bot1V4Decision
from kalshi_sim.ml.eth_bot1v4.eth_bot1v4_engine import EthBot1V4Engine
from kalshi_sim.ml.session_timing_guard import SessionTimingGuard
from kalshi_sim.orderflow.eth_orderflow_feed import EthOrderflowFeed
from kalshi_sim.schemas import CryptoAsset, L2BookState, MarketInfo, MarketStatus


def test_eth_orderflow_feed_initialization_and_snapshot() -> None:
    """Test EthOrderflowFeed initializes with realistic ETH depth and valid Decimal math."""
    feed = EthOrderflowFeed()
    assert feed.last_spot_price == Decimal("2600.00")
    assert feed.book.market_ticker == "ETH-USDT"

    # Verify 20-level bids and asks
    assert len(feed.book.yes_book) == 20
    assert len(feed.book.no_book) == 20

    # Ensure all bids and asks are Decimal
    for p, q in feed.book.yes_book.items():
        assert isinstance(p, Decimal)
        assert isinstance(q, Decimal)

    snapshot_book, trades = feed.get_eth_l2_state()
    assert isinstance(snapshot_book, L2BookState)
    assert len(trades) > 0

    summary = feed.get_orderflow_summary()
    assert summary["spot_price"] == 2600.0
    assert summary["best_bid"] > 0
    assert summary["best_ask"] > summary["best_bid"]

    candles_5m = feed.get_candles(symbol="ETHUSDT", interval_seconds=300)
    assert len(candles_5m) > 0


def test_eth_orderflow_tick_dispatch() -> None:
    """Test callback registration and sub-millisecond tick dispatch."""
    feed = EthOrderflowFeed()
    received_prices = []

    def on_tick(price: Decimal) -> None:
        received_prices.append(price)

    feed.register_on_tick(on_tick)
    feed._dispatch_on_tick(Decimal("2615.50"))

    assert len(received_prices) == 1
    assert received_prices[0] == Decimal("2615.50")


def test_eth_bot1v4_engine_calibration_and_defaults(tmp_path: Path) -> None:
    """Test EthBot1V4Engine is correctly calibrated for Kalshi 15M Ethereum contracts."""
    hist_file = tmp_path / "eth_win_loss_reports.json"
    engine = EthBot1V4Engine(history_file=hist_file)

    assert engine.STRATEGY_ID == "eth_bot1_v4"
    assert engine.STRATEGY_NAME == "ETH Bot 1 V4 (Ethereum Domination)"
    assert engine.asset == CryptoAsset.ETH
    assert engine.default_btc_1m_volatility == 0.60
    assert engine.min_spot_diff == 2.50
    assert engine.chop_range_threshold == 7.50
    assert engine.chop_vol_threshold == 0.60
    assert engine.min_spot_diff_bleed == 5.00
    assert engine.taker_breakout_min_velocity == 1.50
    assert engine.discount_limit_price == Decimal("0.46")
    assert engine.max_entry_price == Decimal("0.54")
    assert engine.max_turnover_per_event == 1


def test_eth_bot1v4_engine_evaluation() -> None:
    """Test evaluation on an ETH orderbook returns a valid Bot1V4Decision with Zero Float math."""
    engine = EthBot1V4Engine()
    book = L2BookState("KXETH15M-TEST")
    book.yes_book = {Decimal("0.42"): Decimal("10"), Decimal("0.40"): Decimal("20")}
    book.no_book = {Decimal("0.58"): Decimal("10"), Decimal("0.60"): Decimal("20")}

    decision = engine.evaluate(
        book=book,
        spot_price=2620.0,
        target_strike=2600.0,
        time_to_expiry_s=400.0,
        recent_trades=[],
        total_equity=Decimal("100.00"),
        max_position_size=1,
        estimated_vpin=0.15,
        cycle_id="KXETH15M-TEST",
        spot_velocity_3s=0.0,
    )

    assert isinstance(decision, Bot1V4Decision)
    assert decision.strategy_id == "eth_bot1_v4"
    assert decision.recommended_side in ("yes", "no", "wait")
    assert decision.recommended_contracts <= 1  # Micro-bankroll invariant


@pytest.mark.asyncio
async def test_eth_bot1v4_run_cycle_with_mock_order_client() -> None:
    """Test EthBot1V4Engine run_cycle executes and adheres to 1-trade-per-cycle lock."""
    mock_order_client = AsyncMock()
    mock_order_client.place_order.return_value = {"order_id": "test_order_123", "status": "executed"}

    feed = EthOrderflowFeed()
    feed.last_spot_price = Decimal("2650.00")

    engine = EthBot1V4Engine(
        order_client=mock_order_client,
        orderflow_feed=feed,
        ticker="KXETH15M-26OCT132100-2600",
    )

    # Mock fetch_orderbook to return a realistic book
    async def mock_fetch_orderbook(ticker: str, rest_base: str = None) -> L2BookState:
        book = L2BookState(ticker)
        book.yes_book = {Decimal("0.42"): Decimal("5")}
        book.no_book = {Decimal("0.58"): Decimal("5")}
        return book

    engine.fetch_orderbook = mock_fetch_orderbook
    engine.get_macro_1h_slope = lambda: 0.0
    engine.experience_buffer = None
    engine.timing_guard = SessionTimingGuard(enabled=False)

    # Cycle 1: Execute opportunity
    decision = await engine.run_cycle()
    assert decision is not None

    if decision.recommended_side in ("yes", "no") and decision.recommended_contracts > 0:
        assert mock_order_client.place_order.call_count == 1
        assert engine.get_completed_turnovers("KXETH15M-26OCT132100-2600") == 1

        # Cycle 2: Same cycle ID should be locked
        second_decision = await engine.run_cycle()
        assert second_decision is not None
        # Should NOT place order again due to 1-trade-per-cycle lock
        assert mock_order_client.place_order.call_count == 1


def test_council_langgraph_deliberation_for_eth() -> None:
    """Test LangGraph Council Orchestrator evaluates and ratifies ETH Bot 1 V4."""
    orch = CouncilOrchestrator()
    res = orch.deliberate(
        raw_prompt="Deploy ETH Bot 1 V4 for 15-minute Kalshi KXETH15M contracts with $2.50 strike step and $0.60 volatility",
        target_asset="ETH",
    )

    assert res.get("consensus_verdict") == "APPROVED"
    assert "nash" in res.get("council_votes", {})
    assert "vance" in res.get("council_votes", {})
    assert "silas" in res.get("council_votes", {})
    assert len(res.get("task_contract", [])) > 0


@pytest.mark.asyncio
async def test_eth_bot1v4_otm_trap_protection() -> None:
    """Ensure OTM trap filter prevents buying YES when spot is > $3.00 below strike."""
    mock_order_client = AsyncMock()
    feed = EthOrderflowFeed()
    feed.last_spot_price = Decimal("2595.00")  # $5 below strike

    engine = EthBot1V4Engine(
        order_client=mock_order_client,
        orderflow_feed=feed,
        ticker="KXETH15M-26OCT132100-2600",
    )

    async def mock_fetch_orderbook(ticker: str, rest_base: str = None) -> L2BookState:
        book = L2BookState(ticker)
        book.yes_book = {Decimal("0.40"): Decimal("10")}
        book.no_book = {Decimal("0.60"): Decimal("10")}
        return book

    engine.fetch_orderbook = mock_fetch_orderbook

    # Force Kev to recommend YES
    from kalshi_sim.ml.kev_oracle import KevDecisionResult, KevQuestionType
    async def mock_answer_batch(*args, **kwargs):
        return [
            KevDecisionResult(
                key="trade_direction",
                question_type=KevQuestionType.CHOICE,
                selected_option="YES",
                probabilities={"YES": Decimal("0.85"), "NO": Decimal("0.10"), "WAIT": Decimal("0.05")},
                confidence=Decimal("0.85"),
            ),
            KevDecisionResult(
                key="is_toxic_sweep",
                question_type=KevQuestionType.BOOLEAN,
                selected_option="false",
                probabilities={"true": Decimal("0.05"), "false": Decimal("0.95")},
                confidence=Decimal("0.95"),
            )
        ]
    engine.kev_oracle.answer_batch = mock_answer_batch

    decision = await engine.run_cycle()
    # Must NOT place order because spot $2595 is $5 below strike $2600 (OTM trap)
    assert mock_order_client.place_order.call_count == 0


def test_eth_bot1v4_record_cycle_settlement_tolerance() -> None:
    """Ensure record_cycle_settlement accepts flexible parameter signatures without throwing."""
    engine = EthBot1V4Engine(ticker="KXETH15M-26OCT132100-2600")
    # Call with ticker, pnl, entry_price, side
    res = engine.record_cycle_settlement(
        won_or_pnl=True,
        ticker="KXETH15M-26OCT132100-2600",
        entry_price=Decimal("0.42"),
        pnl=Decimal("0.58"),
        side="yes",
        execution_mode="paper",
    )
    assert res is not None
    assert res.get("outcome") == "win"
    assert res.get("contracts") == 1


def test_eth_bot1v4_macro_slope_caching() -> None:
    """Verify get_macro_1h_slope caches result for 60 seconds on ETH."""
    engine = EthBot1V4Engine()
    engine._last_1h_slope = -0.32
    engine._last_1h_slope_ts = time.monotonic()
    assert engine.get_macro_1h_slope() == -0.32


@pytest.mark.asyncio
async def test_eth_bot1v4_opening_noise_maturity_gate() -> None:
    """Verify that tau > 600s with spot_diff < $4.50 triggers opening noise gate on ETH."""
    from unittest.mock import AsyncMock
    engine = EthBot1V4Engine(ticker="KXETH15M-TEST-2600")
    engine.get_spot_price = lambda: Decimal("2602.00")  # diff = +$2.00 < $4.50 threshold
    engine.get_macro_1h_slope = lambda: -0.20

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
        ticker="KXETH15M-TEST-2600",
        event_ticker="KXETH15M",
        status=MarketStatus.ACTIVE,
        open_time=now_utc - timedelta(seconds=150),
        close_time=now_utc + timedelta(seconds=750),
        expiration_time=now_utc + timedelta(seconds=750),
        floor_strike=Decimal("2600.00"),
        cap_strike=None,
        strike_type="greater",
    )
    engine._last_market_fetch_ts = time.monotonic()

    decision = await engine.run_cycle()
    assert decision is not None
    assert mock_client.place_order.call_count == 0


@pytest.mark.asyncio
async def test_eth_bot1v4_macro_bleed_veto() -> None:
    """Verify that in an ETH macro bleed (slope <= -0.10%), counter-trend YES is vetoed."""
    from unittest.mock import AsyncMock
    engine = EthBot1V4Engine(ticker="KXETH15M-TEST-2600")
    engine.get_spot_price = lambda: Decimal("2602.00")  # diff = +$2.00 < $3.50 moat requirement
    engine.get_macro_1h_slope = lambda: -0.35

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
        ticker="KXETH15M-TEST-2600",
        event_ticker="KXETH15M",
        status=MarketStatus.ACTIVE,
        open_time=now_utc - timedelta(seconds=400),
        close_time=now_utc + timedelta(seconds=500),
        expiration_time=now_utc + timedelta(seconds=500),  # tau = 500s <= 600s
        floor_strike=Decimal("2600.00"),
        cap_strike=None,
        strike_type="greater",
    )
    engine._last_market_fetch_ts = time.monotonic()

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
    assert mock_client.place_order.call_count == 0



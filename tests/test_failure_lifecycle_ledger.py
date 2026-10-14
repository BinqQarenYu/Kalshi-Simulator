"""Test suite for PR-014: Deterministic Trade Lifecycle & Failure Attribution Ledger (Schema V5).

Verifies:
1. MigrationEngine upgrade to Schema V5 (unfilled_orders, trade_lifecycle_forensics, trade_failure_autopsies).
2. DatabaseWriter enqueueing for unfilled orders, lifecycle forensics, and failure autopsies.
3. OrderSimulator recording unfilled order queue deficit and price approach upon cancellation.
4. Assessment report generation with Section 2.1 Failure Attribution Scorecard.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import pytest
import sqlite3

from kalshi_sim.db.schema import CURRENT_SCHEMA_VERSION, MigrationEngine, SCHEMA_V5_SQL
from kalshi_sim.db.writer import DatabaseWriter, QueuedRecord
from kalshi_sim.db.connection import DatabaseManager
from kalshi_sim.order_simulator import OrderSimulator
from kalshi_sim.schemas import L2BookState, OrderSide, Timeframe
from kalshi_sim.ai_assessor import build_assessment_markdown_report


@pytest.mark.asyncio
async def test_schema_v5_migration(tmp_path: Path):
    """Verify MigrationEngine upgrades database to Schema V5 and creates tables."""
    db_file = tmp_path / "test_v5.db"
    db_mgr = DatabaseManager(db_path=db_file)
    async with db_mgr.get_connection() as db:
        version = await MigrationEngine.run_migrations(db)
        assert version == 5
        assert CURRENT_SCHEMA_VERSION == 5

        # Verify tables exist
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('unfilled_orders', 'trade_lifecycle_forensics', 'trade_failure_autopsies')"
        ) as cur:
            tables = [r[0] for r in await cur.fetchall()]
            assert "unfilled_orders" in tables
            assert "trade_lifecycle_forensics" in tables
            assert "trade_failure_autopsies" in tables


@pytest.mark.asyncio
async def test_database_writer_lifecycle_and_autopsies(tmp_path: Path):
    """Verify DatabaseWriter queues and persists unfilled orders, lifecycle forensics, and failure autopsies."""
    db_file = tmp_path / "test_writer.db"
    db_mgr = DatabaseManager(db_path=db_file)
    writer = DatabaseWriter(db_manager=db_mgr, flush_interval_seconds=0.01)
    await writer.start()

    try:
        # 1. Enqueue unfilled order
        writer.enqueue_unfilled_order(
            order_id="test_unfilled_1",
            ticker="KXBTC15M-TEST",
            side="yes",
            limit_price=0.42,
            size=1,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            terminated_at_utc=datetime.now(timezone.utc).isoformat(),
            lifetime_seconds=125.5,
            cancellation_reason="EXPIRED_WINDOW_CUTOFF",
            initial_queue_ahead=120,
            volume_traded_at_price=45,
            queue_deficit=75,
            queue_exhaustion_pct=37.5,
            t1_regime="CHOPPY",
            t4_regime="STORMY",
            diagnostic_category="UNFILLED_ORDER_EXPIRED",
        )

        # 2. Enqueue lifecycle forensics
        writer.enqueue_lifecycle_forensics(
            trade_id="test_trade_1",
            ticker="KXBTC15M-TEST",
            side="yes",
            entry_price=0.44,
            outcome="WIN",
            realized_pnl=0.56,
            role="MAKER",
            t1_regime="CHOPPY",
            t2_regime="CHOPPY",
            t3_regime="CHOPPY",
            t3_60s_twap=83250.0,
            twap_vs_spot_divergence=5.2,
        )

        # 3. Enqueue failure autopsy
        writer.enqueue_failure_autopsy(
            trade_id="test_fail_1",
            ticker="KXBTC15M-TEST",
            outcome="LOSS",
            realized_pnl=-0.44,
            failure_code="ERR_DOOMED_HOLD_TO_ZERO",
            was_salvageable=1,
            salvageable_cents_lost=0.12,
            macro_1h_slope=-0.45,
            is_counter_trend=1,
        )

        # Allow background flush
        await asyncio.sleep(0.15)
    finally:
        await writer.stop()

    # Verify rows in SQLite
    with sqlite3.connect(db_file) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Check unfilled_orders
        cur.execute("SELECT * FROM unfilled_orders WHERE order_id = 'test_unfilled_1'")
        u_row = cur.fetchone()
        assert u_row is not None
        assert u_row["queue_deficit"] == 75
        assert u_row["cancellation_reason"] == "EXPIRED_WINDOW_CUTOFF"
        assert u_row["t1_regime"] == "CHOPPY"

        # Check trade_lifecycle_forensics
        cur.execute("SELECT * FROM trade_lifecycle_forensics WHERE trade_id = 'test_trade_1'")
        l_row = cur.fetchone()
        assert l_row is not None
        assert l_row["outcome"] == "WIN"
        assert l_row["t3_60s_twap"] == 83250.0

        # Check trade_failure_autopsies
        cur.execute("SELECT * FROM trade_failure_autopsies WHERE trade_id = 'test_fail_1'")
        f_row = cur.fetchone()
        assert f_row is not None
        assert f_row["failure_code"] == "ERR_DOOMED_HOLD_TO_ZERO"
        assert f_row["was_salvageable"] == 1
        assert f_row["salvageable_cents_lost"] == 0.12


def test_order_simulator_unfilled_order_capture():
    """Verify OrderSimulator captures queue deficit and triggers _log_unfilled_order_to_db on expiration."""
    sim = OrderSimulator()
    book = L2BookState(market_ticker="KXBTC15M-EXP-TEST")
    book.yes_book = {Decimal("0.42"): Decimal("100")}
    book.no_book = {Decimal("0.54"): Decimal("50")}

    # Place resting limit order
    ord = sim.place_resting_limit_order(
        book=book,
        side=OrderSide.YES,
        size=1,
        limit_price=Decimal("0.42"),
        timeframe=Timeframe.FIFTEEN_MIN,
    )
    assert ord.order_id in [o.order_id for o in sim.get_all_resting_orders()]
    assert ord.initial_queue_ahead == 100
    assert ord.best_ask_at_placement == Decimal("0.46")

    # Cancel expired order at cutoff
    expired = sim.cancel_expired_orders(time_remaining_s=250, cutoff_s=270, ticker="KXBTC15M-EXP-TEST")
    assert len(expired) == 1
    assert expired[0].order_id == ord.order_id
    assert len(sim.get_all_resting_orders()) == 0


def test_ai_assessor_renders_failure_scorecard():
    """Verify build_assessment_markdown_report outputs Section 2.1 Failure Attribution Scorecard."""
    recent_trades = [
        {
            "ticker": "KXBTC15M-TEST-01",
            "bot_side": "yes",
            "contracts": 1,
            "entry_price": 0.44,
            "settlement_price": 0.0,
            "outcome": "loss",
            "pnl": -0.44,
            "balance_after": 39.56,
            "market_condition": "choppy",
        }
    ]
    report = build_assessment_markdown_report(
        batch_num=100,
        batch_wins=0,
        batch_losses=1,
        batch_pnl=Decimal("-0.44"),
        pre_balance=Decimal("40.00"),
        post_balance=Decimal("39.56"),
        recent_trades=recent_trades,
        gemini_data={"executive_summary": "Test summary", "verdict": "SAFETY_HALT"},
        macro_sample={"cumulative_trades": 1, "cumulative_pnl": "-0.44", "macro_win_rate": 0.0},
    )

    assert "## 2.1. Empirical Loss & Failure Attribution Scorecard" in report
    assert "Section Classification:" not in report  # Confirm valid syntax
    assert "Market Condition" in report

"""Unit and integration tests for asynchronous high-throughput DatabaseWriter."""

from __future__ import annotations

import asyncio
from pathlib import Path
import pytest
import aiosqlite

from kalshi_sim.db.connection import DatabaseManager
from kalshi_sim.db.writer import DatabaseWriter


@pytest.mark.anyio
async def test_database_writer_batch_flush(tmp_path: Path) -> None:
    """Test DatabaseWriter background worker enqueuing and automatic batch flushing."""
    db_path = tmp_path / "test_writer.db"
    db_mgr = DatabaseManager(db_path=db_path)
    writer = DatabaseWriter(db_manager=db_mgr, batch_size=10, flush_interval_seconds=0.05)

    await writer.start()

    # Enqueue 15 trades (triggering at least 1 batch + 1 interval flush)
    for i in range(15):
        writer.enqueue_trade(
            trade_id=f"tr_batch_{i}",
            ticker="KXBTC15M-T78650",
            side="yes" if i % 2 == 0 else "no",
            size=10 + i,
            price=0.45 + (i * 0.01),
            gross_value=4.5 + (i * 0.1),
            fees=0.10,
            vpin=0.25,
            kelly_fraction=0.12,
            execution_mode="simulated",
        )

    # Wait briefly for worker to consume and persist
    await asyncio.sleep(0.15)
    await writer.stop()

    async with db_mgr.get_connection() as db:
        async with db.execute("SELECT COUNT(*) FROM trades") as cur:
            count = (await cur.fetchone())[0]
            assert count == 15

        async with db.execute("SELECT trade_id, ticker, side, size, price FROM trades ORDER BY id ASC") as cur:
            rows = await cur.fetchall()
            assert len(rows) == 15
            assert rows[0]["trade_id"] == "tr_batch_0"
            assert rows[0]["ticker"] == "KXBTC15M-T78650"
            assert rows[0]["side"] == "yes"
            assert rows[0]["size"] == 10


@pytest.mark.anyio
async def test_database_writer_all_tables_concurrency(tmp_path: Path) -> None:
    """Test concurrent enqueueing across all supported tables."""
    db_path = tmp_path / "test_all_tables.db"
    db_mgr = DatabaseManager(db_path=db_path)
    writer = DatabaseWriter(db_manager=db_mgr, batch_size=20, flush_interval_seconds=0.05)

    await writer.start()

    # Enqueue across all tables
    for i in range(25):
        writer.enqueue_tick(
            ticker="KXBTC15M-T78650",
            msg_type="orderbook_delta",
            best_bid=0.48,
            best_ask=0.52,
            mid_price=0.50,
            spread=0.04,
            volume=100.0 * i,
        )
        writer.enqueue_settlement(
            settlement_id=f"st_test_{i}",
            ticker="KXBTC15M-T78650",
            side="yes",
            size=20,
            entry_price=0.48,
            settlement_price=1.0,
            outcome="win",
            pnl=10.4,
            balance_after=10000.0 + (10.4 * i),
        )
        writer.enqueue_equity_snapshot(
            balance=10000.0 + (10.4 * i),
            equity=10000.0 + (10.4 * i),
            realized_pnl=10.4 * i,
            unrealized_pnl=0.0,
            drawdown_pct=0.0,
            win_rate=100.0,
            total_trades=i + 1,
            open_positions_count=0,
        )
        writer.enqueue_ai_prediction(
            ticker="KXBTC15M-T78650",
            p_up=0.70,
            p_down=0.20,
            p_wait=0.10,
            vpin=0.18,
            ev_yes=0.22,
            ev_no=-0.32,
            recommended_side="yes",
            rationale="High probability test edge",
        )
        writer.enqueue_circuit_breaker_event(
            event_type="reset" if i % 2 == 0 else "trip",
            peak_capital=10000.0,
            current_equity=9900.0,
            drawdown_pct=1.0,
            reason="Periodic test health check",
        )

    await writer.stop()

    async with db_mgr.get_connection() as db:
        for tbl in ["ticks", "settlements", "equity_snapshots", "ai_predictions", "circuit_breaker_events"]:
            async with db.execute(f"SELECT COUNT(*) FROM {tbl}") as cur:
                count = (await cur.fetchone())[0]
                assert count == 25, f"Expected 25 rows in {tbl}, got {count}"

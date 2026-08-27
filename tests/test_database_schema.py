"""Unit and integration tests for SQLite schema, migrations, and WAL database manager."""

from __future__ import annotations

from pathlib import Path
import pytest
import aiosqlite

from kalshi_sim.db.connection import DatabaseManager
from kalshi_sim.db.schema import MigrationEngine, CURRENT_SCHEMA_VERSION


@pytest.mark.anyio
async def test_database_init_and_migrations(tmp_path: Path) -> None:
    """Test initializing database and applying schema migrations."""
    db_path = tmp_path / "test_kalshi.db"
    db_mgr = DatabaseManager(db_path=db_path)

    await db_mgr.init_db()
    assert db_path.exists()

    async with db_mgr.get_connection() as db:
        # Check migration version
        version = await MigrationEngine.get_current_version(db)
        assert version == CURRENT_SCHEMA_VERSION

        # Check WAL journal mode
        async with db.execute("PRAGMA journal_mode;") as cursor:
            row = await cursor.fetchone()
            assert row[0].lower() == "wal"

        # Check tables existence
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        ) as cursor:
            rows = await cursor.fetchall()
            table_names = {r["name"] for r in rows}
            expected_tables = {
                "schema_migrations",
                "ticks",
                "trades",
                "settlements",
                "equity_snapshots",
                "ai_predictions",
                "circuit_breaker_events",
            }
            for table in expected_tables:
                assert table in table_names


@pytest.mark.anyio
async def test_database_crud_operations(tmp_path: Path) -> None:
    """Test inserting and querying records across all database tables."""
    db_path = tmp_path / "test_crud.db"
    db_mgr = DatabaseManager(db_path=db_path)
    await db_mgr.init_db()

    async with db_mgr.get_connection() as db:
        # 1. Insert tick
        await db.execute(
            """
            INSERT INTO ticks (timestamp_utc, timestamp_epoch_ms, ticker, msg_type, best_bid, best_ask, mid_price, spread, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-08-27T12:00:00Z", 1787798400000, "KXBTC15M-T78650", "orderbook_delta", 0.48, 0.52, 0.50, 0.04, 1500.0),
        )

        # 2. Insert trade
        await db.execute(
            """
            INSERT INTO trades (trade_id, timestamp_utc, timestamp_epoch_ms, ticker, side, size, price, gross_value, fees, execution_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("tr_12345", "2026-08-27T12:00:01Z", 1787798401000, "KXBTC15M-T78650", "yes", 50, 0.48, 24.0, 0.50, "simulated"),
        )

        # 3. Insert settlement
        await db.execute(
            """
            INSERT INTO settlements (settlement_id, timestamp_utc, timestamp_epoch_ms, ticker, side, size, entry_price, settlement_price, outcome, pnl, balance_after)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("st_999", "2026-08-27T12:15:00Z", 1787799300000, "KXBTC15M-T78650", "yes", 50, 0.48, 1.0, "win", 26.0, 10026.0),
        )

        # 4. Insert equity snapshot
        await db.execute(
            """
            INSERT INTO equity_snapshots (timestamp_utc, timestamp_epoch_ms, balance, equity, realized_pnl, unrealized_pnl, drawdown_pct, win_rate, total_trades, open_positions_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-08-27T12:15:01Z", 1787799301000, 10026.0, 10026.0, 26.0, 0.0, 0.0, 100.0, 1, 0),
        )

        # 5. Insert AI prediction
        await db.execute(
            """
            INSERT INTO ai_predictions (timestamp_utc, timestamp_epoch_ms, ticker, p_up, p_down, p_wait, vpin, ev_yes, ev_no, recommended_side, rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-08-27T12:00:00Z", 1787798400000, "KXBTC15M-T78650", 0.65, 0.20, 0.15, 0.18, 0.17, -0.32, "yes", "Strong positive edge"),
        )

        # 6. Insert circuit breaker event
        await db.execute(
            """
            INSERT INTO circuit_breaker_events (timestamp_utc, timestamp_epoch_ms, event_type, peak_capital, current_equity, drawdown_pct, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-08-27T12:05:00Z", 1787798700000, "trip", 10000.0, 7900.0, 21.0, "Max drawdown exceeded 20% limit"),
        )

        await db.commit()

        # Verify reads
        async with db.execute("SELECT COUNT(*) FROM ticks") as cur:
            assert (await cur.fetchone())[0] == 1

        async with db.execute("SELECT COUNT(*) FROM trades") as cur:
            assert (await cur.fetchone())[0] == 1

        async with db.execute("SELECT COUNT(*) FROM settlements") as cur:
            assert (await cur.fetchone())[0] == 1

        async with db.execute("SELECT COUNT(*) FROM equity_snapshots") as cur:
            assert (await cur.fetchone())[0] == 1

        async with db.execute("SELECT COUNT(*) FROM ai_predictions") as cur:
            assert (await cur.fetchone())[0] == 1

        async with db.execute("SELECT COUNT(*) FROM circuit_breaker_events") as cur:
            assert (await cur.fetchone())[0] == 1

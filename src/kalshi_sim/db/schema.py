"""SQLite Database Schemas and Migration Engine for Kalshi Historical Store.

Defines optimized relational schemas and compound indexes for:
- ticks (raw L2 orderbook updates and trades)
- trades (executed simulator and live orders)
- settlements (binary option contract resolutions)
- equity_snapshots (periodic portfolio state and drawdown checkpoints)
- ai_predictions (Stage 1/2 ONNX inferences and EV decisions)
- circuit_breaker_events (safety lock events)
"""

from __future__ import annotations

import logging
from typing import List

import aiosqlite

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 2

SCHEMA_V1_SQL = """
-- 1. Schema Migrations Version Registry
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT NOT NULL
);

-- 2. Ticks Time-Series Table
CREATE TABLE IF NOT EXISTS ticks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc TEXT NOT NULL,
    timestamp_epoch_ms INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    msg_type TEXT NOT NULL,
    best_bid REAL,
    best_ask REAL,
    mid_price REAL,
    spread REAL,
    volume REAL DEFAULT 0.0,
    payload_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_ticks_ticker_time ON ticks (ticker, timestamp_epoch_ms);
CREATE INDEX IF NOT EXISTS idx_ticks_epoch ON ticks (timestamp_epoch_ms);

-- 3. Trades Execution Ledger Table
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE NOT NULL,
    timestamp_utc TEXT NOT NULL,
    timestamp_epoch_ms INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    timeframe TEXT DEFAULT '15m',
    side TEXT NOT NULL,
    size INTEGER NOT NULL,
    price REAL NOT NULL,
    gross_value REAL NOT NULL,
    fees REAL DEFAULT 0.0,
    vpin REAL,
    kelly_fraction REAL,
    bot_type TEXT DEFAULT '3_step_domination_bot',
    execution_mode TEXT DEFAULT 'simulated',
    status TEXT DEFAULT 'filled'
);

CREATE INDEX IF NOT EXISTS idx_trades_ticker_time ON trades (ticker, timestamp_epoch_ms);
CREATE INDEX IF NOT EXISTS idx_trades_trade_id ON trades (trade_id);
CREATE INDEX IF NOT EXISTS idx_trades_bot_mode ON trades (bot_type, execution_mode);

-- 4. Settlements Resolution Table
CREATE TABLE IF NOT EXISTS settlements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    settlement_id TEXT UNIQUE NOT NULL,
    timestamp_utc TEXT NOT NULL,
    timestamp_epoch_ms INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    size INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    settlement_price REAL NOT NULL,
    outcome TEXT NOT NULL,
    pnl REAL NOT NULL,
    balance_after REAL NOT NULL,
    bot_type TEXT DEFAULT '3_step_domination_bot',
    execution_mode TEXT DEFAULT 'simulated'
);

CREATE INDEX IF NOT EXISTS idx_settlements_ticker_time ON settlements (ticker, timestamp_epoch_ms);
CREATE INDEX IF NOT EXISTS idx_settlements_bot_mode ON settlements (bot_type, execution_mode);

-- 5. Portfolio Equity Snapshots Table
CREATE TABLE IF NOT EXISTS equity_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc TEXT NOT NULL,
    timestamp_epoch_ms INTEGER NOT NULL,
    balance REAL NOT NULL,
    equity REAL NOT NULL,
    realized_pnl REAL NOT NULL,
    unrealized_pnl REAL NOT NULL,
    drawdown_pct REAL DEFAULT 0.0,
    win_rate REAL DEFAULT 0.0,
    total_trades INTEGER DEFAULT 0,
    open_positions_count INTEGER DEFAULT 0,
    bot_type TEXT DEFAULT 'all',
    execution_mode TEXT DEFAULT 'simulated'
);

CREATE INDEX IF NOT EXISTS idx_equity_time ON equity_snapshots (timestamp_epoch_ms);
CREATE INDEX IF NOT EXISTS idx_equity_bot_mode ON equity_snapshots (bot_type, execution_mode);

-- 6. AI Microstructure Predictions Table
CREATE TABLE IF NOT EXISTS ai_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc TEXT NOT NULL,
    timestamp_epoch_ms INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    p_up REAL NOT NULL,
    p_down REAL NOT NULL,
    p_wait REAL NOT NULL,
    vpin REAL NOT NULL,
    ev_yes REAL NOT NULL,
    ev_no REAL NOT NULL,
    recommended_side TEXT NOT NULL,
    rationale TEXT,
    bot_type TEXT DEFAULT 'onnx_ml_bot'
);

CREATE INDEX IF NOT EXISTS idx_ai_ticker_time ON ai_predictions (ticker, timestamp_epoch_ms);

-- 7. Circuit Breaker Safety Events Table
CREATE TABLE IF NOT EXISTS circuit_breaker_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc TEXT NOT NULL,
    timestamp_epoch_ms INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    peak_capital REAL NOT NULL,
    current_equity REAL NOT NULL,
    drawdown_pct REAL NOT NULL,
    reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_cb_time ON circuit_breaker_events (timestamp_epoch_ms);
"""


class MigrationEngine:
    """Manages database initialization and incremental migrations."""

    @staticmethod
    async def get_current_version(db: aiosqlite.Connection) -> int:
        """Query the current schema migration version."""
        try:
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return 0

            async with db.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ) as cursor:
                row = await cursor.fetchone()
                return int(row[0]) if row and row[0] is not None else 0
        except Exception as exc:
            logger.warning("Could not determine schema version: %s", exc)
            return 0

    @classmethod
    async def run_migrations(cls, db: aiosqlite.Connection) -> int:
        """Run all pending schema migrations sequentially in transactions."""
        current_version = await cls.get_current_version(db)
        logger.info("Current database schema version: %d (target: %d)", current_version, CURRENT_SCHEMA_VERSION)

        if current_version < 1:
            logger.info("Applying migration V1 (initial schema setup)...")
            await db.executescript(SCHEMA_V1_SQL)
            await db.execute(
                "INSERT OR REPLACE INTO schema_migrations (version, description) VALUES (1, 'Initial historical tables and indexes')"
            )
            await db.commit()
            current_version = 1
            logger.info("Successfully applied migration V1.")

        if current_version < 2:
            logger.info("Applying migration V2 (bot_type and execution_mode multi-bot isolation columns)...")
            for table, col, col_type in [
                ("trades", "bot_type", "TEXT DEFAULT '3_step_domination_bot'"),
                ("settlements", "bot_type", "TEXT DEFAULT '3_step_domination_bot'"),
                ("settlements", "execution_mode", "TEXT DEFAULT 'simulated'"),
                ("ai_predictions", "bot_type", "TEXT DEFAULT 'onnx_ml_bot'"),
                ("equity_snapshots", "bot_type", "TEXT DEFAULT 'all'"),
                ("equity_snapshots", "execution_mode", "TEXT DEFAULT 'simulated'"),
            ]:
                try:
                    await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                except Exception as exc:
                    logger.debug("Column %s in %s may already exist: %s", col, table, exc)
            await db.execute(
                "INSERT OR REPLACE INTO schema_migrations (version, description) VALUES (2, 'Multi-bot and mode tagging columns')"
            )
            await db.commit()
            current_version = 2
            logger.info("Successfully applied migration V2.")

        return current_version

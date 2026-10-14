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

CURRENT_SCHEMA_VERSION = 5

SCHEMA_V5_SQL = """
-- 12. Unfilled Orders & Opportunity Loss Ledger
CREATE TABLE IF NOT EXISTS unfilled_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    limit_price REAL NOT NULL,
    size INTEGER NOT NULL,
    created_at_utc TEXT NOT NULL,
    terminated_at_utc TEXT NOT NULL,
    lifetime_seconds REAL NOT NULL,
    time_remaining_at_cancel_s REAL,
    cancellation_reason TEXT NOT NULL,
    best_ask_at_placement REAL,
    closest_ask_approach REAL,
    price_gap_cents REAL,
    initial_queue_ahead INTEGER,
    volume_traded_at_price INTEGER,
    queue_deficit INTEGER,
    queue_exhaustion_pct REAL,
    t1_spot_price REAL,
    t1_strike_diff REAL,
    t1_macro_1h_slope REAL,
    t1_regime TEXT,
    t1_vpin REAL,
    t4_spot_price REAL,
    t4_macro_1h_slope REAL,
    t4_regime TEXT,
    settlement_outcome_if_filled TEXT,
    counterfactual_pnl REAL,
    diagnostic_category TEXT,
    bot_type TEXT DEFAULT 'bot1_v4_domination',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_unfilled_ticker ON unfilled_orders (ticker);
CREATE INDEX IF NOT EXISTS idx_unfilled_diag ON unfilled_orders (diagnostic_category);
CREATE INDEX IF NOT EXISTS idx_unfilled_reason ON unfilled_orders (cancellation_reason);

-- 13. Trade Lifecycle Forensics (4-Checkpoint Executed Ledger)
CREATE TABLE IF NOT EXISTS trade_lifecycle_forensics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price REAL NOT NULL,
    role TEXT DEFAULT 'MAKER',
    fee_paid REAL DEFAULT 0.0,
    t1_timestamp TEXT,
    t1_spot REAL,
    t1_strike_diff REAL,
    t1_1h_slope REAL,
    t1_regime TEXT,
    t1_vpin REAL,
    t2_timestamp TEXT,
    t2_queue_wait_seconds REAL,
    t2_spot REAL,
    t2_1h_slope REAL,
    t2_regime TEXT,
    t2_vpin REAL,
    t3_timestamp TEXT,
    t3_spot REAL,
    t3_60s_twap REAL,
    twap_vs_spot_divergence REAL,
    t3_1h_slope REAL,
    t3_regime TEXT,
    mfe_favorable_excursion REAL,
    mae_adverse_excursion REAL,
    outcome TEXT NOT NULL,
    realized_pnl REAL NOT NULL,
    regime_mutated INTEGER DEFAULT 0,
    trend_flipped INTEGER DEFAULT 0,
    adverse_selection_fill INTEGER DEFAULT 0,
    bot_type TEXT DEFAULT 'bot1_v4_domination',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lifecycle_trade_id ON trade_lifecycle_forensics (trade_id);
CREATE INDEX IF NOT EXISTS idx_lifecycle_outcome ON trade_lifecycle_forensics (outcome);
CREATE INDEX IF NOT EXISTS idx_lifecycle_regime ON trade_lifecycle_forensics (t1_regime, t3_regime);

-- 14. Trade Failure & Mistake Autopsies Ledger
CREATE TABLE IF NOT EXISTS trade_failure_autopsies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE NOT NULL,
    ticker TEXT NOT NULL,
    outcome TEXT NOT NULL,
    realized_pnl REAL NOT NULL,
    failure_code TEXT NOT NULL,
    is_counter_trend INTEGER DEFAULT 0,
    macro_1h_slope REAL,
    is_double_wick_trap INTEGER DEFAULT 0,
    wick_to_body_ratio REAL,
    moat_deficit_dollars REAL DEFAULT 0.0,
    was_salvageable INTEGER DEFAULT 0,
    salvageable_cents_lost REAL DEFAULT 0.0,
    mfe_price REAL,
    peak_profit_giveback_pct REAL DEFAULT 0.0,
    cents_left_on_table REAL DEFAULT 0.0,
    stinginess_gap_cents REAL DEFAULT 0.0,
    queue_deficit INTEGER DEFAULT 0,
    is_toxic_dump_fill INTEGER DEFAULT 0,
    vpin_spike_at_fill REAL DEFAULT 0.0,
    is_twap_pin_victim INTEGER DEFAULT 0,
    twap_vs_spot_divergence REAL DEFAULT 0.0,
    bot_type TEXT DEFAULT 'bot1_v4_domination',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_failure_code ON trade_failure_autopsies (failure_code);
CREATE INDEX IF NOT EXISTS idx_failure_salvage ON trade_failure_autopsies (was_salvageable);
CREATE INDEX IF NOT EXISTS idx_failure_counter_trend ON trade_failure_autopsies (is_counter_trend);
"""

SCHEMA_V4_SQL = """
-- 10. Batch Assessments Ledger Table
CREATE TABLE IF NOT EXISTS batch_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_number INTEGER UNIQUE NOT NULL,
    document_id TEXT,
    evaluation_date TEXT NOT NULL,
    time_window TEXT,
    market_session TEXT,
    target_asset TEXT DEFAULT 'KXBTC15M',
    vessel TEXT,
    active_playbook TEXT,
    verdict TEXT NOT NULL,
    wins INTEGER NOT NULL,
    losses INTEGER NOT NULL,
    total_trades INTEGER NOT NULL,
    win_rate REAL NOT NULL,
    net_pnl REAL NOT NULL,
    pre_batch_balance REAL,
    post_batch_balance REAL,
    market_regime TEXT,
    microstructure_context TEXT,
    winning_autopsy TEXT,
    losing_autopsy TEXT,
    root_cause_why TEXT,
    changes_triggered TEXT,
    council_directives TEXT,
    lessons_learned TEXT,
    trades_json TEXT,
    raw_markdown TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_batch_assessments_batch ON batch_assessments (batch_number);
CREATE INDEX IF NOT EXISTS idx_batch_assessments_date ON batch_assessments (evaluation_date);
CREATE INDEX IF NOT EXISTS idx_batch_assessments_verdict ON batch_assessments (verdict);

-- 11. General Macro Assessments Table
CREATE TABLE IF NOT EXISTS general_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    evaluation_date TEXT NOT NULL,
    time_window TEXT,
    total_trades INTEGER,
    wins INTEGER,
    losses INTEGER,
    win_rate REAL,
    net_pnl REAL,
    pre_balance REAL,
    post_balance REAL,
    leaks_identified TEXT,
    architecture_innovations TEXT,
    dof_portfolio_json TEXT,
    lessons_learned TEXT,
    raw_markdown TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_general_assessments_id ON general_assessments (assessment_id);
"""

SCHEMA_V3_SQL = """
-- 8. Perpetual Trading Positions Table
CREATE TABLE IF NOT EXISTS perp_positions (
    id TEXT PRIMARY KEY,
    asset TEXT NOT NULL,
    side TEXT NOT NULL,
    size REAL NOT NULL,
    entry_price REAL NOT NULL,
    mark_price REAL NOT NULL,
    leverage REAL NOT NULL,
    liquidation_price REAL NOT NULL,
    margin REAL NOT NULL,
    unrealized_pnl REAL DEFAULT 0.0,
    realized_pnl REAL DEFAULT 0.0,
    status TEXT DEFAULT 'open',
    bot_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_perp_positions_asset ON perp_positions (asset, status);

-- 9. Perpetual Trading Orders Table
CREATE TABLE IF NOT EXISTS perp_orders (
    id TEXT PRIMARY KEY,
    asset TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT NOT NULL,
    size REAL NOT NULL,
    price REAL,
    leverage REAL NOT NULL,
    margin REAL NOT NULL,
    status TEXT DEFAULT 'pending',
    bot_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_perp_orders_asset ON perp_orders (asset, status);
"""


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

        if current_version < 3:
            logger.info("Applying migration V3 (Perpetual trading tables and indexes)...")
            await db.executescript(SCHEMA_V3_SQL)
            await db.execute(
                "INSERT OR REPLACE INTO schema_migrations (version, description) VALUES (3, 'Perpetual trading positions and orders schema')"
            )
            await db.commit()
            current_version = 3
            logger.info("Successfully applied migration V3.")

        if current_version < 4:
            logger.info("Applying migration V4 (Batch Assessments and Quantitative Lessons Ledger)...")
            await db.executescript(SCHEMA_V4_SQL)
            await db.execute(
                "INSERT OR REPLACE INTO schema_migrations (version, description) VALUES (4, 'Batch assessments and quantitative lessons ledger')"
            )
            await db.commit()
            current_version = 4
            logger.info("Successfully applied migration V4.")

        if current_version < 5:
            logger.info("Applying migration V5 (Unfilled Orders, Lifecycle Forensics & Failure Autopsies)...")
            await db.executescript(SCHEMA_V5_SQL)
            await db.execute(
                "INSERT OR REPLACE INTO schema_migrations (version, description) VALUES (5, 'Unfilled orders, lifecycle forensics, and failure attribution autopsies')"
            )
            await db.commit()
            current_version = 5
            logger.info("Successfully applied migration V5.")

        return current_version

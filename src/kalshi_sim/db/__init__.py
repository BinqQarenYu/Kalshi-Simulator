"""Database persistence and historical analytics package for Kalshi Simulator."""

from __future__ import annotations

from kalshi_sim.db.connection import DatabaseManager, get_db
from kalshi_sim.db.queries import HistoricalQueryService
from kalshi_sim.db.schema import CURRENT_SCHEMA_VERSION, MigrationEngine
from kalshi_sim.db.writer import DatabaseWriter, get_db_writer

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "DatabaseManager",
    "DatabaseWriter",
    "HistoricalQueryService",
    "MigrationEngine",
    "get_db",
    "get_db_writer",
]

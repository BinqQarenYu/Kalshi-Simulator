"""Database Connection Manager and WAL Mode Configuration for SQLite.

Provides thread-safe async connections with:
- PRAGMA journal_mode = WAL (Write-Ahead Logging for non-blocking concurrent reads)
- PRAGMA synchronous = NORMAL (Optimal performance while maintaining durability)
- PRAGMA busy_timeout = 5000 (Prevents lock contention under high-throughput writes)
- PRAGMA foreign_keys = ON
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Union

import aiosqlite

from kalshi_sim.db.schema import MigrationEngine

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/kalshi_history.db")


class DatabaseManager:
    """Manages SQLite connection lifecycle and WAL configuration."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._initialized = False

    async def init_db(self) -> None:
        """Ensure parent directory exists and run pending migrations."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with self.get_connection() as db:
            await MigrationEngine.run_migrations(db)
        self._initialized = True
        logger.info("Database initialized successfully at %s", self.db_path)

    @asynccontextmanager
    async def get_connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """Async context manager yielding a WAL-configured SQLite connection."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(str(self.db_path))
        conn.row_factory = aiosqlite.Row
        try:
            # Configure high-concurrency PRAGMAs
            await conn.execute("PRAGMA journal_mode = WAL;")
            await conn.execute("PRAGMA synchronous = NORMAL;")
            await conn.execute("PRAGMA busy_timeout = 5000;")
            await conn.execute("PRAGMA foreign_keys = ON;")
            yield conn
        finally:
            await conn.close()


# Global default database manager singleton
_global_db_manager: Optional[DatabaseManager] = None


def get_db(db_path: Optional[Union[str, Path]] = None) -> DatabaseManager:
    """Retrieve or create the global DatabaseManager instance."""
    global _global_db_manager
    if _global_db_manager is None or db_path is not None:
        _global_db_manager = DatabaseManager(db_path)
    return _global_db_manager

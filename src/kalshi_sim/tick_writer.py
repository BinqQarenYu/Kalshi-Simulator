"""Structured tick data writer — JSON Lines output for replay and backtest.

Writes Pydantic model instances (snapshots, deltas, tickers, trades) as
newline-delimited JSON using ``orjson`` for speed. Each session produces
one file in ``data/ticks_{timeframe}_{timestamp}.jsonl``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import orjson
from pydantic import BaseModel

from kalshi_sim.schemas import (
    OrderBookDelta,
    OrderBookSnapshot,
    TickerUpdate,
    TradeEvent,
)

logger = logging.getLogger(__name__)


def _orjson_default(obj: Any) -> Any:
    """Handle types that orjson can't serialise natively."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Cannot serialise {type(obj)}")


class TickWriter:
    """Async JSON Lines writer for structured tick data.

    Usage::

        writer = TickWriter(data_dir=Path("data"), timeframe="15m")
        await writer.open()
        await writer.write(some_pydantic_model)
        await writer.close()
    """

    def __init__(
        self,
        data_dir: Path,
        timeframe: str = "15m",
        flush_interval: int = 50,
    ) -> None:
        self._data_dir = data_dir
        self._timeframe = timeframe
        self._flush_interval = flush_interval

        self._file_path: Path | None = None
        self._file = None
        self._write_count: int = 0
        self._lock = asyncio.Lock()

    @property
    def file_path(self) -> Path | None:
        return self._file_path

    async def open(self) -> Path:
        """Create and open a new tick file for the current session.

        Returns the path to the created file.
        """
        self._data_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._file_path = self._data_dir / f"ticks_{self._timeframe}_{ts}.jsonl"
        self._file = open(self._file_path, "ab")  # binary for orjson
        self._write_count = 0
        logger.info("Tick writer opened: %s", self._file_path)
        return self._file_path

    async def write(self, record: BaseModel) -> None:
        """Serialise a Pydantic model and append it as a JSON line.

        Adds a ``_type`` field to identify the record kind on replay.
        """
        if self._file is None:
            raise RuntimeError("TickWriter not opened — call open() first")

        # Build the output dict with type tag
        data = record.model_dump()
        data["_type"] = type(record).__name__

        async with self._lock:
            line = orjson.dumps(data, default=_orjson_default)
            self._file.write(line + b"\n")
            self._write_count += 1

            if self._write_count % self._flush_interval == 0:
                self._file.flush()

    async def write_raw(self, msg_type: str, payload: dict) -> None:
        """Write a raw dict (non-Pydantic) with a type tag."""
        if self._file is None:
            raise RuntimeError("TickWriter not opened — call open() first")

        payload["_type"] = msg_type
        async with self._lock:
            line = orjson.dumps(payload, default=_orjson_default)
            self._file.write(line + b"\n")
            self._write_count += 1

            if self._write_count % self._flush_interval == 0:
                self._file.flush()

    async def close(self) -> None:
        """Flush and close the tick file."""
        if self._file is not None:
            self._file.flush()
            self._file.close()
            self._file = None
            logger.info(
                "Tick writer closed: %s (%d records)",
                self._file_path, self._write_count,
            )

    # -- Context manager support ---------------------------------------------

    async def __aenter__(self) -> TickWriter:
        await self.open()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

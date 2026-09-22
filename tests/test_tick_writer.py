"""Unit tests for asynchronous non-blocking TickWriter."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import orjson
import pytest
from pydantic import BaseModel

from shared.schemas import TradeEvent
from app_1_machine_engine.tick_writer import TickWriter


class DummyRecord(BaseModel):
    id: str
    amount: Decimal
    timestamp: datetime


@pytest.mark.anyio
async def test_tick_writer_write_raw_queue_full(tmp_path: Path) -> None:
    """Verify write_raw handles QueueFull exception gracefully when queue is full."""
    # Create writer with max_queue_size=1
    writer = TickWriter(data_dir=tmp_path, max_queue_size=1)

    # Fill the queue manually without running the drain worker task
    writer._queue.put_nowait(("raw", ("test_msg", {"a": 1})))
    assert writer._queue.full()

    # Attempt to write_raw when queue is full - should catch QueueFull and pass
    await writer.write_raw("test_msg_overflow", {"b": 2})

    # Verify queue length remains 1 (overflow item dropped)
    assert writer._queue.qsize() == 1


@pytest.mark.anyio
async def test_tick_writer_write_pydantic_queue_full(tmp_path: Path) -> None:
    """Verify write handles QueueFull exception gracefully when queue is full."""
    writer = TickWriter(data_dir=tmp_path, max_queue_size=1)

    # Fill queue
    record1 = DummyRecord(
        id="rec1",
        amount=Decimal("12.34"),
        timestamp=datetime.now(timezone.utc),
    )
    writer._queue.put_nowait(("pydantic", record1))
    assert writer._queue.full()

    # Attempt to write when queue is full
    record2 = DummyRecord(
        id="rec2",
        amount=Decimal("56.78"),
        timestamp=datetime.now(timezone.utc),
    )
    await writer.write(record2)

    assert writer._queue.qsize() == 1


@pytest.mark.anyio
async def test_tick_writer_explicit_mock_queue_full(tmp_path: Path) -> None:
    """Explicitly mock put_nowait to raise asyncio.QueueFull to verify exception path."""
    writer = TickWriter(data_dir=tmp_path)
    writer._queue.put_nowait = MagicMock(side_effect=asyncio.QueueFull)

    # Both write_raw and write should swallow QueueFull without raising
    await writer.write_raw("raw_event", {"key": "value"})
    record = DummyRecord(id="rec1", amount=Decimal("1.0"), timestamp=datetime.now(timezone.utc))
    await writer.write(record)


@pytest.mark.anyio
async def test_tick_writer_write_and_flush_lifecycle(tmp_path: Path) -> None:
    """Test full open, write (Pydantic and raw), drain, flush, and close lifecycle."""
    async with TickWriter(data_dir=tmp_path, timeframe="15m", flush_interval=2) as writer:
        path = writer.file_path
        assert path is not None
        assert path.exists()

        # Write Pydantic model
        trade = TradeEvent(
            trade_id="tr_1001",
            market_ticker="KXBTC15M-T78650",
            yes_price=Decimal("0.45"),
            count=Decimal("10"),
            taker_side="yes",
        )
        await writer.write(trade)

        # Write raw dict
        await writer.write_raw("custom_ticker", {"ticker": "KXBTC15M-T78650", "bid": "0.44"})

        # Brief delay to allow drain worker to process queue
        await asyncio.sleep(0.15)

    # After exiting context manager, file is closed
    assert writer._file is None

    # Read and inspect JSON lines file
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    data1 = orjson.loads(lines[0])
    assert data1["_type"] == "TradeEvent"
    assert data1["trade_id"] == "tr_1001"
    assert data1["yes_price"] == "0.45"

    data2 = orjson.loads(lines[1])
    assert data2["_type"] == "custom_ticker"
    assert data2["ticker"] == "KXBTC15M-T78650"
    assert data2["bid"] == "0.44"


@pytest.mark.anyio
async def test_tick_writer_closed_ignore(tmp_path: Path) -> None:
    """Verify write and write_raw return immediately when writer is closed."""
    writer = TickWriter(data_dir=tmp_path)
    await writer.open()
    await writer.close()
    assert writer._closed is True

    record = DummyRecord(id="rec1", amount=Decimal("1.0"), timestamp=datetime.now(timezone.utc))
    await writer.write(record)
    await writer.write_raw("msg", {"a": 1})

    assert writer._queue.empty()

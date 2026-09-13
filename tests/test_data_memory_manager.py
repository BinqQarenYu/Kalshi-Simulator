"""Unit tests for high-throughput ZeroCopyRingBuffer and MarketDataMemoryManager."""

import asyncio
import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from kalshi_sim.data_memory_manager import (
    MarketDataMemoryManager,
    ZeroCopyRingBuffer,
)
from kalshi_sim.schemas import TickerUpdate


def test_ring_buffer_empty_and_capacity():
    buf = ZeroCopyRingBuffer[int](capacity=5)
    assert buf.capacity == 5
    assert buf.size == 0
    assert len(buf) == 0
    assert buf.is_empty()
    assert not buf.is_full()
    assert buf.get_latest() is None
    assert buf.get_oldest() is None
    assert buf.to_list() == []


def test_ring_buffer_fifo_ordering():
    buf = ZeroCopyRingBuffer[int](capacity=4)
    buf.append(10)
    buf.append(20)
    buf.append(30)

    assert buf.size == 3
    assert buf.get_oldest() == 10
    assert buf.get_latest() == 30
    assert buf.to_list() == [10, 20, 30]
    assert buf.get_tail(2) == [20, 30]


def test_ring_buffer_overflow_eviction():
    buf = ZeroCopyRingBuffer[str](capacity=3)
    evicted1 = buf.append("A")
    evicted2 = buf.append("B")
    evicted3 = buf.append("C")
    assert evicted1 is None and evicted2 is None and evicted3 is None
    assert buf.is_full()

    # Overwrite A
    evicted4 = buf.append("D")
    assert evicted4 == "A"
    assert buf.to_list() == ["B", "C", "D"]
    assert buf.get_oldest() == "B"
    assert buf.get_latest() == "D"

    # Overwrite B
    evicted5 = buf.append("E")
    assert evicted5 == "B"
    assert buf.to_list() == ["C", "D", "E"]
    assert buf.total_appends == 5


def test_ring_buffer_batch_extend():
    buf = ZeroCopyRingBuffer[int](capacity=3)
    evicted = buf.extend([1, 2, 3, 4, 5])
    assert evicted == [1, 2]
    assert buf.to_list() == [3, 4, 5]


@pytest.mark.anyio
async def test_memory_manager_hot_ingestion_and_telemetry():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        mgr = MarketDataMemoryManager(
            data_dir=tmp_dir,
            max_hot_ticks_per_ticker=5,
            max_active_tickers=3,
        )
        await mgr.start()

        # Ingest 8 ticks for BTC
        for i in range(8):
            mgr.record_tick("BTC-USDT", {"price": 70000 + i, "seq": i})

        hot = mgr.get_hot_ticks("BTC-USDT", limit=5)
        assert len(hot) == 5
        assert hot[-1]["price"] == 70007
        assert hot[0]["price"] == 70003

        latest = mgr.get_latest_tick("BTC-USDT")
        assert latest is not None
        assert latest["price"] == 70007

        profile = mgr.get_memory_profile()
        assert profile.active_tickers_count == 1
        assert profile.total_hot_ticks == 5
        assert not profile.is_pressure_critical

        await mgr.stop()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.anyio
async def test_memory_manager_async_disk_drain():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        mgr = MarketDataMemoryManager(
            data_dir=tmp_dir,
            max_hot_ticks_per_ticker=2,
            batch_flush_size=2,
            flush_interval_seconds=0.1,
        )
        await mgr.start()

        # Ingest 6 ticks (4 should be evicted to disk queue)
        for i in range(6):
            mgr.record_tick("KXBTC-TEST", {"tick_idx": i, "val": 100 * i})

        # Wait briefly for drain
        await asyncio.sleep(0.25)
        await mgr.stop()

        # Check that disk file was written
        written_files = list(tmp_dir.glob("stream_*.jsonl"))
        assert len(written_files) == 1
        with open(written_files[0], "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 4  # 4 evicted items persisted
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.anyio
async def test_memory_manager_lru_ticker_eviction():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        mgr = MarketDataMemoryManager(
            data_dir=tmp_dir,
            max_hot_ticks_per_ticker=5,
            max_active_tickers=2,
        )
        await mgr.start()

        mgr.record_tick("TICKER_A", {"data": 1})
        mgr.record_tick("TICKER_B", {"data": 2})
        mgr.record_tick("TICKER_C", {"data": 3})  # Should evict TICKER_A from hot RAM

        assert mgr.get_latest_tick("TICKER_A") is None
        assert mgr.get_latest_tick("TICKER_B") is not None
        assert mgr.get_latest_tick("TICKER_C") is not None
        assert mgr.get_memory_profile().active_tickers_count == 2

        await mgr.stop()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.anyio
async def test_memory_manager_compressed_offload():
    """Verify compress_offload=True writes .jsonl.gz files with valid gzip content."""
    import gzip
    import json

    tmp_dir = Path(tempfile.mkdtemp())
    try:
        mgr = MarketDataMemoryManager(
            data_dir=tmp_dir,
            max_hot_ticks_per_ticker=2,
            batch_flush_size=2,
            flush_interval_seconds=0.1,
            compress_offload=True,
        )
        await mgr.start()

        # Ingest 6 ticks (4 should be evicted to disk queue)
        for i in range(6):
            mgr.record_tick("KXBTC-GZ-TEST", {"tick_idx": i, "val": 100 * i})

        # Wait for disk drain
        await asyncio.sleep(0.25)
        await mgr.stop()

        # Check that gzip file was written (not plain .jsonl)
        gz_files = list(tmp_dir.glob("stream_*.jsonl.gz"))
        plain_files = list(tmp_dir.glob("stream_*.jsonl"))
        assert len(gz_files) == 1, f"Expected 1 .gz file, found {len(gz_files)}"
        assert len(plain_files) == 0, f"Expected 0 plain .jsonl files, found {len(plain_files)}"

        # Verify gzip content is valid JSON lines
        with gzip.open(gz_files[0], "rt", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 4  # 4 evicted items persisted
        for line in lines:
            record = json.loads(line)
            assert "tick_idx" in record
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


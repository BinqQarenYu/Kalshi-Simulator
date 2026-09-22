"""Unit tests for src/kalshi_sim/rate_limiter.py.

Tests cover initialization, token refill logic, immediate acquisition,
waiting/refill acquisition, timeout behavior, concurrency, and global instance configuration.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from app_2_execution_bot.rate_limiter import AsyncTokenBucket, kalshi_rate_limiter


def test_init_defaults_and_custom() -> None:
    """Test default and custom initialization parameters of AsyncTokenBucket."""
    bucket_default = AsyncTokenBucket()
    assert bucket_default.rate == 20.0
    assert bucket_default.capacity == 20.0
    assert bucket_default._tokens == 20.0

    bucket_custom = AsyncTokenBucket(rate=10.5, capacity=5.0)
    assert bucket_custom.rate == 10.5
    assert bucket_custom.capacity == 5.0
    assert bucket_custom._tokens == 5.0


def test_global_rate_limiter_instance() -> None:
    """Test global kalshi_rate_limiter instance attributes."""
    assert isinstance(kalshi_rate_limiter, AsyncTokenBucket)
    assert kalshi_rate_limiter.rate == 20.0
    assert kalshi_rate_limiter.capacity == 20.0


@pytest.mark.anyio
async def test_acquire_immediate_within_capacity() -> None:
    """Test acquiring tokens immediately when available in capacity."""
    bucket = AsyncTokenBucket(rate=10.0, capacity=10.0)
    # Acquire 5 tokens immediately
    acquired = await bucket.acquire(5.0, timeout=1.0)
    assert acquired is True
    assert bucket._tokens == pytest.approx(5.0, abs=1e-2)

    # Acquire remaining 5 tokens immediately
    acquired = await bucket.acquire(5.0, timeout=1.0)
    assert acquired is True
    assert bucket._tokens == pytest.approx(0.0, abs=1e-2)


@pytest.mark.anyio
async def test_refill_cap_at_capacity() -> None:
    """Test that bucket refill does not exceed maximum capacity."""
    bucket = AsyncTokenBucket(rate=10.0, capacity=10.0)
    await asyncio.sleep(0.05)
    bucket._refill()
    assert bucket._tokens == 10.0


@pytest.mark.anyio
async def test_acquire_wait_and_refill() -> None:
    """Test acquiring tokens that require waiting for refill."""
    bucket = AsyncTokenBucket(rate=50.0, capacity=5.0)
    # Empty the bucket
    assert await bucket.acquire(5.0) is True

    # Acquire 1 token (requires 1 / 50 = 0.02s)
    start = time.monotonic()
    acquired = await bucket.acquire(1.0, timeout=1.0)
    elapsed = time.monotonic() - start

    assert acquired is True
    assert elapsed >= 0.015


@pytest.mark.anyio
async def test_acquire_timeout() -> None:
    """Test timeout when tokens cannot be replenished in time."""
    bucket = AsyncTokenBucket(rate=1.0, capacity=1.0)
    # Empty bucket
    assert await bucket.acquire(1.0) is True

    # Request 5 tokens (requires 5s, but timeout is 0.1s)
    start = time.monotonic()
    acquired = await bucket.acquire(5.0, timeout=0.1)
    elapsed = time.monotonic() - start

    assert acquired is False
    assert elapsed < 1.0


@pytest.mark.anyio
async def test_acquire_with_none_timeout() -> None:
    """Test acquiring tokens with timeout=None (wait indefinitely)."""
    bucket = AsyncTokenBucket(rate=100.0, capacity=1.0)
    assert await bucket.acquire(1.0) is True

    # Need 1 token = 0.01s wait
    acquired = await bucket.acquire(1.0, timeout=None)
    assert acquired is True


@pytest.mark.anyio
async def test_acquire_zero_tokens() -> None:
    """Test acquiring 0 tokens."""
    bucket = AsyncTokenBucket(rate=10.0, capacity=10.0)
    acquired = await bucket.acquire(0.0, timeout=0.1)
    assert acquired is True
    assert bucket._tokens == 10.0


@pytest.mark.anyio
async def test_acquire_concurrent() -> None:
    """Test concurrent acquisitions across multiple asynchronous tasks."""
    bucket = AsyncTokenBucket(rate=100.0, capacity=10.0)

    async def worker():
        return await bucket.acquire(1.0, timeout=2.0)

    results = await asyncio.gather(*[worker() for _ in range(15)])
    assert all(results)
    assert len(results) == 15


@pytest.mark.anyio
async def test_refill_time_jump() -> None:
    """Test refill behavior when monotonic time advances."""
    bucket = AsyncTokenBucket(rate=10.0, capacity=20.0)
    bucket._tokens = 0.0

    with patch("time.monotonic") as mock_time:
        # Initial call in __init__ used current time
        # Advance monotonic time by 1.5 seconds
        mock_time.return_value = bucket._last_refill + 1.5
        bucket._refill()
        assert bucket._tokens == 15.0
        assert bucket._last_refill == mock_time.return_value

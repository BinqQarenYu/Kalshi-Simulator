"""Asynchronous Token Bucket Rate Limiter for Kalshi API requests.

Kalshi imposes rate limits (default: 20 requests per second).
This module provides a thread-safe, non-blocking token bucket algorithm
to ensure compliance and avoid HTTP 429 errors.
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional


class AsyncTokenBucket:
    """Asynchronous Token Bucket rate limiter.

    Attributes:
        rate: Token replenishment rate in tokens per second.
        capacity: Maximum burst capacity of the token bucket.
    """

    def __init__(self, rate: float = 20.0, capacity: float = 20.0) -> None:
        self.rate = float(rate)
        self.capacity = float(capacity)
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """Add tokens according to elapsed monotonic time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now

    async def acquire(self, tokens: float = 1.0, timeout: Optional[float] = 10.0) -> bool:
        """Acquire `tokens` from the bucket, pausing asynchronously if necessary.

        Args:
            tokens: Number of tokens required for the request.
            timeout: Maximum seconds to wait before giving up.

        Returns:
            bool: True if tokens acquired, False if timed out.
        """
        start_time = time.monotonic()

        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True

                # Compute required wait time for next token
                needed = tokens - self._tokens
                wait_time = needed / self.rate

            if timeout is not None and (time.monotonic() - start_time + wait_time) > timeout:
                return False

            await asyncio.sleep(min(wait_time, 0.05))


# Global default rate limiter instance for Kalshi REST API
kalshi_rate_limiter = AsyncTokenBucket(rate=20.0, capacity=20.0)

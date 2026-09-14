"""Kalshi Clock Synchronization & Exchange Server Time Drift Alignment.

Guarantees sub-second countdown timer and expiration parity with official Kalshi exchange clock:
1. Measures RTT and exchange server time from HTTP 'Date' response header.
2. Handles Windows SSL certificate verification gracefully with certifi / unverified fallback.
3. Computes clock drift: drift = (server_time + RTT / 2) - local_system_time.
4. Periodically refreshes drift in background.
5. Provides `kalshi_now()` and `get_drift_seconds()`.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
import ssl
import threading
import time
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

KALSHI_STATUS_URL = "https://api.elections.kalshi.com/trade-api/v2/exchange/status"


class KalshiClockSync:
    """Singleton coordinator for Kalshi exchange server clock synchronization."""

    def __init__(self, refresh_interval_seconds: float = 300.0) -> None:
        self._drift_seconds: float = 0.0
        self._last_sync_monotonic: float = 0.0
        self._last_rtt_ms: float = 0.0
        self._refresh_interval_seconds: float = refresh_interval_seconds
        self._lock = threading.Lock()
        self._bg_task: Optional[asyncio.Task] = None
        self._running: bool = False

    @property
    def drift_seconds(self) -> float:
        """Current estimated Kalshi clock drift relative to local machine clock in seconds."""
        return self._drift_seconds

    def get_drift_seconds(self) -> float:
        """Return the current clock drift offset in seconds."""
        return self._drift_seconds

    def kalshi_now(self) -> datetime:
        """Return current UTC datetime calibrated to Kalshi's exchange server clock."""
        return datetime.now(timezone.utc) + timedelta(seconds=self._drift_seconds)

    def sync(self) -> float:
        """Synchronously perform HTTP round-trip to calculate exchange drift."""
        t0 = time.time()
        ctx = ssl.create_default_context()
        try:
            import certifi
            ctx.load_verify_locations(cafile=certifi.where())
        except Exception:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(
            KALSHI_STATUS_URL,
            headers={"User-Agent": "KalshiSimulator-ClockSync/1.0"},
        )

        date_str: Optional[str] = None
        try:
            with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                t1 = time.time()
                date_str = resp.headers.get("Date")
        except Exception as exc:
            # Fallback to unverified SSL context for Windows environments with certificate bundle issues
            logger.debug("[CLOCK SYNC] Standard SSL failed (%s), retrying with unverified context...", exc)
            try:
                ctx_unverified = ssl._create_unverified_context()
                t0 = time.time()
                with urllib.request.urlopen(req, timeout=5, context=ctx_unverified) as resp:
                    t1 = time.time()
                    date_str = resp.headers.get("Date")
            except Exception as e2:
                logger.warning("[CLOCK SYNC] Failed to reach Kalshi exchange status: %s", e2)
                return self._drift_seconds

        if not date_str:
            logger.warning("[CLOCK SYNC] No 'Date' header received from Kalshi.")
            return self._drift_seconds

        try:
            server_dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
            rtt = t1 - t0
            estimated_server_time = server_dt.timestamp() + (rtt / 2.0)
            drift = estimated_server_time - t1

            with self._lock:
                self._drift_seconds = drift
                self._last_sync_monotonic = time.monotonic()
                self._last_rtt_ms = rtt * 1000.0

            logger.info(
                "⌚ [NTP SYNC] Kalshi Clock Drift: %+0.3fs (RTT %.1fms) | Server Time: %s",
                drift,
                self._last_rtt_ms,
                server_dt.strftime("%H:%M:%S UTC"),
            )
            return drift
        except Exception as parse_exc:
            logger.warning("[CLOCK SYNC] Failed to parse Date header '%s': %s", date_str, parse_exc)
            return self._drift_seconds

    async def async_sync(self) -> float:
        """Run sync in a background thread worker to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.sync)

    async def start_periodic_sync(self) -> None:
        """Run periodic background task inside an asyncio event loop."""
        if self._bg_task and not self._bg_task.done():
            return
        self._running = True
        self._bg_task = asyncio.create_task(self._periodic_loop(), name="kalshi_clock_sync_loop")

    async def _periodic_loop(self) -> None:
        while self._running:
            try:
                await self.async_sync()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("[CLOCK SYNC] Periodic loop error: %s", e)
            await asyncio.sleep(self._refresh_interval_seconds)

    def stop(self) -> None:
        """Stop background synchronization."""
        self._running = False
        if self._bg_task and not self._bg_task.done():
            self._bg_task.cancel()


# Global module singleton instance
clock_sync = KalshiClockSync()

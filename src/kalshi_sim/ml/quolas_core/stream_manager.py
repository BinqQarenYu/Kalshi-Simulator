"""WebSocket Stream Manager — Binance multi-stream consumer (Transplanted from QuoLas Core).

Manages high-throughput connections to:
- @aggTrade: Tick-by-tick trades (for CVD + absorption)
- @depth@100ms: Order book snapshots (for spoofing & spatial matrices)
- @bookTicker: Best bid/ask (for spread capture & micro-pricing)

Features:
- Exponential backoff reconnection
- Combined stream multiplexing (up to 200 streams per single connection)
- Connection health monitoring and graceful shutdown
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any, Callable, Dict, List, Optional

import websockets
from websockets.exceptions import ConnectionClosed

from kalshi_sim.ml.quolas_core.config import StreamConfig

logger = logging.getLogger("kalshi_sim.ml.quolas_core.stream_manager")


class StreamManager:
    """Manages Binance WebSocket streams using combined multi-stream connections."""

    def __init__(self, config: Optional[StreamConfig] = None, testnet: bool = False) -> None:
        self.config = config or StreamConfig(testnet=testnet)
        self.base_url = self.config.testnet_base_url if self.config.testnet else self.config.base_url
        self.connections: Dict[str, Any] = {}
        self.callbacks: Dict[str, List[Callable]] = {}
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._reconnect_counts: Dict[str, int] = {}

    async def start(
        self,
        pairs: Optional[List[str]] = None,
        on_trade: Optional[Callable] = None,
        on_depth: Optional[Callable] = None,
        on_book_ticker: Optional[Callable] = None,
    ) -> None:
        """Start all WebSocket streams.

        Args:
            pairs: List of trading pair symbols (e.g. ['BTCUSDT']).
            on_trade: Callback for @aggTrade events.
            on_depth: Callback for @depth@100ms events.
            on_book_ticker: Callback for @bookTicker events.
        """
        if pairs is None:
            pairs = self.config.default_pairs

        self._running = True

        # Build stream subscriptions
        streams: List[str] = []
        for pair in pairs:
            symbol = pair.lower()
            if on_trade:
                streams.append(f"{symbol}@aggTrade")
                self.callbacks.setdefault("aggTrade", []).append(on_trade)
            if on_depth:
                streams.append(f"{symbol}@depth@100ms")
                self.callbacks.setdefault("depth", []).append(on_depth)
            if on_book_ticker:
                streams.append(f"{symbol}@bookTicker")
                self.callbacks.setdefault("bookTicker", []).append(on_book_ticker)

        # Split streams into connection groups (max streams per connection)
        max_streams = self.config.max_streams_per_connection
        for i in range(0, len(streams), max_streams):
            chunk = streams[i : i + max_streams]
            stream_path = "/".join(chunk)
            url = f"{self.base_url}/stream?streams={stream_path}"
            conn_id = f"conn_{i // max_streams}"

            task = asyncio.create_task(self._connect_with_retry(conn_id, url))
            self._tasks.append(task)

        logger.info(
            "QuoLas StreamManager started: %d streams across %d connection(s) for %d pair(s)",
            len(streams),
            len(self._tasks),
            len(pairs),
        )

    async def _connect_with_retry(self, conn_id: str, url: str) -> None:
        """Connect with exponential backoff retry."""
        delay = self.config.reconnect_base_delay
        self._reconnect_counts[conn_id] = 0

        while self._running:
            try:
                async with websockets.connect(
                    url,
                    ping_interval=self.config.ping_interval,
                    ping_timeout=self.config.ping_timeout,
                    close_timeout=self.config.close_timeout,
                    max_size=10 * 1024 * 1024,
                ) as ws:
                    self.connections[conn_id] = ws
                    delay = self.config.reconnect_base_delay
                    self._reconnect_counts[conn_id] = 0

                    logger.info("QuoLas WebSocket connected: conn_id=%s", conn_id)

                    async for message in ws:
                        try:
                            data = json.loads(message)
                            await self._dispatch(data)
                        except json.JSONDecodeError:
                            logger.warning("QuoLas WebSocket invalid JSON: conn_id=%s", conn_id)

            except ConnectionClosed as e:
                logger.warning("QuoLas WebSocket closed: conn_id=%s code=%s reason=%s", conn_id, e.code, e.reason)
            except Exception as e:
                logger.error("QuoLas WebSocket error: conn_id=%s error=%s", conn_id, e)

            if not self._running:
                break

            self._reconnect_counts[conn_id] += 1
            logger.info("QuoLas WebSocket reconnecting: conn_id=%s delay=%.1fs", conn_id, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2.0, self.config.reconnect_max_delay)

    async def _dispatch(self, data: Dict) -> None:
        """Route incoming WebSocket messages to registered callbacks."""
        stream_name = data.get("stream", "")
        payload = data.get("data", data)

        if "aggTrade" in stream_name:
            for cb in self.callbacks.get("aggTrade", []):
                try:
                    if inspect.iscoroutinefunction(cb):
                        await cb(payload)
                    else:
                        cb(payload)
                except Exception as e:
                    logger.error("Error in aggTrade callback: %s", e)

        elif "depth" in stream_name:
            for cb in self.callbacks.get("depth", []):
                try:
                    if inspect.iscoroutinefunction(cb):
                        await cb(payload)
                    else:
                        cb(payload)
                except Exception as e:
                    logger.error("Error in depth callback: %s", e)

        elif "bookTicker" in stream_name:
            for cb in self.callbacks.get("bookTicker", []):
                try:
                    if inspect.iscoroutinefunction(cb):
                        await cb(payload)
                    else:
                        cb(payload)
                except Exception as e:
                    logger.error("Error in bookTicker callback: %s", e)

    async def stop(self) -> None:
        """Gracefully stop all streams."""
        self._running = False

        for conn_id, ws in list(self.connections.items()):
            try:
                await ws.close()
            except Exception:
                pass

        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.connections.clear()
        self._tasks.clear()
        logger.info("QuoLas StreamManager stopped gracefully.")

    def get_status(self) -> Dict[str, Any]:
        """Return stream manager status dictionary."""
        return {
            "running": self._running,
            "active_connections": len(self.connections),
            "reconnect_counts": dict(self._reconnect_counts),
            "registered_callbacks": {k: len(v) for k, v in self.callbacks.items()},
        }

"""Resilient WebSocket client for Kalshi Demo exchange.

Handles authenticated connection, exponential backoff reconnection,
subscription management, and heartbeat monitoring.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Coroutine

import aiohttp

from kalshi_sim.auth import get_ws_auth_headers

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEMO_WS_URL = "wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2"

# Backoff parameters
BACKOFF_BASE_S = 1.0
BACKOFF_MAX_S = 60.0
BACKOFF_JITTER_MAX_S = 1.0
STABLE_CONNECTION_THRESHOLD_S = 30.0

# Heartbeat / watchdog
WATCHDOG_TIMEOUT_S = 30.0


# ---------------------------------------------------------------------------
# Subscription tracking
# ---------------------------------------------------------------------------

@dataclass
class SubscriptionState:
    """Tracks an active channel subscription."""
    sid: int
    channel: str
    market_tickers: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# WebSocket Connection Manager
# ---------------------------------------------------------------------------

class KalshiWSClient:
    """Resilient authenticated WebSocket client for the Kalshi Demo exchange.

    Usage::

        client = KalshiWSClient(api_key_id, private_key)
        async for message in client.stream():
            # message is a parsed JSON dict
            handle(message)
    """

    def __init__(
        self,
        api_key_id: str,
        private_key: Any,
        ws_url: str = DEMO_WS_URL,
    ) -> None:
        self._api_key_id = api_key_id
        self._private_key = private_key
        self._ws_url = ws_url

        # Connection state
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._connected = asyncio.Event()
        self._shutdown = asyncio.Event()

        # Subscription tracking
        self._next_cmd_id: int = 1
        self._subscriptions: dict[int, SubscriptionState] = {}
        self._pending_subs: dict[int, asyncio.Future[int]] = {}

        # Reconnection state
        self._reconnect_attempt: int = 0
        self._last_connect_time: float = 0.0

        # Watchdog
        self._last_message_time: float = 0.0

    # -- Lifecycle -----------------------------------------------------------

    async def connect(self) -> None:
        """Establish authenticated WebSocket connection."""
        if self._session is None:
            self._session = aiohttp.ClientSession()

        headers = get_ws_auth_headers(self._api_key_id, self._private_key)
        logger.info("Connecting to %s ...", self._ws_url)

        try:
            self._ws = await self._session.ws_connect(
                self._ws_url,
                headers=headers,
                heartbeat=10.0,
                autoclose=True,
                autoping=True,
            )
            self._connected.set()
            self._last_connect_time = time.monotonic()
            self._last_message_time = time.monotonic()
            self._reconnect_attempt = 0
            logger.info("WebSocket connected successfully.")
        except Exception as exc:
            logger.error("WebSocket connection failed: %s", exc)
            self._connected.clear()
            raise

    async def disconnect(self) -> None:
        """Gracefully close the WebSocket and HTTP session."""
        self._shutdown.set()
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
            logger.info("WebSocket closed.")
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None
        self._connected.clear()

    # -- Subscription commands -----------------------------------------------

    async def subscribe(
        self,
        channels: list[str],
        market_tickers: list[str],
        use_yes_price: bool = True,
    ) -> dict[str, int]:
        """Subscribe to channels for the given tickers.

        Returns a mapping of channel → subscription ID (sid).
        """
        await self._connected.wait()

        cmd_id = self._next_cmd_id
        self._next_cmd_id += 1

        cmd = {
            "id": cmd_id,
            "cmd": "subscribe",
            "params": {
                "channels": channels,
                "market_tickers": market_tickers,
                "use_yes_price": use_yes_price,
            },
        }

        # Create a future to await the subscription confirmation
        fut: asyncio.Future[int] = asyncio.get_event_loop().create_future()
        self._pending_subs[cmd_id] = fut

        await self._send(cmd)
        logger.info(
            "Sent subscribe (id=%d) channels=%s tickers=%s",
            cmd_id, channels, market_tickers[:5],
        )

        # We don't await the future here — confirmations arrive asynchronously
        # and are handled in the message loop. Return the cmd_id for tracking.
        return {"cmd_id": cmd_id, "channels": channels}

    async def update_subscription(
        self,
        sid: int,
        action: str,
        market_tickers: list[str],
    ) -> None:
        """Add or remove tickers from an existing subscription.

        Args:
            sid: The subscription ID to modify.
            action: ``"add_markets"`` or ``"remove_markets"``.
            market_tickers: Tickers to add/remove.
        """
        cmd_id = self._next_cmd_id
        self._next_cmd_id += 1

        cmd = {
            "id": cmd_id,
            "cmd": "update_subscription",
            "params": {
                "sid": sid,
                "action": action,
                "market_tickers": market_tickers,
            },
        }
        await self._send(cmd)
        logger.info(
            "Update subscription sid=%d action=%s tickers=%s",
            sid, action, market_tickers[:5],
        )

    async def unsubscribe(self, sids: list[int]) -> None:
        """Unsubscribe from one or more subscriptions by SID."""
        cmd_id = self._next_cmd_id
        self._next_cmd_id += 1

        cmd = {
            "id": cmd_id,
            "cmd": "unsubscribe",
            "params": {"sids": sids},
        }
        await self._send(cmd)

        for sid in sids:
            self._subscriptions.pop(sid, None)
        logger.info("Unsubscribed sids=%s", sids)

    # -- Message streaming ---------------------------------------------------

    async def stream(self) -> AsyncIterator[dict]:
        """Yield parsed messages with automatic reconnection.

        This is the main entry point. Yields every incoming message as a dict.
        Handles reconnection transparently.
        """
        while not self._shutdown.is_set():
            try:
                if not self._connected.is_set():
                    await self._reconnect_with_backoff()

                async for raw_msg in self._ws:
                    self._last_message_time = time.monotonic()

                    if raw_msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            payload = json.loads(raw_msg.data)
                        except json.JSONDecodeError:
                            logger.warning("Invalid JSON: %s", raw_msg.data[:200])
                            continue

                        # Handle subscription confirmations internally
                        if payload.get("type") == "subscribed":
                            self._handle_subscribed(payload)
                            continue

                        yield payload

                    elif raw_msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(
                            "WebSocket error: %s",
                            self._ws.exception() if self._ws else "unknown",
                        )
                        break

                    elif raw_msg.type in (
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.CLOSING,
                    ):
                        logger.warning("WebSocket closing/closed.")
                        break

                # If we exit the for-loop, connection dropped
                logger.warning("WebSocket stream ended, will reconnect.")
                self._connected.clear()

            except asyncio.CancelledError:
                logger.info("Stream cancelled.")
                break
            except Exception as exc:
                logger.error("Stream error: %s", exc, exc_info=True)
                self._connected.clear()
                # Will reconnect on next loop iteration

    # -- Watchdog ------------------------------------------------------------

    async def run_watchdog(self) -> None:
        """Background task: force reconnect if no messages for WATCHDOG_TIMEOUT_S."""
        while not self._shutdown.is_set():
            await asyncio.sleep(5.0)
            if not self._connected.is_set():
                continue
            elapsed = time.monotonic() - self._last_message_time
            if elapsed > WATCHDOG_TIMEOUT_S:
                logger.warning(
                    "Watchdog: no messages for %.1fs, forcing reconnect.", elapsed
                )
                if self._ws and not self._ws.closed:
                    await self._ws.close()
                self._connected.clear()

    # -- Internal helpers ----------------------------------------------------

    async def _send(self, payload: dict) -> None:
        """Send a JSON command over the WebSocket."""
        if self._ws is None or self._ws.closed:
            raise ConnectionError("WebSocket not connected")
        await self._ws.send_json(payload)

    async def _reconnect_with_backoff(self) -> None:
        """Reconnect with exponential backoff + jitter."""
        self._reconnect_attempt += 1
        delay = min(
            BACKOFF_BASE_S * (2 ** (self._reconnect_attempt - 1)),
            BACKOFF_MAX_S,
        )
        jitter = random.uniform(0, BACKOFF_JITTER_MAX_S)
        total_delay = delay + jitter

        logger.info(
            "Reconnect attempt %d — waiting %.1fs (backoff=%.1f + jitter=%.1f)",
            self._reconnect_attempt, total_delay, delay, jitter,
        )
        await asyncio.sleep(total_delay)

        try:
            await self.connect()
            # Re-subscribe to previously active subscriptions
            await self._resubscribe_all()
        except Exception as exc:
            logger.error("Reconnection failed: %s", exc)
            self._connected.clear()

    async def _resubscribe_all(self) -> None:
        """Re-establish all subscriptions after a reconnect."""
        if not self._subscriptions:
            return

        # Group by channel for efficient re-subscription
        channel_tickers: dict[str, list[str]] = {}
        for sub in self._subscriptions.values():
            channel_tickers.setdefault(sub.channel, []).extend(sub.market_tickers)

        # Clear old subscriptions (SIDs are invalidated after reconnect)
        old_subs = dict(self._subscriptions)
        self._subscriptions.clear()

        for channel, tickers in channel_tickers.items():
            unique_tickers = list(set(tickers))
            if unique_tickers:
                await self.subscribe([channel], unique_tickers)
                logger.info(
                    "Re-subscribed channel=%s tickers=%d",
                    channel, len(unique_tickers),
                )

    def _handle_subscribed(self, payload: dict) -> None:
        """Process a subscription confirmation message."""
        msg = payload.get("msg", {})
        sid = msg.get("sid")
        channel = msg.get("channel", "")
        cmd_id = payload.get("id")

        if sid is not None:
            self._subscriptions[sid] = SubscriptionState(
                sid=sid,
                channel=channel,
            )
            logger.info(
                "Subscription confirmed: sid=%d channel=%s (cmd_id=%s)",
                sid, channel, cmd_id,
            )

        # Resolve pending future if exists
        if cmd_id in self._pending_subs:
            fut = self._pending_subs.pop(cmd_id)
            if not fut.done():
                fut.set_result(sid)

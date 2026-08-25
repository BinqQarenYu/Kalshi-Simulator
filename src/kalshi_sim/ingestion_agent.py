"""Data Ingestion Agent — main coordinator.

Orchestrates the full pipeline:
1. Load config & validate credentials
2. Discover BTC markets via REST
3. Connect to WebSocket with authentication
4. Subscribe to orderbook_delta, ticker, and trade channels
5. Dispatch messages to order book engine + tick writer
6. Periodically refresh market list
7. Handle graceful shutdown
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

from kalshi_sim.auth import DEMO_REST_BASE, load_private_key
from kalshi_sim.market_discovery import discover_btc_markets, get_all_tickers
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.schemas import (
    OrderBookDelta,
    OrderBookSnapshot,
    TickerUpdate,
    Timeframe,
    TradeEvent,
)
from kalshi_sim.simulation_agent import SimulationAgent
from kalshi_sim.tick_writer import TickWriter
from kalshi_sim.ws_connection import KalshiWSClient

logger = logging.getLogger(__name__)

# How often to re-scan REST for new/expired markets (seconds)
MARKET_REFRESH_INTERVAL_S = 60.0


class IngestionAgent:
    """Top-level async coordinator for the Kalshi BTC data ingestion pipeline."""

    def __init__(
        self,
        api_key_id: str,
        private_key_path: str,
        timeframes: list[Timeframe],
        data_dir: Path = Path("data"),
        enable_simulation: bool = False,
        starting_capital: Decimal = Decimal("10000"),
    ) -> None:
        self._api_key_id = api_key_id
        self._private_key = load_private_key(private_key_path)
        self._timeframes = timeframes
        self._data_dir = data_dir
        self._enable_simulation = enable_simulation

        # Components
        self._ws_client = KalshiWSClient(api_key_id, self._private_key)
        self._orderbook = OrderBookManager()
        self._tick_writer = TickWriter(
            data_dir=data_dir,
            timeframe="_".join(tf.value for tf in timeframes),
        )
        self._sim_agent: SimulationAgent | None = None
        if enable_simulation:
            self._sim_agent = SimulationAgent(
                orderbook_manager=self._orderbook,
                timeframes=timeframes,
                starting_capital=starting_capital,
                data_dir=data_dir,
            )

        # State
        self._active_tickers: set[str] = set()
        self._shutdown_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    # -- Public API ----------------------------------------------------------

    async def run(self) -> None:
        """Start the ingestion pipeline. Blocks until shutdown."""
        logger.info("=" * 60)
        logger.info("Kalshi BTC Data Ingestion Agent starting")
        logger.info("Timeframes: %s", [tf.value for tf in self._timeframes])
        logger.info("Data dir:   %s", self._data_dir.resolve())
        logger.info("=" * 60)

        # Open tick writer
        await self._tick_writer.open()

        # Start simulation agent if enabled
        if self._sim_agent is not None:
            await self._sim_agent.start()

        try:
            # Initial market discovery
            await self._refresh_markets()

            if not self._active_tickers:
                logger.error(
                    "No active BTC markets found for timeframes %s. "
                    "The demo exchange may not have these series active right now.",
                    [tf.value for tf in self._timeframes],
                )
                return

            # Connect WebSocket
            await self._ws_client.connect()

            # Subscribe to all channels for discovered tickers
            tickers_list = list(self._active_tickers)
            await self._ws_client.subscribe(
                channels=["orderbook_delta", "ticker", "trade"],
                market_tickers=tickers_list,
            )
            logger.info(
                "Subscribed to %d tickers across %d channels",
                len(tickers_list), 3,
            )

            # Launch background tasks
            self._tasks = [
                asyncio.create_task(self._message_loop(), name="message_loop"),
                asyncio.create_task(self._ws_client.run_watchdog(), name="watchdog"),
                asyncio.create_task(self._market_refresh_loop(), name="market_refresh"),
            ]

            # Wait for shutdown signal or task failure
            done, _ = await asyncio.wait(
                self._tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                if task.exception():
                    logger.error(
                        "Task %s failed: %s",
                        task.get_name(), task.exception(),
                    )

        except asyncio.CancelledError:
            logger.info("Agent cancelled.")
        except Exception as exc:
            logger.error("Agent fatal error: %s", exc, exc_info=True)
        finally:
            await self._shutdown()

    async def run_dry(self) -> None:
        """Dry-run mode: validate auth, discover markets, print tickers, exit."""
        logger.info("=== DRY RUN MODE ===")

        connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
        async with aiohttp.ClientSession(connector=connector) as session:
            markets = await discover_btc_markets(
                session, self._api_key_id, self._private_key, self._timeframes
            )

        for tf, market_list in markets.items():
            logger.info("Timeframe %s: %d markets", tf.value, len(market_list))
            for m in market_list[:10]:
                logger.info(
                    "  %s | close=%s | strike=%s/%s | bid=%s ask=%s",
                    m.ticker,
                    m.close_time,
                    m.floor_strike,
                    m.cap_strike,
                    m.yes_bid,
                    m.yes_ask,
                )

        all_tickers = get_all_tickers(markets)
        logger.info("Total unique tickers: %d", len(all_tickers))
        logger.info("=== DRY RUN COMPLETE ===")

    # -- Message dispatch ----------------------------------------------------

    async def _message_loop(self) -> None:
        """Main message dispatch loop: reads from WebSocket, routes to handlers."""
        async for message in self._ws_client.stream():
            if self._shutdown_event.is_set():
                break

            msg_type = message.get("type")
            seq = message.get("seq", 0)
            msg_body = message.get("msg", {})

            try:
                if msg_type == "orderbook_snapshot":
                    await self._handle_snapshot(msg_body, seq)
                elif msg_type == "orderbook_delta":
                    await self._handle_delta(msg_body, seq)
                elif msg_type == "ticker":
                    await self._handle_ticker(msg_body)
                elif msg_type == "trade":
                    await self._handle_trade(msg_body)
                elif msg_type == "error":
                    logger.error("Server error: %s", msg_body)
                else:
                    logger.debug("Unhandled message type: %s", msg_type)
            except Exception as exc:
                logger.error(
                    "Error handling %s message: %s",
                    msg_type, exc, exc_info=True,
                )

    async def _handle_snapshot(self, msg: dict, seq: int) -> None:
        """Process an orderbook_snapshot message."""
        snapshot = OrderBookSnapshot.from_ws(msg, seq)
        book = self._orderbook.apply_snapshot(snapshot)
        await self._tick_writer.write(snapshot)

        if self._sim_agent is not None:
            await self._sim_agent.on_orderbook_update(snapshot.market_ticker)

        logger.info(
            "[SNAPSHOT] %s | seq=%d | yes_levels=%d no_levels=%d | spread=%s",
            snapshot.market_ticker,
            seq,
            len(snapshot.yes_levels),
            len(snapshot.no_levels),
            book.spread,
        )

    async def _handle_delta(self, msg: dict, seq: int) -> None:
        """Process an orderbook_delta message."""
        delta = OrderBookDelta.from_ws(msg, seq)
        book = self._orderbook.apply_delta(delta)
        await self._tick_writer.write(delta)

        if book is None:
            # Sequence gap — need to re-subscribe for a fresh snapshot
            ticker = delta.market_ticker
            logger.warning(
                "[SEQ GAP] %s — will re-subscribe for fresh snapshot", ticker
            )
            # The stale ticker will be picked up in the next refresh cycle
            return

        if self._sim_agent is not None:
            await self._sim_agent.on_orderbook_update(delta.market_ticker)

        logger.debug(
            "[DELTA] %s | seq=%d | %s %s %+s | spread=%s",
            delta.market_ticker, seq, delta.side,
            delta.price, delta.delta, book.spread,
        )

    async def _handle_ticker(self, msg: dict) -> None:
        """Process a ticker update."""
        update = TickerUpdate.from_ws(msg)
        await self._tick_writer.write(update)

        if self._sim_agent is not None:
            await self._sim_agent.on_ticker_update(update)

        logger.debug(
            "[TICKER] %s | bid=%s ask=%s | vol=%s",
            update.market_ticker, update.yes_bid,
            update.yes_ask, update.volume,
        )

    async def _handle_trade(self, msg: dict) -> None:
        """Process a public trade event."""
        trade = TradeEvent.from_ws(msg)
        await self._tick_writer.write(trade)

        if self._sim_agent is not None:
            await self._sim_agent.on_trade_event(trade)

        logger.debug(
            "[TRADE] %s | %s %s @ %s | count=%s",
            trade.market_ticker, trade.taker_side,
            trade.yes_price, trade.no_price, trade.count,
        )

    # -- Market refresh ------------------------------------------------------

    async def _refresh_markets(self) -> None:
        """Scan REST API for current active BTC markets."""
        connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
        async with aiohttp.ClientSession(connector=connector) as session:
            markets = await discover_btc_markets(
                session, self._api_key_id, self._private_key, self._timeframes
            )

        if self._sim_agent is not None:
            all_market_dict = {}
            for tf, mlist in markets.items():
                for m in mlist:
                    all_market_dict[m.ticker] = m
                    self._sim_agent.set_ticker_timeframe(m.ticker, tf)
            self._sim_agent.update_market_cache(all_market_dict)

        new_tickers = set(get_all_tickers(markets))

        added = new_tickers - self._active_tickers
        removed = self._active_tickers - new_tickers

        if added:
            logger.info("New markets discovered: %s", added)
        if removed:
            logger.info("Markets expired/removed: %s", removed)
            for ticker in removed:
                self._orderbook.remove_book(ticker)

        self._active_tickers = new_tickers
        logger.info("Active tickers: %d", len(self._active_tickers))

    async def _market_refresh_loop(self) -> None:
        """Periodically re-scan for market changes."""
        while not self._shutdown_event.is_set():
            await asyncio.sleep(MARKET_REFRESH_INTERVAL_S)
            try:
                old_tickers = set(self._active_tickers)
                await self._refresh_markets()

                # Handle stale books (sequence gaps)
                stale = self._orderbook.get_stale_tickers()
                if stale:
                    logger.warning("Stale books detected: %s", stale)
                    # TODO: trigger re-subscription for stale tickers

                # Dynamically update WebSocket subscriptions for new tickers
                new_tickers = self._active_tickers - old_tickers
                if new_tickers:
                    await self._ws_client.subscribe(
                        channels=["orderbook_delta", "ticker", "trade"],
                        market_tickers=list(new_tickers),
                    )
            except Exception as exc:
                logger.error("Market refresh error: %s", exc)

    # -- Shutdown ------------------------------------------------------------

    async def _shutdown(self) -> None:
        """Graceful shutdown sequence."""
        logger.info("Shutting down ingestion agent...")
        self._shutdown_event.set()

        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Stop simulation agent if enabled
        if self._sim_agent is not None:
            await self._sim_agent.stop()

        # Disconnect WebSocket
        await self._ws_client.disconnect()

        # Close tick writer
        await self._tick_writer.close()

        logger.info("Ingestion agent stopped.")


# ---------------------------------------------------------------------------
# Entry-point helper
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Load and validate configuration from environment variables.

    Returns a dict with keys: api_key_id, private_key_path, timeframes.

    Raises:
        SystemExit: If required config is missing or env is not 'demo'.
    """
    load_dotenv()

    # Safety check: MUST be demo environment
    env = os.getenv("KALSHI_ENV", "demo").lower()
    if env != "demo":
        logger.critical(
            "KALSHI_ENV=%s — ONLY 'demo' is allowed. Aborting.", env
        )
        sys.exit(1)

    api_key_id = os.getenv("KALSHI_API_KEY_ID", "")
    private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")

    if not api_key_id or not private_key_path:
        logger.critical(
            "Missing KALSHI_API_KEY_ID or KALSHI_PRIVATE_KEY_PATH. "
            "Copy .env.example to .env and fill in your demo credentials."
        )
        sys.exit(1)

    if not Path(private_key_path).exists():
        logger.critical("Private key file not found: %s", private_key_path)
        sys.exit(1)

    # Parse timeframes
    tf_str = os.getenv("KALSHI_TIMEFRAMES", "15m")
    timeframes = []
    for tf in tf_str.split(","):
        tf = tf.strip()
        try:
            timeframes.append(Timeframe(tf))
        except ValueError:
            logger.warning("Unknown timeframe '%s', skipping.", tf)

    if not timeframes:
        timeframes = [Timeframe.FIFTEEN_MIN]

    return {
        "api_key_id": api_key_id,
        "private_key_path": private_key_path,
        "timeframes": timeframes,
    }

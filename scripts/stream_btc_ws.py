"""Standalone Kalshi Demo WebSocket L2 CLOB Ingestion Script for Bitcoin Prediction Markets.

This script connects directly to Kalshi's demo WebSocket endpoint, authenticates
using RSA-PSS SHA-256 signatures, discovers active BTC contracts via REST,
subscribes to L2 orderbook deltas, ticker stats, and trade executions, and maintains
an in-memory Level-2 Central Limit Order Book with real-time sequence validation.

Usage:
    python scripts/stream_btc_ws.py --timeframe 15m
    python scripts/stream_btc_ws.py --key-id YOUR_KEY_ID --key-path ./keys/kalshi_demo.pem
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import os
import random
import signal
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Constants & Configuration (Hard-locked to Demo)
# ---------------------------------------------------------------------------

DEMO_REST_BASE = "https://external-api.demo.kalshi.co/trade-api/v2"
DEMO_WS_URL = "wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2"

TIMEFRAME_SERIES_MAP = {
    "5m": "KXBTC15M",    # Shortest native interval available; windowed locally
    "15m": "KXBTC15M",
    "1h": "KXBTCH",
    "daily": "KXBTCD",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("KalshiWS")


# ---------------------------------------------------------------------------
# Cryptographic Authentication (RSA-PSS SHA-256)
# ---------------------------------------------------------------------------

def load_private_key(pem_path: str | Path) -> RSAPrivateKey:
    """Load an RSA private key from a PEM-encoded file."""
    path = Path(pem_path)
    if not path.exists():
        raise FileNotFoundError(f"Private key file not found: {path.resolve()}")
    pem_bytes = path.read_bytes()
    private_key = serialization.load_pem_private_key(pem_bytes, password=None)
    if not isinstance(private_key, RSAPrivateKey):
        raise TypeError(f"Expected RSAPrivateKey, loaded {type(private_key).__name__}")
    return private_key


def sign_request(private_key: RSAPrivateKey, timestamp_ms: str, method: str, path: str) -> str:
    """Sign an API request using RSA-PSS SHA-256.
    
    Canonical message: timestamp_ms + METHOD + path_without_query
    """
    clean_path = path.split("?")[0]
    canonical_message = f"{timestamp_ms}{method.upper()}{clean_path}".encode("utf-8")
    signature = private_key.sign(
        canonical_message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def get_auth_headers(api_key_id: str, private_key: RSAPrivateKey, method: str, path: str) -> dict[str, str]:
    """Generate the 3 required Kalshi authentication headers."""
    timestamp_ms = str(int(time.time() * 1000))
    signature = sign_request(private_key, timestamp_ms, method, path)
    return {
        "KALSHI-ACCESS-KEY": api_key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
        "KALSHI-ACCESS-SIGNATURE": signature,
    }


def get_ws_handshake_headers(api_key_id: str, private_key: RSAPrivateKey) -> dict[str, str]:
    """Generate headers for the WebSocket HTTP Upgrade handshake."""
    return get_auth_headers(api_key_id, private_key, "GET", "/trade-api/ws/v2")


# ---------------------------------------------------------------------------
# Market Discovery via REST
# ---------------------------------------------------------------------------

async def discover_btc_markets(
    session: aiohttp.ClientSession,
    api_key_id: str,
    private_key: RSAPrivateKey,
    series_ticker: str,
) -> list[dict[str, Any]]:
    """Query open BTC contracts for the requested series."""
    endpoint_path = "/trade-api/v2/markets"
    url = f"{DEMO_REST_BASE}/markets"
    params = {
        "series_ticker": series_ticker,
        "status": "open",
        "limit": 100,
    }
    headers = get_auth_headers(api_key_id, private_key, "GET", endpoint_path)

    async with session.get(url, params=params, headers=headers) as resp:
        if resp.status != 200:
            err_text = await resp.text()
            logger.error("Failed to fetch markets (HTTP %d): %s", resp.status, err_text)
            return []
        data = await resp.json()
        markets = data.get("markets", [])
        logger.info("Discovered %d active %s markets", len(markets), series_ticker)
        return markets


# ---------------------------------------------------------------------------
# In-Memory L2 Order Book State
# ---------------------------------------------------------------------------

class L2Book:
    """Maintains reconstructed Level-2 order book depth for a market."""

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        self.last_seq: int = -1
        self.yes_book: dict[Decimal, Decimal] = {}   # Yes bids: price -> qty
        self.no_book: dict[Decimal, Decimal] = {}    # No bids: price -> qty
        self.is_stale: bool = True
        self.last_update: datetime = datetime.now(timezone.utc)

    def apply_snapshot(self, yes_raw: list[list[str]], no_raw: list[list[str]], seq: int) -> None:
        """Reset book from a full depth snapshot."""
        self.yes_book = {Decimal(p): Decimal(q) for p, q in yes_raw}
        self.no_book = {Decimal(p): Decimal(q) for p, q in no_raw}
        self.last_seq = seq
        self.is_stale = False
        self.last_update = datetime.now(timezone.utc)

    def apply_delta(self, side: str, price_str: str, delta_str: str, seq: int) -> bool:
        """Apply an incremental order book delta. Returns False on sequence gap."""
        expected_seq = self.last_seq + 1
        if seq != expected_seq:
            logger.error(
                "[%s] Sequence Gap! Expected %d, Received %d. Marking book as stale.",
                self.ticker, expected_seq, seq
            )
            self.is_stale = True
            return False

        price = Decimal(price_str)
        delta = Decimal(delta_str)
        book = self.yes_book if side == "yes" else self.no_book

        curr_qty = book.get(price, Decimal("0"))
        new_qty = curr_qty + delta

        if new_qty <= Decimal("0"):
            book.pop(price, None)
        else:
            book[price] = new_qty

        self.last_seq = seq
        self.last_update = datetime.now(timezone.utc)
        return True

    @property
    def best_yes_bid(self) -> Decimal | None:
        return max(self.yes_book.keys()) if self.yes_book else None

    @property
    def best_yes_ask(self) -> Decimal | None:
        # In Kalshi binary markets: Yes Ask = 1.00 - Best No Bid
        best_no = max(self.no_book.keys()) if self.no_book else None
        return (Decimal("1.00") - best_no) if best_no is not None else None

    @property
    def spread(self) -> Decimal | None:
        bid, ask = self.best_yes_bid, self.best_yes_ask
        return (ask - bid) if (bid is not None and ask is not None) else None

    @property
    def mid_price(self) -> Decimal | None:
        bid, ask = self.best_yes_bid, self.best_yes_ask
        return ((bid + ask) / Decimal("2")) if (bid is not None and ask is not None) else None


# ---------------------------------------------------------------------------
# WebSocket Client & Stream Runner
# ---------------------------------------------------------------------------

class KalshiWebSocketRunner:
    """Autonomous WebSocket streaming client with reconnect logic & dispatch."""

    def __init__(
        self,
        api_key_id: str,
        private_key: RSAPrivateKey,
        tickers: list[str],
        save_ticks_dir: Path | None = None,
    ) -> None:
        self.api_key_id = api_key_id
        self.private_key = private_key
        self.tickers = tickers
        self.save_ticks_dir = save_ticks_dir
        self.books: dict[str, L2Book] = {t: L2Book(t) for t in tickers}
        self._shutdown = asyncio.Event()
        self._tick_file = None

    async def run(self) -> None:
        """Main loop with exponential backoff reconnection."""
        if self.save_ticks_dir:
            self.save_ticks_dir.mkdir(parents=True, exist_ok=True)
            log_path = self.save_ticks_dir / f"ws_ticks_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl"
            self._tick_file = open(log_path, "a", encoding="utf-8")
            logger.info("Recording tick events to: %s", log_path.resolve())

        backoff = 1.0
        max_backoff = 60.0

        while not self._shutdown.is_set():
            try:
                headers = get_ws_handshake_headers(self.api_key_id, self.private_key)
                logger.info("Connecting to Kalshi Demo WebSocket: %s", DEMO_WS_URL)

                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(
                        DEMO_WS_URL,
                        headers=headers,
                        heartbeat=10.0,
                        autoping=True,
                    ) as ws:
                        logger.info("WebSocket handshake successful! Subscribing to channels...")
                        backoff = 1.0  # Reset backoff on successful connection

                        # Subscribe to channels
                        sub_cmd = {
                            "id": 1,
                            "cmd": "subscribe",
                            "params": {
                                "channels": ["orderbook_delta", "ticker", "trade"],
                                "market_tickers": self.tickers,
                                "use_yes_price": True,
                            },
                        }
                        await ws.send_json(sub_cmd)
                        logger.info("Subscribed to %d tickers across [orderbook_delta, ticker, trade]", len(self.tickers))

                        async for msg in ws:
                            if self._shutdown.is_set():
                                break

                            if msg.type == aiohttp.WSMsgType.TEXT:
                                self._handle_ws_message(msg.data)
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                logger.error("WebSocket transport error: %s", ws.exception())
                                break
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                                logger.warning("WebSocket closed by server.")
                                break

            except asyncio.CancelledError:
                logger.info("Shutdown requested.")
                break
            except Exception as exc:
                logger.error("Connection error: %s", exc)

            if not self._shutdown.is_set():
                jitter = random.uniform(0.1, 1.0)
                wait_time = min(backoff, max_backoff) + jitter
                logger.info("Reconnecting in %.2f seconds...", wait_time)
                await asyncio.sleep(wait_time)
                backoff *= 2.0

        if self._tick_file:
            self._tick_file.close()

    def _handle_ws_message(self, raw_text: str) -> None:
        """Parse incoming JSON frame and update order book / logs."""
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            return

        if self._tick_file:
            self._tick_file.write(raw_text + "\n")
            self._tick_file.flush()

        msg_type = data.get("type")
        msg_body = data.get("msg", {})
        seq = data.get("seq", 0)

        # 1. Order Book Snapshot
        if msg_type == "orderbook_snapshot":
            ticker = msg_body.get("market_ticker")
            if ticker in self.books:
                book = self.books[ticker]
                book.apply_snapshot(
                    msg_body.get("yes_dollars_fp", []),
                    msg_body.get("no_dollars_fp", []),
                    seq,
                )
                logger.info(
                    "[SNAPSHOT] %s | seq=%d | Bid=$%s Ask=$%s Spread=$%s Mid=$%s",
                    ticker, seq, book.best_yes_bid, book.best_yes_ask, book.spread, book.mid_price
                )

        # 2. Incremental Delta
        elif msg_type == "orderbook_delta":
            ticker = msg_body.get("market_ticker")
            if ticker in self.books:
                book = self.books[ticker]
                valid = book.apply_delta(
                    msg_body.get("side", ""),
                    msg_body.get("price_dollars", "0"),
                    msg_body.get("delta_fp", "0"),
                    seq,
                )
                if valid:
                    logger.debug(
                        "[DELTA] %s | seq=%d | %s %s delta=%s | Bid=$%s Ask=$%s",
                        ticker, seq, msg_body.get("side"), msg_body.get("price_dollars"),
                        msg_body.get("delta_fp"), book.best_yes_bid, book.best_yes_ask
                    )

        # 3. Ticker Stats Update
        elif msg_type == "ticker":
            ticker = msg_body.get("market_ticker")
            logger.info(
                "[TICKER]   %s | Last=$%s | YesBid=$%s YesAsk=$%s | Vol=%s OI=%s",
                ticker,
                msg_body.get("price_dollars"),
                msg_body.get("yes_bid_dollars"),
                msg_body.get("yes_ask_dollars"),
                msg_body.get("volume_fp"),
                msg_body.get("open_interest_fp"),
            )

        # 4. Public Trade Execution
        elif msg_type == "trade":
            ticker = msg_body.get("market_ticker")
            logger.info(
                "[TRADE]    %s | Taker=%s | Count=%s @ YesPrice=$%s (NoPrice=$%s)",
                ticker,
                msg_body.get("taker_side", "").upper(),
                msg_body.get("count_fp"),
                msg_body.get("yes_price_dollars"),
                msg_body.get("no_price_dollars"),
            )

        elif msg_type == "subscribed":
            logger.info("Subscription active: sid=%s channel=%s", msg_body.get("sid"), msg_body.get("channel"))


# ---------------------------------------------------------------------------
# CLI Argument Parser & Entry Point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kalshi Demo WebSocket L2 Ingestion for Bitcoin Markets",
    )
    parser.add_argument(
        "--timeframe", "-t",
        choices=["5m", "15m", "1h", "daily"],
        default="15m",
        help="BTC contract series timeframe (default: 15m -> KXBTC15M)",
    )
    parser.add_argument(
        "--key-id",
        type=str,
        default=None,
        help="Kalshi API Key ID (defaults to KALSHI_API_KEY_ID in .env)",
    )
    parser.add_argument(
        "--key-path",
        type=str,
        default=None,
        help="Path to RSA PEM private key (defaults to KALSHI_PRIVATE_KEY_PATH in .env)",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="Explicit comma-separated market tickers to subscribe (bypasses REST discovery)",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Record raw tick stream to data/*.jsonl file",
    )
    return parser.parse_args()


async def main_async() -> None:
    args = parse_args()
    load_dotenv()

    # Verify Demo Environment Safety Lock
    env = os.getenv("KALSHI_ENV", "demo").lower()
    if env != "demo":
        logger.critical("Safety lock violation: KALSHI_ENV is '%s', must be 'demo'. Aborting.", env)
        sys.exit(1)

    api_key_id = args.key_id or os.getenv("KALSHI_API_KEY_ID")
    key_path = args.key_path or os.getenv("KALSHI_PRIVATE_KEY_PATH", "./keys/kalshi_demo.pem")

    if not api_key_id:
        logger.critical("API Key ID missing. Specify via --key-id or KALSHI_API_KEY_ID in .env")
        sys.exit(1)

    try:
        private_key = load_private_key(key_path)
    except Exception as exc:
        logger.critical("Failed to load private key from '%s': %s", key_path, exc)
        sys.exit(1)

    # Market Selection
    if args.tickers:
        target_tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    else:
        series = TIMEFRAME_SERIES_MAP.get(args.timeframe, "KXBTC15M")
        async with aiohttp.ClientSession() as session:
            markets = await discover_btc_markets(session, api_key_id, private_key, series)
            target_tickers = [m["ticker"] for m in markets]

    if not target_tickers:
        logger.warning(
            "No active %s markets found on the Kalshi Demo environment right now. "
            "Pass specific tickers with --tickers or check demo market hours.",
            args.timeframe
        )
        return

    logger.info("Target Market Tickers (%d): %s", len(target_tickers), target_tickers[:5])

    data_dir = Path("data") if args.record else None
    runner = KalshiWebSocketRunner(api_key_id, private_key, target_tickers, save_ticks_dir=data_dir)

    # Run stream
    await runner.run()


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Terminated by user.")


if __name__ == "__main__":
    main()

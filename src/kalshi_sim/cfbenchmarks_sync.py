"""CF Benchmarks BRTI (Bitcoin Real-Time Index) Synchronization Client.

Provides authenticated, real-time ingestion of Kalshi's official settlement index:
- Primary: 5Hz (200ms) WebSocket stream ('cfbenchmarks_value_5hz' channel).
- Settlement TWAP: 1Hz WebSocket stream with trailing 60s average ('cfbenchmarks_value' channel).
- Secondary: 1.0s REST polling fallback ('GET /trade-api/v2/cfbenchmarks/values?id=BRTI').
- Tertiary: Coinbase Pro BTC-USD emergency fallback during Kalshi network disconnects.
- Strict Decimal financial arithmetic throughout.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import aiohttp

from kalshi_sim.auth import (
    PROD_REST_BASE,
    PROD_WS_URL,
    create_aiohttp_connector,
    get_auth_headers,
    get_ws_auth_headers,
    load_private_key,
)

logger = logging.getLogger("CFBenchmarksBRTI")


class CFBenchmarksBRTISync:
    """Ingests official CME CF Bitcoin Real-Time Index (BRTI) directly from Kalshi."""

    def __init__(
        self,
        api_key_id: str,
        private_key_path: str | Path | Any,
        ws_url: str = PROD_WS_URL,
        rest_base: str = PROD_REST_BASE,
        on_price_update: Optional[Callable[[Decimal, Optional[Decimal], str], None]] = None,
    ) -> None:
        self.api_key_id = api_key_id
        if hasattr(private_key_path, "sign"):
            self.private_key = private_key_path
        elif private_key_path and (isinstance(private_key_path, Path) or Path(str(private_key_path)).exists() or "\n" in str(private_key_path)):
            self.private_key = load_private_key(private_key_path)
        else:
            self.private_key = None

        self.ws_url = ws_url
        self.rest_base = rest_base.rstrip("/")
        self.on_price_update = on_price_update

        # Price State
        self.current_price: Decimal = Decimal("0.00")
        self.twap_60s: Optional[Decimal] = None
        self.last_update_ts: float = 0.0
        self.last_source_ts_ms: int = 0
        self.source: str = "Uninitialized"
        self.is_connected: bool = False
        self.brti_connected: bool = False
        self.latency_ms: float = 0.0

        self._running: bool = False
        self._tasks: List[asyncio.Task] = []
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        """Start real-time ingestion loops."""
        if self._running:
            return
        self._running = True
        self._session = aiohttp.ClientSession(connector=create_aiohttp_connector())

        # Spawn primary Kalshi WebSocket ingestion task
        self._tasks.append(asyncio.create_task(self._ws_loop(), name="brti_ws_feed"))
        # Spawn watchdog / REST fallback loop
        self._tasks.append(asyncio.create_task(self._watchdog_and_rest_loop(), name="brti_rest_watchdog"))
        logger.info("🚀 [CF BENCHMARKS BRTI] Synchronization worker started.")

    async def stop(self) -> None:
        """Stop ingestion loops cleanly."""
        self._running = False
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        self.is_connected = False
        self.brti_connected = False
        logger.info("🛑 [CF BENCHMARKS BRTI] Ingestion stopped.")

    def _update_price(
        self,
        price_dec: Decimal,
        twap_dec: Optional[Decimal] = None,
        source_label: str = "BRTI",
        source_ts_ms: int = 0,
    ) -> None:
        """Update internal state and trigger listener."""
        if price_dec <= Decimal("0.00"):
            return
        self.current_price = price_dec
        if twap_dec is not None and twap_dec > Decimal("0.00"):
            self.twap_60s = twap_dec
        self.source = source_label
        self.last_update_ts = time.time()
        self.is_connected = True
        if "BRTI" in source_label:
            self.brti_connected = True
            if source_ts_ms > 0:
                self.last_source_ts_ms = source_ts_ms
                self.latency_ms = max(0.0, (time.time() * 1000.0) - source_ts_ms)

        if self.on_price_update:
            try:
                self.on_price_update(self.current_price, self.twap_60s, self.source)
            except Exception as e:
                logger.debug("Error in on_price_update callback: %s", e)

    async def _ws_loop(self) -> None:
        """Maintain persistent authenticated WebSocket connection to Kalshi for BRTI."""
        backoff = 1.0
        while self._running:
            if not self.api_key_id or not self.private_key:
                logger.warning("CF Benchmarks BRTI: Missing Kalshi credentials, WebSocket feed paused.")
                await asyncio.sleep(5.0)
                continue

            try:
                headers = get_ws_auth_headers(self.api_key_id, self.private_key)
                logger.info("🔌 [BRTI WS] Connecting to Kalshi WebSocket for CF Benchmarks BRTI...")
                async with self._session.ws_connect(self.ws_url, headers=headers, timeout=10.0) as ws:
                    logger.info("✅ [BRTI WS] Connected. Subscribing to cfbenchmarks_value_5hz & cfbenchmarks_value...")
                    
                    sub_cmd = {
                        "id": 1,
                        "cmd": "subscribe",
                        "params": {
                            "channels": ["cfbenchmarks_value_5hz", "cfbenchmarks_value"],
                            "index_ids": ["BRTI"],
                        },
                    }
                    await ws.send_json(sub_cmd)
                    backoff = 1.0  # Reset backoff on successful connect

                    async for msg in ws:
                        if not self._running:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                payload = json.loads(msg.data)
                                m_type = payload.get("type")
                                m_body = payload.get("msg", {})

                                if m_type == "cfbenchmarks_value_5hz":
                                    idx_id = m_body.get("index_id")
                                    if idx_id == "BRTI":
                                        val_raw = m_body.get("value_usd")
                                        if not val_raw and "data" in m_body:
                                            try:
                                                nested = json.loads(m_body["data"])
                                                val_raw = nested.get("value")
                                            except Exception:
                                                pass
                                        if val_raw:
                                            price = Decimal(str(val_raw))
                                            ts_ms = m_body.get("source_ts_ms", 0)
                                            self._update_price(
                                                price,
                                                source_label="CF Benchmarks BRTI (5Hz WS)",
                                                source_ts_ms=ts_ms,
                                            )

                                elif m_type == "cfbenchmarks_value":
                                    idx_id = m_body.get("index_id")
                                    if idx_id == "BRTI":
                                        # Extract 60s TWAP
                                        avg_data = m_body.get("avg_60s_data")
                                        twap_val = None
                                        if avg_data and "value" in avg_data:
                                            try:
                                                twap_val = Decimal(str(avg_data["value"]))
                                            except (InvalidOperation, TypeError):
                                                pass

                                        # Extract 1Hz spot price if 5Hz is slightly delayed
                                        val_raw = None
                                        if "data" in m_body:
                                            try:
                                                nested = json.loads(m_body["data"])
                                                val_raw = nested.get("value")
                                            except Exception:
                                                pass
                                        if val_raw:
                                            price = Decimal(str(val_raw))
                                            self._update_price(
                                                price,
                                                twap_dec=twap_val,
                                                source_label="CF Benchmarks BRTI (1Hz WS)",
                                            )
                                        elif twap_val is not None:
                                            self.twap_60s = twap_val

                                elif m_type == "subscribed":
                                    logger.info("📡 [BRTI WS] Subscribed successfully to channel: %s", m_body.get("channel"))
                                elif m_type == "error":
                                    logger.warning("⚠️ [BRTI WS] Exchange error: %s", m_body)

                            except Exception as parse_err:
                                logger.debug("Error parsing BRTI WS message: %s", parse_err)

                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            logger.warning("⚠️ [BRTI WS] WebSocket closed/error: %s", msg.data)
                            break

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.brti_connected = False
                logger.warning("⚠️ [BRTI WS] Connection error: %s. Retrying in %.1fs...", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.5, 30.0)

    async def _watchdog_and_rest_loop(self) -> None:
        """Fallback watchdog: polls Kalshi REST if WS is silent, or Coinbase if Kalshi is down."""
        while self._running:
            await asyncio.sleep(1.0)
            now = time.time()
            stale_threshold = 3.0  # If no BRTI update within 3s, trigger REST poll

            if now - self.last_update_ts > stale_threshold:
                # 1. Try Kalshi REST BRTI Polling
                polled = await self._poll_kalshi_brti_rest()
                if not polled:
                    # 2. Emergency Tertiary Fallback: Coinbase Pro REST
                    await self._poll_coinbase_fallback()

    async def _poll_kalshi_brti_rest(self) -> bool:
        """Query 'GET /trade-api/v2/cfbenchmarks/values?id=BRTI'."""
        if not self.api_key_id or not self.private_key or not self._session:
            return False
        endpoint = "/trade-api/v2/cfbenchmarks/values"
        try:
            headers = get_auth_headers(self.api_key_id, self.private_key, "GET", endpoint)
            url = f"{self.rest_base}{endpoint}?id=BRTI"
            async with self._session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    payload = data.get("data", {}).get("payload", {})
                    values = payload.get("values", [])
                    if values:
                        latest = values[-1]
                        price_str = latest.get("value")
                        ts_ms = latest.get("time", 0)
                        if price_str:
                            self._update_price(
                                Decimal(str(price_str)),
                                source_label="CF Benchmarks BRTI (REST)",
                                source_ts_ms=ts_ms,
                            )
                            return True
        except Exception as e:
            logger.debug("Failed Kalshi BRTI REST poll: %s", e)
        return False

    async def _poll_coinbase_fallback(self) -> None:
        """Query Coinbase Pro BTC-USD spot as tertiary fallback."""
        if not self._session:
            return
        try:
            async with self._session.get(
                "https://api.coinbase.com/v2/prices/BTC-USD/spot",
                timeout=aiohttp.ClientTimeout(total=2.0),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    amt = data.get("data", {}).get("amount")
                    if amt:
                        self._update_price(
                            Decimal(str(amt)),
                            source_label="Coinbase Pro Fallback",
                        )
        except Exception as e:
            logger.debug("Failed Coinbase fallback poll: %s", e)

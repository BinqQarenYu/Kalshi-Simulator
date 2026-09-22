"""CF Benchmarks Multi-Asset Synchronization Client.

Provides authenticated, real-time ingestion of Kalshi's official CME CF settlement indices:
- Bitcoin: 'BRTI'
- Ethereum: 'ETHUSD_RTI'
- Solana: 'SOLUSD_RTI'
- Dogecoin: 'DOGEUSD_RTI'

Capabilities:
- Primary: 5Hz (200ms) WebSocket stream ('cfbenchmarks_value_5hz' channel).
- Settlement TWAP: 1Hz WebSocket stream with trailing 60s average ('cfbenchmarks_value' channel).
- Secondary: 1.0s REST polling fallback ('GET /trade-api/v2/cfbenchmarks/values?id={index_id}').
- Tertiary: Coinbase Pro USD spot emergency fallback.
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

from shared.auth import (
    PROD_REST_BASE,
    PROD_WS_URL,
    create_aiohttp_connector,
    get_auth_headers,
    get_ws_auth_headers,
    load_private_key,
)
from shared.schemas import CRYPTO_ASSETS, CryptoAsset, get_asset_config

logger = logging.getLogger("CFBenchmarksSync")

DEFAULT_CF_INDICES: list[str] = [
    "BRTI",
    "ETHUSD_RTI",
    "SOLUSD_RTI",
    "DOGEUSD_RTI",
    "HYPEUSD_RTI",
]

INDEX_TO_ASSET: dict[str, CryptoAsset] = {
    "BRTI": CryptoAsset.BTC,
    "ETHUSD_RTI": CryptoAsset.ETH,
    "SOLUSD_RTI": CryptoAsset.SOL,
    "DOGEUSD_RTI": CryptoAsset.DOGE,
    "XAUUSD": CryptoAsset.GOLD,
    "GOLD": CryptoAsset.GOLD,
    "HYPEUSD_RTI": CryptoAsset.HYPER,
    "HYPE": CryptoAsset.HYPER,
    "HYPER": CryptoAsset.HYPER,
}

COINBASE_FALLBACK_PAIRS: dict[CryptoAsset, str] = {
    CryptoAsset.BTC: "BTC-USD",
    CryptoAsset.ETH: "ETH-USD",
    CryptoAsset.SOL: "SOL-USD",
    CryptoAsset.DOGE: "DOGE-USD",
    CryptoAsset.GOLD: "PAXG-USD",
    CryptoAsset.HYPER: "HYPE-USD",
}


class CFBenchmarksSync:
    """Ingests official CME CF Real-Time Indices directly from Kalshi for multiple assets."""

    def __init__(
        self,
        api_key_id: str,
        private_key_path: str | Path | Any,
        ws_url: str = PROD_WS_URL,
        rest_base: str = PROD_REST_BASE,
        index_ids: Optional[List[str]] = None,
        on_price_update: Optional[Callable[[Decimal, Optional[Decimal], str], None]] = None,
        on_asset_price_update: Optional[Callable[[CryptoAsset, Decimal, Optional[Decimal], str], None]] = None,
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
        self.index_ids = list(index_ids) if index_ids else list(DEFAULT_CF_INDICES)
        self.on_price_update = on_price_update
        self.on_asset_price_update = on_asset_price_update

        # Multi-Asset Price State
        self.current_prices: Dict[CryptoAsset, Decimal] = {a: Decimal("0.00") for a in CryptoAsset}
        self.twap_60s_map: Dict[CryptoAsset, Optional[Decimal]] = {a: None for a in CryptoAsset}
        self.source_map: Dict[CryptoAsset, str] = {a: "Uninitialized" for a in CryptoAsset}
        self.last_update_ts_map: Dict[CryptoAsset, float] = {a: 0.0 for a in CryptoAsset}
        self.last_source_ts_ms_map: Dict[CryptoAsset, int] = {a: 0 for a in CryptoAsset}
        self.latency_ms_map: Dict[CryptoAsset, float] = {a: 0.0 for a in CryptoAsset}

        self.is_connected: bool = False
        self.brti_connected: bool = False

        self._running: bool = False
        self._tasks: List[asyncio.Task] = []
        self._session: Optional[aiohttp.ClientSession] = None

    # -----------------------------------------------------------------------
    # Backwards-compatible properties (defaulting to BTC)
    # -----------------------------------------------------------------------

    @property
    def current_price(self) -> Decimal:
        """Current Bitcoin spot price."""
        return self.current_prices[CryptoAsset.BTC]

    @current_price.setter
    def current_price(self, val: Decimal) -> None:
        self.current_prices[CryptoAsset.BTC] = val

    @property
    def twap_60s(self) -> Optional[Decimal]:
        """Current Bitcoin 60-second settlement TWAP."""
        return self.twap_60s_map[CryptoAsset.BTC]

    @twap_60s.setter
    def twap_60s(self, val: Optional[Decimal]) -> None:
        self.twap_60s_map[CryptoAsset.BTC] = val

    @property
    def source(self) -> str:
        """Current Bitcoin source label."""
        return self.source_map[CryptoAsset.BTC]

    @source.setter
    def source(self, val: str) -> None:
        self.source_map[CryptoAsset.BTC] = val

    @property
    def last_update_ts(self) -> float:
        return self.last_update_ts_map[CryptoAsset.BTC]

    @property
    def last_source_ts_ms(self) -> int:
        return self.last_source_ts_ms_map[CryptoAsset.BTC]

    @property
    def latency_ms(self) -> float:
        return self.latency_ms_map[CryptoAsset.BTC]

    # -----------------------------------------------------------------------
    # Multi-Asset Accessors
    # -----------------------------------------------------------------------

    def get_price(self, asset: CryptoAsset | str) -> Decimal:
        """Get current spot price for specified asset."""
        if isinstance(asset, str):
            asset = CryptoAsset(asset.upper())
        return self.current_prices.get(asset, Decimal("0.00"))

    def get_twap(self, asset: CryptoAsset | str) -> Optional[Decimal]:
        """Get 60s settlement TWAP for specified asset."""
        if isinstance(asset, str):
            asset = CryptoAsset(asset.upper())
        return self.twap_60s_map.get(asset)

    def get_source(self, asset: CryptoAsset | str) -> str:
        """Get source label for specified asset."""
        if isinstance(asset, str):
            asset = CryptoAsset(asset.upper())
        return self.source_map.get(asset, "Unknown")

    def get_all_prices(self) -> Dict[str, Decimal]:
        """Return dictionary of all current crypto spot prices."""
        return {a.value: p for a, p in self.current_prices.items() if p > Decimal("0.00")}

    def get_all_state(self) -> Dict[str, Any]:
        """Return comprehensive state across all assets."""
        res: Dict[str, Any] = {}
        for a in CryptoAsset:
            cfg = get_asset_config(a)
            price = self.current_prices[a]
            twap = self.twap_60s_map[a]
            res[a.value] = {
                "asset": a.value,
                "name": cfg.name,
                "price": float(price) if price > Decimal("0.00") else None,
                "price_str": cfg.format_price(price) if price > Decimal("0.00") else None,
                "twap_60s": float(twap) if twap else None,
                "twap_60s_str": cfg.format_price(twap) if twap else None,
                "source": self.source_map[a],
                "last_update_ts": self.last_update_ts_map[a],
                "latency_ms": self.latency_ms_map[a],
            }
        return res

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start real-time multi-asset ingestion loops."""
        if self._running:
            return
        self._running = True
        self._session = aiohttp.ClientSession(connector=create_aiohttp_connector())

        # Spawn primary Kalshi WebSocket ingestion task
        self._tasks.append(asyncio.create_task(self._ws_loop(), name="cf_multi_ws_feed"))
        # Spawn watchdog / REST fallback loop
        self._tasks.append(asyncio.create_task(self._watchdog_and_rest_loop(), name="cf_multi_rest_watchdog"))
        logger.info("🚀 [CF BENCHMARKS] Multi-asset synchronization worker started for indices: %s", self.index_ids)

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
        logger.info("🛑 [CF BENCHMARKS] Multi-asset ingestion stopped.")

    def _update_price(
        self,
        price_dec: Decimal,
        twap_dec: Optional[Decimal] = None,
        source_label: str = "CF Benchmarks BRTI",
        source_ts_ms: int = 0,
    ) -> None:
        """Legacy helper: update Bitcoin price directly."""
        self._update_asset_price(
            asset=CryptoAsset.BTC,
            price_dec=price_dec,
            twap_dec=twap_dec,
            source_label=source_label,
            source_ts_ms=source_ts_ms,
        )

    def _update_asset_price(
        self,
        asset: CryptoAsset,
        price_dec: Decimal,
        twap_dec: Optional[Decimal] = None,
        source_label: str = "CF Benchmarks",
        source_ts_ms: int = 0,
    ) -> None:

        """Update internal state for a specific asset and trigger listeners."""
        if price_dec <= Decimal("0.00"):
            return
        self.current_prices[asset] = price_dec
        if twap_dec is not None and twap_dec > Decimal("0.00"):
            self.twap_60s_map[asset] = twap_dec
        self.source_map[asset] = source_label
        self.last_update_ts_map[asset] = time.time()
        self.is_connected = True

        if asset == CryptoAsset.BTC:
            self.brti_connected = True
        if source_ts_ms > 0:
            self.last_source_ts_ms_map[asset] = source_ts_ms
            self.latency_ms_map[asset] = max(0.0, (time.time() * 1000.0) - source_ts_ms)

        # Trigger asset-specific listener
        if self.on_asset_price_update:
            try:
                self.on_asset_price_update(asset, price_dec, self.twap_60s_map[asset], source_label)
            except Exception as e:
                logger.debug("Error in on_asset_price_update callback: %s", e)

        # Trigger legacy BTC listener if asset is BTC
        if asset == CryptoAsset.BTC and self.on_price_update:
            try:
                self.on_price_update(price_dec, self.twap_60s_map[CryptoAsset.BTC], source_label)
            except Exception as e:
                logger.debug("Error in on_price_update callback: %s", e)

    # -----------------------------------------------------------------------
    # WebSocket Loop
    # -----------------------------------------------------------------------

    async def _ws_loop(self) -> None:
        """Maintain persistent authenticated WebSocket connection to Kalshi for all CF indices."""
        backoff = 1.0
        while self._running:
            if not self.api_key_id or not self.private_key:
                logger.warning("CF Benchmarks: Missing Kalshi credentials, WebSocket feed paused.")
                await asyncio.sleep(5.0)
                continue

            try:
                headers = get_ws_auth_headers(self.api_key_id, self.private_key)
                logger.info("🔌 [CF WS] Connecting to Kalshi WebSocket for indices %s...", self.index_ids)
                async with self._session.ws_connect(self.ws_url, headers=headers, timeout=10.0) as ws:
                    logger.info("✅ [CF WS] Connected. Subscribing to cfbenchmarks_value_5hz & cfbenchmarks_value...")
                    
                    sub_cmd = {
                        "id": 1,
                        "cmd": "subscribe",
                        "params": {
                            "channels": ["cfbenchmarks_value_5hz", "cfbenchmarks_value"],
                            "index_ids": self.index_ids,
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
                                    asset = INDEX_TO_ASSET.get(idx_id)
                                    if asset:
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
                                            self._update_asset_price(
                                                asset=asset,
                                                price_dec=price,
                                                source_label=f"CF Benchmarks {idx_id} (5Hz WS)",
                                                source_ts_ms=ts_ms,
                                            )

                                elif m_type == "cfbenchmarks_value":
                                    idx_id = m_body.get("index_id")
                                    asset = INDEX_TO_ASSET.get(idx_id)
                                    if asset:
                                        # Extract 60s TWAP
                                        avg_data = m_body.get("avg_60s_data")
                                        twap_val = None
                                        if avg_data and "value" in avg_data:
                                            try:
                                                twap_val = Decimal(str(avg_data["value"]))
                                            except (InvalidOperation, TypeError):
                                                pass

                                        # Extract 1Hz spot price
                                        val_raw = None
                                        if "data" in m_body:
                                            try:
                                                nested = json.loads(m_body["data"])
                                                val_raw = nested.get("value")
                                            except Exception:
                                                pass
                                        if not val_raw:
                                            val_raw = m_body.get("value_usd")

                                        if val_raw:
                                            price = Decimal(str(val_raw))
                                            self._update_asset_price(
                                                asset=asset,
                                                price_dec=price,
                                                twap_dec=twap_val,
                                                source_label=f"CF Benchmarks {idx_id} (1Hz WS)",
                                            )

                                elif m_type == "error":
                                    logger.warning("CF Benchmarks WS error response: %s", payload)

                            except Exception as parse_err:
                                logger.debug("Error parsing CF Benchmarks WS payload: %s", parse_err)

                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            logger.warning("CF Benchmarks WS stream closed or errored.")
                            break

            except asyncio.CancelledError:
                break
            except Exception as conn_err:
                logger.warning("CF Benchmarks WS connection failed: %s. Reconnecting in %0.1fs...", conn_err, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.5, 30.0)

    # -----------------------------------------------------------------------
    # Watchdog & Fallback Loop
    # -----------------------------------------------------------------------

    async def _watchdog_and_rest_loop(self) -> None:
        """Fallback watchdog: polls Kalshi REST if any asset WS feed goes stale."""
        while self._running:
            await asyncio.sleep(1.0)
            now = time.time()
            stale_threshold = 3.0

            for asset, idx_id in [
                (CryptoAsset.BTC, "BRTI"),
                (CryptoAsset.ETH, "ETHUSD_RTI"),
                (CryptoAsset.SOL, "SOLUSD_RTI"),
                (CryptoAsset.DOGE, "DOGEUSD_RTI"),
            ]:
                if now - self.last_update_ts_map[asset] > stale_threshold:
                    polled = await self._poll_kalshi_rest(idx_id, asset)
                    if not polled:
                        await self._poll_coinbase_fallback(asset)

    async def _poll_kalshi_rest(self, index_id: str, asset: CryptoAsset) -> bool:
        """Query 'GET /trade-api/v2/cfbenchmarks/values?id={index_id}'."""
        if not self.api_key_id or not self.private_key or not self._session:
            return False
        endpoint = "/trade-api/v2/cfbenchmarks/values"
        try:
            headers = get_auth_headers(self.api_key_id, self.private_key, "GET", endpoint)
            url = f"{self.rest_base}{endpoint}?id={index_id}"
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
                            self._update_asset_price(
                                asset=asset,
                                price_dec=Decimal(str(price_str)),
                                source_label=f"CF Benchmarks {index_id} (REST)",
                                source_ts_ms=ts_ms,
                            )
                            return True
        except Exception as e:
            logger.debug("Failed Kalshi REST poll for %s: %s", index_id, e)
        return False

    async def _poll_coinbase_fallback(self, asset: CryptoAsset) -> None:
        """Query Coinbase Pro spot as tertiary fallback for specified asset."""
        if not self._session:
            return
        pair = COINBASE_FALLBACK_PAIRS.get(asset)
        if not pair:
            return
        try:
            async with self._session.get(
                f"https://api.coinbase.com/v2/prices/{pair}/spot",
                timeout=aiohttp.ClientTimeout(total=2.0),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    amt = data.get("data", {}).get("amount")
                    if amt:
                        self._update_asset_price(
                            asset=asset,
                            price_dec=Decimal(str(amt)),
                            source_label=f"Coinbase {pair} Fallback",
                        )
        except Exception as e:
            logger.debug("Failed Coinbase fallback poll for %s: %s", pair, e)


# Backwards compatibility alias
CFBenchmarksBRTISync = CFBenchmarksSync

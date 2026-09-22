"""Standalone Bot Spot Feeds & Market Discovery Module."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
import ctypes
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
import logging
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Union
from zoneinfo import ZoneInfo

import aiohttp
from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.auth import (
    DEMO_REST_BASE,
    DEMO_WS_URL,
    PROD_REST_BASE,
    PROD_WS_URL,
    create_aiohttp_connector,
    load_private_key,
)
from kalshi_sim.bot_deployment_auditor import BotDeploymentAuditor
from kalshi_sim.cfbenchmarks_sync import CFBenchmarksSync
from kalshi_sim.clock_sync import clock_sync
from kalshi_sim.db import get_db, get_db_writer, DatabaseWriter
from kalshi_sim.incubator_manager import get_incubator_manager
from kalshi_sim.live_coordinator import LiveCoordinator
from kalshi_sim.ml.domination_bot import DominationDecision, ThreeStepDominationBot
from kalshi_sim.ml.macro_trend_dominion_bot import MacroTrendDominionBot
from kalshi_sim.ml.onnx_engine import KalshiONNXEngine
from kalshi_sim.order_client import KalshiDemoOrderClient, KalshiLiveOrderClient
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.poe_flight_recorder import POEFlightRecorder, POEDecisionRecord
from kalshi_sim.rate_limiter import kalshi_rate_limiter
from kalshi_sim.schemas import (
    CRYPTO_ASSETS,
    CryptoAsset,
    get_asset_config,
    L2BookState,
    MarketInfo,
    MarketStatus,
    OrderSide,
    OrderType,
    Timeframe,
    TradeEvent,
)
from kalshi_sim.standalone_bot_modules.config import DEFAULT_ASSET_PROFILES, ET_ZONE
from kalshi_sim.standalone_bot_modules.power import format_cycle_time_from_iso

logger = logging.getLogger("StandaloneBot")


class _BaseCoordinator:
    """Base proxy coordinator forwarding attribute lookup and mutation to the parent engine."""
    def __init__(self, engine: Any) -> None:
        object.__setattr__(self, "engine", engine)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "engine"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "engine":
            object.__setattr__(self, "engine", value)
        else:
            setattr(object.__getattribute__(self, "engine"), name, value)


class StandaloneFeedsCoordinator(_BaseCoordinator):
    """Handles spot price streaming, market discovery, L2 book polling, and keep-alive loops."""

    async def _windows_keep_alive_loop(self) -> None:
        """Periodically refresh Win32 execution state every 60s to prevent laptop sleep on lid close or monitor flip."""
        while self._running:
            try:
                await asyncio.sleep(60.0)
                prevent_windows_sleep()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("Windows keep-alive loop error: %s", exc)


    async def _spot_feed_loop(self) -> None:
        """Stream real-time crypto spot price prioritizing official CF Benchmarks 5Hz feed."""
        def _on_cf_asset_update(asset: CryptoAsset, price: Decimal, twap: Optional[Decimal], source: str) -> None:
            a_key = asset.value if hasattr(asset, "value") else str(asset)
            if a_key not in self.asset_markets:
                self.asset_markets[a_key] = {}
            self.asset_markets[a_key]["spot_price"] = price
            self.asset_markets[a_key]["twap"] = twap
            self.asset_markets[a_key]["spot_source"] = source

            # Record rolling history for sub-second velocity & front-running
            self._spot_history[a_key].append((time.time(), float(price)))

            if asset == self.active_asset:
                self.current_btc_spot = price
                if twap is not None:
                    self.twap_60s_price = twap
                self.spot_source = source
                self.spot_connected = True
                self.brti_connected = True
                asyncio.create_task(self.evaluate_and_execute())
            elif self.asset_mode == "all":
                asyncio.create_task(self.evaluate_and_execute())

        if self.api_key_id and self.private_key_path:
            try:
                self.cf_sync = CFBenchmarksSync(
                    api_key_id=self.api_key_id,
                    private_key_path=self.private_key_path,
                    ws_url=self.ws_url,
                    rest_base=self.rest_base,
                    on_asset_price_update=_on_cf_asset_update,
                )
                self.brti_sync = self.cf_sync
                await self.cf_sync.start()
                logger.info("📡 [CF BENCHMARKS] Official Multi-Asset 5Hz client active on Standalone Bot.")
            except Exception as e:
                logger.warning("Could not start CF Benchmarks sync: %s. Falling back to public feeds.", e)

        product_map = {
            "BTC-USD": CryptoAsset.BTC,
            "ETH-USD": CryptoAsset.ETH,
            "SOL-USD": CryptoAsset.SOL,
            "DOGE-USD": CryptoAsset.DOGE,
            "PAXG-USD": CryptoAsset.GOLD,
        }

        connector = create_aiohttp_connector()
        async with aiohttp.ClientSession(connector=connector) as session:
            async def _coinbase_worker() -> None:
                while self._running:
                    try:
                        async with session.ws_connect("wss://ws-feed.exchange.coinbase.com", timeout=5.0) as ws:
                            await ws.send_json({
                                "type": "subscribe",
                                "product_ids": ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "PAXG-USD"],
                                "channels": ["ticker"],
                            })
                            logger.info("📈 [SPOT WS] Connected to Coinbase Pro multi-asset standby feed.")
                            self.coinbase_connected = True
                            if not (self.cf_sync and self.cf_sync.is_connected):
                                self.spot_connected = True
                            async for msg in ws:
                                if not self._running:
                                    break
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    data = json.loads(msg.data)
                                    if data.get("type") == "ticker" and "price" in data:
                                        pid = data.get("product_id")
                                        matched_asset = product_map.get(pid)
                                        if matched_asset:
                                            p_dec = Decimal(str(data["price"]))
                                            m_key = matched_asset.value if hasattr(matched_asset, "value") else str(matched_asset)
                                            if m_key not in self.asset_markets:
                                                self.asset_markets[m_key] = {}
                                            self.asset_markets[m_key]["spot_price"] = p_dec
                                            self.asset_markets[m_key]["spot_source"] = f"Coinbase Pro {pid} (Fallback)"
                                            if matched_asset == self.active_asset and not (self.cf_sync and self.cf_sync.is_connected):
                                                self.current_btc_spot = p_dec
                                                self.spot_source = f"Coinbase Pro {pid} (Fallback)"
                                                self.brti_connected = False
                                                await self.evaluate_and_execute()
                                            elif self.asset_mode == "all" and not (self.cf_sync and self.cf_sync.is_connected):
                                                await self.evaluate_and_execute()
                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                    break
                    except asyncio.CancelledError:
                        break
                    except Exception as exc:
                        logger.debug("[SPOT WS] Coinbase retry in 2s: %s", exc)
                    finally:
                        self.coinbase_connected = False
                    await asyncio.sleep(2.0)

            async def _binance_worker() -> None:
                streams = "btcusdt@ticker/ethusdt@ticker/solusdt@ticker/dogeusdt@ticker/paxgusdt@ticker"
                bn_sym_map = {
                    "BTCUSDT": CryptoAsset.BTC,
                    "ETHUSDT": CryptoAsset.ETH,
                    "SOLUSDT": CryptoAsset.SOL,
                    "DOGEUSDT": CryptoAsset.DOGE,
                    "PAXGUSDT": CryptoAsset.GOLD,
                }
                while self._running:
                    try:
                        async with session.ws_connect(f"wss://stream.binance.com:9443/stream?streams={streams}", timeout=5.0) as ws:
                            logger.info("📈 [SPOT WS] Connected to Binance multi-asset fallback feed.")
                            self.binance_connected = True
                            async for msg in ws:
                                if not self._running:
                                    break
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    raw = json.loads(msg.data)
                                    s_data = raw.get("data", raw)
                                    if "c" in s_data and "s" in s_data:
                                        symbol = s_data.get("s", "").upper()
                                        if symbol in bn_sym_map:
                                            b_asset = bn_sym_map[symbol]
                                            b_key = b_asset.value
                                            b_price = Decimal(str(s_data["c"]))
                                            if b_key not in self.asset_markets:
                                                self.asset_markets[b_key] = {}
                                            self.asset_markets[b_key]["spot_price"] = b_price
                                            self.asset_markets[b_key]["spot_source"] = f"Binance {symbol} (Fallback)"
                                            if b_asset == self.active_asset and not (self.cf_sync and self.cf_sync.is_connected) and not self.coinbase_connected:
                                                self.current_btc_spot = b_price
                                                self.spot_source = f"Binance {symbol} (Fallback)"
                                                self.brti_connected = False
                                                await self.evaluate_and_execute()
                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                    break
                    except asyncio.CancelledError:
                        break
                    except Exception as exc:
                        logger.debug("[SPOT WS] Binance retry in 2s: %s", exc)
                    finally:
                        self.binance_connected = False
                    await asyncio.sleep(2.0)

            async def _rest_fallback_worker() -> None:
                while self._running:
                    try:
                        if not (self.cf_sync and self.cf_sync.is_connected) and not self.coinbase_connected:
                            pair = self.active_cfg.coinbase_pair
                            async with session.get(f"https://api.coinbase.com/v2/prices/{pair}/spot", timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
                                if resp.status == 200:
                                    r_data = await resp.json()
                                    amt = r_data.get("data", {}).get("amount")
                                    if amt:
                                        p_dec = Decimal(str(amt))
                                        self.current_btc_spot = p_dec
                                        self.spot_source = f"Coinbase REST {pair} (Fallback)"
                                        self.spot_connected = True
                                        self.brti_connected = False
                                        await self.evaluate_and_execute()
                    except asyncio.CancelledError:
                        break
                    except Exception as exc:
                        logger.debug("[SPOT REST] Fallback error: %s", exc)
                    await asyncio.sleep(1.0)

            cb_t = asyncio.create_task(_coinbase_worker())
            bn_t = asyncio.create_task(_binance_worker())
            rst_t = asyncio.create_task(_rest_fallback_worker())
            try:
                await asyncio.gather(cb_t, bn_t, rst_t)
            except asyncio.CancelledError:
                cb_t.cancel()
                bn_t.cancel()
                rst_t.cancel()

    async def _market_discovery_and_book_loop(self) -> None:
        """Discover active 15M crypto contracts and sync L2 orderbook every 500ms."""
        connector = create_aiohttp_connector()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
        last_discovery: Dict[CryptoAsset, float] = {}
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            while self._running:
                try:
                    assets_to_poll = list(CryptoAsset)
                    now_utc = datetime.now(timezone.utc)
                    now_mono = time.monotonic()

                    for ast in assets_to_poll:
                        cfg = get_asset_config(ast)
                        ast_key = ast.value
                        cached_m = self.asset_markets.get(ast_key, {})
                        cur_ticker = cached_m.get("ticker")
                        cur_close = cached_m.get("close_dt")

                        needs_disc = (
                            not cur_ticker
                            or not cur_close
                            or cur_close <= now_utc
                            or (now_mono - last_discovery.get(ast, 0.0) >= 6.0)
                        )

                        if needs_disc:
                            url = f"{self.rest_base}/markets?series_ticker={cfg.series_ticker_15m}&status=open&limit=15"
                            try:
                                async with session.get(url, timeout=aiohttp.ClientTimeout(total=3.0)) as resp:
                                    if resp.status == 200:
                                        data = await resp.json()
                                        markets = data.get("markets", [])
                                        if markets:
                                            open_m = []
                                            for m in markets:
                                                c_str = m.get("close_time")
                                                if c_str:
                                                    c_dt = datetime.fromisoformat(c_str.replace("Z", "+00:00"))
                                                    if c_dt > now_utc:
                                                        open_m.append((c_dt, m))
                                            if open_m:
                                                open_m.sort(key=lambda x: x[0])
                                                active_close, active_m = open_m[0]
                                                new_ticker = active_m.get("ticker", "")
                                                old_ticker = cached_m.get("ticker")
                                                if old_ticker and new_ticker != old_ticker:
                                                    logger.info("🔄 [CYCLE ROLLOVER - %s] %s -> %s. Sweeping resting orders...", ast_key, old_ticker, new_ticker)
                                                    self._flush_cycle_veto(old_ticker)
                                                    asyncio.create_task(self.sweep_old_orders(keep_ticker=new_ticker))

                                                floor = active_m.get("floor_strike")
                                                floor_dec = Decimal(str(floor)) if floor is not None else Decimal("0.00")
                                                et_zone = ZoneInfo("America/New_York")
                                                close_et = active_close.astimezone(et_zone)
                                                start_et = close_et - timedelta(minutes=15)
                                                t_str = close_et.strftime("%I:%M%p").lower() + " ET"
                                                w_str = f"{start_et.strftime('%B %d, %I:%M')} - {close_et.strftime('%I:%M %p')} ET"

                                                yb = active_m.get("yes_bid_dollars")
                                                ya = active_m.get("yes_ask_dollars")
                                                nb = active_m.get("no_bid_dollars")
                                                na = active_m.get("no_ask_dollars")
                                                lp = active_m.get("last_price_dollars")

                                                if ast_key not in self.asset_markets:
                                                    self.asset_markets[ast_key] = {}
                                                self.asset_markets[ast_key].update({
                                                    "asset": ast_key,
                                                    "ticker": new_ticker,
                                                    "close_dt": active_close,
                                                    "target_strike": floor_dec,
                                                    "target_time_str": t_str,
                                                    "time_window_str": w_str,
                                                })
                                                if yb is not None:
                                                    self.asset_markets[ast_key]["best_yes_bid"] = Decimal(str(yb))
                                                if ya is not None:
                                                    self.asset_markets[ast_key]["best_yes_ask"] = Decimal(str(ya))
                                                if nb is not None:
                                                    self.asset_markets[ast_key]["best_no_bid"] = Decimal(str(nb))
                                                if na is not None:
                                                    self.asset_markets[ast_key]["best_no_ask"] = Decimal(str(na))
                                                if lp is not None:
                                                    self.asset_markets[ast_key]["last_price"] = Decimal(str(lp))
                                                if not self.asset_markets[ast_key].get("spot_price"):
                                                    if lp is not None and float(lp) > 0:
                                                        self.asset_markets[ast_key]["spot_price"] = Decimal(str(lp))
                                                    elif floor_dec > Decimal("0.00"):
                                                        self.asset_markets[ast_key]["spot_price"] = floor_dec

                                                last_discovery[ast] = now_mono

                                                if ast == self.active_asset:
                                                    self.active_ticker = new_ticker
                                                    self.active_market_close_dt = active_close
                                                    self.target_strike = floor_dec
                                                    self.target_time_str = t_str
                                                    self.time_window_str = w_str
                            except Exception as dexc:
                                logger.debug("[DISCOVERY] %s query error: %s", ast_key, dexc)

                        # Ingest orderbook for discovered active contract
                        polled_ticker = self.asset_markets.get(ast_key, {}).get("ticker")
                        if not polled_ticker and ast == self.active_asset:
                            polled_ticker = self.active_ticker
                        if polled_ticker:
                            ob_url = f"{self.rest_base}/markets/{polled_ticker}/orderbook"
                            try:
                                async with session.get(ob_url, timeout=aiohttp.ClientTimeout(total=2.0)) as ob_resp:
                                    if ob_resp.status == 200:
                                        ob_data = await ob_resp.json()
                                        raw_book = ob_data.get("orderbook_fp") or ob_data.get("orderbook") or {}
                                        bids = raw_book.get("yes_dollars") or raw_book.get("yes") or []
                                        asks = raw_book.get("no_dollars") or raw_book.get("no") or []

                                        book = self.orderbook.get_book(polled_ticker)
                                        if not book:
                                            book = L2BookState(polled_ticker)
                                            self.orderbook.set_book(polled_ticker, book)

                                        new_yes: Dict[Decimal, Decimal] = {}
                                        for item in bids:
                                            p, q = item[0], item[1]
                                            p_dec = Decimal(str(p))
                                            if p_dec > 1:
                                                p_dec = p_dec / Decimal("100")
                                            new_yes[p_dec] = Decimal(str(q))

                                        new_no: Dict[Decimal, Decimal] = {}
                                        for item in asks:
                                            p, q = item[0], item[1]
                                            p_dec = Decimal(str(p))
                                            if p_dec > 1:
                                                p_dec = p_dec / Decimal("100")
                                            new_no[p_dec] = Decimal(str(q))

                                        book.yes_book = new_yes
                                        book.no_book = new_no

                                        if ast_key not in self.asset_markets:
                                            self.asset_markets[ast_key] = {}
                                        self.asset_markets[ast_key]["best_yes_bid"] = book.best_yes_bid
                                        self.asset_markets[ast_key]["best_yes_ask"] = book.best_yes_ask
                                        self.asset_markets[ast_key]["best_no_bid"] = book.best_no_bid
                                        self.asset_markets[ast_key]["best_no_ask"] = book.best_no_ask

                                        if ast == self.active_asset:
                                            self.best_yes_bid = book.best_yes_bid
                                            self.best_yes_ask = book.best_yes_ask
                                            self.best_no_bid = book.best_no_bid
                                            self.best_no_ask = book.best_no_ask
                            except Exception as oexc:
                                logger.debug("[ORDERBOOK] %s query error: %s", polled_ticker, oexc)

                    self.kalshi_ws_connected = True
                    await self.evaluate_and_execute()

                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.debug("[MARKET SYNC] Loop tick error: %s", exc)
                    self.kalshi_ws_connected = False

                await asyncio.sleep(0.5)



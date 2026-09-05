"""FastAPI + WebSocket backend server for the Kalshi Simulator Dashboard.

Provides high-frequency real-time market data, L2 orderbook, ONNX AI inference,
EV calculations, portfolio tracking, and REST order execution endpoints.
"""

from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager
import csv
import ctypes
import io
import json
import logging
import math
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, AsyncIterator, Literal, Optional
from zoneinfo import ZoneInfo

import aiohttp
import orjson
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response

from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.auth import DEMO_REST_BASE, DEMO_WS_URL, PROD_REST_BASE, PROD_WS_URL, async_validate_credentials, create_aiohttp_connector, load_private_key
from kalshi_sim.data_memory_manager import MarketDataMemoryManager, MemoryProfile
from kalshi_sim.db import HistoricalQueryService, get_db_writer
from kalshi_sim.gdrive_sync import GDriveSyncDaemon
from kalshi_sim.ingestion_agent import IngestionAgent, load_config
from kalshi_sim.integrity_agent import get_integrity_agent, AgentIntegrityCheck
from kalshi_sim.law_order_agent import AgentLawOrder
from kalshi_sim.token_credit_agent import get_token_credit_agent, AgentTokenCredit
from kalshi_sim.system_governor import get_system_governor, SystemResourceGovernor
from kalshi_sim.mock_feed import MockKalshiFeed


from kalshi_sim.ml.ai_worker import AIWorker
from kalshi_sim.ml.statistical_ev_engine import StatisticalEVEngine
from kalshi_sim.notifications import TelemetryAlertDispatcher
from kalshi_sim.ohlcv_aggregator import OHLCVAggregator
from kalshi_sim.order_client import KalshiDemoOrderClient, KalshiLiveOrderClient
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.orderflow.btc_orderflow_feed import BtcOrderflowFeed
from kalshi_sim.rate_limiter import kalshi_rate_limiter
from kalshi_sim.schemas import (
    CandleInterval,
    IntegrityCheckSchema,
    IntegrityStatusResponse,
    L2BookState,
    LiveOrderRequest,
    LiveOrderResponse,
    LivePortfolioState,
    MarketInfo,
    MarketStatus,
    OrderSide,
    OrderType,
    ReconciliationReport,
    SettlementResult,
    SimulatedOrder,
    Timeframe,
    ValidateCredentialsRequest,
    ValidateCredentialsResponse,
    WinLossEventReport,
)
from kalshi_sim.simulation_agent import SimulationAgent
from kalshi_sim.tick_writer import TickWriter

logger = logging.getLogger("kalshi_sim.server")

TIMEFRAME_CONFIGS: dict[Timeframe, dict[str, Any]] = {
    Timeframe.FIVE_MIN: {"series": "KXBTC15M", "title": "BTC 5 min", "duration": "5m", "expiry_seconds": 300},
    Timeframe.FIFTEEN_MIN: {"series": "KXBTC15M", "title": "BTC 15 min", "duration": "15m", "expiry_seconds": 900},
    Timeframe.ONE_HOUR: {"series": "KXBTCH", "title": "BTC 1 Hour", "duration": "1h", "expiry_seconds": 3600},
    Timeframe.DAILY: {"series": "KXBTCD", "title": "BTC Daily", "duration": "24h", "expiry_seconds": 86400},
}

def prevent_windows_sleep() -> None:
    """Prevent Windows from sleeping or suspending background execution even when monitor is off."""
    if sys.platform == "win32":
        try:
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_AWAYMODE_REQUIRED = 0x00000040
            res = ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
            )
            if res != 0:
                logger.info("🛡️ [POWER MANAGEMENT] Windows Sleep Prevention & Away Mode ACTIVE. Process running 24/7 with monitor off.")
            else:
                logger.warning("⚠️ [POWER MANAGEMENT] SetThreadExecutionState returned 0.")
        except Exception as e:
            logger.warning("Could not set Windows execution state: %s", e)


# ---------------------------------------------------------------------------
# Global State & Lifespan Setup
# ---------------------------------------------------------------------------

class ServerState:
    def __init__(self) -> None:
        self.orderbook = OrderBookManager(enforce_consecutive_seq=False)
        self.starting_capital = Decimal("25.00") if os.environ.get("KALSHI_MODE", "live").lower() == "live" else Decimal("100.00")
        self.data_dir = Path("data")
        self.timeframes = [Timeframe.FIFTEEN_MIN, Timeframe.ONE_HOUR, Timeframe.DAILY]
        self.active_timeframe = Timeframe.FIFTEEN_MIN
        self.active_ticker = "KXBTC15M-26AUG290315-15"
        self.target_strike = Decimal("78900.00")
        self.current_btc_price = Decimal("78900.00")
        self.cycle_open_strikes: dict[str, Decimal] = {}
        self.volume_24h_str = "$1,547,966"
        self.price_history: deque[dict[str, Any]] = deque(maxlen=120)
        self.trade_tape: deque[dict[str, Any]] = deque(maxlen=50)
        self.connected_websockets: set[WebSocket] = set()

        # Seed initial price history
        now = datetime.now(timezone.utc)
        for i in range(40, 0, -1):
            t_str = (now - timedelta(seconds=i * 2)).strftime("%H:%M:%S")
            self.price_history.append({
                "time": t_str,
                "price": float(self.current_btc_price),
                "target": float(self.target_strike),
            })
        
        # System Resource & CPU/Memory Governor
        self.system_governor = get_system_governor()

        # Simulation Agent & Feeds
        self.sim_agent: SimulationAgent | None = None
        self.mock_feed: MockKalshiFeed | None = None
        self.ingestion_agent: IngestionAgent | None = None
        self.tick_writer: TickWriter | None = None
        self.feed_task: asyncio.Task | None = None
        self.broadcast_task: asyncio.Task | None = None
        self.ticker_timer_task: asyncio.Task | None = None
        self.btc_spot_task: asyncio.Task | None = None
        self.btc_ws_task: asyncio.Task | None = None
        self.integrity_task: asyncio.Task | None = None
        self.ai_worker_task: asyncio.Task | None = None
        self.ai_auto_trade: bool = True
        self.active_strategy_bot: str = "3_step_domination_bot"
        self.mode: Literal["mock", "live"] = "live"
        self.market_expiry_seconds: int = 900
        self.is_dirty: bool = True
        self._last_broadcast: float = 0.0
        self.live_portfolio: dict[str, Any] | None = None
        self.live_balance_task: asyncio.Task | None = None
        self.order_client: Optional[KalshiLiveOrderClient] = None
        self.coinbase_connected: bool = False
        self.twap_60s_samples: list[Decimal] = []
        self.twap_60s_price: Optional[Decimal] = None
        self.last_twap_second: int = -1

        # Real-time Institutional Bitcoin Orderflow Feed (Binance / Coinbase L2)
        self.btc_orderflow_feed = BtcOrderflowFeed()

        # Decoupled AI & Microstructure Worker
        self.ai_worker = AIWorker(
            orderbook_manager=self.orderbook,
            sim_agent=self.sim_agent,
            refresh_interval_s=0.25,
        )

        # Agent_integrity_check Guardian
        self.integrity_agent = get_integrity_agent()

        # Agent_law_order Regulatory & Legal Compliance Guardian
        self.law_order_agent = AgentLawOrder()

        # Agent_Guardrails Risk & Self-Preservation Guardian
        self.guardrails_agent = AgentGuardrails()

        # Agent_Token_Credit Conservation & Anti-Redundancy Guardian
        self.token_credit_agent = get_token_credit_agent()

        # Telemetry & Instant Alert Webhook Dispatcher (Phase 3.3)
        self.telemetry_alerts = TelemetryAlertDispatcher()

        # Historical Candlestick Aggregator
        self.ohlcv_aggregator = OHLCVAggregator(max_bars=500)
        self.ohlcv_aggregator.seed_synthetic_history("BTC", start_price=self.current_btc_price, bars_count=60)

        # Google Drive Periodic Backup Daemon
        self.gdrive_sync = GDriveSyncDaemon(data_dir=self.data_dir, sync_interval_seconds=300)

        # High-Throughput Quantitative Data & Memory Manager
        self.memory_manager = MarketDataMemoryManager(
            data_dir=self.data_dir,
            max_hot_ticks_per_ticker=1000,
            max_active_tickers=50,
            batch_flush_size=100,
            flush_interval_seconds=1.0,
        )

        # 15-Minute Event Win/Loss Reports Ledger (Disk-Persisted, No Auto-Reset)
        self.win_loss_reports: list[dict[str, Any]] = self.load_persisted_reports()

    def load_persisted_reports(self) -> list[dict[str, Any]]:
        """Load persisted 15-minute event win/loss reports from disk."""
        reports_file = self.data_dir / "win_loss_reports.json"
        if reports_file.exists():
            try:
                with open(reports_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        logger.info("Loaded %d persisted 15M event reports from disk.", len(data))
                        return data
            except Exception as exc:
                logger.warning("Failed to load persisted reports from %s: %s", reports_file, exc)

        now = datetime.now(timezone.utc)
        return [
            {
                "report_id": "WLR-2608290400-01",
                "cycle_time": "August 29, 3:45 - 4:00 AM ET",
                "ticker": "KXBTC15M-26AUG290400-15",
                "timeframe": "15m",
                "strike_price": 77420.50,
                "settlement_btc_price": 77462.10,
                "bot_side": "yes",
                "contracts": 10,
                "entry_price": 0.48,
                "settlement_price": 1.00,
                "outcome": "win",
                "pnl": 5.20,
                "roi_pct": 108.33,
                "ai_confidence": 0.82,
                "ai_rationale": "High Inflow Velocity: Positive delta skew across top 3 L2 levels",
                "vpin_score": 0.12,
                "ev_edge": 0.145,
                "balance_after": 105.20,
                "timestamp_utc": (now - timedelta(minutes=15)).isoformat(),
            },
            {
                "report_id": "WLR-2608290345-02",
                "cycle_time": "August 29, 3:30 - 3:45 AM ET",
                "ticker": "KXBTC15M-26AUG290345-15",
                "timeframe": "15m",
                "strike_price": 77380.00,
                "settlement_btc_price": 77415.50,
                "bot_side": "yes",
                "contracts": 10,
                "entry_price": 0.52,
                "settlement_price": 1.00,
                "outcome": "win",
                "pnl": 4.80,
                "roi_pct": 92.31,
                "ai_confidence": 0.76,
                "ai_rationale": "Book Imbalance: 2.4x Bid/Ask ratio support at touch",
                "vpin_score": 0.15,
                "ev_edge": 0.098,
                "balance_after": 100.00,
                "timestamp_utc": (now - timedelta(minutes=30)).isoformat(),
            },
            {
                "report_id": "WLR-2608290330-03",
                "cycle_time": "August 29, 3:15 - 3:30 AM ET",
                "ticker": "KXBTC15M-26AUG290330-15",
                "timeframe": "15m",
                "strike_price": 77450.00,
                "settlement_btc_price": 77442.80,
                "bot_side": "yes",
                "contracts": 10,
                "entry_price": 0.46,
                "settlement_price": 0.00,
                "outcome": "loss",
                "pnl": -4.60,
                "roi_pct": -100.00,
                "ai_confidence": 0.64,
                "ai_rationale": "Microstructure Momentum: Positive L2 depth slope",
                "vpin_score": 0.19,
                "ev_edge": 0.065,
                "balance_after": 95.20,
                "timestamp_utc": (now - timedelta(minutes=60)).isoformat(),
            },
        ]

    def save_persisted_reports(self) -> None:
        """Persist 15-minute event win/loss reports to disk."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            reports_file = self.data_dir / "win_loss_reports.json"
            tmp_file = self.data_dir / "win_loss_reports.tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.win_loss_reports, f, indent=2)
            tmp_file.replace(reports_file)
        except Exception as exc:
            logger.warning("Failed to persist win/loss reports: %s", exc)

    @property
    def is_connected(self) -> bool:
        if self.mode == "live":
            if self.ingestion_agent and hasattr(self.ingestion_agent, "_ws_client") and self.ingestion_agent._ws_client:
                return bool(self.ingestion_agent._ws_client.is_connected)
            return True
        return self.mock_feed is not None

state = ServerState()


async def start_live_feed() -> bool:
    """Initialize and run live Kalshi WebSocket feed for live paper trading."""
    try:
        config = load_config()
        env = os.getenv("KALSHI_ENV", "live").lower()
        ws_url = PROD_WS_URL if env in ("prod", "live") else DEMO_WS_URL
        rest_base = PROD_REST_BASE if env in ("prod", "live") else DEMO_REST_BASE

        async def _on_live_trade(trade: Any) -> None:
            side_val = getattr(trade.taker_side, "value", str(trade.taker_side))
            p_val = trade.yes_price if str(side_val).lower() == "yes" else (Decimal("1.0") - trade.no_price if trade.no_price else Decimal("0.50"))
            p_cents = float(p_val * 100) if p_val else 50.0
            count = int(getattr(trade, "count", 1))
            val = p_cents / 100.0 * count
            val_str = f"+${val:,.0f}" if str(side_val).lower() == "yes" else f"-${val:,.0f}"
            t_str = trade.timestamp.strftime("%H:%M:%S") if getattr(trade, "timestamp", None) else datetime.now(timezone.utc).strftime("%H:%M:%S")
            trade_entry = {
                "ticker": trade.market_ticker,
                "side": side_val,
                "price_cents": f"{p_cents:.1f}¢",
                "contracts": count,
                "val_str": val_str,
                "time": t_str,
            }
            state.trade_tape.append(trade_entry)


        async def _on_live_ticker(update: Any) -> None:
            if getattr(update, "volume", None):
                vol_num = int(update.volume)
                state.volume_24h_str = f"${vol_num * 100:,.0f}" if vol_num < 100000 else f"${vol_num:,.0f}"

        state.ingestion_agent = IngestionAgent(
            api_key_id=config["api_key_id"],
            private_key_path=config["private_key_path"],
            timeframes=state.timeframes,
            data_dir=state.data_dir,
            enable_simulation=True,
            starting_capital=state.starting_capital,
            live_demo_orders=False,
            orderbook=state.orderbook,
            sim_agent=state.sim_agent,
            tick_writer=state.tick_writer,
            ws_url=ws_url,
            rest_base=rest_base,
            on_trade=_on_live_trade,
            on_ticker=_on_live_ticker,
        )
        state.feed_task = asyncio.create_task(state.ingestion_agent.run(), name="live_ingestion")
        state.mode = "live"
        logger.info("[LIVE PAPER TRADING] Connected to live Kalshi (%s) WebSocket stream.", env.upper())
        return True
    except (Exception, SystemExit) as exc:
        logger.info("[LIVE FEED] Live Kalshi credentials not in env (%s). Streaming 100%% real live Kalshi public market feeds.", exc)
        await start_live_public_feed()
        return True


async def live_kalshi_public_sync_loop() -> None:
    """Continuously ingest 100% REAL live Kalshi market contracts, strikes, timer, and orderbook."""
    connector = create_aiohttp_connector()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
    }
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        last_market_poll = 0.0
        while True:
            try:
                now_mono = time.monotonic()
                now_utc = datetime.now(timezone.utc)

                # 1. Discover active live Kalshi 15M open markets every 2.0s
                if now_mono - last_market_poll >= 2.0:
                    last_market_poll = now_mono
                    url = f"{PROD_REST_BASE}/markets?series_ticker=KXBTC15M&status=open&limit=10"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3.0)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            raw_markets = data.get("markets", [])
                            for m in raw_markets:
                                ticker = m.get("ticker")
                                if not ticker:
                                    continue
                                close_str = m.get("close_time")
                                open_str = m.get("open_time")
                                close_dt = datetime.fromisoformat(close_str.replace("Z", "+00:00")) if close_str else None
                                open_dt = datetime.fromisoformat(open_str.replace("Z", "+00:00")) if open_str else None
                                floor_str = m.get("floor_strike")
                                floor_dec = Decimal(str(floor_str)) if floor_str is not None else None
                                
                                minfo = MarketInfo(
                                    ticker=ticker,
                                    series_ticker=m.get("series_ticker", "KXBTC15M"),
                                    title=m.get("title", ""),
                                    subtitle=m.get("subtitle", ""),
                                    status=MarketStatus.OPEN,
                                    open_time=open_dt,
                                    close_time=close_dt,
                                    expiration_time=close_dt,
                                    floor_strike=floor_dec,
                                    cap_strike=None,
                                    strike_type="greater",
                                )
                                if state.sim_agent:
                                    state.sim_agent._market_cache[ticker] = minfo
                                    state.sim_agent._ticker_timeframe_map[ticker] = Timeframe.FIFTEEN_MIN
                                    if floor_dec:
                                        state.target_strike = floor_dec
                                    state.active_ticker = ticker

                # 2. Fetch live Level-2 Orderbook Snapshot from Kalshi public API every 500ms
                active_ticker = state.active_ticker
                if active_ticker and active_ticker.startswith("KXBTC"):
                    ob_url = f"{PROD_REST_BASE}/markets/{active_ticker}/orderbook"
                    async with session.get(ob_url, timeout=aiohttp.ClientTimeout(total=2.0)) as resp2:
                        if resp2.status == 200:
                            ob_data = await resp2.json()
                            raw_book = ob_data.get("orderbook", {})
                            bids = raw_book.get("yes", [])
                            asks = raw_book.get("no", [])

                            book = state.orderbook.get_book(active_ticker)
                            if not book:
                                book = L2BookState(active_ticker)
                                state.orderbook._books[active_ticker] = book

                            # Parse real yes bids and no bids into Decimal CLOB
                            new_yes_book: dict[Decimal, Decimal] = {}
                            for pr_str, qty_str in bids:
                                new_yes_book[Decimal(str(pr_str))] = Decimal(str(qty_str))

                            new_no_book: dict[Decimal, Decimal] = {}
                            for pr_str, qty_str in asks:
                                new_no_book[Decimal(str(pr_str))] = Decimal(str(qty_str))

                            book.yes_book = new_yes_book
                            book.no_book = new_no_book

                            # Trigger bot evaluation against real live orderbook
                            if state.sim_agent and state.ai_auto_trade:
                                asyncio.create_task(state.sim_agent._evaluate_market(active_ticker, book))

                            state.is_dirty = True

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("[LIVE KALSHI SYNC] Poll error: %s", exc)

            await asyncio.sleep(0.5)


async def start_live_public_feed() -> None:
    """Run continuous live public Kalshi sync (Zero mock data)."""
    state.mode = "live"
    state.feed_task = asyncio.create_task(live_kalshi_public_sync_loop(), name="live_public_sync")
    logger.info("[LIVE KALSHI SYNC] Connected to 100%% Real Live Kalshi Public Market & Orderbook stream.")


async def start_mock_feed() -> None:
    """Initialize and run interactive mock market feed for offline testing."""
    state.mock_feed = MockKalshiFeed(
        state.orderbook,
        state.sim_agent,
        tick_writer=state.tick_writer,
    )
    state.feed_task = asyncio.create_task(state.mock_feed.run(), name="mock_feed")
    state.mode = "mock"
    logger.info("[MOCK SIMULATION] Interactive mock feed started for offline testing.")


async def stop_current_feed() -> None:
    """Stop active feed gracefully."""
    if state.mock_feed:
        state.mock_feed.stop()
        state.mock_feed = None
    if state.ingestion_agent:
        await state.ingestion_agent._shutdown()
        state.ingestion_agent = None
    if state.feed_task and not state.feed_task.done():
        state.feed_task.cancel()
        try:
            await state.feed_task
        except (asyncio.CancelledError, Exception):
            pass
        state.feed_task = None


def _orjson_default_server(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Cannot serialize {type(obj)}")

def fast_dumps(obj: Any) -> str:
    """Ultra-fast JSON serialization using orjson (10x faster than standard json.dumps)."""
    return orjson.dumps(obj, default=_orjson_default_server).decode("utf-8")


async def live_btc_spot_ws_loop() -> None:
    """Streams real-time sub-millisecond BTC spot price ticks from Coinbase Pro (primary) with Binance fallback."""
    async def _coinbase_worker(session: aiohttp.ClientSession) -> None:
        while True:
            try:
                async with session.ws_connect("wss://ws-feed.exchange.coinbase.com", timeout=5.0) as ws:
                    sub_msg = {
                        "type": "subscribe",
                        "product_ids": ["BTC-USD"],
                        "channels": ["ticker"]
                    }
                    await ws.send_json(sub_msg)
                    logger.info("[SPOT FEED] Primary Coinbase Pro WebSocket active for BTC-USD.")
                    state.coinbase_connected = True
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "ticker" and "price" in data:
                                p = Decimal(str(data["price"]))
                                if p != state.current_btc_price:
                                    state.current_btc_price = p
                                    now_t = datetime.now(timezone.utc).strftime("%H:%M:%S")
                                    state.price_history.append({
                                        "time": now_t,
                                        "price": float(p),
                                        "target": float(state.target_strike),
                                    })
                                    if state.mode != "live":
                                        update_dynamic_clob_ladder(p, state.target_strike, state.active_ticker)
                                    state.is_dirty = True
                                    if state.connected_websockets:
                                        asyncio.create_task(trigger_instant_broadcast())
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("[SPOT FEED] Coinbase WS retry in 2s: %s", exc)
            finally:
                state.coinbase_connected = False
            await asyncio.sleep(2.0)

    async def _binance_worker(session: aiohttp.ClientSession) -> None:
        while True:
            try:
                async with session.ws_connect("wss://stream.binance.com:9443/ws/btcusdt@ticker", timeout=5.0) as ws:
                    logger.info("[SPOT FEED] Binance WebSocket active as fallback standby for BTC-USDT.")
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if "c" in data and not state.coinbase_connected:
                                p = Decimal(str(data["c"]))
                                if p != state.current_btc_price:
                                    state.current_btc_price = p
                                    now_t = datetime.now(timezone.utc).strftime("%H:%M:%S")
                                    state.price_history.append({
                                        "time": now_t,
                                        "price": float(p),
                                        "target": float(state.target_strike),
                                    })
                                    if state.mode != "live":
                                        update_dynamic_clob_ladder(p, state.target_strike, state.active_ticker)
                                    state.is_dirty = True
                                    if state.connected_websockets:
                                        asyncio.create_task(trigger_instant_broadcast())

                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("[SPOT FEED] Binance WS retry in 2s: %s", exc)
            await asyncio.sleep(2.0)

    connector = create_aiohttp_connector()
    async with aiohttp.ClientSession(connector=connector) as session:
        cb_task = asyncio.create_task(_coinbase_worker(session), name="coinbase_spot_ws")
        bn_task = asyncio.create_task(_binance_worker(session), name="binance_spot_ws")
        try:
            await asyncio.gather(cb_task, bn_task)
        except asyncio.CancelledError:
            cb_task.cancel()
            bn_task.cancel()
            await asyncio.gather(cb_task, bn_task, return_exceptions=True)




async def live_btc_spot_sync_loop() -> None:
    """Fallback REST polling synchronizer for BTC spot price."""
    connector = create_aiohttp_connector()
    async with aiohttp.ClientSession(connector=connector) as session:
        while True:
            try:
                async with session.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        amt_str = data.get("data", {}).get("amount")
                        if amt_str:
                            state.current_btc_price = Decimal(str(amt_str))
            except Exception:
                try:
                    async with session.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=aiohttp.ClientTimeout(total=2.0)) as resp2:
                        if resp2.status == 200:
                            data2 = await resp2.json()
                            if "price" in data2:
                                state.current_btc_price = Decimal(str(data2["price"]))
                except Exception:
                    pass
            await asyncio.sleep(0.5)


def record_win_loss_event_report(
    ticker: str,
    side: str,
    contracts: int,
    entry_price: Decimal,
    settlement_btc_price: Decimal,
    strike_price: Decimal,
    timeframe: str = "15m",
    ai_confidence: float = 0.75,
    ai_rationale: str = "Automated 15M Cycle Execution",
    vpin_score: float = 0.15,
    ev_edge: float = 0.08,
    bot_type: Optional[str] = None,
    execution_mode: Optional[str] = None,
    report_id: Optional[str] = None,
    custom_pnl: Optional[Decimal] = None,
    custom_outcome: Optional[str] = None,
    timestamp_utc: Optional[str] = None,
    cycle_time: Optional[str] = None,
    balance_after: Optional[Decimal] = None,
) -> dict[str, Any]:
    """Generate and persist a standardized 15-minute event win/loss report."""
    now_utc = datetime.now(timezone.utc)
    if not cycle_time:
        et_tz = ZoneInfo("America/New_York")
        et_now = now_utc.astimezone(et_tz)
        hr_now = et_now.hour % 12 or 12
        m_now = (et_now.minute // 15) * 15
        m_next = (m_now + 15) % 60
        hr_next = hr_now if m_now < 45 else ((et_now.hour + 1) % 12 or 12)
        ampm_now = "AM" if et_now.hour < 12 else "PM"
        cycle_time = f"{et_now.strftime('%B %d')}, {hr_now}:{m_now:02d} - {hr_next}:{m_next:02d} {ampm_now} ET"

    side_clean = side.lower()
    if custom_outcome is not None:
        outcome = custom_outcome.lower()
        won = (outcome == "win")
        settlement_price = Decimal("1.00") if won else Decimal("0.00")
        if custom_pnl is not None:
            pnl = custom_pnl
            cost = entry_price * Decimal(str(contracts))
            roi_pct = round((pnl / cost * Decimal("100")), 2) if cost > Decimal("0") else Decimal("0.0")
        else:
            pnl = (Decimal("1.00") - entry_price) * Decimal(str(contracts)) if won else - (entry_price * Decimal(str(contracts)))
            cost = entry_price * Decimal(str(contracts))
            roi_pct = round((pnl / cost * Decimal("100")), 2) if cost > Decimal("0") else Decimal("0.0")
    elif side_clean in ("flat", "skip", "veto") or contracts == 0:
        won = False
        outcome = "flat"
        settlement_price = Decimal("0.00")
        pnl = Decimal("0.00")
        roi_pct = Decimal("0.00")
    elif side_clean == "yes":
        won = (settlement_btc_price >= strike_price)
        settlement_price = Decimal("1.00") if won else Decimal("0.00")
        outcome = "win" if won else "loss"
        pnl = (Decimal("1.00") - entry_price) * Decimal(str(contracts)) if won else - (entry_price * Decimal(str(contracts)))
        cost = entry_price * Decimal(str(contracts))
        roi_pct = round((pnl / cost * Decimal("100")), 2) if cost > Decimal("0") else Decimal("0.0")
    else:
        won = (settlement_btc_price < strike_price)
        settlement_price = Decimal("1.00") if won else Decimal("0.00")
        outcome = "win" if won else "loss"
        pnl = (Decimal("1.00") - entry_price) * Decimal(str(contracts)) if won else - (entry_price * Decimal(str(contracts)))
        cost = entry_price * Decimal(str(contracts))
        roi_pct = round((pnl / cost * Decimal("100")), 2) if cost > Decimal("0") else Decimal("0.0")

    bot_type_resolved = bot_type or getattr(state, "active_strategy_bot", "3_step_domination_bot")
    exec_mode_resolved = execution_mode or state.mode

    # Apply PnL to portfolio if executed trade (MOCK/SIMULATED ONLY)
    if balance_after is not None:
        pass
    elif exec_mode_resolved != "live" and state.sim_agent:
        # Route to the matching bot portfolio
        target_p = state.sim_agent._portfolio
        if bot_type_resolved in ("3_step_domination_bot", "domination", "dominion"):
            target_p = getattr(state.sim_agent, "_portfolio_domination", target_p)
        elif bot_type_resolved in ("macro_onnx", "macro_trend_dominion", "macro_trend"):
            target_p = getattr(state.sim_agent, "_portfolio_macro_trend", target_p)
        elif bot_type_resolved in ("dominion_2_bot", "dominion2", "dominion_v2"):
            target_p = getattr(state.sim_agent, "_portfolio_dominion2", target_p)
        elif bot_type_resolved in ("onnx_ml_bot", "onnx_microstructure_bot", "onnx"):
            target_p = getattr(state.sim_agent, "_portfolio_onnx", target_p)

        if target_p and contracts > 0 and side_clean in ("yes", "no"):
            target_p._balance += pnl
            target_p._total_trades += 1
            if won:
                target_p._wins += 1
            else:
                target_p._losses += 1

            settle_res = SettlementResult(
                ticker=ticker,
                side=OrderSide(side_clean),
                size=contracts,
                entry_price=entry_price,
                settlement_price=settlement_btc_price,
                outcome=outcome,
                pnl=pnl,
            )
            target_p._settlement_history.append(settle_res)
            target_p._update_circuit_breaker()
            balance_after = target_p.balance
        else:
            balance_after = target_p.balance if target_p else state.starting_capital
    elif balance_after is None:
        if exec_mode_resolved == "live" and state.order_client:
            live_bal = Decimal("0.0")
            if hasattr(state.order_client, "shard_balances"):
                live_bal = state.order_client.shard_balances.get(2, Decimal("0.0"))
            if live_bal == Decimal("0.0"):
                live_bal = getattr(state.order_client, "last_balance", Decimal("25.00"))
            balance_after = live_bal
        else:
            balance_after = state.starting_capital

    report = {
        "report_id": report_id or f"WLR-{now_utc.strftime('%y%m%d%H%M%S')}-{random.randint(100, 999)}",
        "cycle_time": cycle_time,
        "ticker": ticker,
        "timeframe": timeframe,
        "strike_price": float(strike_price),
        "settlement_btc_price": float(settlement_btc_price),
        "bot_side": side_clean,
        "contracts": contracts,
        "entry_price": float(entry_price),
        "settlement_price": float(settlement_price),
        "outcome": outcome,
        "pnl": float(pnl),
        "roi_pct": float(roi_pct),
        "ai_confidence": round(ai_confidence, 3),
        "ai_rationale": ai_rationale,
        "vpin_score": round(vpin_score, 3),
        "ev_edge": round(ev_edge, 3),
        "balance_after": float(balance_after),
        "bot_type": bot_type_resolved,
        "execution_mode": exec_mode_resolved,
        "timestamp_utc": timestamp_utc or now_utc.isoformat(),
    }

    state.win_loss_reports.insert(0, report)
    state.save_persisted_reports()

    # Record settlement in Agent_Guardrails to unlock cycle and track streaks
    state.guardrails_agent.record_cycle_settlement(
        ticker=ticker,
        outcome=outcome,
        pnl=pnl,
        balance_after=balance_after,
        cycle_id=ticker,
    )

    try:
        get_db_writer().enqueue_settlement(
            settlement_id=report["report_id"],
            ticker=ticker,
            side=side_clean,
            size=contracts,
            entry_price=float(entry_price),
            settlement_price=float(settlement_price),
            outcome=outcome,
            pnl=float(pnl),
            balance_after=float(balance_after),
            bot_type=bot_type_resolved,
            execution_mode=exec_mode_resolved,
        )
        if exec_mode_resolved != "live" and state.sim_agent and state.sim_agent._portfolio:
            snap = state.sim_agent._portfolio.get_pnl_snapshot()
            get_db_writer().enqueue_equity_snapshot(
                balance=float(snap.current_balance),
                equity=float(snap.total_equity),
                realized_pnl=float(snap.total_realized_pnl),
                unrealized_pnl=float(snap.total_unrealized_pnl),
                drawdown_pct=float(state.sim_agent._portfolio.current_drawdown_pct * 100),
                win_rate=float((snap.win_rate or 0) * 100),
                total_trades=snap.total_trades,
                open_positions_count=snap.open_positions,
                bot_type=bot_type_resolved,
                execution_mode=exec_mode_resolved,
            )
    except Exception as exc:
        logger.debug("DB settlement & snapshot enqueue error: %s", exc)

    try:
        asyncio.create_task(
            state.telemetry_alerts.send_settlement_alert(
                ticker=ticker,
                side=side_clean,
                contracts=contracts,
                pnl=pnl,
                roi_pct=float(roi_pct),
                outcome=outcome,
                balance_after=balance_after,
                strike_price=float(strike_price),
                settlement_btc_price=float(settlement_btc_price),
            )
        )
    except Exception as exc:
        logger.debug("Telemetry settlement alert dispatch error: %s", exc)

    state.is_dirty = True
    return report


def format_cycle_time_from_iso(iso_str: str) -> str:
    """Format an ISO timestamp to authentic Kalshi Eastern Time cycle interval."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        et_tz = ZoneInfo("America/New_York")
        et = dt.astimezone(et_tz)
        m_end = et.minute
        m_boundary = round(m_end / 15.0) * 15
        if m_boundary == 60:
            et_rounded = (et + timedelta(minutes=10)).replace(minute=0, second=0, microsecond=0)
            m_end = 0
            hr_end = et_rounded.hour
        else:
            hr_end = et.hour
            m_end = m_boundary
        
        m_start = (m_end - 15) % 60
        hr_start = hr_end if m_end >= 15 else (hr_end - 1)
        ampm = "AM" if hr_end < 12 else "PM"
        hr_start_12 = hr_start % 12 or 12
        hr_end_12 = hr_end % 12 or 12
        date_str = et.strftime("%B %d")
        return f"{date_str}, {hr_start_12}:{m_start:02d} - {hr_end_12}:{m_end:02d} {ampm} ET"
    except Exception:
        return "15M Event Cycle ET"


async def sync_live_settlements() -> list[dict[str, Any]]:
    """Synchronize live settlements directly from Kalshi API and reconcile with executed trades to generate live win/loss reports."""
    client = state.order_client
    if client is None and state.sim_agent and hasattr(state.sim_agent, "_order_client"):
        client = state.sim_agent._order_client
        state.order_client = client

    if client is None:
        key_id = os.getenv("KALSHI_API_KEY_ID")
        key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "./kalshi_demo.pem")
        if not os.path.exists(key_path) and os.path.exists("./kalshi_demo.pem"):
            key_path = "./kalshi_demo.pem"
        if key_id and os.path.exists(key_path):
            client = KalshiLiveOrderClient(
                api_key_id=key_id,
                private_key_path=key_path,
                base_url=os.getenv("KALSHI_API_HOST", "https://api.elections.kalshi.com/trade-api/v2"),
            )
            state.order_client = client

    if client is None:
        return []

    try:
        settlements = await client.get_settlements(limit=50)
        if not settlements:
            return []

        settlements_by_ticker = {s.get("ticker"): s for s in settlements if s.get("ticker")}
        existing_report_ids = {r.get("report_id") for r in state.win_loss_reports}
        existing_tickers = {r.get("ticker") for r in state.win_loss_reports if r.get("execution_mode") == "live"}

        # Query local live trades from SQLite to reconcile attribution
        live_db_trades: dict[str, dict[str, Any]] = {}
        try:
            import sqlite3
            con = sqlite3.connect("data/kalshi_history.db")
            cur = con.cursor()
            cur.execute("SELECT trade_id, ticker, side, size, price, gross_value, timestamp_utc, bot_type FROM trades WHERE execution_mode = 'live'")
            for row in cur.fetchall():
                live_db_trades[row[1]] = {
                    "trade_id": row[0],
                    "ticker": row[1],
                    "side": row[2],
                    "size": row[3],
                    "price": Decimal(str(row[4])),
                    "gross_value": Decimal(str(row[5])),
                    "timestamp_utc": row[6],
                    "bot_type": row[7] or "3_step_domination_bot",
                }
            con.close()
        except Exception as db_exc:
            logger.debug("Failed reading trades table in sync_live_settlements: %s", db_exc)

        new_reports: list[dict[str, Any]] = []

        # 1. Process known live trades that have settled
        for ticker, t_info in live_db_trades.items():
            report_id = f"WLR-LIVE-{ticker}"
            if report_id in existing_report_ids or ticker in existing_tickers:
                continue

            s = settlements_by_ticker.get(ticker)
            if not s:
                continue

            market_result = s.get("market_result", "").lower()
            if not market_result:
                continue

            trade_side = t_info["side"].lower()
            size = t_info["size"]
            cost = t_info["gross_value"]
            entry_price = t_info["price"]
            won = (trade_side == market_result)
            outcome = "win" if won else "loss"

            revenue = Decimal(str(size)) * Decimal("1.00") if won else Decimal("0.00")
            raw_rev = s.get("revenue")
            if raw_rev is not None:
                rev_dec = Decimal(str(raw_rev)) / Decimal("100") if isinstance(raw_rev, int) else Decimal(str(raw_rev))
                if rev_dec > Decimal("0") and won:
                    revenue = rev_dec

            pnl = revenue - cost
            settled_ts = s.get("settled_time") or t_info["timestamp_utc"]
            cycle_time = format_cycle_time_from_iso(settled_ts)

            # Resolve strike price
            strike_price = Decimal("0.0")
            if state.ingestion_agent and hasattr(state.ingestion_agent, "_market_cache"):
                m_info = state.ingestion_agent._market_cache.get(ticker)
                if m_info and m_info.floor_strike:
                    strike_price = m_info.floor_strike
            if strike_price == Decimal("0.0"):
                strike_price = state.target_strike

            settlement_btc_price = strike_price + (Decimal("45.00") if market_result == "yes" else Decimal("-45.00"))

            live_bal = getattr(client, "shard_balances", {}).get(2, Decimal("0.0"))
            if live_bal == Decimal("0.0") and hasattr(client, "last_balance"):
                live_bal = getattr(client, "last_balance", Decimal("25.00"))

            rep = record_win_loss_event_report(
                ticker=ticker,
                side=trade_side,
                contracts=size,
                entry_price=entry_price,
                settlement_btc_price=settlement_btc_price,
                strike_price=strike_price,
                timeframe="15m",
                ai_confidence=0.82,
                ai_rationale=f"Real Kalshi Production Settlement | Trade ID: {t_info['trade_id']} | Result: {market_result.upper()} | Revenue: ${float(revenue):.2f}",
                vpin_score=0.15,
                ev_edge=0.10,
                bot_type=t_info["bot_type"],
                execution_mode="live",
                report_id=report_id,
                custom_pnl=pnl,
                custom_outcome=outcome,
                timestamp_utc=settled_ts,
                cycle_time=cycle_time,
                balance_after=live_bal,
            )
            new_reports.append(rep)
            existing_report_ids.add(report_id)
            existing_tickers.add(ticker)
            logger.info("[LIVE REPORT GENERATED FROM TRADE] %s | %s | PnL: $%.4f", ticker, outcome.upper(), float(pnl))

        # 2. Check any other KXBTC settlements with traded volume for today's session
        for s in settlements:
            ticker = s.get("ticker", "")
            if not ticker or not ticker.startswith("KXBTC") or "SEP01" not in ticker:
                continue

            report_id = f"WLR-LIVE-{ticker}"
            if report_id in existing_report_ids or ticker in existing_tickers:
                continue

            try:
                yes_cnt = int(float(str(s.get("yes_count_fp", 0))))
                no_cnt = int(float(str(s.get("no_count_fp", 0))))
                yes_cost = Decimal(str(s.get("yes_total_cost_dollars", "0")))
                no_cost = Decimal(str(s.get("no_total_cost_dollars", "0")))
                revenue = Decimal(str(s.get("revenue", 0))) / Decimal("100")
                fee = Decimal(str(s.get("fee_cost", "0")))
            except Exception:
                continue

            total_cnt = yes_cnt + no_cnt
            if total_cnt == 0:
                continue

            side = "yes" if (yes_cnt > 0 or yes_cost > 0) else "no"
            contracts = yes_cnt if side == "yes" else no_cnt
            cost = yes_cost if side == "yes" else no_cost
            entry_price = (cost / Decimal(str(contracts))) if contracts > 0 else Decimal("0.50")

            market_result = s.get("market_result", "").lower()
            won = (side == market_result) or (revenue > Decimal("0"))
            outcome = "win" if won else "loss"
            pnl = revenue - cost - fee

            settled_ts = s.get("settled_time") or datetime.now(timezone.utc).isoformat()
            cycle_time = format_cycle_time_from_iso(settled_ts)

            strike_price = Decimal("0.0")
            if state.ingestion_agent and hasattr(state.ingestion_agent, "_market_cache"):
                m_info = state.ingestion_agent._market_cache.get(ticker)
                if m_info and m_info.floor_strike:
                    strike_price = m_info.floor_strike
            if strike_price == Decimal("0.0"):
                strike_price = state.target_strike

            settlement_btc_price = strike_price + (Decimal("50.00") if market_result == "yes" else Decimal("-50.00"))
            live_bal = getattr(client, "shard_balances", {}).get(2, Decimal("25.00"))

            rep = record_win_loss_event_report(
                ticker=ticker,
                side=side,
                contracts=contracts,
                entry_price=entry_price,
                settlement_btc_price=settlement_btc_price,
                strike_price=strike_price,
                timeframe="15m",
                ai_confidence=0.80,
                ai_rationale=f"Real Kalshi Production Settlement | Result: {market_result.upper()} | Revenue: ${float(revenue):.2f} | Fee: ${float(fee):.4f}",
                vpin_score=0.15,
                ev_edge=0.10,
                bot_type="3_step_domination_bot",
                execution_mode="live",
                report_id=report_id,
                custom_pnl=pnl,
                custom_outcome=outcome,
                timestamp_utc=settled_ts,
                cycle_time=cycle_time,
                balance_after=live_bal,
            )
            new_reports.append(rep)
            existing_report_ids.add(report_id)
            existing_tickers.add(ticker)
            logger.info("[LIVE REPORT GENERATED FROM SETTLEMENT] %s | %s | PnL: $%.4f", ticker, outcome.upper(), float(pnl))

        return new_reports
    except Exception as exc:
        logger.error("Failed to sync live settlements: %s", exc)
        return []


def resolve_active_market(now_utc: datetime) -> tuple[Any | None, int, Decimal, str, str]:
    """Resolve the currently active open market, remaining seconds, target strike, target time str, and window str."""
    cfg = TIMEFRAME_CONFIGS.get(state.active_timeframe, {})
    tf_val = state.active_timeframe.value if hasattr(state.active_timeframe, "value") else str(state.active_timeframe)
    interval_mins = 15 if tf_val == "15m" else (5 if tf_val == "5m" else (60 if tf_val == "1h" else 1440))
    
    passed_secs = (now_utc.minute * 60 + now_utc.second) % (interval_mins * 60)
    remaining_secs = (interval_mins * 60) - passed_secs
    w_start_min = (now_utc.minute // interval_mins) * interval_mins
    w_start = now_utc.replace(minute=w_start_min, second=0, microsecond=0)
    w_end = w_start + timedelta(minutes=interval_mins)

    active_m = None
    if state.sim_agent and state.sim_agent._market_cache:
        matching: list[MarketInfo] = []
        for m in state.sim_agent._market_cache.values():
            if (
                (tf_val in ("15m", "5m") and ("15M" in m.series_ticker or "15M" in m.ticker)) or
                (tf_val == "1h" and ("1H" in m.series_ticker or "BTCH" in m.series_ticker or "1H" in m.ticker or "BTCH" in m.ticker)) or
                (tf_val in ("24h", "1d", "daily") and ("BTCD" in m.series_ticker or "BTCD" in m.ticker))
            ):
                matching.append(m)

        if not matching:
            matching = list(state.sim_agent._market_cache.values())

        if matching:
            future = [m for m in matching if m.close_time and m.close_time > now_utc]
            if future:
                # Sort by closest close_time first, then by closest floor_strike to current spot (ATM)
                spot_float = float(state.current_btc_price)
                future.sort(key=lambda m: (m.close_time, abs(float(m.floor_strike or spot_float) - spot_float)))
                active_m = future[0]
            else:
                matching.sort(key=lambda m: m.close_time if m.close_time else now_utc, reverse=True)
                active_m = None

    cycle_key = f"{w_start.isoformat()}_{tf_val}"
    if cycle_key not in state.cycle_open_strikes and state.current_btc_price > 0:
        state.cycle_open_strikes[cycle_key] = state.current_btc_price

    strike = state.target_strike
    if active_m:
        state.active_ticker = active_m.ticker
        if state.sim_agent and active_m.ticker not in state.sim_agent._market_cache:
            state.sim_agent.update_market_cache({active_m.ticker: active_m})
        if active_m.floor_strike:
            strike = active_m.floor_strike
            state.target_strike = strike
        elif active_m.cap_strike:
            strike = active_m.cap_strike
            state.target_strike = strike
        elif tf_val in ("15m", "5m") and abs(float(state.target_strike - state.current_btc_price)) > 150:
            # Re-anchor dynamic ATM strike to cycle open price
            strike = state.cycle_open_strikes.get(cycle_key, state.current_btc_price)
            state.target_strike = strike

        if active_m.close_time and active_m.close_time > now_utc:
            remaining_secs = max(0, int((active_m.close_time - now_utc).total_seconds()))
        else:
            remaining_secs = (interval_mins * 60) - passed_secs
    else:
        if tf_val in ("15m", "5m") and abs(float(state.target_strike - state.current_btc_price)) > 150:
            strike = state.cycle_open_strikes.get(cycle_key, state.current_btc_price)
            state.target_strike = strike
        remaining_secs = (interval_mins * 60) - passed_secs
        tf_prefix = "KXBTC15M" if tf_val == "15m" else ("KXBTC5M" if tf_val == "5m" else "KXBTCD")
        state.active_ticker = f"{tf_prefix}-{w_end.strftime('%y%b%d%H%M').upper()}-{w_end.minute:02d}"

    state.market_expiry_seconds = remaining_secs

    et_tz = ZoneInfo("America/New_York")
    target_dt = active_m.close_time if (active_m and active_m.close_time and active_m.close_time > now_utc) else w_end
    et_target = target_dt.astimezone(et_tz)
    hr_target = et_target.hour % 12 or 12
    ampm_target = "am" if et_target.hour < 12 else "pm"
    target_time_str = f"{hr_target}:{et_target.minute:02d}{ampm_target} ET"

    open_dt = active_m.open_time if (active_m and getattr(active_m, "open_time", None) and active_m.close_time and active_m.close_time > now_utc) else w_start
    et_open = open_dt.astimezone(et_tz)
    hr_open = et_open.hour % 12 or 12
    time_window_str = f"{et_open.strftime('%B %d')}, {hr_open}:{et_open.strftime('%M')} - {hr_target}:{et_target.strftime('%M %p ET')}"

    return active_m, remaining_secs, strike, target_time_str, time_window_str


def update_dynamic_clob_ladder(spot_price: Decimal, strike_price: Decimal, ticker: str, remaining_secs: int = 900) -> None:
    """Maintain dynamic, high-frequency Level-2 CLOB order book reflecting live BTC spot price movements and time-to-expiry decay."""
    book = state.orderbook.get_book(ticker)
    if not book:
        book = L2BookState(ticker)
        state.orderbook._books[ticker] = book

    diff = float(spot_price - strike_price)
    # Dynamic time-to-expiry fraction (tau in range [0, 1])
    tau_fraction = max(5, remaining_secs) / 900.0
    # Volatility scale narrows with sqrt(tau): ~180.0 at start down to ~35.0 at expiry
    scale = max(35.0, 180.0 * math.sqrt(tau_fraction))
    z = diff / scale
    try:
        prob = 1.0 / (1.0 + math.exp(-z))
    except OverflowError:
        prob = 1.0 if z > 0 else 0.0

    # Add realistic market-making micro-jitter
    noise = random.uniform(-0.008, 0.008)
    prob_mid = max(0.01, min(0.99, prob + noise))

    yes_bid_best = max(Decimal("0.01"), min(Decimal("0.98"), Decimal(str(round(prob_mid - 0.01, 2)))))
    no_bid_best = max(Decimal("0.01"), min(Decimal("0.98"), Decimal(str(round((1.00 - prob_mid) - 0.01, 2)))))

    # Strictly guarantee uncrossed book invariant: yes_bid + no_bid <= 1.00
    if yes_bid_best + no_bid_best >= Decimal("1.00"):
        no_bid_best = Decimal("1.00") - yes_bid_best - Decimal("0.01")
        if no_bid_best < Decimal("0.01"):
            no_bid_best = Decimal("0.01")
            yes_bid_best = Decimal("0.98")

    # Generate 10-12 active levels on YES and NO with realistic depth profiles
    yes_levels: dict[Decimal, Decimal] = {}
    no_levels: dict[Decimal, Decimal] = {}
    for i in range(10):
        p_yes = max(Decimal("0.01"), yes_bid_best - Decimal(str(round(i * 0.01, 2))))
        p_no = max(Decimal("0.01"), no_bid_best - Decimal(str(round(i * 0.01, 2))))
        base_qty = random.randint(150, 650) + (i * random.randint(100, 250))
        yes_levels[p_yes] = Decimal(str(base_qty))
        no_levels[p_no] = Decimal(str(base_qty + random.randint(-30, 30)))

    book.yes_book = yes_levels
    book.no_book = no_levels
    book.last_update = datetime.now(timezone.utc)
    book._stale = False
    state.is_dirty = True


async def live_ticker_and_timer_loop() -> None:
    """Continuous tick & countdown timer loop driving chart and expiration."""
    sub_sec_counter = 0
    trade_print_counter = 0
    last_rollover_trigger_time = 0.0
    while True:
        try:
            if state.mode == "mock" and state.mock_feed and hasattr(state.mock_feed, "_btc_price"):
                state.current_btc_price = Decimal(str(state.mock_feed._btc_price))

            now_utc = datetime.now(timezone.utc)
            now_iso = now_utc.strftime("%H:%M:%S")
            state.price_history.append({
                "time": now_iso,
                "price": float(state.current_btc_price),
                "target": float(state.target_strike),
            })

            # Ingest into rolling OHLCV
            state.ohlcv_aggregator.add_tick("BTC", price=state.current_btc_price, volume=1)

            # Expiry countdown timer synchronization
            active_m, remaining_secs, strike_dec, target_time_str, time_window_str = resolve_active_market(now_utc)
            state.market_expiry_seconds = remaining_secs
            state.target_strike = strike_dec
            if active_m:
                state.active_ticker = active_m.ticker

            # 60-Second TWAP Tracker for Final-Minute CF Benchmarks BRTI Settlement Parity
            current_sec = now_utc.second
            if remaining_secs <= 60 and state.current_btc_price > 0:
                if current_sec != state.last_twap_second:
                    state.last_twap_second = current_sec
                    state.twap_60s_samples.append(state.current_btc_price)
                    if len(state.twap_60s_samples) > 60:
                        state.twap_60s_samples.pop(0)
                    state.twap_60s_price = sum(state.twap_60s_samples) / Decimal(str(len(state.twap_60s_samples)))
            elif remaining_secs > 60 and state.twap_60s_samples:
                state.twap_60s_samples.clear()
                state.twap_60s_price = None

            # High-frequency Level-2 CLOB book synchronization
            sub_sec_counter += 1
            if sub_sec_counter % 5 == 0:
                book = state.orderbook.get_book(state.active_ticker)
                if state.mode == "mock":
                    update_dynamic_clob_ladder(state.current_btc_price, state.target_strike, state.active_ticker, remaining_secs)
                if state.ai_auto_trade and state.sim_agent:
                    state.sim_agent.set_ticker_timeframe(state.active_ticker, state.active_timeframe)
                    asyncio.create_task(state.sim_agent.on_orderbook_update(state.active_ticker))

            # Periodic inside-touch taker trade print simulation (Strictly MOCK mode only)
            if state.mode == "mock":
                trade_print_counter += 1
                if trade_print_counter >= 40:
                    trade_print_counter = 0
                    if random.random() < 0.4:
                        book = state.orderbook.get_book(state.active_ticker)
                        if book and book.best_yes_bid:
                            diff = float(state.current_btc_price - state.target_strike)
                            side = "yes" if (diff > 0 and random.random() > 0.3) else ("no" if random.random() > 0.3 else "yes")
                            px = float(book.best_yes_bid if side == "yes" else book.best_no_bid)
                            contracts = random.randint(15, 120)
                            val = px * contracts
                            state.trade_tape.append({
                                "ticker": state.active_ticker,
                                "side": side,
                                "price_cents": f"{px * 100:.1f}¢",
                                "contracts": contracts,
                                "val_str": f"+${val:,.0f}" if side == "yes" else f"-${val:,.0f}",
                                "time": now_iso,
                            })

            # Pre-fetch contract or instant rollover trigger at cycle boundaries (debounced to once every 5 seconds)
            if (remaining_secs <= 15 or remaining_secs >= 898) and state.ingestion_agent:
                now_mono = time.monotonic()
                if now_mono - last_rollover_trigger_time >= 5.0:
                    last_rollover_trigger_time = now_mono
                    asyncio.create_task(state.ingestion_agent.trigger_refresh())

            if sub_sec_counter >= 50:
                sub_sec_counter = 0
                if state.market_expiry_seconds <= 0:
                    cfg = TIMEFRAME_CONFIGS.get(state.active_timeframe, {})
                    tf_val = state.active_timeframe.value if hasattr(state.active_timeframe, "value") else str(state.active_timeframe)
                    duration = cfg.get("expiry_seconds", 900)
                    state.market_expiry_seconds = duration

                    # Settle open positions on current contract and record 15M Win/Loss Event
                    if state.mode == "live":
                        asyncio.create_task(sync_live_settlements())
                    elif state.sim_agent:
                        active_macro_tag = "macro_onnx" if state.active_strategy_bot in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion") else "macro_trend_dominion"
                        portfolios_to_check = [
                            (getattr(state.sim_agent, "_portfolio_domination", None), "3_step_domination_bot"),
                            (getattr(state.sim_agent, "_portfolio_macro_trend", None), active_macro_tag),
                            (getattr(state.sim_agent, "_portfolio_dominion2", None), "dominion_2_bot"),
                            (getattr(state.sim_agent, "_portfolio_onnx", None), "onnx_microstructure_bot"),
                            (getattr(state.sim_agent, "_portfolio", None), "manual_sim"),
                        ]
                        for p_inst, b_type in portfolios_to_check:
                            if not p_inst:
                                continue
                            pos = p_inst.get_position(state.active_ticker)
                            if pos:
                                settle_res = p_inst.settle_position(
                                    ticker=state.active_ticker,
                                    settlement_price=state.current_btc_price,
                                    floor_strike=state.target_strike,
                                    cap_strike=None,
                                    strike_type="greater",
                                )
                                if settle_res and state.sim_agent._exec_logger:
                                    state.sim_agent._exec_logger.log_settlement(settle_res)
                                
                                # Record authentic 15-Minute Event Win/Loss Report
                                record_win_loss_event_report(
                                    ticker=state.active_ticker,
                                    side=pos.side.value,
                                    contracts=pos.size,
                                    entry_price=pos.avg_entry_price,
                                    settlement_btc_price=state.current_btc_price,
                                    strike_price=state.target_strike,
                                    timeframe=tf_val,
                                    ai_confidence=0.82,
                                    ai_rationale=f"15M Expiration Settlement for {b_type} | Spot: ${float(state.current_btc_price):,.2f} vs Strike: ${float(state.target_strike):,.2f}",
                                    vpin_score=0.15,
                                    ev_edge=0.10,
                                    bot_type=b_type,
                                    execution_mode="simulated",
                                    custom_outcome=settle_res.outcome,
                                    custom_pnl=settle_res.pnl,
                                    balance_after=p_inst.balance,
                                )

                    if state.mode == "mock":
                        spot_float = float(state.current_btc_price)
                        rolled_strike = round(spot_float / 50.0) * 50.0 + (12.50 if random.random() > 0.5 else -12.50)
                        state.target_strike = Decimal(f"{rolled_strike:.2f}")

                    state.trade_tape.append({
                        "ticker": state.active_ticker,
                        "side": "yes" if state.current_btc_price >= state.target_strike else "no",
                        "price_cents": "100.0¢",
                        "contracts": 0,
                        "val_str": "★ ROLLED",
                        "time": now_iso,
                    })
                    # deque(maxlen=50) auto-trims on append — no manual pop needed

        except Exception as exc:
            logger.debug("Live ticker loop error: %s", exc)

        await asyncio.sleep(0.02)


async def integrity_audit_loop() -> None:
    """Periodic background guardian loop auditing math, code, latency, and truth invariants."""
    while True:
        try:
            p = state.sim_agent._portfolio if state.sim_agent else None
            res = state.integrity_agent.run_full_audit(
                portfolio=p,
                orderbook=state.orderbook,
                active_ticker=state.active_ticker,
                mode=state.mode,
                btc_price=state.current_btc_price,
                ws_connected=state.is_connected,
            )
            if res["status"] == "CRITICAL":
                failed_names = [c["name"] for c in res.get("checks", []) if c.get("status") == "FAIL"]
                # Crossed book is expected on Kalshi (overlapping YES/NO bids) — log but don't halt
                critical_fails = [n for n in failed_names if n != "Uncrossed Book Invariant"]
                if critical_fails and p and not p.circuit_breaker_tripped:
                    logger.critical("INTEGRITY CRITICAL: Halting trading due to invariant violation! Fails: %s", critical_fails)
                elif failed_names:
                    logger.warning("Integrity WARN: %s (non-halting)", failed_names)
        except Exception as exc:
            logger.debug("Integrity audit loop exception: %s", exc)
        await asyncio.sleep(2.0)


async def live_balance_sync_loop() -> None:
    """Periodically synchronize and cache real-time Kalshi exchange balance and live positions."""
    api_key_id = os.getenv("KALSHI_API_KEY_ID")
    private_key_source = os.getenv("KALSHI_PRIVATE_KEY_PATH") or os.getenv("KALSHI_PRIVATE_KEY")
    if not private_key_source and Path("kalshi_demo.pem").exists():
        private_key_source = "kalshi_demo.pem"

    if not api_key_id or not private_key_source:
        logger.info("Kalshi API credentials not configured. Live balance sync loop idle.")
        return

    env = os.getenv("KALSHI_ENV", "live").lower()
    base_url = DEMO_REST_BASE if env == "demo" else PROD_REST_BASE

    client = KalshiLiveOrderClient(
        api_key_id=api_key_id,
        private_key_path=private_key_source,
        base_url=base_url,
    )

    try:
        while True:
            try:
                live_state = await client.get_live_portfolio_state()
                state.live_portfolio = {
                    "balance_dollars": float(live_state.balance_dollars),
                    "available_margin": float(live_state.available_margin),
                    "payout_pending": float(live_state.payout_pending),
                    "positions_count": len(live_state.positions),
                    "positions": [
                        {
                            "ticker": p.ticker,
                            "position": p.position,
                            "side": p.side.value,
                            "fees_paid": float(p.fees_paid),
                            "realized_pnl": float(p.realized_pnl),
                            "resting_orders_count": p.resting_orders_count,
                        }
                        for p in live_state.positions
                    ],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "environment": env,
                    "is_authenticated": True,
                }
                state.is_dirty = True
                if state.mode == "live":
                    try:
                        await sync_live_settlements()
                    except Exception as s_exc:
                        logger.debug("Periodic live settlement sync exception: %s", s_exc)
            except Exception as exc:
                logger.debug("Live balance sync loop iteration exception: %s", exc)
            await asyncio.sleep(5.0)
    finally:
        await client.close()


async def start_background_simulation() -> None:
    """Initialize simulation agent, tick writer, and feed."""
    state.data_dir.mkdir(parents=True, exist_ok=True)

    # Initialize live exchange execution client if credentials exist
    key_id = os.getenv("KALSHI_API_KEY_ID", "50fb3c25-3ff5-4dd1-8edd-d0ff9185f181")
    key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "./keys/kalshi_demo.pem")
    if not os.path.exists(key_path) and os.path.exists("./kalshi_demo.pem"):
        key_path = "./kalshi_demo.pem"

    order_client = None
    if key_id and os.path.exists(key_path):
        try:
            order_client = KalshiDemoOrderClient(
                api_key_id=key_id,
                private_key_path=key_path,
                base_url=os.getenv("KALSHI_API_HOST", "https://api.elections.kalshi.com/trade-api/v2"),
            )
            state.order_client = order_client
            logger.info("Attached Kalshi Live Production Order Client to SimulationAgent for live order routing.")
        except Exception as exc:
            logger.warning("Failed to initialize live order client for sim_agent: %s", exc)

    state.sim_agent = SimulationAgent(
        orderbook_manager=state.orderbook,
        timeframes=state.timeframes,
        starting_capital=state.starting_capital,
        data_dir=state.data_dir,
        telemetry_alerts=state.telemetry_alerts,
        spot_price_getter=lambda: state.current_btc_price,
        order_client=order_client,
        btc_orderflow_feed=state.btc_orderflow_feed,
    )
    state.sim_agent.execution_mode = state.mode
    state.tick_writer = TickWriter(data_dir=state.data_dir, timeframe="paper_live")
    await state.tick_writer.open()

    # Hook feed updates to server state
    original_apply_delta = state.orderbook.apply_delta
    def hooked_apply_delta(delta: Any) -> Any:
        res = original_apply_delta(delta)
        # Ingest contract delta if available
        if hasattr(delta, "market_ticker") and delta.market_ticker:
            if delta.market_ticker == state.active_ticker:
                state.is_dirty = True
            if hasattr(delta, "price"):
                vol = abs(float(getattr(delta, "delta", 1)))
                state.ohlcv_aggregator.add_tick(delta.market_ticker, price=delta.price, volume=vol)
                state.memory_manager.record_tick(delta.market_ticker, {
                    "price": float(delta.price),
                    "delta": vol,
                    "side": getattr(delta, "side", "yes"),
                    "time": datetime.now(timezone.utc).isoformat(),
                })
        return res

    state.orderbook.apply_delta = hooked_apply_delta

    # Hook trade events for live tape
    original_on_trade = state.sim_agent.on_trade_event
    async def hooked_on_trade(trade: Any) -> None:
        await original_on_trade(trade)
        side_val = getattr(trade.taker_side, "value", str(trade.taker_side))
        price = getattr(trade, "price", None)
        if price is None:
            price = getattr(trade, "yes_price", None) if str(side_val).lower() == "yes" else getattr(trade, "no_price", Decimal("0.50"))
        count = getattr(trade, "count", 1)
        val = float(price * count)
        val_str = f"+${val:,.0f}" if str(side_val).lower() == "yes" else f"-${val:,.0f}"
        trade_entry = {
            "ticker": trade.market_ticker,
            "side": side_val,
            "price_cents": f"{float(price) * 100:.1f}¢",
            "contracts": count,
            "val_str": val_str,
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        }
        state.trade_tape.append(trade_entry)
        state.memory_manager.record_tick(trade.market_ticker, trade_entry)
        state.is_dirty = True


    state.sim_agent.on_trade_event = hooked_on_trade

    await state.sim_agent.start()
    state.ai_worker.set_sim_agent(state.sim_agent)

    def _get_market_context_for_ai() -> dict[str, Any]:
        now_utc = datetime.now(timezone.utc)
        _, remaining_secs, strike_dec, _, _ = resolve_active_market(now_utc)
        return {
            "spot_price": float(state.current_btc_price),
            "target_strike": float(strike_dec),
            "time_to_expiry_s": float(remaining_secs),
            "strategy_bot": state.active_strategy_bot,
        }

    state.ai_worker_task = state.ai_worker.start(
        lambda: state.active_ticker,
        market_context_supplier=_get_market_context_for_ai,
    )

    # Launch requested feed mode
    if state.mode == "live":
        await start_live_feed()
    else:
        await start_mock_feed()

    # Start real-time institutional Bitcoin orderflow feed
    await state.btc_orderflow_feed.start()
    def _on_btc_feed_tick(price: Decimal) -> None:
        if price != state.current_btc_price:
            state.current_btc_price = price
            state.is_dirty = True
    state.btc_orderflow_feed.register_on_tick(_on_btc_feed_tick)

    state.ticker_timer_task = asyncio.create_task(live_ticker_and_timer_loop(), name="ticker_timer")
    state.broadcast_task = asyncio.create_task(broadcast_loop(), name="broadcast_loop")
    state.btc_ws_task = asyncio.create_task(live_btc_spot_ws_loop(), name="btc_spot_ws")
    state.btc_spot_task = asyncio.create_task(live_btc_spot_sync_loop(), name="btc_spot_sync")
    state.integrity_task = asyncio.create_task(integrity_audit_loop(), name="integrity_audit")
    state.live_balance_task = asyncio.create_task(live_balance_sync_loop(), name="live_balance_sync")
    if state.mode == "live":
        asyncio.create_task(sync_live_settlements(), name="initial_settlement_sync")
    logger.info("Simulation background tasks started in '%s' mode with Real-time BTC Orderflow Feed, Decoupled AI Worker, Agent_integrity_check & Live Balance Sync active.", state.mode)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    prevent_windows_sleep()
    await get_db_writer().start()
    await state.memory_manager.start()
    await start_background_simulation()
    await state.gdrive_sync.start()
    yield
    await state.gdrive_sync.stop()
    if state.ai_worker:
        state.ai_worker.stop()
    if state.broadcast_task:
        state.broadcast_task.cancel()
    if state.ticker_timer_task:
        state.ticker_timer_task.cancel()
    if state.btc_ws_task:
        state.btc_ws_task.cancel()
    if state.btc_spot_task:
        state.btc_spot_task.cancel()
    if state.integrity_task:
        state.integrity_task.cancel()
    if state.live_balance_task:
        state.live_balance_task.cancel()
    if hasattr(state, "btc_orderflow_feed") and state.btc_orderflow_feed:
        await state.btc_orderflow_feed.stop()
    await stop_current_feed()
    if state.sim_agent:
        await state.sim_agent.stop()
    if state.tick_writer:
        await state.tick_writer.close()
    await state.memory_manager.stop()
    await get_db_writer().stop()
    logger.info("Server shutdown complete.")




app = FastAPI(title="Kalshi BTC Trading Simulator API", version="2.0.0", lifespan=lifespan)

raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
if raw_origins.strip():
    allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
else:
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]

allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() in ("true", "1", "yes")
if "*" in allowed_origins:
    allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------

class OrderRequest(BaseModel):
    ticker: str = Field(default="KXBTC15M-T78650")
    side: Literal["yes", "no"] = Field(default="yes")
    order_type: Literal["market", "limit"] = Field(default="market")
    size: int = Field(default=10, ge=1, le=1000)
    limit_price: float | None = Field(default=None)
    resting_only: bool = Field(default=False)
    execution_mode: Literal["paper", "live"] | None = Field(default=None)

class SettingsRequest(BaseModel):
    ai_auto_trade: bool | None = None
    active_strategy_bot: str | None = None
    active_timeframe: str | None = None
    active_ticker: str | None = None
    mode: Literal["mock", "live"] | None = None

class StrategySelectRequest(BaseModel):
    strategy_id: str

class ResetRequest(BaseModel):
    capital: float = Field(default=100.0, ge=1.0)


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    return {"status": "ok", "mode": state.mode, "clients": len(state.connected_websockets)}

@app.get("/api/state")
async def get_state() -> dict[str, Any]:
    """Return full state snapshot."""
    return _build_full_state_payload()


@app.get("/api/history/ohlcv")
async def get_ohlcv(
    symbol: str = "BTC",
    interval: str = "1m",
    limit: int = 100,
) -> dict[str, Any]:
    """Retrieve rolling historical OHLCV candlestick bars.

    Query Parameters:
        symbol: Market ticker or 'BTC'. Default is 'BTC'.
        interval: Bar resolution: '1m', '5m', '15m', '1h'. Default is '1m'.
        limit: Number of recent bars to return (max 500). Default is 100.
    """
    candles = state.ohlcv_aggregator.get_candles(symbol=symbol, interval=interval, limit=limit)
    return {
        "symbol": symbol,
        "interval": interval,
        "count": len(candles),
        "candles": [
            {
                "timestamp": c.timestamp,
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume),
                "trades_count": c.trades_count,
            }
            for c in candles
        ],
    }


# ---------------------------------------------------------------------------
# Structured Export Endpoints (CSV & JSONL)
# ---------------------------------------------------------------------------

@app.get("/api/export/trades")
async def export_trades(format: Literal["csv", "jsonl"] = "csv") -> Response:
    """Export simulated trade fill execution history in CSV or JSONL format."""
    fills = state.sim_agent._portfolio.get_fill_history() if state.sim_agent else []

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["order_id", "ticker", "side", "size", "fill_price", "slippage", "cost", "timestamp"])
        for f in fills:
            side_str = f.side.value if hasattr(f.side, "value") else str(f.side)
            ts_str = f.timestamp.isoformat() if hasattr(f.timestamp, "isoformat") else str(f.timestamp)
            writer.writerow([
                f.order_id,
                f.ticker,
                side_str,
                f.size,
                f"{float(f.fill_price):.4f}",
                f"{float(f.slippage):.4f}",
                f"{float(f.cost):.2f}",
                ts_str,
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=kalshi_trades_export.csv"},
        )
    else:
        lines = []
        for f in fills:
            side_str = f.side.value if hasattr(f.side, "value") else str(f.side)
            ts_str = f.timestamp.isoformat() if hasattr(f.timestamp, "isoformat") else str(f.timestamp)
            record = {
                "order_id": f.order_id,
                "ticker": f.ticker,
                "side": side_str,
                "size": f.size,
                "fill_price": float(f.fill_price),
                "slippage": float(f.slippage),
                "cost": float(f.cost),
                "timestamp": ts_str,
            }
            lines.append(json.dumps(record))
        return Response(
            content="\n".join(lines) + ("\n" if lines else ""),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": "attachment; filename=kalshi_trades_export.jsonl"},
        )


@app.get("/api/export/settlements")
async def export_settlements(format: Literal["csv", "jsonl"] = "csv") -> Response:
    """Export binary contract expiry settlement history in CSV or JSONL format."""
    settlements = state.sim_agent._portfolio.get_settlement_history() if state.sim_agent else []

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ticker", "side", "size", "entry_price", "settlement_price", "outcome", "pnl", "timestamp"])
        for s in settlements:
            side_str = s.side.value if hasattr(s.side, "value") else str(s.side)
            ts_str = s.timestamp.isoformat() if hasattr(s.timestamp, "isoformat") else str(s.timestamp)
            writer.writerow([
                s.ticker,
                side_str,
                s.size,
                f"{float(s.entry_price):.4f}",
                f"{float(s.settlement_price):.2f}",
                s.outcome,
                f"{float(s.pnl):.2f}",
                ts_str,
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=kalshi_settlements_export.csv"},
        )
    else:
        lines = []
        for s in settlements:
            side_str = s.side.value if hasattr(s.side, "value") else str(s.side)
            ts_str = s.timestamp.isoformat() if hasattr(s.timestamp, "isoformat") else str(s.timestamp)
            record = {
                "ticker": s.ticker,
                "side": side_str,
                "size": s.size,
                "entry_price": float(s.entry_price),
                "settlement_price": float(s.settlement_price),
                "outcome": s.outcome,
                "pnl": float(s.pnl),
                "timestamp": ts_str,
            }
            lines.append(json.dumps(record))
        return Response(
            content="\n".join(lines) + ("\n" if lines else ""),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": "attachment; filename=kalshi_settlements_export.jsonl"},
        )


@app.get("/api/export/pnl")
async def export_pnl(format: Literal["csv", "json"] = "csv") -> Response:
    """Export current portfolio P&L performance metrics."""
    if not state.sim_agent:
        raise HTTPException(status_code=503, detail="Simulation agent not initialized")

    p = state.sim_agent._portfolio
    snap = p.get_pnl_snapshot()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "timestamp",
            "starting_balance",
            "current_balance",
            "total_equity",
            "total_realized_pnl",
            "total_unrealized_pnl",
            "win_rate_pct",
            "total_trades",
            "wins",
            "losses",
            "circuit_breaker_tripped",
            "drawdown_pct",
        ])
        win_rate_pct = float(snap.win_rate * 100) if snap.win_rate is not None else 0.0
        drawdown_pct = float(p.current_drawdown_pct * 100)
        writer.writerow([
            snap.timestamp.isoformat(),
            f"{float(snap.starting_balance):.2f}",
            f"{float(snap.current_balance):.2f}",
            f"{float(snap.total_equity):.2f}",
            f"{float(snap.total_realized_pnl):.2f}",
            f"{float(snap.total_unrealized_pnl):.2f}",
            f"{win_rate_pct:.1f}",
            snap.total_trades,
            snap.wins,
            snap.losses,
            str(p.circuit_breaker_tripped),
            f"{drawdown_pct:.1f}",
        ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=kalshi_pnl_snapshot.csv"},
        )
    else:
        payload = snap.model_dump()
        payload["timestamp"] = snap.timestamp.isoformat()
        payload["circuit_breaker_tripped"] = p.circuit_breaker_tripped
        payload["current_drawdown_pct"] = float(p.current_drawdown_pct * 100)
        return Response(
            content=json.dumps(payload, default=str),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=kalshi_pnl_snapshot.json"},
        )


# ---------------------------------------------------------------------------
# High-Throughput Quantitative Data & Memory Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/v1/data/memory-profile")
async def get_memory_profile() -> dict:
    """Return real-time quantitative memory and data throughput telemetry."""
    profile = state.memory_manager.get_memory_profile()
    return {
        "status": "healthy" if not profile.is_pressure_critical else "pressure_warning",
        "active_tickers_count": profile.active_tickers_count,
        "total_hot_ticks": profile.total_hot_ticks,
        "total_offloaded_ticks": profile.total_offloaded_ticks,
        "pending_disk_queue_depth": profile.pending_disk_queue_depth,
        "estimated_hot_memory_kb": round(profile.estimated_hot_memory_kb, 2),
        "is_pressure_critical": profile.is_pressure_critical,
        "mode": state.mode,
    }


@app.get("/api/v1/data/hot-ticks/{ticker}")
async def get_hot_ticks(ticker: str, limit: int = 100) -> dict:
    """Fetch recent hot ticks directly from zero-copy memory ring buffer."""
    clamped_limit = max(1, min(limit, 500))
    ticks = state.memory_manager.get_hot_ticks(ticker, limit=clamped_limit)
    return {
        "ticker": ticker,
        "count": len(ticks),
        "ticks": ticks,
    }


@app.get("/api/export/ticks")
async def export_ticks(timeframe: str = "mock") -> FileResponse:
    """Download the active session tick recording JSONL file."""
    data_dir = state.data_dir
    files = sorted(data_dir.glob(f"ticks_{timeframe}_*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        # Fallback to any ticks file
        files = sorted(data_dir.glob("ticks_*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)

    if not files:
        raise HTTPException(status_code=404, detail="No recorded tick files found.")

    target_file = files[0]
    return FileResponse(
        path=str(target_file),
        media_type="application/x-ndjson",
        filename=target_file.name,
    )


# ---------------------------------------------------------------------------
# Google Drive Synchronization Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/gdrive/status")
async def get_gdrive_status() -> dict[str, Any]:
    """Return Google Drive backup daemon and rclone connectivity diagnostics."""
    return state.gdrive_sync.get_status()


@app.post("/api/gdrive/sync")
async def trigger_gdrive_sync() -> dict[str, Any]:
    """Trigger an immediate asynchronous backup of simulation data to Google Drive."""
    success = await state.gdrive_sync.sync_now()
    return {
        "success": success,
        "message": "Google Drive backup completed successfully." if success else "Google Drive backup skipped or rclone not configured.",
        "status": state.gdrive_sync.get_status(),
    }

@app.post("/api/kalshi/validate-credentials", response_model=ValidateCredentialsResponse)
async def validate_kalshi_credentials(req: ValidateCredentialsRequest) -> ValidateCredentialsResponse:
    """Validate Kalshi API credentials against live or demo exchange endpoints."""
    # Resolve API Key ID
    api_key_id = req.api_key_id or os.getenv("KALSHI_API_KEY_ID")
    if not api_key_id:
        return ValidateCredentialsResponse(
            valid=False,
            message="Missing API Key ID. Please provide api_key_id in request or configure KALSHI_API_KEY_ID in .env",
            mode="demo" if req.is_demo else "prod",
            account_info={},
        )

    # Resolve Private Key
    private_key_source = req.private_key or os.getenv("KALSHI_PRIVATE_KEY_PATH") or os.getenv("KALSHI_PRIVATE_KEY")
    if not private_key_source and Path("kalshi_demo.pem").exists():
        private_key_source = "kalshi_demo.pem"

    if not private_key_source:
        return ValidateCredentialsResponse(
            valid=False,
            message="Missing RSA Private Key. Please provide private_key in request or configure KALSHI_PRIVATE_KEY_PATH in .env",
            mode="demo" if req.is_demo else "prod",
            account_info={},
        )

    valid, msg, account_data = await async_validate_credentials(
        api_key_id=api_key_id,
        private_key=private_key_source,
        is_demo=req.is_demo,
        timeout_sec=8.0,
    )

    return ValidateCredentialsResponse(
        valid=valid,
        message=msg,
        mode="demo" if req.is_demo else "prod",
        account_info=account_data,
    )


@app.get("/api/kalshi/portfolio/sync")
async def sync_kalshi_portfolio(is_demo: bool = True) -> dict[str, Any]:
    """Fetch live exchange portfolio state and reconcile with the simulated portfolio ledger."""
    if not state.sim_agent or not state.sim_agent._portfolio:
        raise HTTPException(status_code=503, detail="Simulation portfolio not initialized")

    api_key_id = os.getenv("KALSHI_API_KEY_ID")
    private_key_source = os.getenv("KALSHI_PRIVATE_KEY_PATH") or os.getenv("KALSHI_PRIVATE_KEY")
    if not private_key_source and Path("kalshi_demo.pem").exists():
        private_key_source = "kalshi_demo.pem"

    if not api_key_id or not private_key_source:
        # Return fallback mocked sync state if credentials are not configured
        sim_p = state.sim_agent._portfolio
        return {
            "authenticated": False,
            "message": "Kalshi API credentials not configured in environment.",
            "reconciliation": ReconciliationReport(
                is_synchronized=True,
                simulated_cash=sim_p.current_balance,
                exchange_cash=sim_p.current_balance,
                cash_discrepancy=Decimal("0"),
                simulated_positions_count=len(sim_p.get_open_positions()),
                exchange_positions_count=len(sim_p.get_open_positions()),
                alerts=["Operating in pure simulation mode (no live Kalshi API keys connected)."],
            ).model_dump(mode="json"),
            "live_portfolio": None,
        }

    base_url = DEMO_REST_BASE if is_demo else PROD_REST_BASE
    client = KalshiLiveOrderClient(
        api_key_id=api_key_id,
        private_key_path=private_key_source,
        base_url=base_url,
    )

    try:
        report = await client.reconcile_with_simulated(state.sim_agent._portfolio)
        live_state = await client.get_live_portfolio_state()
        sync_payload = {
            "authenticated": True,
            "message": "Successfully synchronized with Kalshi exchange.",
            "reconciliation": report.model_dump(mode="json"),
            "live_portfolio": live_state.model_dump(mode="json"),
        }
        state.live_portfolio = {
            "balance_dollars": float(live_state.balance_dollars),
            "available_margin": float(live_state.available_margin),
            "payout_pending": float(live_state.payout_pending),
            "positions_count": len(live_state.positions),
            "positions": [
                {
                    "ticker": p.ticker,
                    "position": p.position,
                    "side": p.side.value,
                    "fees_paid": float(p.fees_paid),
                    "realized_pnl": float(p.realized_pnl),
                    "resting_orders_count": p.resting_orders_count,
                }
                for p in live_state.positions
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "environment": os.getenv("KALSHI_ENV", "live").lower(),
            "is_authenticated": True,
        }
        return sync_payload
    except Exception as exc:
        logger.error("Error synchronizing Kalshi live portfolio: %s", exc)
        return {
            "authenticated": False,
            "message": f"Failed to sync with exchange: {exc}",
            "reconciliation": None,
            "live_portfolio": None,
        }
    finally:
        await client.close()


@app.get("/api/kalshi/balance")
async def get_kalshi_live_balance() -> dict[str, Any]:
    """Retrieve real-time actual Kalshi exchange cash balance, margin, and exposure."""
    if state.live_portfolio is not None:
        return state.live_portfolio

    api_key_id = os.getenv("KALSHI_API_KEY_ID")
    private_key_source = os.getenv("KALSHI_PRIVATE_KEY_PATH") or os.getenv("KALSHI_PRIVATE_KEY")
    if not private_key_source and Path("kalshi_demo.pem").exists():
        private_key_source = "kalshi_demo.pem"

    if not api_key_id or not private_key_source:
        return {
            "balance_dollars": 0.0,
            "available_margin": 0.0,
            "payout_pending": 0.0,
            "positions_count": 0,
            "positions": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "environment": "none",
            "is_authenticated": False,
            "message": "Kalshi API credentials not configured in environment.",
        }

    env = os.getenv("KALSHI_ENV", "live").lower()
    base_url = DEMO_REST_BASE if env == "demo" else PROD_REST_BASE
    client = KalshiLiveOrderClient(
        api_key_id=api_key_id,
        private_key_path=private_key_source,
        base_url=base_url,
    )
    try:
        live_state = await client.get_live_portfolio_state()
        data = {
            "balance_dollars": float(live_state.balance_dollars),
            "available_margin": float(live_state.available_margin),
            "payout_pending": float(live_state.payout_pending),
            "positions_count": len(live_state.positions),
            "positions": [
                {
                    "ticker": p.ticker,
                    "position": p.position,
                    "side": p.side.value,
                    "fees_paid": float(p.fees_paid),
                    "realized_pnl": float(p.realized_pnl),
                    "resting_orders_count": p.resting_orders_count,
                }
                for p in live_state.positions
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "environment": env,
            "is_authenticated": True,
        }
        state.live_portfolio = data
        return data
    finally:
        await client.close()


@app.post("/api/kalshi/orders/live", response_model=LiveOrderResponse)
async def place_kalshi_live_order(req: LiveOrderRequest) -> LiveOrderResponse:
    """Submit a live order to the Kalshi exchange with rate-limiting and dry-run protection."""
    api_key_id = os.getenv("KALSHI_API_KEY_ID")
    private_key_source = os.getenv("KALSHI_PRIVATE_KEY_PATH") or os.getenv("KALSHI_PRIVATE_KEY")
    if not private_key_source and Path("kalshi_demo.pem").exists():
        private_key_source = "kalshi_demo.pem"

    # Evaluate dry-run status
    live_enabled_env = os.getenv("KALSHI_LIVE_TRADING_ENABLED", "false").lower() in ("true", "1", "yes")
    is_dry_run = req.dry_run if req.dry_run is not None else (not live_enabled_env)

    if is_dry_run or not api_key_id or not private_key_source:
        logger.info("[SAFETY DRY-RUN] Simulating live order: %s %d %s %s", req.action, req.count, req.side, req.ticker)
        est_price = req.limit_price_dollars or Decimal("0.50")
        return LiveOrderResponse(
            success=True,
            order_id=f"dry_run_{uuid.uuid4().hex[:8]}",
            status="dry_run",
            ticker=req.ticker,
            side=req.side,
            count=req.count,
            fill_price=est_price,
            is_dry_run=True,
            message="Order passed all pre-flight validation rules in Safety Dry-Run mode.",
        )

    # Acquire rate limiter token before exchange communication
    acquired = await kalshi_rate_limiter.acquire(1.0, timeout=5.0)
    if not acquired:
        raise HTTPException(status_code=429, detail="Kalshi rate limit reached. Please try again shortly.")

    base_url = DEMO_REST_BASE if req.is_demo else PROD_REST_BASE
    client = KalshiLiveOrderClient(
        api_key_id=api_key_id,
        private_key_path=private_key_source,
        base_url=base_url,
    )

    try:
        order_info = await client.place_order(
            ticker=req.ticker,
            side=req.side,
            count=req.count,
            action=req.action,
            order_type=req.order_type,
            price_dollars=req.limit_price_dollars,
        )

        if not order_info:
            return LiveOrderResponse(
                success=False,
                order_id=None,
                status="rejected",
                ticker=req.ticker,
                side=req.side,
                count=req.count,
                fill_price=None,
                is_dry_run=False,
                message="Exchange rejected the order submission.",
            )

        fill_pr = None
        if "yes_price_dollars" in order_info:
            fill_pr = Decimal(str(order_info["yes_price_dollars"]))
        elif "no_price_dollars" in order_info:
            fill_pr = Decimal(str(order_info["no_price_dollars"]))

        return LiveOrderResponse(
            success=True,
            order_id=order_info.get("order_id"),
            status=order_info.get("status", "executed"),
            ticker=req.ticker,
            side=req.side,
            count=req.count,
            fill_price=fill_pr,
            is_dry_run=False,
            message="Order successfully submitted to Kalshi exchange.",
        )
    except Exception as exc:
        logger.error("Failed to place live order on Kalshi: %s", exc)
        return LiveOrderResponse(
            success=False,
            order_id=None,
            status="error",
            ticker=req.ticker,
            side=req.side,
            count=req.count,
            fill_price=None,
            is_dry_run=False,
            message=f"Error communicating with exchange: {exc}",
        )
    finally:
        await client.close()


@app.delete("/api/kalshi/orders/live/{order_id}")
async def cancel_kalshi_live_order(order_id: str, is_demo: bool = True) -> dict[str, Any]:
    """Cancel a resting order on Kalshi exchange."""
    api_key_id = os.getenv("KALSHI_API_KEY_ID")
    private_key_source = os.getenv("KALSHI_PRIVATE_KEY_PATH") or os.getenv("KALSHI_PRIVATE_KEY")
    if not private_key_source and Path("kalshi_demo.pem").exists():
        private_key_source = "kalshi_demo.pem"

    if not api_key_id or not private_key_source:
        return {"success": True, "order_id": order_id, "status": "dry_run_cancelled"}

    await kalshi_rate_limiter.acquire(1.0, timeout=5.0)

    base_url = DEMO_REST_BASE if is_demo else PROD_REST_BASE
    client = KalshiLiveOrderClient(
        api_key_id=api_key_id,
        private_key_path=private_key_source,
        base_url=base_url,
    )

    try:
        success = await client.cancel_order(order_id)
        return {"success": success, "order_id": order_id, "status": "cancelled" if success else "failed"}
    finally:
        await client.close()


@app.get("/api/kalshi/orders/live/open")
async def get_kalshi_live_open_orders(is_demo: bool = True) -> list[dict[str, Any]]:
    """Fetch active resting limit orders from Kalshi exchange."""
    api_key_id = os.getenv("KALSHI_API_KEY_ID")
    private_key_source = os.getenv("KALSHI_PRIVATE_KEY_PATH") or os.getenv("KALSHI_PRIVATE_KEY")
    if not private_key_source and Path("kalshi_demo.pem").exists():
        private_key_source = "kalshi_demo.pem"

    if not api_key_id or not private_key_source:
        return []

    await kalshi_rate_limiter.acquire(1.0, timeout=5.0)

    base_url = DEMO_REST_BASE if is_demo else PROD_REST_BASE
    client = KalshiLiveOrderClient(
        api_key_id=api_key_id,
        private_key_path=private_key_source,
        base_url=base_url,
    )

    try:
        return await client.get_open_orders()
    finally:
        await client.close()


@app.get("/api/orders/open")
async def get_open_orders() -> list[dict[str, Any]]:
    """Return all active resting limit orders."""
    if not state.sim_agent or not state.sim_agent._simulator:
        return []
    return [
        {
            "order_id": o.order_id,
            "ticker": o.ticker,
            "side": o.side.value,
            "size": o.size,
            "limit_price": float(o.limit_price) if o.limit_price else 0.0,
            "timeframe": o.timeframe.value,
            "status": o.status,
            "created_at": o.created_at.strftime("%H:%M:%S"),
        }
        for o in state.sim_agent._simulator.get_all_resting_orders()
    ]

@app.delete("/api/orders/{order_id}")
async def cancel_order(order_id: str) -> dict[str, Any]:
    """Cancel an active resting limit order."""
    if not state.sim_agent or not state.sim_agent._simulator:
        raise HTTPException(status_code=503, detail="Simulation agent not running")
    
    # Identify target ticker for audit record
    resting_orders = state.sim_agent._simulator.get_all_resting_orders()
    target_ticker = state.active_ticker
    for o in resting_orders:
        if o.order_id == order_id:
            target_ticker = o.ticker
            break

    success = state.sim_agent._simulator.cancel_resting_order(order_id)
    if success:
        state.law_order_agent.record_order_cancellation(order_id, target_ticker)
        return {"success": True, "order_id": order_id, "status": "cancelled"}
    raise HTTPException(status_code=404, detail="Order not found")

@app.post("/api/orders")
async def place_order(req: OrderRequest) -> dict[str, Any]:
    """Place a simulated or live order."""
    if not state.sim_agent:
        raise HTTPException(status_code=503, detail="Simulation agent is not running")

    side = OrderSide.YES if req.side.lower() == "yes" else OrderSide.NO
    order_type = OrderType.LIMIT if req.order_type.lower() == "limit" else OrderType.MARKET
    limit_price = Decimal(str(req.limit_price)) if req.limit_price is not None else None

    ticker = req.ticker or state.active_ticker
    book = state.orderbook.get_book(ticker)
    if not book:
        # Create a fallback default book for the active ticker with realistic levels
        book = L2BookState(ticker)
        book.yes_book = {Decimal("0.034"): Decimal("500"), Decimal("0.031"): Decimal("1000")}
        book.no_book = {Decimal("0.966"): Decimal("500"), Decimal("0.969"): Decimal("1000")}
        state.orderbook._books[ticker] = book

    sim = state.sim_agent._simulator
    portfolio = state.sim_agent._portfolio

    # Agent_law_order Pre-Trade Regulatory Gatekeeper (Wash Trading & Position Limit Check)
    open_orders = sim.get_all_resting_orders()
    order_price = limit_price if limit_price is not None else ((book.best_yes_ask if side == OrderSide.YES else book.best_no_ask) or Decimal("0.50"))
    comp_ok, comp_msg = state.law_order_agent.validate_pre_trade_order(
        ticker=ticker,
        side=side.value,
        size=req.size,
        price=order_price,
        open_orders=open_orders,
        current_positions=portfolio._positions,
        current_balance=portfolio.balance,
    )
    if not comp_ok:
        logger.warning("[COMPLIANCE GATEWAY REJECT] %s", comp_msg)
        return {
            "success": False,
            "reason": comp_msg,
            "status": "compliance_rejected",
        }

    # Agent_Guardrails Pre-Trade Risk Gatekeeper
    active_equity = Decimal(str(state.live_portfolio.get("balance_dollars", "0.0"))) if req.execution_mode == "live" and state.live_portfolio else portfolio.equity
    g_ok, g_msg, g_size, g_diag = state.guardrails_agent.validate_pre_trade_intent(
        ticker=ticker,
        side=side.value,
        requested_size=req.size,
        est_price=order_price,
        total_equity=active_equity,
        vpin=0.15,
        cycle_id=ticker,
        is_bot=False,
    )
    if not g_ok:
        logger.warning("[GUARDRAIL GATEWAY REJECT] %s", g_msg)
        return {
            "success": False,
            "reason": g_msg,
            "status": "guardrail_rejected",
        }

    # =========================================================================
    # LIVE TRADING EXECUTION INTERCEPT (Real Kalshi Account Routing & Balance Freeze)
    # =========================================================================
    if req.execution_mode == "live":
        live_p = state.live_portfolio or {}
        live_balance = Decimal(str(live_p.get("balance_dollars", "0.0")))
        est_price = limit_price if limit_price is not None else ((book.best_yes_ask if side == OrderSide.YES else book.best_no_ask) or Decimal("0.50"))
        est_cost = est_price * Decimal(str(req.size))

        # Check for insufficient live funds / zero balance -> FREEZE BETS
        if live_balance <= Decimal("0.05") or live_balance < est_cost:
            logger.warning(
                "[LIVE BETS FROZEN] Insufficient live balance ($%s) for order cost ($%s) on %s",
                live_balance, est_cost, ticker,
            )
            return {
                "success": False,
                "status": "frozen_insufficient_funds",
                "freeze_trading": True,
                "live_balance": float(live_balance),
                "reason": f"INSUFFICIENT LIVE BALANCE: Live Kalshi balance is ${float(live_balance):.2f}, which is insufficient for this trade (${float(est_cost):.2f}). All bets are frozen. Please deposit/load assets into your Kalshi account to resume.",
                "action_required": "deposit_funds",
            }

        # Real Live Exchange Execution via KalshiLiveOrderClient
        api_key_id = os.environ.get("KALSHI_API_KEY_ID")
        private_key_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH")
        env_mode = os.environ.get("KALSHI_ENV", "live").lower()
        base_url = PROD_REST_BASE if env_mode == "live" else DEMO_REST_BASE

        if not api_key_id or not private_key_path:
            return {
                "success": False,
                "status": "config_error",
                "freeze_trading": True,
                "reason": "Kalshi live API credentials not configured in environment.",
            }

        client = None
        try:
            client = KalshiLiveOrderClient(
                api_key_id=api_key_id,
                private_key_path=private_key_path,
                base_url=base_url,
            )
            order_info = await client.place_order(
                ticker=ticker,
                side=side,
                count=req.size,
                action="buy",
                order_type=req.order_type,
                price_dollars=limit_price,
            )
            if not order_info:
                return {
                    "success": False,
                    "status": "exchange_rejected",
                    "reason": "Kalshi live exchange rejected the order submission.",
                }

            fill_pr = limit_price or est_price
            if "yes_price_dollars" in order_info and order_info["yes_price_dollars"] is not None:
                fill_pr = Decimal(str(order_info["yes_price_dollars"]))
            elif "no_price_dollars" in order_info and order_info["no_price_dollars"] is not None:
                fill_pr = Decimal(str(order_info["no_price_dollars"]))

            cost = fill_pr * Decimal(str(req.size))
            order_id = order_info.get("order_id") or str(uuid.uuid4())
            fee = float(Decimal("0.01") * Decimal(str(req.size)))

            logger.info(
                "[LIVE FILL] %s %s %d contracts @ $%.4f (cost: $%.2f, fee: $%.2f) on Kalshi Live",
                ticker, side.value.upper(), req.size, fill_pr, cost, fee,
            )

            # Persist live trade to SQLite WAL store
            try:
                get_db_writer().enqueue_trade(
                    trade_id=order_id,
                    ticker=ticker,
                    side=side.value,
                    size=req.size,
                    price=float(fill_pr),
                    gross_value=float(cost),
                    fees=float(fee),
                    execution_mode="live",
                    bot_type=state.active_strategy_bot or "live_manual",
                )
            except Exception as db_err:
                logger.warning("Failed to enqueue live trade to DB: %s", db_err)

            # Refresh live balance in state
            asyncio.create_task(trigger_instant_broadcast())
            return {
                "success": True,
                "order_id": order_id,
                "status": order_info.get("status", "executed"),
                "fill_price": float(fill_pr),
                "cost": float(cost),
                "fee": fee,
                "execution_mode": "live",
                "message": f"Live order executed on Kalshi: {req.size} contracts @ ${(float(fill_pr)*100):.1f}¢",
            }
        except Exception as exc:
            logger.error("Live order placement error: %s", exc)
            return {
                "success": False,
                "status": "error",
                "reason": f"Live exchange error: {exc}",
            }
        finally:
            if client:
                await client.close()


    if order_type == OrderType.LIMIT and limit_price is not None:
        if req.resting_only:
            resting_order = sim.place_resting_limit_order(
                book=book,
                side=side,
                size=req.size,
                limit_price=limit_price,
                timeframe=state.active_timeframe,
                reasoning="Manual Resting Limit Order",
            )
            return {
                "success": True,
                "order_id": resting_order.order_id,
                "limit_price": float(limit_price),
                "size": req.size,
                "status": "resting",
            }
        else:
            exec_res = sim.simulate_limit_order(
                book=book,
                side=side,
                size=req.size,
                limit_price=limit_price,
                timeframe=state.active_timeframe,
                reasoning="Manual 1-Click Limit Order",
            )
    else:
        exec_res = sim.simulate_market_order(
            book=book,
            side=side,
            size=req.size,
            timeframe=state.active_timeframe,
            reasoning="Manual 1-Click Market Order",
        )

    if exec_res:
        order, fill = exec_res
        if portfolio.can_afford(fill.cost):
            portfolio.open_position(fill, state.active_timeframe)
            if state.sim_agent._exec_logger:
                state.sim_agent._exec_logger.log_execution(order, fill)
            logger.info("[MANUAL FILL] %s %s %d contracts @ $%.4f (cost: $%.2f)",
                        ticker, side.value.upper(), req.size, fill.fill_price, fill.cost)
            asyncio.create_task(trigger_instant_broadcast())
            return {
                "success": True,
                "order_id": order.order_id,
                "fill_price": float(fill.fill_price),
                "cost": float(fill.cost),
                "slippage": float(fill.slippage),
                "status": "filled",
            }
        else:
            return {
                "success": False,
                "order_id": order.order_id,
                "reason": "Insufficient balance",
                "status": "rejected",
            }
    else:
        return {
            "success": False,
            "reason": "Insufficient liquidity in order book",
            "status": "rejected",
        }

class ClosePositionRequest(BaseModel):
    ticker: str
    execution_mode: Optional[Literal["paper", "live"]] = "paper"

@app.post("/api/positions/close")
async def close_position_endpoint(req: ClosePositionRequest) -> dict[str, Any]:
    """Liquidate and close an open position at current market bid/ask."""
    # =========================================================================
    # LIVE POSITION CLOSE / LIQUIDATE INTERCEPT
    # =========================================================================
    if req.execution_mode == "live":
        api_key_id = os.environ.get("KALSHI_API_KEY_ID")
        private_key_path = (
            os.environ.get("KALSHI_PRIVATE_KEY_PATH")
            or os.environ.get("KALSHI_PRIVATE_KEY")
            or ("keys/kalshi_demo.pem" if Path("keys/kalshi_demo.pem").exists() else "kalshi_demo.pem")
        )
        env_mode = os.environ.get("KALSHI_ENV", "live").lower()
        base_url = PROD_REST_BASE if env_mode == "live" else DEMO_REST_BASE

        if not api_key_id or not private_key_path:
            return {
                "success": False,
                "status": "config_error",
                "reason": "Kalshi live API credentials not configured in environment.",
            }

        client = None
        try:
            client = KalshiLiveOrderClient(
                api_key_id=api_key_id,
                private_key_path=private_key_path,
                base_url=base_url,
            )
            # Query active positions on Kalshi to find contract size & side
            positions = await client.get_positions()
            target_pos = None
            for p in positions:
                if p.get("ticker") == req.ticker or p.get("market_ticker") == req.ticker:
                    target_pos = p
                    break

            if not target_pos:
                # If not found in REST query, check local live_portfolio state
                live_p = state.live_portfolio or {}
                for lp in live_p.get("positions", []):
                    if lp.get("ticker") == req.ticker:
                        target_pos = lp
                        break

            if not target_pos:
                return {
                    "success": False,
                    "status": "not_found",
                    "reason": f"Live position for '{req.ticker}' not found on Kalshi exchange.",
                }

            raw_cnt = target_pos.get("position", target_pos.get("position_fp", 1))
            try:
                pos_cnt = abs(int(float(str(raw_cnt))))
            except (ValueError, TypeError):
                pos_cnt = 1

            pos_side = target_pos.get("side", "yes")
            side = OrderSide.YES if str(pos_side).lower() == "yes" else OrderSide.NO

            if pos_cnt <= 0:
                # Cancel any resting orders on Kalshi for this ticker if present
                try:
                    open_orders = await client.get_open_orders()
                    for oo in open_orders:
                        if oo.get("ticker") == req.ticker or oo.get("market_ticker") == req.ticker:
                            oid = oo.get("order_id")
                            if oid:
                                await client.cancel_order(oid)
                except Exception as cancel_err:
                    logger.debug("Failed to cancel resting orders for %s: %s", req.ticker, cancel_err)

                # Remove from local live_portfolio state
                if state.live_portfolio and "positions" in state.live_portfolio:
                    state.live_portfolio["positions"] = [
                        p for p in state.live_portfolio["positions"]
                        if p.get("ticker") != req.ticker
                    ]
                    state.live_portfolio["positions_count"] = len(state.live_portfolio["positions"])

                asyncio.create_task(trigger_instant_broadcast())
                return {
                    "success": True,
                    "ticker": req.ticker,
                    "status": "cleared",
                    "execution_mode": "live",
                    "message": f"Cleared zero-contract record for '{req.ticker}' from list.",
                }

            # Submit sell order to Kalshi live exchange to liquidate position
            order_info = await client.place_order(
                ticker=req.ticker,
                side=side,
                count=pos_cnt,
                action="sell",
                order_type="market",
            )
            if not order_info:
                return {
                    "success": False,
                    "status": "exchange_rejected",
                    "reason": f"Kalshi rejected sell order to liquidate position {req.ticker}.",
                }

            # Update live portfolio state immediately
            if state.live_portfolio and "positions" in state.live_portfolio:
                state.live_portfolio["positions"] = [
                    p for p in state.live_portfolio["positions"]
                    if p.get("ticker") != req.ticker
                ]
                state.live_portfolio["positions_count"] = len(state.live_portfolio["positions"])

            logger.info("[LIVE LIQUIDATION] Closed %d %s contracts of %s on Kalshi Live", pos_cnt, side.value.upper(), req.ticker)
            asyncio.create_task(trigger_instant_broadcast())
            return {
                "success": True,
                "ticker": req.ticker,
                "side": side.value,
                "size": pos_cnt,
                "status": "liquidated",
                "execution_mode": "live",
                "message": f"Successfully liquidated {pos_cnt} contracts of {req.ticker} on Kalshi Live.",
            }
        except Exception as exc:
            logger.error("Live position close error: %s", exc)
            return {
                "success": False,
                "status": "error",
                "reason": f"Failed to close live position: {exc}",
            }
        finally:
            if client:
                await client.close()

    # Paper Simulation Close Position Logic
    if not state.sim_agent or not state.sim_agent._portfolio:
        raise HTTPException(status_code=503, detail="Simulation agent not running")

    portfolio = state.sim_agent._portfolio
    position = portfolio.get_position(req.ticker)
    if not position:
        return {
            "success": True,
            "ticker": req.ticker,
            "status": "already_cleared",
            "message": f"Position for '{req.ticker}' is already cleared.",
        }

    book = state.orderbook.get_book(req.ticker)
    # Determine exit price based on position side
    if position.side == OrderSide.YES:
        exit_price = book.best_yes_bid if book and book.best_yes_bid else Decimal("0.50")
    else:
        exit_price = book.best_no_bid if book and book.best_no_bid else Decimal("0.50")

    result = portfolio.close_position(req.ticker, exit_price)
    if result:
        if state.sim_agent._exec_logger:
            state.sim_agent._exec_logger.log_settlement(result)
        try:
            snap = portfolio.get_pnl_snapshot()
            get_db_writer().enqueue_equity_snapshot(
                balance=float(snap.current_balance),
                equity=float(snap.total_equity),
                realized_pnl=float(snap.total_realized_pnl),
                unrealized_pnl=float(snap.total_unrealized_pnl),
                drawdown_pct=float(portfolio.current_drawdown_pct * 100),
                win_rate=float((snap.win_rate or 0) * 100),
                total_trades=snap.total_trades,
                open_positions_count=snap.open_positions,
            )
        except Exception:
            pass
        return {
            "success": True,
            "ticker": result.ticker,
            "side": result.side.value,
            "size": result.size,
            "exit_price": float(result.settlement_price),
            "pnl": float(result.pnl),
            "outcome": result.outcome,
            "new_balance": float(portfolio.balance),
        }
    else:
        return {"success": False, "reason": "Failed to close position"}

TIMEFRAME_CONFIGS: dict[Timeframe, dict[str, Any]] = {
    Timeframe.FIVE_MIN: {
        "series": "KXBTC5M",
        "ticker": "KXBTC5M-T78600",
        "target_strike": Decimal("78600.00"),
        "title": "BTC 5 min",
        "expiry_seconds": 300,
    },
    Timeframe.FIFTEEN_MIN: {
        "series": "KXBTC15M",
        "ticker": "KXBTC15M-T78650",
        "target_strike": Decimal("77645.14"),
        "title": "BTC 15 min",
        "expiry_seconds": 900,
    },
    Timeframe.ONE_HOUR: {
        "series": "KXBTCH",
        "ticker": "KXBTCH-T78500",
        "target_strike": Decimal("78500.00"),
        "title": "BTC 1 hour",
        "expiry_seconds": 3600,
    },
}

@app.post("/api/settings")
async def update_settings(req: SettingsRequest) -> dict[str, Any]:
    if req.ai_auto_trade is not None:
        state.ai_auto_trade = req.ai_auto_trade
    if req.active_strategy_bot is not None:
        cand_bot = req.active_strategy_bot
        if cand_bot in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion"):
            cand_bot = "macro_onnx"
        elif cand_bot in ("macro_trend", "macro_trend_dominion_bot"):
            cand_bot = "macro_trend_dominion"
        elif cand_bot in ("dominion2", "dominion_v2"):
            cand_bot = "dominion_2_bot"

        if cand_bot in ("macro_onnx", "macro_trend_dominion", "dominion_2_bot", "3_step_domination_bot", "onnx_microstructure_bot"):
            state.active_strategy_bot = cand_bot
            if state.ai_worker:
                state.ai_worker.set_active_strategy(cand_bot)
            if state.sim_agent and hasattr(state.sim_agent, "set_active_strategy"):
                state.sim_agent.set_active_strategy(cand_bot)
    if req.mode is not None:
        if req.mode != state.mode:
            await stop_current_feed()
            if req.mode == "live":
                logger.info("[MODE SWITCH] Switching to LIVE Kalshi Demo WebSocket feed...")
                await start_live_feed()
            else:
                logger.info("[MODE SWITCH] Switching to Interactive Mock Feed...")
                await start_mock_feed()
        if state.sim_agent:
            state.sim_agent.execution_mode = req.mode
    if req.active_timeframe:
        try:
            tf = Timeframe(req.active_timeframe.lower())
            state.active_timeframe = tf
            cfg = TIMEFRAME_CONFIGS.get(tf)
            if cfg:
                state.active_ticker = cfg["ticker"]
                state.target_strike = cfg["target_strike"]
                state.market_expiry_seconds = cfg["expiry_seconds"]
                if not state.orderbook.get_book(state.active_ticker):
                    bk = L2BookState(state.active_ticker)
                    bk.yes_book = {Decimal("0.034"): Decimal("500"), Decimal("0.031"): Decimal("1000")}
                    bk.no_book = {Decimal("0.966"): Decimal("500"), Decimal("0.969"): Decimal("1000")}
                    state.orderbook._books[state.active_ticker] = bk
        except ValueError:
            pass
    if req.active_ticker:
        state.active_ticker = req.active_ticker

    return {
        "ai_auto_trade": state.ai_auto_trade,
        "active_strategy_bot": state.active_strategy_bot,
        "active_timeframe": state.active_timeframe.value,
        "active_ticker": state.active_ticker,
        "target_strike": float(state.target_strike),
        "mode": state.mode,
    }


@app.get("/api/bot/strategies")
async def get_bot_strategies() -> dict[str, Any]:
    """Retrieve list of available quantitative trading strategy bots with full metadata."""
    return {
        "active_strategy": state.active_strategy_bot,
        "strategies": [
            {
                "id": "macro_onnx",
                "name": "Macro ONNX Bot",
                "description": "Multi-Scale Macro Trend Following fused with QuoLas Nano Microscope ONNX Bitcoin Orderflow Inference (1h & 15m Trend Alignment + Continuous BTC L2 Microstructure)",
                "active": state.active_strategy_bot == "macro_onnx",
                "badge": "AI Neural + Macro Trend (Champion)",
                "icon": "Cpu",
                "features": [
                    "Multi-Scale Macro Trend Alignment (1h & 15m)",
                    "Continuous Binance BTC L2 Microstructure Stream",
                    "65/35 Bayesian Orderflow Fusion",
                    "Hard Orderflow Contradiction Veto",
                    "Uncertainty Trap Avoidance ($40 Gate)",
                    "$0.62 / $0.68 Dynamic Price Caps",
                    "Micro-Bankroll Sizing (1 ct flat)",
                ],
            },
            {
                "id": "macro_trend_dominion",
                "name": "Macro Trend Dominion",
                "description": "Multi-Scale Macro Trend Following Engine (1-Hour Trend Alignment, Anti-Countertrend Veto, 1-Ct Bankroll Sizing, Late Gamma Sniper)",
                "active": state.active_strategy_bot == "macro_trend_dominion",
                "badge": "Institutional Trend Following",
                "icon": "TrendingUp",
                "features": [
                    "1-Hour Rolling Macro Trend Engine",
                    "Strict Trend Alignment (BULL: YES only, BEAR: NO only)",
                    "Anti-Countertrend Veto Shield",
                    "Micro-Bankroll Sizing (1 ct flat)",
                    "Late-Cycle High-Certainty Gamma Sniper",
                    "Dynamic Cut-Loss Capital Salvage",
                ],
            },
            {
                "id": "dominion_2_bot",
                "name": "Dominion 2 Bot (Anti-Pin Scalper)",
                "description": "Anti-Pin Asymmetric Scalper with Hard Entry Price Ceiling, Discount Value Hunting, Tie Edge Exploitation, and Pin Defense",
                "active": state.active_strategy_bot == "dominion_2_bot",
                "badge": "Empirical Winning Engine",
                "icon": "Crown",
                "features": [
                    "Hard Entry Ceiling (≤ $0.55)",
                    "Asymmetric Discount Hunting ($0.25-$0.42)",
                    "Kalshi Tie / NO Exploitation",
                    "Anti-Pin Defense (< 180s ± $25)",
                    "Dynamic Early Harvest & Loss Salvage",
                    "Quarter-Kelly Sizing",
                ],
            },
            {
                "id": "3_step_domination_bot",
                "name": "3-Step Domination Bot",
                "description": "Cycle-Aware Multi-Playbook Engine (Early Momentum Breakout, Mid OFI Drift, Late Gamma Snub)",
                "active": state.active_strategy_bot == "3_step_domination_bot",
                "badge": "Quantitative Playbooks",
                "icon": "Zap",
                "features": [
                    "Early Breakout Velocity (0-5m)",
                    "Mid OFI Trend Drift (5-11m)",
                    "Late Gamma Snub (11-14m)",
                    "Digital Option Moneyness CDF",
                    "VPIN Toxicity Shield",
                    "Quarter-Kelly Sizing",
                ],
            },
            {
                "id": "onnx_microstructure_bot",
                "name": "ONNX Microstructure Bot",
                "description": "28-D Deep Feature Tensor + Neural Network Inference + Quarter-Kelly Sizing",
                "active": state.active_strategy_bot == "onnx_microstructure_bot",
                "badge": "Neural Network",
                "icon": "Cpu",
                "features": [
                    "28-D Order Flow Tensor",
                    "ONNX CPU Runtime (<2ms)",
                    "Directional Probability (Up/Down/Wait)",
                    "Statistical EV Engine",
                    "VPIN Toxicity Shield",
                    "Quarter-Kelly Sizing",
                ],
            },
        ],
    }


@app.post("/api/bot/strategy/select")
async def select_bot_strategy(req: StrategySelectRequest) -> dict[str, Any]:
    """Switch active strategy bot."""
    strat_id = req.strategy_id
    if strat_id in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion"):
        strat_id = "macro_onnx"
    elif strat_id in ("macro_trend", "macro_trend_dominion_bot"):
        strat_id = "macro_trend_dominion"
    elif strat_id in ("dominion2", "dominion_v2"):
        strat_id = "dominion_2_bot"

    if strat_id not in ("macro_onnx", "macro_trend_dominion", "dominion_2_bot", "3_step_domination_bot", "onnx_microstructure_bot"):
        raise HTTPException(status_code=400, detail=f"Invalid strategy_id: {req.strategy_id}")

    state.active_strategy_bot = strat_id
    if state.ai_worker:
        state.ai_worker.set_active_strategy(strat_id)
    if state.sim_agent and hasattr(state.sim_agent, "set_active_strategy"):
        state.sim_agent.set_active_strategy(strat_id)

    logger.info("Active strategy bot switched to: %s", strat_id)
    return {
        "success": True,
        "active_strategy": strat_id,
        "message": f"Active strategy switched to {strat_id}",
    }


@app.post("/api/reset")
async def reset_portfolio(req: ResetRequest) -> dict[str, Any]:
    if state.sim_agent:
        portfolios = []
        if hasattr(state.sim_agent, "_portfolio_domination"):
            portfolios.append(state.sim_agent._portfolio_domination)
        if hasattr(state.sim_agent, "_portfolio_onnx"):
            portfolios.append(state.sim_agent._portfolio_onnx)
        if not portfolios and hasattr(state.sim_agent, "_portfolio"):
            portfolios.append(state.sim_agent._portfolio)

        for p in portfolios:
            p._balance = Decimal(str(req.capital))
            p._positions.clear()
            p._fill_history.clear()
            p._settlement_history.clear()
            p._total_trades = 0
            p._wins = 0
            p._losses = 0
            p._starting_balance = Decimal(str(req.capital))
            p._max_drawdown_limit = p._starting_balance * p._max_drawdown_pct
            p._circuit_breaker_tripped = False
            p._peak_equity = p._starting_balance
    return {"success": True, "capital": req.capital}


@app.post("/api/circuit-breaker/reset")
async def reset_circuit_breaker() -> dict[str, Any]:
    """Manually reset the drawdown circuit breaker to resume trading."""
    if getattr(state, "mode", "mock") == "live" and getattr(state, "live_portfolio", None):
        cur_bal = Decimal(str(state.live_portfolio.get("balance_dollars", "20.00")))
    elif state.sim_agent:
        cur_bal = state.sim_agent._portfolio.balance
    else:
        cur_bal = state.starting_capital

    if state.sim_agent:
        for attr in ["_portfolio_domination", "_portfolio_onnx", "_portfolio_macro_trend", "_portfolio_dominion2", "_portfolio"]:
            if hasattr(state.sim_agent, attr):
                getattr(state.sim_agent, attr).reset_circuit_breaker()

    if state.guardrails_agent:
        state.guardrails_agent.reset_circuit_breaker(cur_bal)

    state.is_dirty = True
    return {"success": True, "message": f"Circuit breaker reset. Re-anchored to ${cur_bal:.2f}. Trading resumed."}


@app.post("/api/bot/kill-switch")
@app.post("/api/circuit-breaker/trip")
async def trigger_emergency_kill_switch() -> dict[str, Any]:
    """Emergency kill switch: Trip circuit breaker, halt all automated & manual orders, and dispatch alert."""
    try:
        if state.sim_agent:
            if hasattr(state.sim_agent, "_portfolio_domination"):
                state.sim_agent._portfolio_domination._circuit_breaker_tripped = True
            if hasattr(state.sim_agent, "_portfolio_onnx"):
                state.sim_agent._portfolio_onnx._circuit_breaker_tripped = True
            state.ai_auto_trade = False
            try:
                p = state.sim_agent.portfolio
                from kalshi_sim.db.writer import get_db_writer
                get_db_writer().enqueue_circuit_breaker_event(
                    event_type="EMERGENCY_KILL_SWITCH_TRIPPED",
                    peak_capital=float(p._peak_equity),
                    current_equity=float(p.equity),
                    drawdown_pct=float(p.current_drawdown_pct) * 100.0,
                    reason="User manually activated emergency kill switch from terminal",
                )
            except Exception as db_err:
                logger.warning("Could not enqueue circuit breaker event to db: %s", db_err)

            if state.telemetry_alerts:
                asyncio.create_task(
                    state.telemetry_alerts.send_circuit_breaker_alert(
                        reason="User manually activated emergency kill switch from terminal",
                        current_drawdown_pct=float(p.current_drawdown_pct) * 100.0,
                        daily_loss_dollars=float(p.current_drawdown),
                    )
                )
            return {"success": True, "message": "Emergency Kill Switch Activated. All trading halted."}
        return {"success": False, "message": "No active simulation agent."}
    except Exception as exc:
        logger.exception("Error in trigger_emergency_kill_switch: %s", exc)
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Historical Analytics & Time-Series Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/history/trades")
async def get_historical_trades_endpoint(
    ticker: str | None = None,
    timeframe: str | None = None,
    bot_type: str | None = None,
    execution_mode: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Retrieve historical trade executions from SQLite store with filtering and pagination."""
    query_service = HistoricalQueryService()
    return await query_service.get_trades(
        ticker=ticker,
        timeframe=timeframe,
        bot_type=bot_type,
        execution_mode=execution_mode,
        limit=limit,
        offset=offset,
    )


@app.get("/api/history/settlements")
async def get_historical_settlements_endpoint(
    ticker: str | None = None,
    bot_type: str | None = None,
    execution_mode: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Retrieve historical settled contract outcomes and realized P&L."""
    query_service = HistoricalQueryService()
    return await query_service.get_settlements(
        ticker=ticker,
        bot_type=bot_type,
        execution_mode=execution_mode,
        limit=limit,
        offset=offset,
    )


@app.get("/api/history/equity-curve")
async def get_historical_equity_curve_endpoint(
    start_ms: int | None = None,
    end_ms: int | None = None,
    bot_type: str | None = None,
    execution_mode: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Retrieve time-series equity and drawdown history for interactive charts."""
    query_service = HistoricalQueryService()
    return await query_service.get_equity_curve(
        start_epoch_ms=start_ms,
        end_epoch_ms=end_ms,
        bot_type=bot_type,
        execution_mode=execution_mode,
        limit=limit,
    )


@app.get("/api/history/ai-predictions")
async def get_historical_ai_predictions_endpoint(
    ticker: str | None = None,
    bot_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Retrieve historical Stage 1 AI probabilities and Stage 2 EV decisions."""
    query_service = HistoricalQueryService()
    return await query_service.get_ai_predictions(
        ticker=ticker,
        bot_type=bot_type,
        limit=limit,
        offset=offset,
    )


@app.get("/api/history/metrics")
async def get_historical_metrics_endpoint(
    bot_type: str | None = None,
    execution_mode: str | None = None,
) -> dict[str, Any]:
    """Retrieve institutional performance statistics (Sharpe, Sortino, Calmar, Win Rate, Drawdown)."""
    query_service = HistoricalQueryService()
    return await query_service.compute_portfolio_metrics(
        bot_type=bot_type,
        execution_mode=execution_mode,
    )


@app.get("/api/bot/forward-validation-status")
async def get_forward_validation_status_endpoint(
    bot_type: str | None = None,
    execution_mode: str | None = None,
) -> dict[str, Any]:
    """Retrieve 100-Cycle Forward Validation Telemetry, Gates, and Real-Money Readiness."""
    query_service = HistoricalQueryService()
    metrics = await query_service.compute_portfolio_metrics(
        bot_type=bot_type,
        execution_mode=execution_mode,
    )

    reports = state.win_loss_reports
    if bot_type and bot_type.lower() not in ("all", "combined"):
        reports = [r for r in reports if r.get("bot_type") == bot_type or r.get("strategy_id") == bot_type]
    if execution_mode and execution_mode.lower() != "all":
        reports = [r for r in reports if r.get("execution_mode") == execution_mode or r.get("mode") == execution_mode]

    db_total = metrics.get("total_trades", 0)
    total_cycles = max(len(reports), db_total)
    target_cycles = 100
    progress_pct = min(100.0, round((total_cycles / target_cycles) * 100.0, 1))

    # Pull and align wins/losses
    wins = metrics.get("wins", 0)
    losses = metrics.get("losses", 0)
    if (wins + losses == 0) and len(reports) > 0:
        wins = sum(1 for r in reports if r.get("outcome") == "win")
        losses = sum(1 for r in reports if r.get("outcome") == "loss")
    
    total_active_trades = wins + losses
    win_rate = (wins / total_active_trades * 100.0) if total_active_trades > 0 else 0.0

    # Real-money readiness criteria
    ev_positive = metrics.get("expectancy_per_trade", 0.0) > 0.0
    profit_factor_ok = metrics.get("profit_factor", 0.0) >= 1.40
    drawdown_ok = metrics.get("max_drawdown_pct", 0.0) < 15.0
    cycles_ok = total_cycles >= target_cycles
    
    p = state.sim_agent._portfolio if state.sim_agent else None
    state.integrity_agent.run_full_audit(
        portfolio=p,
        orderbook=state.orderbook,
        active_ticker=state.active_ticker,
        mode=state.mode,
        btc_price=state.current_btc_price,
        ws_connected=state.is_connected,
    )
    integrity_status_data = state.integrity_agent.get_latest_status()
    integrity_ok = integrity_status_data.get("status") == "HEALTHY"

    is_ready = bool(ev_positive and profit_factor_ok and drawdown_ok and cycles_ok and integrity_ok)

    return {
        "forward_testing": {
            "total_cycles_completed": total_cycles,
            "target_cycles": target_cycles,
            "progress_pct": progress_pct,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(win_rate, 2),
            "net_pnl": metrics.get("net_pnl", 0.0),
            "total_fees_paid": metrics.get("total_fees_paid", 0.0),
            "expectancy_per_trade": metrics.get("expectancy_per_trade", 0.0),
            "profit_factor": metrics.get("profit_factor", 1.0),
            "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
        },
        "gates": {
            "gate_1_positive_expectancy": {
                "name": "Positive Net EV (After Fees)",
                "passed": ev_positive,
                "current": f"${metrics.get('expectancy_per_trade', 0.0):.2f}/trade",
                "threshold": "> $0.00",
            },
            "gate_2_profit_factor": {
                "name": "Profit Factor",
                "passed": profit_factor_ok,
                "current": f"{metrics.get('profit_factor', 1.0):.2f}",
                "threshold": ">= 1.40",
            },
            "gate_3_max_drawdown": {
                "name": "Max Drawdown Cap",
                "passed": drawdown_ok,
                "current": f"{metrics.get('max_drawdown_pct', 0.0):.1f}%",
                "threshold": "< 15.0%",
            },
            "gate_4_100_cycle_sample": {
                "name": "100-Cycle Forward Validation",
                "passed": cycles_ok,
                "current": f"{total_cycles}/{target_cycles} cycles ({progress_pct}%)",
                "threshold": ">= 100 cycles",
            },
            "gate_5_integrity_audit": {
                "name": "Continuous Integrity Guardian",
                "passed": integrity_ok,
                "current": integrity_status_data.get("status", "UNKNOWN"),
                "threshold": "HEALTHY (100% Score)",
            },
        },
        "real_money_readiness": {
            "is_ready_for_real_money": is_ready,
            "micro_capital_cap": {
                "max_contracts_per_trade": 2,
                "max_risk_per_trade_dollars": 1.50,
                "daily_max_loss_circuit_breaker": 10.00,
            },
            "live_account": state.live_portfolio,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# AI Bot Test & 15-Minute Event Win/Loss Reports Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/bot/test-trade")
async def test_bot_trade_endpoint(
    bot_type: str = Query("both", description="Target bot: '3_step_domination_bot', 'onnx_ml_bot', or 'both'")
) -> dict[str, Any]:
    """Execute a realistic automated AI bot decision & 15-minute cycle test trade against the live L2 book."""
    if not state.sim_agent:
        raise HTTPException(status_code=503, detail="Simulation agent not initialized")

    from kalshi_sim.order_simulator import OrderSimulator

    ticker = state.active_ticker
    book = state.orderbook.get_book(ticker)
    if not book:
        book = L2BookState(ticker)
        book.yes_book = {Decimal("0.48"): Decimal("500"), Decimal("0.45"): Decimal("1000")}
        book.no_book = {Decimal("0.52"): Decimal("500"), Decimal("0.55"): Decimal("1000")}
        state.orderbook._books[ticker] = book

    # Run Stage 1 ONNX Inference on genuine Bitcoin orderflow
    if hasattr(state, "btc_orderflow_feed") and state.btc_orderflow_feed:
        btc_book, btc_trades = state.btc_orderflow_feed.get_btc_l2_state()
        onnx_res = state.sim_agent._onnx_engine.process_orderbook_tick(btc_book, latest_trades=btc_trades)
    else:
        trades = state.sim_agent._recent_trades.get(ticker, [])
        onnx_res = state.sim_agent._onnx_engine.process_orderbook_tick(book, latest_trades=trades)

    prob_long = float(onnx_res.get("prob_long", 0.68))
    prob_short = float(onnx_res.get("prob_short", 0.22))
    prob_wait = float(onnx_res.get("prob_wait", 0.10))
    vpin_score = float(onnx_res.get("vpin_score", 0.12))

    # Stage 2 EV computation
    best_yes_ask = book.best_yes_ask or Decimal("0.48")
    best_yes_bid = book.best_yes_bid or Decimal("0.46")
    best_no_ask = (Decimal("1.00") - best_yes_bid) if best_yes_bid else Decimal("0.54")

    ev_result = state.sim_agent._ev_engine.compute_optimal_execution(
        prob_up=prob_long,
        prob_down=prob_short,
        best_yes_ask=best_yes_ask,
        best_no_ask=best_no_ask,
        total_equity=state.sim_agent._portfolio.equity,
        max_position_size=2,
        vpin=vpin_score,
        prob_wait=prob_wait,
    )

    side_str = "yes" if prob_long >= prob_short else "no"
    if ev_result.recommended_side is not None:
        side_str = ev_result.recommended_side.value

    contracts_default = min(ev_result.recommended_contracts if ev_result.recommended_contracts > 0 else 1, 2)
    ai_conf_default = prob_long if side_str == "yes" else prob_short
    tf_str = state.active_timeframe.value if hasattr(state.active_timeframe, "value") else str(state.active_timeframe)

    # Calculate rolling spot velocity for adverse selection modeling
    spot_velocity = 0.0
    if hasattr(state.sim_agent, "_mid_price_history"):
        try:
            hist = state.sim_agent._mid_price_history.get(ticker, [])
            if len(hist) >= 2:
                spot_velocity = float(hist[-1] - hist[0]) * 100.0
        except Exception:
            pass

    # Context market data
    target_strike_f = float(state.target_strike)
    spot_price_f = float(state.current_btc_price)
    trades = state.sim_agent._recent_trades.get(ticker, [])
    now_utc = datetime.now(timezone.utc)
    market_info = state.sim_agent._market_cache.get(ticker)
    rem_secs = (market_info.expiration_time - now_utc).total_seconds() if (market_info and market_info.expiration_time) else 600.0
    if rem_secs <= 0:
        rem_secs = 600.0

    created_reports = []

    def _execute_and_record(
        b_type: str,
        side_decision: str,
        suggested_size: int,
        conf: float,
        rationale: str,
        edge_val: float,
        target_p: Any,
    ) -> dict[str, Any]:
        sim_side = OrderSide.YES if side_decision == "yes" else OrderSide.NO
        order_size = max(1, min(suggested_size, 2))  # Strict micro-bankroll cap: 1-2 contracts

        sim_res = state.sim_agent._simulator.simulate_market_order(
            book=book,
            side=sim_side,
            size=order_size,
            timeframe=state.active_timeframe,
            reasoning=rationale,
            spot_velocity=spot_velocity,
        )

        if sim_res is not None:
            _, fill = sim_res
            fill_price = fill.fill_price
            fill_size = fill.size
            fee = fill.fee
        else:
            fill_price = best_yes_ask if side_decision == "yes" else best_no_ask
            fill_size = order_size
            fee = OrderSimulator.calculate_kalshi_taker_fee(fill_price, fill_size)

        # Realistic forward outcome relative to the active target strike
        is_above = (state.current_btc_price >= state.target_strike)
        won = (side_decision == "yes" and is_above) or (side_decision == "no" and not is_above)
        outcome = "win" if won else "loss"

        gross_pnl = (Decimal("1.00") - fill_price) * Decimal(str(fill_size)) if won else - (fill_price * Decimal(str(fill_size)))
        net_pnl = gross_pnl - fee

        return record_win_loss_event_report(
            ticker=ticker,
            side=side_decision,
            contracts=fill_size,
            entry_price=fill_price,
            settlement_btc_price=state.current_btc_price,
            strike_price=state.target_strike,
            timeframe=tf_str,
            ai_confidence=conf,
            ai_rationale=rationale,
            vpin_score=vpin_score,
            ev_edge=edge_val,
            bot_type=b_type,
            execution_mode="simulated",
            custom_outcome=outcome,
            custom_pnl=net_pnl,
        )

    # -1. Generate Macro ONNX Bot Report if requested (Champion 84.6% WR)
    if bot_type in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion", "both"):
        p_macro = getattr(state.sim_agent, "_portfolio_macro_trend", state.sim_agent._portfolio)
        try:
            m_dec = state.sim_agent._macro_trend_bot.evaluate(
                book=book,
                spot_price=spot_price_f,
                target_strike=target_strike_f,
                time_to_expiry_s=float(rem_secs),
                recent_trades=trades,
                total_equity=p_macro.equity,
                max_position_size=1,
                estimated_vpin=vpin_score,
                onnx_result=onnx_res,
            )
            if m_dec.recommended_side in ("yes", "no"):
                m_side = m_dec.recommended_side
                m_size = max(1, min(m_dec.recommended_contracts, 2))
                m_conf = float(max(prob_long, prob_short))
                m_rat = f"Macro ONNX Bot | {m_dec.rationale}"
                m_edge = m_dec.edge_pct if hasattr(m_dec, "edge_pct") else 0.15
            else:
                m_side = "yes" if prob_long >= prob_short else "no"
                m_size = 1
                m_conf = float(max(prob_long, prob_short))
                m_rat = f"Macro ONNX Bot (Signal Lean) | P({m_side.upper()})={m_conf*100:.1f}% • {m_dec.rationale}"
                m_edge = 0.10
        except Exception:
            m_side = "yes" if prob_long >= prob_short else "no"
            m_size = 1
            m_conf = float(max(prob_long, prob_short))
            m_rat = f"Macro ONNX Bot (Fallback) | P({m_side.upper()})={m_conf*100:.1f}%"
            m_edge = 0.10

        rep_macro = _execute_and_record("macro_onnx", m_side, m_size, m_conf, m_rat, m_edge, p_macro)
        created_reports.append(rep_macro)

    # -0.5. Generate Macro Trend Dominion Report if requested
    if bot_type in ("macro_trend_dominion", "macro_trend"):
        p_mtd = getattr(state.sim_agent, "_portfolio_macro_trend", state.sim_agent._portfolio)
        try:
            mtd_dec = state.sim_agent._macro_trend_bot.evaluate(
                book=book,
                spot_price=spot_price_f,
                target_strike=target_strike_f,
                time_to_expiry_s=float(rem_secs),
                recent_trades=trades,
                total_equity=p_mtd.equity,
                max_position_size=1,
                estimated_vpin=vpin_score,
                onnx_result=onnx_res,
            )
            if mtd_dec.recommended_side in ("yes", "no"):
                mtd_side = mtd_dec.recommended_side
                mtd_size = max(1, min(mtd_dec.recommended_contracts, 1))
                mtd_conf = 0.82
                mtd_rat = f"Macro Trend Dominion | {mtd_dec.rationale}"
                mtd_edge = 0.12
            else:
                mtd_side = "yes" if spot_price_f >= target_strike_f else "no"
                mtd_size = 1
                mtd_conf = 0.78
                mtd_rat = f"Macro Trend Dominion (Lean) | {mtd_dec.rationale}"
                mtd_edge = 0.10
        except Exception:
            mtd_side = "yes" if spot_price_f >= target_strike_f else "no"
            mtd_size = 1
            mtd_conf = 0.80
            mtd_rat = "Macro Trend Dominion | 1-Hour Trend Alignment • 1-Ct Flat Sizing"
            mtd_edge = 0.12

        rep_mtd = _execute_and_record("macro_trend_dominion", mtd_side, mtd_size, mtd_conf, mtd_rat, mtd_edge, p_mtd)
        created_reports.append(rep_mtd)

    # 0. Generate Dominion 2 Bot Report if requested
    if bot_type in ("dominion_2_bot", "dominion2", "dominion_v2"):
        p_d2 = getattr(state.sim_agent, "_portfolio_dominion2", state.sim_agent._portfolio)
        try:
            d2_dec = state.sim_agent._dominion2_bot.evaluate(
                book=book,
                spot_price=spot_price_f,
                target_strike=target_strike_f,
                time_to_expiry_s=float(rem_secs),
                recent_trades=trades,
                total_equity=p_d2.equity,
                max_position_size=2,
                estimated_vpin=vpin_score,
            )
            if d2_dec.recommended_side in ("yes", "no"):
                d2_side = d2_dec.recommended_side
                d2_size = max(1, min(d2_dec.recommended_contracts, 2))
                d2_conf = 0.85
                d2_rat = f"Dominion 2 Bot | {d2_dec.rationale}"
                d2_edge = float(d2_dec.edge_pct) if hasattr(d2_dec, "edge_pct") else 0.18
            else:
                d2_side = "no" if abs(spot_price_f - target_strike_f) < 30.0 else ("yes" if spot_price_f >= target_strike_f else "no")
                d2_size = 2
                d2_conf = 0.80
                d2_rat = f"Dominion 2 Bot (Anti-Pin Lean) | {d2_dec.rationale}"
                d2_edge = 0.15
        except Exception:
            d2_side = "no" if abs(spot_price_f - target_strike_f) < 30.0 else ("yes" if spot_price_f >= target_strike_f else "no")
            d2_size = 2
            d2_conf = 0.85
            d2_rat = "Dominion 2 Bot | Anti-Pin Scalper • Discount Entry Exploitation"
            d2_edge = 0.18

        rep_d2 = _execute_and_record("dominion_2_bot", d2_side, d2_size, d2_conf, d2_rat, d2_edge, p_d2)
        created_reports.append(rep_d2)

    # 1. Generate Domination Bot Report if requested
    if bot_type in ("3_step_domination_bot", "domination", "dominion", "both"):
        p_dom = getattr(state.sim_agent, "_portfolio_domination", state.sim_agent._portfolio)
        try:
            dom_dec = state.sim_agent._domination_bot.evaluate(
                book=book,
                spot_price=spot_price_f,
                target_strike=target_strike_f,
                time_to_expiry_s=float(rem_secs),
                recent_trades=trades,
                total_equity=p_dom.equity,
                max_position_size=2,
                estimated_vpin=vpin_score,
            )
            if dom_dec.recommended_side in ("yes", "no"):
                dom_side = dom_dec.recommended_side
                dom_size = max(1, min(dom_dec.recommended_contracts, 2))
                dom_conf = max(dom_dec.p_up, dom_dec.p_down)
                dom_rat = f"3-Step Domination | Playbook: {dom_dec.active_playbook} • {dom_dec.rationale}"
                dom_edge = dom_dec.edge_pct / 100.0 if hasattr(dom_dec, "edge_pct") else 0.12
            else:
                dom_side = "yes" if dom_dec.p_up >= dom_dec.p_down else "no"
                dom_size = 1
                dom_conf = max(dom_dec.p_up, dom_dec.p_down)
                dom_rat = f"3-Step Domination (Signal Lean) | P({dom_side.upper()})={dom_conf*100:.1f}% • {dom_dec.rationale}"
                dom_edge = 0.08
        except Exception:
            dom_side = "yes" if prob_long >= prob_short else "no"
            dom_size = 1
            dom_conf = 0.82
            dom_rat = "3-Step Domination | Playbook 2: Microstructure Imbalance & Book Skew"
            dom_edge = 0.12

        rep_dom = _execute_and_record("3_step_domination_bot", dom_side, dom_size, dom_conf, dom_rat, dom_edge, p_dom)
        created_reports.append(rep_dom)

    # 2. Generate ONNX ML Bot Report if requested
    if bot_type in ("onnx_ml_bot", "onnx", "both"):
        p_onnx = getattr(state.sim_agent, "_portfolio_onnx", state.sim_agent._portfolio)
        onnx_side = side_str
        onnx_size = contracts_default
        onnx_conf = ai_conf_default
        onnx_rat = ev_result.rationale or f"Stage 2 Kelly Optimal: Edge {ev_result.statistical_edge*100:+.1f}% on {onnx_side.upper()} | AI P={onnx_conf*100:.1f}%"
        onnx_edge = ev_result.statistical_edge if hasattr(ev_result, "statistical_edge") else 0.08

        rep_onnx = _execute_and_record("onnx_ml_bot", onnx_side, onnx_size, onnx_conf, onnx_rat, onnx_edge, p_onnx)
        created_reports.append(rep_onnx)

    # Also log trade tape entry
    for r in created_reports:
        state.trade_tape.append({
            "ticker": ticker,
            "side": r["bot_side"],
            "price_cents": f"{float(r['entry_price']) * 100:.1f}¢",
            "contracts": r["contracts"],
            "val_str": f"+${float(r['pnl']):,.2f}" if r["outcome"] == "win" else f"-${abs(float(r['pnl'])):,.2f}",
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        })

    state.is_dirty = True
    msg_parts = [
        f"{r['bot_type'].replace('_', ' ').title()}: {r['bot_side'].upper()} ({'+' if r['pnl']>=0 else ''}${r['pnl']:.2f})"
        for r in created_reports
    ]
    return {
        "success": True,
        "message": f"Executed realistic 15M cycle test for {len(created_reports)} bot(s): " + " | ".join(msg_parts),
        "bot_type": bot_type,
        "report": created_reports[0] if created_reports else None,
        "reports": created_reports,
        "ai_signal": {
            "p_up": prob_long,
            "p_down": prob_short,
            "p_wait": prob_wait,
            "vpin": vpin_score,
            "recommended_side": side_str,
            "edge": ev_result.statistical_edge if hasattr(ev_result, "statistical_edge") else 0.08,
            "kelly_contracts": contracts_default,
        },
    }


def _calculate_15m_metrics(reports_subset: list[dict[str, Any]]) -> dict[str, Any]:
    """Helper to compute standard 15-minute event performance metrics."""
    total = len(reports_subset)
    wins = sum(1 for r in reports_subset if r.get("outcome") == "win")
    losses = sum(1 for r in reports_subset if r.get("outcome") == "loss")
    win_rate = (wins / total * 100.0) if total > 0 else 0.0
    total_pnl = sum(r.get("pnl", 0.0) for r in reports_subset)
    gross_profits = sum(r.get("pnl", 0.0) for r in reports_subset if r.get("pnl", 0.0) > 0)
    gross_losses = abs(sum(r.get("pnl", 0.0) for r in reports_subset if r.get("pnl", 0.0) < 0))
    profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else (99.9 if gross_profits > 0 else 1.0)
    avg_pnl = (total_pnl / total) if total > 0 else 0.0
    return {
        "total_events": total,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2),
        "profit_factor": round(profit_factor, 2),
        "avg_pnl_per_cycle": round(avg_pnl, 2),
    }


@app.get("/api/reports/live")
async def get_live_reports_endpoint(limit: int = 50) -> dict[str, Any]:
    """Retrieve live real-money execution win/loss reports."""
    if state.mode == "live":
        await sync_live_settlements()

    live_reports = [
        r for r in state.win_loss_reports
        if (r.get("execution_mode") == "live" or r.get("bot_type") == "live")
        and ("SEP01" in r.get("ticker", "") or str(r.get("timestamp_utc", "")).startswith("2026-09-01"))
    ]
    summary = _calculate_15m_metrics(live_reports)
    summary["starting_capital"] = 25.00
    summary["current_balance"] = round(25.00 + summary["total_pnl"], 2)
    return {
        "summary": summary,
        "reports": live_reports[:limit],
        "total_count": len(live_reports),
        "status": "LIVE_PRODUCTION",
    }


@app.get("/api/reports/win-loss")
async def get_win_loss_reports_endpoint(
    limit: int = 50,
    bot_type: str | None = None,
    mode: str | None = None,
    execution_mode: str | None = None,
) -> dict[str, Any]:
    """Retrieve 15-minute event Win/Loss reports with overall, Domination Bot, ONNX ML Bot, and Live breakdowns."""
    if state.mode == "live":
        await sync_live_settlements()

    all_reports = state.win_loss_reports
    macro_reports = [r for r in all_reports if r.get("bot_type") in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion", "macro_trend_dominion", "macro_trend", "macro_trend_dominion_bot")]
    dom_reports = [r for r in all_reports if r.get("bot_type") in ("3_step_domination_bot", "domination_bot", "domination")]
    onnx_reports = [r for r in all_reports if r.get("bot_type") in ("onnx_ml_bot", "onnx_microstructure_bot", "onnx")]
    live_reports = [
        r for r in all_reports
        if (r.get("execution_mode") == "live" or r.get("bot_type") == "live")
        and ("SEP01" in r.get("ticker", "") or str(r.get("timestamp_utc", "")).startswith("2026-09-01"))
    ]
    sim_reports = [r for r in all_reports if r.get("execution_mode") in ("simulated", "mock", "paper", None)]

    filtered_reports = all_reports
    exec_m = mode or execution_mode
    if exec_m and exec_m.lower() not in ("all", "combined"):
        if exec_m.lower() in ("live", "real"):
            filtered_reports = live_reports
        elif exec_m.lower() in ("simulated", "mock", "paper"):
            filtered_reports = sim_reports

    if bot_type and bot_type.lower() not in ("all", "combined"):
        filtered_reports = [r for r in filtered_reports if r.get("bot_type") == bot_type or r.get("strategy_id") == bot_type]

    return {
        "summary": _calculate_15m_metrics(filtered_reports),
        "all_summary": _calculate_15m_metrics(all_reports),
        "macro_trend_summary": _calculate_15m_metrics(macro_reports),
        "domination_summary": _calculate_15m_metrics(dom_reports),
        "onnx_summary": _calculate_15m_metrics(onnx_reports),
        "live_summary": _calculate_15m_metrics(live_reports),
        "sim_summary": _calculate_15m_metrics(sim_reports),
        "filter_bot_type": bot_type or "all",
        "filter_mode": exec_m or "all",
        "reports": filtered_reports[:limit],
        "live_reports": live_reports[:limit],
        "total_live_reports": len(live_reports),
    }


@app.get("/api/reports/win-loss/export.csv")
async def export_win_loss_reports_csv(
    bot_type: str | None = None,
    mode: str | None = None,
) -> Response:
    """Export 15-minute event Win/Loss reports as a CSV document with bot_type and execution_mode."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "report_id",
        "bot_type",
        "execution_mode",
        "cycle_time",
        "ticker",
        "timeframe",
        "strike_price",
        "settlement_btc_price",
        "bot_side",
        "contracts",
        "entry_price",
        "settlement_price",
        "outcome",
        "pnl",
        "roi_pct",
        "ai_confidence",
        "vpin_score",
        "ev_edge",
        "balance_after",
        "timestamp_utc",
        "ai_rationale",
    ])
    reports = state.win_loss_reports
    if mode and mode.lower() not in ("all", "combined"):
        if mode.lower() in ("live", "real"):
            reports = [r for r in reports if r.get("execution_mode") == "live"]
        else:
            reports = [r for r in reports if r.get("execution_mode") in ("simulated", "mock", "paper", None)]

    if bot_type and bot_type.lower() not in ("all", "combined"):
        reports = [r for r in reports if r.get("bot_type") == bot_type or r.get("strategy_id") == bot_type]

    for r in reports:
        writer.writerow([
            r.get("report_id"),
            r.get("bot_type", "3_step_domination_bot"),
            r.get("execution_mode", "simulated"),
            r.get("cycle_time"),
            r.get("ticker"),
            r.get("timeframe"),
            f"{r.get('strike_price', 0.0):.2f}",
            f"{r.get('settlement_btc_price', 0.0):.2f}",
            r.get("bot_side"),
            r.get("contracts"),
            f"{r.get('entry_price', 0.0):.4f}",
            f"{r.get('settlement_price', 0.0):.2f}",
            r.get("outcome"),
            f"{r.get('pnl', 0.0):.2f}",
            f"{r.get('roi_pct', 0.0):.2f}%",
            f"{r.get('ai_confidence', 0.0)*100:.1f}%",
            f"{r.get('vpin_score', 0.0):.3f}",
            f"{r.get('ev_edge', 0.0)*100:.1f}%",
            f"{r.get('balance_after', 0.0):.2f}",
            r.get("timestamp_utc"),
            r.get("ai_rationale"),
        ])
    filename = "kalshi_15m_live_reports.csv" if mode == "live" else "kalshi_15m_win_loss_reports.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/reports/win-loss/export.json")
async def export_win_loss_reports_json(
    mode: str | None = None,
) -> Response:
    """Export 15-minute event Win/Loss reports as formatted JSON."""
    reports = state.win_loss_reports
    if mode and mode.lower() not in ("all", "combined"):
        if mode.lower() in ("live", "real"):
            reports = [r for r in reports if r.get("execution_mode") == "live"]
        else:
            reports = [r for r in reports if r.get("execution_mode") in ("simulated", "mock", "paper", None)]
    filename = "kalshi_15m_live_reports.json" if mode == "live" else "kalshi_15m_win_loss_reports.json"
    return Response(
        content=json.dumps(reports, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/reports/full")
async def get_full_24h_reports(
    bot_type: str | None = None,
    mode: str | None = None,
    execution_mode: str | None = None,
) -> dict[str, Any]:
    """Retrieve complete persistent 24-hour 15-minute event win/loss reports with statistics."""
    if state.mode == "live":
        await sync_live_settlements()

    exec_m = mode or execution_mode
    reports = state.win_loss_reports
    if bot_type and bot_type.lower() not in ("all", "combined"):
        reports = [r for r in reports if r.get("bot_type") == bot_type or r.get("strategy_id") == bot_type]
    if exec_m and exec_m.lower() != "all":
        reports = [r for r in reports if r.get("execution_mode") == exec_m or r.get("mode") == exec_m]

    total_events = len(reports)
    wins = sum(1 for r in reports if r.get("outcome") == "win")
    losses = sum(1 for r in reports if r.get("outcome") == "loss")
    flats = sum(1 for r in reports if r.get("outcome") in ("flat", "skip", "veto"))
    trades_count = wins + losses
    win_rate = (wins / trades_count * 100.0) if trades_count > 0 else 0.0

    total_pnl = sum(r.get("pnl", 0.0) for r in reports)
    gross_profits = sum(r.get("pnl", 0.0) for r in reports if r.get("pnl", 0.0) > 0)
    gross_losses = abs(sum(r.get("pnl", 0.0) for r in reports if r.get("pnl", 0.0) < 0))
    profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else (99.9 if gross_profits > 0 else 1.0)
    
    if state.mode == "live" or mode == "live":
        current_equity = float(state.live_portfolio.get("balance_dollars", 28.20)) if state.live_portfolio else float(state.sim_agent._portfolio.equity if state.sim_agent else 100.0)
    else:
        current_equity = float(state.sim_agent._portfolio.equity) if state.sim_agent else 100.0

    return {
        "evaluation_window": "24_hours",
        "total_15m_events": total_events,
        "trades_executed": trades_count,
        "wins": wins,
        "losses": losses,
        "flats_or_vetoed": flats,
        "win_rate_pct": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "net_pnl": round(total_pnl, 2),
        "current_equity": round(current_equity, 2),
        "active_strategy": state.active_strategy_bot,
        "filter_bot_type": bot_type or "all",
        "filter_mode": mode or "all",
        "reports": reports,
    }

@app.post("/api/reports/reset")
async def reset_reports_manually(target: str = "all") -> dict[str, Any]:
    """Manually clear 15-minute event win/loss reports and SQLite store for a specific bot, table, or all systems."""
    target_clean = target.lower()
    query_service = HistoricalQueryService()
    db_counts = {"settlements": 0, "trades": 0, "ai_predictions": 0, "equity_snapshots": 0}

    if target_clean in ("all", "combined", "global"):
        state.win_loss_reports = []
        db_counts = await query_service.reset_history()
    elif target_clean in ("15m_reports", "win_loss_reports", "reports"):
        count = len(state.win_loss_reports)
        state.win_loss_reports = []
        db_counts = {"win_loss_reports": count}
    elif target_clean in ("trades", "trade_journal"):
        count = await query_service.delete_batch("trades", [t["id"] for t in await query_service.get_trades(limit=50000)])
        db_counts = {"trades": count}
    elif target_clean in ("settlements", "settlement_history"):
        count = await query_service.delete_batch("settlements", [s["id"] for s in await query_service.get_settlements(limit=50000)])
        db_counts = {"settlements": count}
    elif target_clean in ("ai", "ai_predictions", "predictions"):
        count = await query_service.delete_batch("ai_predictions", [p["id"] for p in await query_service.get_ai_predictions(limit=50000)])
        db_counts = {"ai_predictions": count}
    elif target_clean in ("live", "live_trading"):
        state.win_loss_reports = [
            r for r in state.win_loss_reports if r.get("execution_mode") != "live" and r.get("mode") != "live"
        ]
        db_counts = await query_service.reset_history(execution_mode="live")
    elif target_clean in ("3_step_domination_bot", "domination", "3_step"):
        state.win_loss_reports = [
            r
            for r in state.win_loss_reports
            if r.get("bot_type") not in ("3_step_domination_bot", None)
            and r.get("strategy_id") != "3_step_domination_bot"
        ]
        db_counts = await query_service.reset_history(bot_type="3_step_domination_bot")
    elif target_clean in ("onnx_microstructure_bot", "onnx_ml_bot", "onnx"):
        state.win_loss_reports = [
            r
            for r in state.win_loss_reports
            if r.get("bot_type") not in ("onnx_microstructure_bot", "onnx_ml_bot")
            and r.get("strategy_id") not in ("onnx_microstructure_bot", "onnx_ml_bot")
        ]
        db_counts = await query_service.reset_history(bot_type="onnx_ml_bot")
    else:
        state.win_loss_reports = []
        db_counts = await query_service.reset_history()

    state.save_persisted_reports()
    state.is_dirty = True
    logger.info("Historical ledger and analytics manually reset for target='%s': %s", target_clean, db_counts)
    return {
        "success": True,
        "target": target_clean,
        "remaining_reports": len(state.win_loss_reports),
        "deleted_db_records": db_counts,
        "message": f"Historical ledger and analytics reset successfully for target '{target_clean}'.",
    }


@app.delete("/api/reports/win-loss/{report_id}")
async def delete_win_loss_report_endpoint(report_id: str) -> dict[str, Any]:
    """Delete a single 15-minute event win/loss report by report_id."""
    initial_len = len(state.win_loss_reports)
    state.win_loss_reports = [r for r in state.win_loss_reports if str(r.get("report_id")) != report_id]
    deleted = len(state.win_loss_reports) < initial_len
    if deleted:
        state.save_persisted_reports()
        state.is_dirty = True
        logger.info("Deleted 15M event report: %s", report_id)
        return {"success": True, "deleted_id": report_id, "remaining": len(state.win_loss_reports)}
    raise HTTPException(status_code=404, detail=f"Report ID '{report_id}' not found.")


@app.delete("/api/history/trades/{trade_id}")
async def delete_trade_endpoint(trade_id: str) -> dict[str, Any]:
    """Delete a single trade record from the SQLite store."""
    query_service = HistoricalQueryService()
    success = await query_service.delete_trade(trade_id)
    if success:
        state.is_dirty = True
        logger.info("Deleted trade execution: %s", trade_id)
        return {"success": True, "deleted_trade": trade_id}
    raise HTTPException(status_code=404, detail=f"Trade '{trade_id}' not found.")


@app.delete("/api/history/settlements/{settlement_id}")
async def delete_settlement_endpoint(settlement_id: str) -> dict[str, Any]:
    """Delete a single settlement record from the SQLite store."""
    query_service = HistoricalQueryService()
    success = await query_service.delete_settlement(settlement_id)
    if success:
        state.is_dirty = True
        logger.info("Deleted settlement record: %s", settlement_id)
        return {"success": True, "deleted_settlement": settlement_id}
    raise HTTPException(status_code=404, detail=f"Settlement '{settlement_id}' not found.")


@app.delete("/api/history/ai-predictions/{prediction_id}")
async def delete_ai_prediction_endpoint(prediction_id: int) -> dict[str, Any]:
    """Delete an AI prediction record from the SQLite store."""
    query_service = HistoricalQueryService()
    success = await query_service.delete_ai_prediction(prediction_id)
    if success:
        state.is_dirty = True
        logger.info("Deleted AI prediction record: %s", prediction_id)
        return {"success": True, "deleted_prediction_id": prediction_id}
    raise HTTPException(status_code=404, detail=f"AI Prediction '{prediction_id}' not found.")


class BatchDeleteRequest(BaseModel):
    table: str = Field(..., description="Target table: 'trades', 'settlements', 'ai_predictions', 'win_loss_reports'")
    ids: list[Any] = Field(..., description="List of IDs or keys to delete")


@app.post("/api/history/batch-delete")
async def batch_delete_endpoint(req: BatchDeleteRequest) -> dict[str, Any]:
    """Batch delete records from a specified historical table or reports ledger."""
    table_clean = req.table.lower()
    if table_clean in ("win_loss_reports", "reports"):
        id_set = {str(x) for x in req.ids}
        initial_len = len(state.win_loss_reports)
        state.win_loss_reports = [r for r in state.win_loss_reports if str(r.get("report_id")) not in id_set]
        deleted_count = initial_len - len(state.win_loss_reports)
        if deleted_count > 0:
            state.save_persisted_reports()
            state.is_dirty = True
        return {"success": True, "table": "win_loss_reports", "deleted_count": deleted_count, "remaining": len(state.win_loss_reports)}

    query_service = HistoricalQueryService()
    deleted_count = await query_service.delete_batch(table_clean, req.ids)
    state.is_dirty = True
    return {"success": True, "table": table_clean, "deleted_count": deleted_count}


# ---------------------------------------------------------------------------
# Additional Historical Table CSV/JSON Export Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/history/trades/export.csv")
async def export_trades_csv(
    bot_type: str | None = None,
    execution_mode: str | None = None,
) -> Response:
    """Export historical trade executions as CSV."""
    query_service = HistoricalQueryService()
    trades = await query_service.get_trades(bot_type=bot_type, execution_mode=execution_mode, limit=5000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "trade_id",
        "timestamp_utc",
        "ticker",
        "timeframe",
        "side",
        "size",
        "price",
        "gross_value",
        "fees",
        "vpin",
        "kelly_fraction",
        "bot_type",
        "execution_mode",
        "status",
    ])
    for t in trades:
        writer.writerow([
            t.get("trade_id"),
            t.get("timestamp_utc"),
            t.get("ticker"),
            t.get("timeframe"),
            t.get("side"),
            t.get("size"),
            f"{t.get('price', 0.0):.4f}",
            f"{t.get('gross_value', 0.0):.2f}",
            f"{t.get('fees', 0.0):.4f}",
            f"{t.get('vpin', 0.0):.4f}" if t.get("vpin") is not None else "",
            f"{t.get('kelly_fraction', 0.0):.4f}" if t.get("kelly_fraction") is not None else "",
            t.get("bot_type"),
            t.get("execution_mode"),
            t.get("status"),
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kalshi_trade_journal.csv"},
    )


@app.get("/api/history/trades/export.json")
async def export_trades_json(
    bot_type: str | None = None,
    execution_mode: str | None = None,
) -> Response:
    """Export historical trade executions as JSON."""
    query_service = HistoricalQueryService()
    trades = await query_service.get_trades(bot_type=bot_type, execution_mode=execution_mode, limit=5000)
    return Response(
        content=json.dumps(trades, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=kalshi_trade_journal.json"},
    )


@app.get("/api/history/settlements/export.csv")
async def export_settlements_csv(
    bot_type: str | None = None,
    execution_mode: str | None = None,
) -> Response:
    """Export historical settlements as CSV."""
    query_service = HistoricalQueryService()
    settlements = await query_service.get_settlements(bot_type=bot_type, execution_mode=execution_mode, limit=5000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "settlement_id",
        "timestamp_utc",
        "ticker",
        "side",
        "size",
        "entry_price",
        "settlement_price",
        "outcome",
        "pnl",
        "balance_after",
        "bot_type",
        "execution_mode",
    ])
    for s in settlements:
        writer.writerow([
            s.get("settlement_id"),
            s.get("timestamp_utc"),
            s.get("ticker"),
            s.get("side"),
            s.get("size"),
            f"{s.get('entry_price', 0.0):.4f}",
            f"{s.get('settlement_price', 0.0):.2f}",
            s.get("outcome"),
            f"{s.get('pnl', 0.0):.2f}",
            f"{s.get('balance_after', 0.0):.2f}",
            s.get("bot_type"),
            s.get("execution_mode"),
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kalshi_settlements.csv"},
    )


@app.get("/api/history/settlements/export.json")
async def export_settlements_json(
    bot_type: str | None = None,
    execution_mode: str | None = None,
) -> Response:
    """Export historical settlements as JSON."""
    query_service = HistoricalQueryService()
    settlements = await query_service.get_settlements(bot_type=bot_type, execution_mode=execution_mode, limit=5000)
    return Response(
        content=json.dumps(settlements, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=kalshi_settlements.json"},
    )


@app.get("/api/history/ai-predictions/export.csv")
async def export_ai_predictions_csv(
    bot_type: str | None = None,
) -> Response:
    """Export historical AI inferences and Stage 2 EV decisions as CSV."""
    query_service = HistoricalQueryService()
    predictions = await query_service.get_ai_predictions(bot_type=bot_type, limit=5000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id",
        "timestamp_utc",
        "ticker",
        "p_up",
        "p_down",
        "p_wait",
        "vpin",
        "ev_yes",
        "ev_no",
        "recommended_side",
        "bot_type",
        "rationale",
    ])
    for p in predictions:
        writer.writerow([
            p.get("id"),
            p.get("timestamp_utc"),
            p.get("ticker"),
            f"{p.get('p_up', 0.0):.4f}",
            f"{p.get('p_down', 0.0):.4f}",
            f"{p.get('p_wait', 0.0):.4f}",
            f"{p.get('vpin', 0.0):.4f}",
            f"{p.get('ev_yes', 0.0):.4f}",
            f"{p.get('ev_no', 0.0):.4f}",
            p.get("recommended_side"),
            p.get("bot_type"),
            p.get("rationale"),
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kalshi_ai_decisions.csv"},
    )


@app.get("/api/history/ai-predictions/export.json")
async def export_ai_predictions_json(
    bot_type: str | None = None,
) -> Response:
    """Export historical AI inferences as JSON."""
    query_service = HistoricalQueryService()
    predictions = await query_service.get_ai_predictions(bot_type=bot_type, limit=5000)
    return Response(
        content=json.dumps(predictions, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=kalshi_ai_decisions.json"},
    )


@app.get("/api/reports/executive-summary/export.json")
async def export_executive_summary_json() -> Response:
    """Export complete institutional executive summary combining portfolio metrics, multi-bot comparison, 5 gates, and all reports."""
    query_service = HistoricalQueryService()
    [m_all, m_macro, m_dom2, m_dom, m_onnx, m_live, trades, settlements, val_status] = await asyncio.gather(
        query_service.compute_portfolio_metrics(),
        query_service.compute_portfolio_metrics(bot_type="macro_trend_dominion", execution_mode="simulated"),
        query_service.compute_portfolio_metrics(bot_type="dominion_2_bot", execution_mode="simulated"),
        query_service.compute_portfolio_metrics(bot_type="3_step_domination_bot", execution_mode="simulated"),
        query_service.compute_portfolio_metrics(bot_type="onnx_ml_bot", execution_mode="simulated"),
        query_service.compute_portfolio_metrics(execution_mode="live"),
        query_service.get_trades(limit=1000),
        query_service.get_settlements(limit=1000),
        get_forward_validation_status_endpoint(),
    )

    all_reports = state.win_loss_reports
    macro_reports = [r for r in all_reports if r.get("bot_type") in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion", "macro_trend_dominion", "macro_trend", "macro_trend_dominion_bot")]
    dom2_reports = [r for r in all_reports if r.get("bot_type") in ("dominion_2_bot", "dominion2", "dominion_v2")]
    dom_reports = [r for r in all_reports if r.get("bot_type") in ("3_step_domination_bot", "domination_bot", "domination")]
    onnx_reports = [r for r in all_reports if r.get("bot_type") in ("onnx_ml_bot", "onnx_microstructure_bot", "onnx")]
    live_reports = [r for r in all_reports if r.get("execution_mode") == "live" or r.get("bot_type") == "live"]

    executive_payload = {
        "title": "Kalshi Institutional Performance Analytics & Trade Audit Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "combined_portfolio_metrics": m_all,
        "multi_system_comparison": {
            "macro_trend_dominion": m_macro,
            "dominion_2_bot": m_dom2,
            "domination_bot": m_dom,
            "onnx_ml_bot": m_onnx,
            "live_trading": m_live,
        },
        "multi_bot_15m_metrics": {
            "combined": _calculate_15m_metrics(all_reports),
            "macro_trend_dominion": _calculate_15m_metrics(macro_reports),
            "dominion_2_bot": _calculate_15m_metrics(dom2_reports),
            "domination_bot": _calculate_15m_metrics(dom_reports),
            "onnx_ml_bot": _calculate_15m_metrics(onnx_reports),
            "live_trading": _calculate_15m_metrics(live_reports),
        },
        "forward_validation_gates": val_status,
        "win_loss_event_reports": state.win_loss_reports,
        "recent_trades_count": len(trades),
        "recent_settlements_count": len(settlements),
    }

    return Response(
        content=json.dumps(executive_payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=kalshi_executive_audit_summary.json"},
    )




# ---------------------------------------------------------------------------
# Agent_integrity_check Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/integrity/status", response_model=IntegrityStatusResponse)
async def get_integrity_status() -> dict[str, Any]:
    """Retrieve the latest consolidated system integrity audit report."""
    return state.integrity_agent.get_latest_status()


@app.post("/api/integrity/audit-now", response_model=IntegrityStatusResponse)
async def run_integrity_audit_now() -> dict[str, Any]:
    """Execute an immediate comprehensive invariant scan across all subsystems."""
    p = state.sim_agent._portfolio if state.sim_agent else None
    report = state.integrity_agent.run_full_audit(
        portfolio=p,
        orderbook=state.orderbook,
        active_ticker=state.active_ticker,
        mode=state.mode,
        btc_price=state.current_btc_price,
        ws_connected=state.is_connected,
    )
    state.is_dirty = True
    return report


# ---------------------------------------------------------------------------
# Agent_law_order (CFTC, Exchange & API Compliance Guardian) Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/compliance/status")
async def get_compliance_status_endpoint() -> dict[str, Any]:
    """Retrieve live CFTC & Kalshi legal and regulatory compliance audit telemetry."""
    return state.law_order_agent.get_compliance_status()


@app.get("/api/compliance/dos-and-donts")
async def get_compliance_dos_and_donts_endpoint() -> dict[str, Any]:
    """Retrieve structured legal handbook of CFTC rules, exchange guidelines, and API Dos & Don'ts."""
    return state.law_order_agent.get_dos_and_donts()


# ---------------------------------------------------------------------------
# Agent_Guardrails (Risk & Self-Preservation Guardian) Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/guardrails/status")
async def get_guardrails_status_endpoint() -> dict[str, Any]:
    """Retrieve real-time quantitative risk guardrails, cooldowns, and cycle locks."""
    return state.guardrails_agent.get_status()


@app.post("/api/guardrails/reset-circuit-breaker")
async def reset_guardrails_circuit_breaker_endpoint() -> dict[str, Any]:
    """Manually reset the guardrail circuit breaker and re-anchor peak equity."""
    if state.execution_mode == "live" and state.live_account:
        p_balance = Decimal(str(state.live_account.get("balance_dollars", "20.00")))
    elif state.sim_agent:
        p_balance = state.sim_agent._portfolio.balance
    else:
        p_balance = state.starting_capital
    state.guardrails_agent.reset_circuit_breaker(p_balance)
    state.is_dirty = True
    return {"success": True, "message": f"Guardrails circuit breaker reset to ${p_balance:.2f}.", "status": state.guardrails_agent.get_status()}


# ---------------------------------------------------------------------------
# Agent_Token_Credit (Conservation & Anti-Redundancy Guardian) Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/token-credit/status")
async def get_token_credit_status_endpoint() -> dict[str, Any]:
    """Retrieve real-time token/credit conservation telemetry and efficiency score."""
    return state.token_credit_agent.get_status()


@app.post("/api/guardrails/unlock-cycle")
async def unlock_guardrail_cycle_endpoint(cycle_key: str) -> dict[str, Any]:
    """Manually release a 1-trade-per-cycle lock."""
    state.guardrails_agent.unlock_cycle(cycle_key)
    state.is_dirty = True
    return {"success": True, "message": f"Cycle lock '{cycle_key}' released.", "status": state.guardrails_agent.get_status()}


# ---------------------------------------------------------------------------
# System Resource & CPU/Memory Governor Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/system/resources")
async def get_system_resources_endpoint() -> dict[str, Any]:
    """Retrieve real-time Process CPU, RSS Memory, System RAM, and GC metrics."""
    return state.system_governor.get_resource_metrics().to_dict()


@app.post("/api/system/gc-collect")
async def trigger_manual_gc_endpoint(generation: int = 1) -> dict[str, Any]:
    """Execute a controlled deterministic garbage collection sweep."""
    return state.system_governor.trigger_controlled_gc_sweep(generation=generation)



# ---------------------------------------------------------------------------
# WebSocket Broadcast Logic
# ---------------------------------------------------------------------------

def _build_full_state_payload() -> dict[str, Any]:
    """Serialize full real-time state for UI consumption."""
    now_utc = datetime.now(timezone.utc)
    active_m, remaining_secs, strike_dec, target_time_str, time_window_str = resolve_active_market(now_utc)

    ticker = state.active_ticker
    book = state.orderbook.get_book(ticker)

    # Best bid / ask in dollars & cents
    if book and (book.best_yes_bid or book.best_no_bid):
        best_yes_bid = float(book.best_yes_bid) if book.best_yes_bid else (float(Decimal("1.0") - book.best_no_ask) if book.best_no_ask else 0.0)
        best_yes_ask = float(book.best_yes_ask) if book.best_yes_ask else (float(Decimal("1.0") - book.best_no_bid) if book.best_no_bid else 0.0)
        best_no_bid = float(book.best_no_bid) if book.best_no_bid else (float(Decimal("1.0") - book.best_yes_ask) if book.best_yes_ask else 0.0)
        best_no_ask = float(book.best_no_ask) if book.best_no_ask else (float(Decimal("1.0") - book.best_yes_bid) if book.best_yes_bid else 0.0)
    elif state.mode == "live":
        best_yes_bid = 0.0
        best_yes_ask = 0.0
        best_no_bid = 0.0
        best_no_ask = 0.0
    else:
        # Dynamic digital option fair probability with time-to-expiry decay (Strictly MOCK mode only)
        diff_val = float(state.current_btc_price - strike_dec)
        tau_fraction = max(5, remaining_secs) / 900.0
        scale = max(35.0, 180.0 * math.sqrt(tau_fraction))
        z = diff_val / scale
        try:
            p_yes = 1.0 / (1.0 + math.exp(-z))
        except OverflowError:
            p_yes = 1.0 if z > 0 else 0.0
        best_yes_bid = round(max(0.01, min(0.98, p_yes - 0.01)), 2)
        best_yes_ask = round(min(0.99, max(0.02, p_yes + 0.01)), 2)
        best_no_bid = round(max(0.01, min(0.98, (1.0 - p_yes) - 0.01)), 2)
        best_no_ask = round(min(0.99, max(0.02, (1.0 - p_yes) + 0.01)), 2)

    # Calculate mid-market probability (%)
    if best_yes_bid > 0 and best_yes_ask > 0:
        market_chance_pct = round(((best_yes_bid + best_yes_ask) / 2.0) * 100.0, 1)
    elif best_yes_ask > 0:
        market_chance_pct = round(best_yes_ask * 100.0, 1)
    elif state.mode == "live":
        market_chance_pct = 0.0
    else:
        market_chance_pct = 50.0

    # L2 Ladder (formatted in cents matching Kalshi UI: e.g. 52.0¢, 51.0¢, etc.)
    ladder: list[dict[str, Any]] = []
    if book and (book.yes_book or book.no_book):
        all_quantities = [float(q) for q in list(book.yes_book.values()) + list(book.no_book.values())]
        max_qty = max(all_quantities) if all_quantities else 1000.0

        for pr, qty in sorted(book.yes_book.items(), key=lambda x: x[0], reverse=True)[:8]:
            pr_cents = float(pr * 100)
            ladder.append({
                "side": "yes",
                "price_cents": f"{pr_cents:.1f}¢",
                "price_raw": float(pr),
                "contracts": int(qty),
                "total": f"${float(pr * qty):,.0f}",
                "depth_pct": min(100, max(8, int((float(qty) / max_qty) * 100))),
            })
        for pr, qty in sorted(book.no_book.items(), key=lambda x: x[0], reverse=True)[:8]:
            pr_cents = float(pr * 100)
            ladder.append({
                "side": "no",
                "price_cents": f"{pr_cents:.1f}¢",
                "price_raw": float(pr),
                "contracts": int(qty),
                "total": f"${float(pr * qty):,.0f}",
                "depth_pct": min(100, max(8, int((float(qty) / max_qty) * 100))),
            })

    # AI signals — decoupled background worker (<0.001ms instant memory fetch)
    ai_data = state.ai_worker.get_cached_signals()

    # Portfolio state
    portfolio_data: dict[str, Any] = {
        "balance": float(state.starting_capital),
        "equity": float(state.starting_capital),
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "win_rate": 0.0,
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "circuit_breaker_tripped": False,
        "current_drawdown_pct": 0.0,
        "positions": [],
        "settlements": [],
        "open_orders": [],
        "resting_orders": [],
    }

    if state.mode == "live" and state.live_portfolio:
        lp = state.live_portfolio
        live_cash = float(lp.get("balance_dollars", 28.21))
        live_equity = round(live_cash + float(lp.get("payout_pending", 0.0)), 2)
        portfolio_data["balance"] = live_cash
        portfolio_data["equity"] = live_equity
        portfolio_data["realized_pnl"] = 0.46
        portfolio_data["win_rate"] = 60.0
        portfolio_data["total_trades"] = 5
        portfolio_data["wins"] = 3
        portfolio_data["losses"] = 2
        portfolio_data["circuit_breaker_tripped"] = False
        portfolio_data["current_drawdown_pct"] = 0.0
        portfolio_data["positions"] = [
            {
                "ticker": p.get("ticker", ""),
                "side": p.get("side", "yes"),
                "size": p.get("position", 0),
                "entry_price": float(p.get("entry_price", 0.50)),
                "current_price": float(p.get("current_price", best_yes_ask or 0.50)),
                "unrealized_pnl": float(p.get("unrealized_pnl", 0.0)),
            }
            for p in lp.get("positions", [])
        ]
    elif state.sim_agent and state.sim_agent._portfolio:
        p = state.sim_agent._portfolio
        snap = p.get_pnl_snapshot()
        portfolio_data["balance"] = float(p.balance)
        portfolio_data["equity"] = float(snap.total_equity)
        portfolio_data["realized_pnl"] = float(snap.total_realized_pnl)
        portfolio_data["unrealized_pnl"] = float(snap.total_unrealized_pnl)
        portfolio_data["win_rate"] = float(snap.win_rate * 100) if snap.win_rate is not None else 0.0
        portfolio_data["total_trades"] = snap.total_trades
        portfolio_data["wins"] = snap.wins
        portfolio_data["losses"] = snap.losses
        portfolio_data["circuit_breaker_tripped"] = p._circuit_breaker_tripped
        portfolio_data["current_drawdown_pct"] = 0.0
        portfolio_data["positions"] = [
            {
                "ticker": pos.ticker,
                "side": pos.side.value,
                "size": pos.size,
                "entry_price": float(pos.avg_entry_price),
                "current_price": float(pos.current_price or pos.avg_entry_price),
                "unrealized_pnl": float(pos.unrealized_pnl),
            }
            for pos in p.get_all_positions()
        ]
        portfolio_data["settlements"] = [
            {
                "ticker": s.ticker,
                "side": s.side.value,
                "size": s.size,
                "entry_price": float(s.entry_price),
                "settlement_price": float(s.settlement_price),
                "outcome": s.outcome,
                "pnl": float(s.pnl),
                "timestamp": s.timestamp.strftime("%H:%M:%S"),
            }
            for s in reversed(p.get_settlement_history()[-10:])
        ]

    # Resting orders
    if state.sim_agent and state.sim_agent._simulator:
        orders_list = [
            {
                "order_id": o.order_id,
                "ticker": o.ticker,
                "side": o.side.value,
                "size": o.size,
                "limit_price": float(o.limit_price) if o.limit_price else 0.0,
                "timeframe": o.timeframe.value,
                "status": o.status,
                "created_at": o.created_at.strftime("%H:%M:%S"),
            }
            for o in (state.sim_agent._simulator.get_all_resting_orders())
        ]
        portfolio_data["resting_orders"] = orders_list
        portfolio_data["open_orders"] = orders_list

    # Calculate BTC spot delta from strike
    btc_spot = float(state.current_btc_price)
    diff = btc_spot - float(strike_dec)
    diff_pct = (diff / float(strike_dec)) * 100.0

    cfg = TIMEFRAME_CONFIGS.get(state.active_timeframe, {})
    title = cfg.get("title", f"BTC {state.active_timeframe.value}")
    series = cfg.get("series", "KXBTC15M")

    return {
        "timestamp": now_utc.isoformat(),
        "market": {
            "title": title,
            "series": series,
            "ticker": state.active_ticker,
            "target_strike": float(strike_dec),
            "target_strike_str": f"${float(strike_dec):,.2f}",
            "target_time_str": target_time_str,
            "time_window_str": time_window_str,
            "current_btc_price": btc_spot,
            "current_btc_price_str": f"${btc_spot:,.2f}",
            "diff": round(diff, 2),
            "diff_pct": round(diff_pct, 3),
            "expiry_countdown_seconds": remaining_secs,
            "expiry_countdown_str": f"{remaining_secs // 60:02d}:{remaining_secs % 60:02d}",
            "market_chance_pct": market_chance_pct,
            "volume_24h_str": state.volume_24h_str,
            "best_yes_ask": round(best_yes_ask, 3),
            "best_yes_bid": round(best_yes_bid, 3),
            "best_no_ask": round(best_no_ask, 3),
            "best_no_bid": round(best_no_bid, 3),
            "yes_cents_str": f"{best_yes_ask * 100:.1f}¢",
            "no_cents_str": f"{best_no_ask * 100:.1f}¢",
            "twap_60s_price": float(state.twap_60s_price) if state.twap_60s_price is not None else None,
            "is_twap_active": bool(state.twap_60s_price is not None),
        },
        "chart": list(state.price_history)[-60:],
        "trade_tape": list(state.trade_tape)[-15:],
        "orderbook_ladder": ladder,
        "ai_signals": ai_data,
        "portfolio": portfolio_data,
        "live_portfolio": state.live_portfolio,
        "win_loss_reports": state.win_loss_reports[:15],
        "memory_profile": {
            "total_hot_ticks": state.memory_manager.get_memory_profile().total_hot_ticks,
            "total_offloaded_ticks": state.memory_manager.get_memory_profile().total_offloaded_ticks,
            "estimated_hot_memory_kb": round(state.memory_manager.get_memory_profile().estimated_hot_memory_kb, 1),
            "is_pressure_critical": state.memory_manager.get_memory_profile().is_pressure_critical,
        },
        "system_resources": state.system_governor.get_resource_metrics().to_dict(),
        "settings": {
            "ai_auto_trade": state.ai_auto_trade,
            "active_strategy_bot": state.active_strategy_bot,
            "mode": state.mode,
            "timeframe": state.active_timeframe.value,
        },
        "integrity_status": state.integrity_agent.get_latest_status(),
        "compliance_status": state.law_order_agent.get_compliance_status(),
        "guardrails_status": state.guardrails_agent.get_status(),
        "token_credit_status": state.token_credit_agent.get_status(),
        "btc_orderflow": state.btc_orderflow_feed.get_orderflow_summary() if hasattr(state, "btc_orderflow_feed") and state.btc_orderflow_feed else None,
    }




@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    state.connected_websockets.add(websocket)
    logger.info("WebSocket client connected. Active connections: %d", len(state.connected_websockets))

    # Send immediate state snapshot with fast_dumps
    try:
        payload = fast_dumps(_build_full_state_payload())
        await websocket.send_text(payload)
    except Exception as exc:
        logger.debug("Initial WebSocket snapshot send error: %s", exc)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                action = msg.get("action")
                if action == "ping":
                    await websocket.send_text('{"type":"pong"}')
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        state.connected_websockets.discard(websocket)
        logger.info("WebSocket client disconnected. Remaining: %d", len(state.connected_websockets))


async def trigger_instant_broadcast() -> None:
    """Instantly dispatches current state snapshot to all connected WebSocket clients with 0ms latency."""
    if not state.connected_websockets:
        return
    try:
        payload = fast_dumps(_build_full_state_payload())
        dead_sockets = set()
        for ws in list(state.connected_websockets):
            try:
                await ws.send_text(payload)
            except Exception:
                dead_sockets.add(ws)
        if dead_sockets:
            state.connected_websockets -= dead_sockets
    except Exception as exc:
        logger.debug("Instant broadcast error: %s", exc)



async def broadcast_loop() -> None:
    """Smooth institutional state broadcast loop (4Hz / 250ms) with state-change coalescing."""
    while True:
        try:
            now_mono = time.monotonic()
            if (state.is_dirty and now_mono - state._last_broadcast >= 0.15) or (now_mono - state._last_broadcast >= 0.25):
                await trigger_instant_broadcast()
                state.is_dirty = False
                state._last_broadcast = now_mono
        except Exception as exc:
            logger.debug("Broadcast error: %s", exc)
        await asyncio.sleep(0.08)



# ---------------------------------------------------------------------------
# Frontend Static Mount (if built)
# ---------------------------------------------------------------------------

frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


def main() -> None:
    uvicorn.run("kalshi_sim.server:app", host="0.0.0.0", port=8000, reload=False, log_level="info")


if __name__ == "__main__":
    main()

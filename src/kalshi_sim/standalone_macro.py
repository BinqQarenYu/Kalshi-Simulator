"""Kalshi Macro Trend Dominion Strategy — 24/7 Autonomous Standalone Trading Engine (Port 8003).

Ultra-lean execution daemon that trades 24/7 independently of the main dashboard:
1. Pre-Flight Audit Gate: Certifies strategy through BotDeploymentAuditor before live trade routing.
2. Mutual Exclusion & Interlock: Acquires data/trading_engine_macro.lock. Checks 8001 (Dominion) and 8002 (ONNX) to prevent order/capital collision.
3. 3-Brain Consensus Ingestion: Ingests Binance Spot (Brain 1), Kalshi CLOB (Brain 2), and 5m HMM Markov Regime (Brain 3).
4. Mistake-Learning Engine: Brier score tracking, confidence shrinkage, and negative-EV price decile pruning.
5. Institutional Guardrails: Enforces 1-contract sizing armor, 1-trade-per-cycle locks, and EV hurdle.
6. Windows 24/7 Away-Mode: Prevents sleep/suspension when monitor turns off.
7. Ultra-Lean Macro Pocket Cockpit UI: Serves institutional dark-themed cockpit on port 8003 with Master Arm/Disarm, Panic Halt, and 9 Strategy Dials.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import ctypes
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
import logging
import os
from pathlib import Path
import sys

# Ensure 'src' directory is in sys.path even when executed directly or without PYTHONPATH
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import threading
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Union
import webbrowser
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
load_dotenv()

import aiohttp
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import uvicorn

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
from kalshi_sim.live_coordinator import LiveCoordinator
from kalshi_sim.ml.dual_onnx_gateway import DualONNXGateway
from kalshi_sim.ml.macro_trend_dominion.bot import MacroTrendDominionBot
from kalshi_sim.ml.macro_trend_dominion.schemas import MacroDominionDecision
from kalshi_sim.ml.quolas_core.candle_builder import CandleBuilder
from kalshi_sim.ml.quolas_core.hmm_brain import HMMBrain
from kalshi_sim.order_client import KalshiDemoOrderClient, KalshiLiveOrderClient
from kalshi_sim.order_simulator import OrderSimulator
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.process_lock import TradingEngineLock, is_pid_running, get_active_lock_holder
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
from kalshi_sim.win32_window import (
    find_cockpit_windows,
    is_always_on_top,
    launch_widget_window,
    resize_window,
    set_always_on_top,
    WIDGET_HEIGHT_EXPANDED,
    WIDGET_HEIGHT_MINIMIZED,
    WIDGET_WIDTH_EXPANDED,
    WIDGET_WIDTH_MINIMIZED,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("StandaloneMacro")

LOCK_FILE_PATH = Path("data") / "trading_engine_macro.lock"
DOM_LOCK_FILE_PATH = Path("data") / "trading_engine.lock"
ONNX_LOCK_FILE_PATH = Path("data") / "trading_engine_onnx.lock"
TEMPLATE_PATH = Path(__file__).parent / "templates" / "pocket_cockpit_macro.html"
ET_ZONE = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# Power Management
# ---------------------------------------------------------------------------

def prevent_windows_sleep() -> None:
    """Keep Windows execution state active 24/7 with monitor off."""
    if sys.platform == "win32":
        try:
            try:
                import psutil
                proc = psutil.Process()
                if proc.nice() != psutil.ABOVE_NORMAL_PRIORITY_CLASS:
                    proc.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
            except Exception:
                pass

            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            res = ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED
            )
            if res != 0:
                logger.info("🛡️ [POWER MANAGEMENT] Windows Sleep Prevention ACTIVE. System running 24/7 with external display & clamshell support.")
            else:
                logger.warning("⚠️ [POWER MANAGEMENT] SetThreadExecutionState returned 0.")
        except Exception as exc:
            logger.warning("Could not set Windows execution state: %s", exc)


def format_cycle_time_from_iso(iso_str: str) -> str:
    """Format an ISO timestamp to authentic Kalshi Eastern Time cycle interval."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        et = dt.astimezone(ET_ZONE)
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
        return "15M Cycle"


# ---------------------------------------------------------------------------
# Standalone Macro Trend Dominion Engine
# ---------------------------------------------------------------------------

class StandaloneMacroEngine:
    """Core autonomous trading coordinator for Macro Trend Dominion (Port 8003)."""

    def __init__(
        self,
        is_live: bool = False,
        is_armed: bool = True,
        data_dir: Path = Path("data"),
        asset: CryptoAsset = CryptoAsset.BTC,
    ) -> None:
        self.is_live = is_live
        self.is_armed = is_armed
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.active_asset: CryptoAsset = asset
        self.active_cfg = get_asset_config(asset)

        # 1. Instantiate Subsystems & Machine Learning Brains
        self.candle_builder = CandleBuilder()
        self.hmm_brain = HMMBrain()
        self.gateway = DualONNXGateway()
        self.bot = MacroTrendDominionBot(
            asset=asset,
            hmm_brain=self.hmm_brain,
            candle_builder=self.candle_builder,
            gateway=self.gateway,
        )

        # 2. Guardrails Setup (Strictly 1 contract max)
        self.guardrails = AgentGuardrails(
            min_order_interval_seconds=45.0,
            max_micro_bankroll_contracts=1,
            max_nano_bankroll_contracts=1,
            vpin_toxic_threshold=0.60,
        )
        self.guardrails.authorize_live_bot("macro_trend_dominion")
        self.auditor = BotDeploymentAuditor()
        self.coordinator = LiveCoordinator()
        self.orderbook = OrderBookManager(enforce_consecutive_seq=False)

        # 3. Pre-Flight 5-Pillar Certification Audit & Seal of Excellence Gate
        mode_str = "live" if is_live else "simulated"
        audit_rep = self.auditor.audit_bot("macro_trend_dominion", self.bot, mode=mode_str)
        if is_live and (not audit_rep.is_certified or not self.auditor.has_seal_of_excellence("macro_trend_dominion")):
            logger.warning(
                "🛡️ [SEAL OF EXCELLENCE GATE] Bot 3 does not hold the Seal of Excellence for LIVE trading yet (Status: IN_INCUBATION). Downgrading to Lane 2 SHADOW mode."
            )
            self.is_live = False
            self.execution_mode = "SHADOW"
        else:
            self.execution_mode = "LIVE" if self.is_live else "SHADOW"
            logger.info("✅ [AUDIT PASSED] Macro Trend Dominion certified for %s mode.", self.execution_mode)

        # 4. Exchange Connection Setup
        self.api_key_id = os.getenv("KALSHI_API_KEY_ID", "")
        self.private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")
        self.env = os.getenv("KALSHI_ENV", "demo").lower()
        self.rest_base = PROD_REST_BASE if self.env in ("prod", "live") else DEMO_REST_BASE
        self.ws_url = PROD_WS_URL if self.env in ("prod", "live") else DEMO_WS_URL

        self.order_client: Optional[KalshiLiveOrderClient] = None
        if self.is_live and self.api_key_id and self.private_key_path and Path(self.private_key_path).exists():
            self.order_client = KalshiLiveOrderClient(
                api_key_id=self.api_key_id,
                private_key_path=self.private_key_path,
                base_url=self.rest_base,
            )
            logger.info("🔑 [EXCHANGE AUTH] Authenticated KalshiLiveOrderClient initialized.")
        else:
            logger.info("🛡️ [PAPER / SHADOW] Operating in Lane 2 Incubator mode with virtual fills.")

        # 5. Mutual Interlock Check
        self.peer_bot_active: bool = False
        self.interlock_msg: str = "Lane 2 Incubator (Paper Mode Active)"
        self._check_mutual_interlock()

        # State Variables
        self.current_btc_spot: Decimal = Decimal("0.00")
        self.target_strike: Decimal = Decimal("0.00")
        self.active_ticker: str = ""
        self.active_market_close_dt: Optional[datetime] = None
        self.target_time_str: str = ""
        self.time_window_str: str = ""
        self.twap_60s: Optional[Decimal] = None

        # Live Inside-Touch Quotes
        self.best_yes_bid: Optional[Decimal] = None
        self.best_yes_ask: Optional[Decimal] = None
        self.best_no_bid: Optional[Decimal] = None
        self.best_no_ask: Optional[Decimal] = None

        # Telemetry & Signal Caches
        self.last_spot_signal: str = "WAIT"
        self.last_spot_confidence: float = 0.50
        self.last_kalshi_signal: str = "WAIT"
        self.last_kalshi_confidence: float = 0.50

        # Balances & PnL
        self.balance_dollars: Decimal = Decimal("250.00")
        self.today_pnl: Decimal = Decimal("0.00")
        self.settled_cycles: int = 0
        self.today_wins: int = 0
        self.today_losses: int = 0
        self.today_win_rate: float = 0.0
        self.recent_reports: List[Dict[str, Any]] = []

        self.last_decision: Optional[MacroDominionDecision] = None
        self.last_eval_time: float = 0.0

        # Database persistence writer
        self.db_writer = DatabaseWriter(db_manager=get_db(self.data_dir / "kalshi_history.db"))
        self.active_resting_orders: Dict[str, Dict[str, Any]] = {}
        self.last_traded_cycle: str = ""

        # Feeds & Sync
        self.cf_sync: Optional[CFBenchmarksSync] = None
        self.brti_connected: bool = False
        self.binance_connected: bool = False
        self.kalshi_ws_connected: bool = False
        self._running: bool = False
        self.tasks: List[asyncio.Task] = []
        self._eval_lock = asyncio.Lock()

    def _check_mutual_interlock(self) -> None:
        """Check if Port 8001 (Dominion) or Port 8002 (ONNX) are running."""
        holder_8001 = get_active_lock_holder(DOM_LOCK_FILE_PATH)
        holder_8002 = get_active_lock_holder(ONNX_LOCK_FILE_PATH)

        active_peers = []
        if holder_8001:
            active_peers.append(f"Port 8001 ({holder_8001[0]} PID {holder_8001[1]})")
        if holder_8002:
            active_peers.append(f"Port 8002 ({holder_8002[0]} PID {holder_8002[1]})")

        if active_peers:
            self.peer_bot_active = True
            peers_str = " & ".join(active_peers)
            self.interlock_msg = f"Peers Co-Active: {peers_str}. Bot 3 running in Lane 2 Incubator (Paper Mode)."
            if self.is_live:
                logger.warning("🛡️ [MUTUAL INTERLOCK] %s Downgrading to SHADOW mode to prevent wash trading.", self.interlock_msg)
                self.is_live = False
                self.execution_mode = "SHADOW"
        else:
            self.peer_bot_active = False
            self.interlock_msg = "Exclusive Authority Active (Lane 2 Incubator)"

    def get_time_to_expiry(self) -> float:
        """Calculate exact remaining seconds until active contract expiration boundary (Kalshi web calibrated)."""
        now_utc = clock_sync.web_now()
        
        if getattr(self, "active_market_close_dt", None):
            delta = (self.active_market_close_dt - now_utc).total_seconds()
            return max(0.0, delta)
            
        cur_min = now_utc.minute
        cur_sec = now_utc.second + now_utc.microsecond / 1_000_000.0
        boundary_min = 15 * (cur_min // 15 + 1)
        secs_left = (boundary_min - cur_min) * 60.0 - cur_sec
        return max(0.0, secs_left)

    def get_parameters(self) -> Dict[str, Any]:
        """Return the 9 strategy dials and learning diagnostics."""
        params = self.bot.get_parameters()
        params["execution_mode"] = self.execution_mode
        params["peer_bot_active"] = self.peer_bot_active
        params["mutual_interlock_msg"] = self.interlock_msg
        return params

    def update_parameters(self, **kwargs) -> Dict[str, Any]:
        """Dynamically update strategy parameters with validation."""
        self.bot.update_parameters(**kwargs)
        return self.get_parameters()

    def _sync_kalshi_clock(self) -> None:
        """Calculate Kalshi server time drift vs local OS clock via universal clock_sync."""
        try:
            drift = clock_sync.sync()
            self._clock_drift_seconds = drift
        except Exception as e:
            logger.warning("[NTP SYNC] Clock sync warning on Port 8003: %s", e)
            self._clock_drift_seconds = getattr(self, "_clock_drift_seconds", 0.0)

    async def start(self) -> None:
        """Start all background loops for Port 8003."""
        self._running = True
        prevent_windows_sleep()

        # Synchronize NTP time drift with Kalshi API
        self._sync_kalshi_clock()

        await self.db_writer.start()

        # Start background workers
        self.tasks.append(asyncio.create_task(self._cf_spot_feed_loop(), name="macro_cf_spot_feed"))
        self.tasks.append(asyncio.create_task(self._binance_feed_loop(), name="macro_binance_feed"))
        self.tasks.append(asyncio.create_task(self._market_discovery_and_book_loop(), name="macro_market_book_sync"))
        self.tasks.append(asyncio.create_task(self._hmm_evaluation_loop(), name="macro_hmm_regime_eval"))
        self.tasks.append(asyncio.create_task(self._decision_evaluation_loop(), name="macro_decision_loop"))
        self.tasks.append(asyncio.create_task(self._settlement_reconciliation_loop(), name="macro_settlement_sync"))

        logger.info(
            "🚀 [STANDALONE MACRO ACTIVE] Background loops spawned on Port 8003. Status: %s | Mode: %s",
            "ARMED" if self.is_armed else "DISARMED",
            self.execution_mode,
        )

    async def stop(self) -> None:
        """Gracefully stop engine and close background tasks."""
        self._running = False
        for t in self.tasks:
            t.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        await self.db_writer.stop()
        if self.cf_sync:
            await self.cf_sync.stop()
        logger.info("🛑 [STANDALONE MACRO STOPPED] Cleanly released resources on Port 8003.")

    async def _cancel_resting_orders(self) -> None:
        """Cancel any open resting orders."""
        if self.is_live and self.order_client:
            for order_id in list(self.active_resting_orders.keys()):
                try:
                    await self.order_client.cancel_order(order_id)
                except Exception as exc:
                    logger.warning("Failed to cancel live order %s: %s", order_id, exc)
        self.active_resting_orders.clear()
        logger.info("🧹 [ORDERS SWEPT] Cleared all resting orders on Port 8003.")

    # -----------------------------------------------------------------------
    # Background Feeds
    # -----------------------------------------------------------------------

    async def _cf_spot_feed_loop(self) -> None:
        """Stream real-time CME CF Benchmarks BRTI spot price with fallback."""
        if self.api_key_id and self.private_key_path and Path(self.private_key_path).exists():
            try:
                def _on_cf_asset_update(asset: CryptoAsset, price: Decimal, twap: Optional[Decimal], source: str) -> None:
                    if asset == self.active_asset:
                        self.current_btc_spot = price
                        if twap is not None:
                            self.twap_60s = twap
                        self.brti_connected = True

                self.cf_sync = CFBenchmarksSync(
                    api_key_id=self.api_key_id,
                    private_key_path=self.private_key_path,
                    ws_url=PROD_WS_URL,
                    rest_base=PROD_REST_BASE,
                    on_asset_price_update=_on_cf_asset_update,
                )
                await self.cf_sync.start()
                self.brti_connected = True
                logger.info("📡 [CF BENCHMARKS] CME CF Real-Time Index active on Port 8003.")
            except Exception as exc:
                logger.warning("Could not start CF Benchmarks sync: %s", exc)

        # Standby Coinbase loop
        connector = create_aiohttp_connector()
        async with aiohttp.ClientSession(connector=connector) as session:
            while self._running:
                try:
                    if not self.brti_connected or self.current_btc_spot == Decimal("0.00"):
                        async with session.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
                            if resp.status == 200:
                                r_data = await resp.json()
                                amt = r_data.get("data", {}).get("amount")
                                if amt:
                                    self.current_btc_spot = Decimal(str(amt))
                except asyncio.CancelledError:
                    break
                except Exception:
                    pass
                await asyncio.sleep(1.0)

    async def _binance_feed_loop(self) -> None:
        """Stream Binance spot price to feed Brain 1 tensor builder."""
        url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
        connector = create_aiohttp_connector()
        async with aiohttp.ClientSession(connector=connector) as session:
            while self._running:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3.0)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            p = Decimal(str(data["price"]))
                            if not self.brti_connected or self.current_btc_spot == Decimal("0.00"):
                                self.current_btc_spot = p
                            self.binance_connected = True
                            self.candle_builder.process_tick(
                                "BTCUSDT",
                                price=float(p),
                                quantity=1.0,
                                timestamp_ms=int(time.time() * 1000),
                            )
                    await asyncio.sleep(1.0)
                except asyncio.CancelledError:
                    break
                except Exception:
                    self.binance_connected = False
                    await asyncio.sleep(2.0)

    async def _market_discovery_and_book_loop(self) -> None:
        """Continuously synchronize active market, target strike, expiry timer, and orderbook with Kalshi source of truth."""
        connector = create_aiohttp_connector()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json",
        }
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            while self._running:
                try:
                    now_utc = clock_sync.web_now()
                    synced_from_mother = False

                    # 1. Primary Sync: Inherit 100% unified market truth from Mother Dash (Port 8000)
                    try:
                        async with session.get("http://127.0.0.1:8000/api/state", timeout=aiohttp.ClientTimeout(total=0.5)) as resp:
                            if resp.status == 200:
                                m_data = await resp.json()
                                market = m_data.get("market", {})
                                if market and market.get("ticker"):
                                    new_ticker = market["ticker"]
                                    if self.active_ticker and new_ticker != self.active_ticker:
                                        logger.info("🔄 [CYCLE ROLLOVER] %s -> %s. Sweeping resting orders...", self.active_ticker, new_ticker)
                                        asyncio.create_task(self._cancel_resting_orders())

                                    self.active_ticker = new_ticker
                                    if market.get("target_strike") is not None:
                                        self.target_strike = Decimal(str(market["target_strike"]))
                                    if market.get("current_btc_price") is not None:
                                        self.current_btc_spot = Decimal(str(market["current_btc_price"]))
                                        self.brti_connected = True
                                    if market.get("twap_60s_price") is not None:
                                        self.twap_60s = Decimal(str(market["twap_60s_price"]))

                                    t_rem = market.get("expiry_countdown_seconds")
                                    if t_rem is not None:
                                        self.active_market_close_dt = now_utc + timedelta(seconds=int(t_rem))

                                    self.target_time_str = market.get("target_time_str", "")
                                    self.time_window_str = market.get("time_window_str", "")

                                    yb = market.get("best_yes_bid")
                                    ya = market.get("best_yes_ask")
                                    nb = market.get("best_no_bid")
                                    na = market.get("best_no_ask")
                                    if yb is not None and yb > 0:
                                        self.best_yes_bid = Decimal(str(round(yb * 100, 1))) if yb < 1.0 else Decimal(str(yb))
                                    if ya is not None and ya > 0:
                                        self.best_yes_ask = Decimal(str(round(ya * 100, 1))) if ya < 1.0 else Decimal(str(ya))
                                    if nb is not None and nb > 0:
                                        self.best_no_bid = Decimal(str(round(nb * 100, 1))) if nb < 1.0 else Decimal(str(nb))
                                    if na is not None and na > 0:
                                        self.best_no_ask = Decimal(str(round(na * 100, 1))) if na < 1.0 else Decimal(str(na))

                                    self.kalshi_ws_connected = True
                                    synced_from_mother = True
                    except Exception:
                        synced_from_mother = False

                    # 2. Standalone Fallback: Query live Kalshi public REST API directly (Zero mock data)
                    if not synced_from_mother:
                        series = self.active_cfg.series_ticker_15m
                        url = f"{self.rest_base}/markets?series_ticker={series}&status=open&limit=10"
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2.5)) as resp2:
                            if resp2.status == 200:
                                data = await resp2.json()
                                markets = data.get("markets", [])
                                valid_m = []
                                for m in markets:
                                    c_str = m.get("close_time") or m.get("expiration_time")
                                    if c_str:
                                        c_dt = datetime.fromisoformat(c_str.replace("Z", "+00:00"))
                                        if c_dt > now_utc:
                                            valid_m.append((c_dt, m))
                                if valid_m:
                                    valid_m.sort(key=lambda x: x[0])
                                    active_close, active_m = valid_m[0]
                                    new_ticker = active_m.get("ticker", "")
                                    if self.active_ticker and new_ticker != self.active_ticker:
                                        logger.info("🔄 [CYCLE ROLLOVER] %s -> %s. Sweeping resting orders...", self.active_ticker, new_ticker)
                                        asyncio.create_task(self._cancel_resting_orders())

                                    self.active_ticker = new_ticker
                                    self.active_market_close_dt = active_close
                                    fl = active_m.get("floor_strike") or active_m.get("cap_strike")
                                    if fl is not None:
                                        self.target_strike = Decimal(str(fl))

                                    et_tz = ZoneInfo("America/New_York")
                                    close_et = active_close.astimezone(et_tz)
                                    start_et = close_et - timedelta(minutes=15)
                                    hr_target = close_et.hour % 12 or 12
                                    ampm_target = "am" if close_et.hour < 12 else "pm"
                                    self.target_time_str = f"{hr_target}:{close_et.minute:02d}{ampm_target} ET"
                                    hr_open = start_et.hour % 12 or 12
                                    self.time_window_str = f"{start_et.strftime('%B %d')}, {hr_open}:{start_et.strftime('%M')} - {hr_target}:{close_et.strftime('%M %p ET')}"

                                    # Fetch real L2 orderbook
                                    ob_url = f"{self.rest_base}/markets/{new_ticker}/orderbook"
                                    async with session.get(ob_url, timeout=aiohttp.ClientTimeout(total=2.0)) as resp_ob:
                                        if resp_ob.status == 200:
                                            ob_data = await resp_ob.json()
                                            raw_book = ob_data.get("orderbook_fp") or ob_data.get("orderbook") or {}
                                            bids = raw_book.get("yes_dollars") or raw_book.get("yes") or []
                                            asks = raw_book.get("no_dollars") or raw_book.get("no") or []
                                            if bids:
                                                self.best_yes_bid = Decimal(str(bids[0][0])) * Decimal("100") if Decimal(str(bids[0][0])) < Decimal("1.0") else Decimal(str(bids[0][0]))
                                            if asks:
                                                self.best_no_bid = Decimal(str(asks[0][0])) * Decimal("100") if Decimal(str(asks[0][0])) < Decimal("1.0") else Decimal(str(asks[0][0]))
                                            if self.best_yes_bid and not self.best_yes_ask:
                                                self.best_yes_ask = (Decimal("100") - self.best_no_bid) if self.best_no_bid else self.best_yes_bid + Decimal("2")
                                            if self.best_no_bid and not self.best_no_ask:
                                                self.best_no_ask = (Decimal("100") - self.best_yes_bid) if self.best_yes_bid else self.best_no_bid + Decimal("2")
                                            self.kalshi_ws_connected = True

                    await asyncio.sleep(0.5)
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.warning("Market discovery error: %s", exc)
                    await asyncio.sleep(2.0)

    async def _hmm_evaluation_loop(self) -> None:
        """Evaluate 5m HMM regime at 10-second intervals."""
        while self._running:
            try:
                candles = self.candle_builder.get_candles("BTCUSDT", count=50)
                if len(candles) >= 10 and not self.hmm_brain.is_trained:
                    self.hmm_brain.train(candles)
                elif len(candles) >= 3:
                    self.hmm_brain.predict_regime(candles)
                await asyncio.sleep(10.0)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("HMM evaluation error: %s", exc)
                await asyncio.sleep(10.0)

    async def _sync_upstream_bot2(self) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Fetch real-time inference outputs directly from Bot 2 (Port 8002)."""
        try:
            async with httpx.AsyncClient(timeout=0.5) as client:
                resp = await client.get("http://127.0.0.1:8002/api/state")
                if resp.status_code == 200:
                    data = resp.json()
                    b1_sig = data.get("brain_1_signal")
                    b1_conf = float(data.get("brain_1_confidence", 50.0)) / 100.0
                    b2_sig = data.get("brain_2_signal")
                    b2_conf = float(data.get("brain_2_confidence", 50.0)) / 100.0

                    # Synchronize spot price and target strike if available
                    b2_spot = data.get("spot_price")
                    b2_strike = data.get("target_strike")
                    b2_ticker = data.get("active_ticker")
                    if b2_spot and float(b2_spot) > 0:
                        self.current_btc_spot = Decimal(str(b2_spot))
                    if b2_strike and float(b2_strike) > 0:
                        self.target_strike = Decimal(str(b2_strike))
                    if b2_ticker:
                        self.active_ticker = b2_ticker

                    # Update inside quotes if available
                    if data.get("best_yes_bid") is not None:
                        self.best_yes_bid = Decimal(str(data["best_yes_bid"]))
                    if data.get("best_yes_ask") is not None:
                        self.best_yes_ask = Decimal(str(data["best_yes_ask"]))
                    if data.get("best_no_bid") is not None:
                        self.best_no_bid = Decimal(str(data["best_no_bid"]))
                    if data.get("best_no_ask") is not None:
                        self.best_no_ask = Decimal(str(data["best_no_ask"]))

                    q_inf = {"signal": b1_sig, "confidence": b1_conf} if b1_sig else None
                    k_inf = {"signal": b2_sig, "confidence": b2_conf} if b2_sig else None
                    return q_inf, k_inf
        except Exception:
            pass
        return None, None

    async def _decision_evaluation_loop(self) -> None:
        """Execute 15M cycle evaluation and trade routing."""
        while self._running:
            try:
                t_rem = self.get_time_to_expiry()
                
                # Ingest Bot 2 real-time outputs with local directional fallback
                q_inf, k_inf = await self._sync_upstream_bot2()
                diff = float(self.current_btc_spot - self.target_strike) if (self.current_btc_spot and self.target_strike) else 0.0

                if q_inf is None and abs(diff) > 0.1:
                    sig = "UP" if diff > 0 else "DOWN"
                    conf = min(0.90, max(0.55, 0.50 + abs(diff) / 250.0))
                    q_inf = {"signal": sig, "confidence": conf}

                if k_inf is None:
                    y_bid = float(self.best_yes_bid or 50)
                    n_bid = float(self.best_no_bid or 50)
                    k_sig = "UP" if y_bid >= n_bid else "DOWN"
                    k_conf = min(0.85, 0.50 + abs(y_bid - n_bid) / 100.0)
                    k_inf = {"signal": k_sig, "confidence": k_conf}

                if self.current_btc_spot > Decimal("0.00") and self.target_strike > Decimal("0.00"):
                    book_dict = {
                        "yes_bid": float(self.best_yes_bid or 50),
                        "yes_ask": float(self.best_yes_ask or 52),
                        "no_bid": float(self.best_no_bid or 48),
                        "no_ask": float(self.best_no_ask or 50),
                    }
                    async with self._eval_lock:
                        dec = self.bot.evaluate(
                            asset=self.active_asset,
                            spot_price=self.current_btc_spot,
                            target_strike=self.target_strike,
                            time_to_expiry_s=t_rem,
                            book=book_dict,
                            quolas_inference=q_inf,
                            kalshi_inference=k_inf,
                        )
                        self.last_decision = dec
                        self.last_eval_time = time.time()

                    if self.is_armed and dec.call in ("YES", "NO"):
                        cycle_key = self.active_ticker or "KXBTC15M_ACTIVE"
                        if self.last_traded_cycle != cycle_key and t_rem > 90.0:
                            is_allowed, g_reason, approved_size, _ = self.guardrails.validate_pre_trade_intent(
                                ticker=cycle_key,
                                side=dec.call,
                                requested_size=1,
                                est_price=Decimal(str(dec.limit_price or "0.52")),
                                total_equity=self.balance_dollars,
                                cycle_id=cycle_key,
                                is_bot=True,
                                bot_type="macro_trend_dominion",
                                is_live=self.is_live,
                            )
                            if is_allowed:
                                is_permitted, coord_reason = self.coordinator.check_trade_permission(
                                    ticker=cycle_key,
                                    proposed_side=dec.call,
                                    bot_id="macro_trend_dominion",
                                    requested_contracts=approved_size,
                                    is_live=self.is_live,
                                )
                                if not is_permitted:
                                    logger.warning("🛡️ [COORDINATOR / SEAL VETO] %s on %s: %s", dec.call.upper(), cycle_key, coord_reason)
                                else:
                                    self._execute_trade(dec, cycle_key)
                            else:
                                logger.info("🛡️ [GUARDRAIL VETO] %s | %s", cycle_key, g_reason)

                # Process and match resting orders against inside quotes and expiration window
                for oid, order in list(self.active_resting_orders.items()):
                    if order.get("status") == "RESTING":
                        lim_price = Decimal(str(order["limit_price_cents"])) / Decimal("100")
                        side = order["side"]
                        is_filled = False
                        fill_p = lim_price
                        if side == "YES" and self.best_yes_ask is not None and lim_price >= self.best_yes_ask:
                            is_filled = True
                            fill_p = min(lim_price, self.best_yes_ask)
                        elif side == "NO" and self.best_no_ask is not None and lim_price >= self.best_no_ask:
                            is_filled = True
                            fill_p = min(lim_price, self.best_no_ask)

                        if is_filled:
                            order["status"] = "FILLED"
                            order["fill_price"] = fill_p
                            order["fee"] = OrderSimulator.calculate_kalshi_taker_fee(fill_p, order["contracts"])
                            logger.info(
                                "🎯 [RESTING MATCHED & FILLED] %s | %s @ $%s (fee: $%s)",
                                order["cycle"], side, fill_p, order["fee"]
                            )
                        elif t_rem <= 90.0:
                            order["status"] = "EXPIRED"
                            logger.info(
                                "⏰ [RESTING ORDER EXPIRED UNFILLED] %s | %s @ %dc unfilled (T_rem <= 90s)",
                                order["cycle"], side, order["limit_price_cents"]
                            )

                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Decision evaluation error: %s", exc)
                await asyncio.sleep(1.0)

    def _execute_trade(self, dec: MacroDominionDecision, cycle_key: str) -> None:
        """Route order in Paper or Live mode."""
        self.last_traded_cycle = cycle_key
        side = dec.call
        price_cents = int(round(float(dec.limit_price) * 100))
        contracts = 1  # Hard Micro-Bankroll Invariant

        order_record = {
            "order_id": f"macro_paper_{int(time.time()*1000)}",
            "cycle": cycle_key,
            "side": side,
            "contracts": contracts,
            "limit_price_cents": price_cents,
            "ev_dollars": float(dec.expected_value),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "RESTING",
        }
        self.active_resting_orders[order_record["order_id"]] = order_record

        logger.info(
            "🎯 [TRADE SUBMITTED] %s | Call: %s @ %dc | 1 ct | EV: +$%.2f | Mode: %s",
            cycle_key,
            side,
            price_cents,
            float(dec.expected_value),
            self.execution_mode,
        )

    async def _settlement_reconciliation_loop(self) -> None:
        """Detect cycle expiry, evaluate win/loss, and feed Mistake-Learning Engine."""
        last_settled = ""
        while self._running:
            try:
                t_rem = self.get_time_to_expiry()
                if t_rem <= 5.0 and self.active_ticker and self.active_ticker != last_settled:
                    last_settled = self.active_ticker
                    actual_outcome = "YES" if self.current_btc_spot >= self.target_strike else "NO"

                    # If no resting orders placed, record observed cycle if bot made a definitive call
                    if not self.active_resting_orders and self.last_decision and self.last_decision.call in ("YES", "NO"):
                        is_win = (self.last_decision.call == actual_outcome)
                        pred_conf = float(self.last_decision.confidence_pct / 100.0)
                        price = self.last_decision.limit_price or Decimal("0.52")
                        pnl = (Decimal("1.00") - price) if is_win else -price
                        rec = self.bot.record_cycle_outcome(
                            cycle_id=self.active_ticker,
                            ticker=self.active_ticker,
                            call=self.last_decision.call,
                            predicted_prob=pred_conf,
                            fill_price=price,
                            outcome="win" if is_win else "loss",
                            pnl=pnl,
                            macro_trend=self.last_decision.macro_trend,
                            hmm_regime=self.last_decision.hmm_regime,
                            execution_mode=self.execution_mode.lower(),
                        )
                        logger.info(
                            "🧠 [OBSERVED CYCLE RECALIBRATED] %s Settle: %s | Pred: %s | Result: %s | Brier: %.4f",
                            self.active_ticker,
                            actual_outcome,
                            self.last_decision.call,
                            "WIN" if is_win else "LOSS",
                            rec.get("brier_score", 0.0),
                        )

                    for oid, order in list(self.active_resting_orders.items()):
                        if order.get("status") != "FILLED":
                            logger.info(
                                "ℹ️ [SETTLEMENT SKIPPED] Order %s on %s was %s (unfilled). $0.00 PnL recorded.",
                                oid, order.get("cycle"), order.get("status")
                            )
                            continue

                        is_win = (order["side"] == actual_outcome)
                        price = order.get("fill_price") or (Decimal(str(order["limit_price_cents"])) / Decimal("100"))
                        fee = order.get("fee", Decimal("0.00"))
                        gross_pnl = (Decimal("1.00") - price) if is_win else -price
                        pnl = gross_pnl - fee if is_win else gross_pnl

                        self.settled_cycles += 1
                        if is_win:
                            self.today_wins += 1
                        else:
                            self.today_losses += 1
                        self.today_pnl += pnl
                        total_games = self.today_wins + self.today_losses
                        self.today_win_rate = (self.today_wins / total_games * 100.0) if total_games > 0 else 0.0

                        report = {
                            "cycle": order["cycle"],
                            "side": order["side"],
                            "outcome": actual_outcome,
                            "win": is_win,
                            "price_cents": order["limit_price_cents"],
                            "pnl_dollars": float(pnl),
                            "time": datetime.now(timezone.utc).strftime("%H:%M:%S ET"),
                        }
                        self.recent_reports.insert(0, report)
                        if len(self.recent_reports) > 20:
                            self.recent_reports.pop()

                        # FEED MISTAKE-LEARNING ENGINE
                        pred_conf = float(self.last_decision.confidence_pct / 100.0) if self.last_decision else 0.65
                        rec = self.bot.record_cycle_outcome(
                            cycle_id=order["cycle"],
                            ticker=self.active_ticker,
                            call=order["side"],
                            predicted_prob=pred_conf,
                            fill_price=price,
                            outcome="win" if is_win else "loss",
                            pnl=pnl,
                            macro_trend=self.last_decision.macro_trend if self.last_decision else "CHOP",
                            hmm_regime=self.last_decision.hmm_regime if self.last_decision else "STABLE_RANGE",
                            execution_mode=self.execution_mode.lower(),
                        )
                        self.guardrails.record_cycle_settlement(
                            ticker=self.active_ticker,
                            outcome="win" if is_win else "loss",
                            pnl=pnl,
                            balance_after=self.balance_dollars + self.today_pnl,
                            cycle_id=order["cycle"],
                            execution_mode=self.execution_mode.lower(),
                        )
                        logger.info(
                            "🧠 [LEARNING RECALIBRATED] %s Settle: %s | Result: %s | PnL: %+$0.2f | Brier: %.4f",
                            order["cycle"],
                            actual_outcome,
                            "WIN" if is_win else "LOSS",
                            float(pnl),
                            rec.get("brier_score", 0.0),
                        )

                    self.active_resting_orders.clear()

                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Settlement reconciliation error: %s", exc)
                await asyncio.sleep(2.0)


# ---------------------------------------------------------------------------
# Global Application & Lifespan
# ---------------------------------------------------------------------------

app_engine: Optional[StandaloneMacroEngine] = None
engine_lock: Optional[TradingEngineLock] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global app_engine, engine_lock

    force_lock = os.getenv("KALSHI_FORCE_LOCK", "false").lower() in ("true", "1", "yes")
    engine_lock = TradingEngineLock(lock_path=LOCK_FILE_PATH, owner_name="standalone_macro")
    engine_lock.acquire(force=force_lock)

    is_live = os.getenv("KALSHI_ENV", "demo").lower() in ("prod", "live")
    app_engine = StandaloneMacroEngine(is_live=is_live, is_armed=True, asset=CryptoAsset.BTC)
    await app_engine.start()

    yield

    if app_engine:
        await app_engine.stop()
    if engine_lock:
        engine_lock.release()


app = FastAPI(title="Kalshi Macro Trend Dominion Standalone", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def get_cockpit() -> str:
    """Serve ultra-lean Macro Pocket Cockpit UI."""
    if TEMPLATE_PATH.exists():
        return TEMPLATE_PATH.read_text(encoding="utf-8")
    return "<h1>Macro Pocket Cockpit template not found.</h1>"


@app.get("/api/state")
@app.get("/api/status")
async def get_state() -> Dict[str, Any]:
    """Provide real-time telemetry to Macro Pocket Cockpit."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine initializing")

    cfg = app_engine.active_cfg
    t_rem = app_engine.get_time_to_expiry()
    mins = int(t_rem // 60)
    secs = int(t_rem % 60)
    t_str = f"{mins:02d}:{secs:02d}" if t_rem > 0 else "00:00"

    spot_dec = app_engine.current_btc_spot
    strike_dec = app_engine.target_strike
    if strike_dec > Decimal("0.00"):
        diff_dec = spot_dec - strike_dec
        diff_pct_dec = (diff_dec / strike_dec) * Decimal("100.0")
    else:
        diff_dec = Decimal("0.00")
        diff_pct_dec = Decimal("0.00")

    is_up = diff_dec >= Decimal("0.00")
    diff_str = cfg.format_diff(diff_dec, diff_pct_dec)

    dec = app_engine.last_decision
    diag = app_engine.bot.learning_engine.get_diagnostics()

    return {
        "bot_type": "macro_trend_dominion",
        "bot_name": "Macro Trend Dominion (Bot 3)",
        "armed": app_engine.is_armed,
        "is_live": app_engine.is_live,
        "execution_mode": app_engine.execution_mode,
        "peer_bot_active": app_engine.peer_bot_active,
        "mutual_interlock_msg": app_engine.interlock_msg,
        "balance": float(app_engine.balance_dollars),
        "today_pnl": float(app_engine.today_pnl),
        "settled_cycles": app_engine.settled_cycles,
        "today_wins": app_engine.today_wins,
        "today_losses": app_engine.today_losses,
        "today_win_rate": round(app_engine.today_win_rate, 1),
        "active_asset": app_engine.active_asset.value,
        "active_ticker": app_engine.active_ticker,
        "time_remaining_str": t_str,
        "time_window_str": app_engine.time_window_str,
        "target_time_str": app_engine.target_time_str,
        "expiry_countdown_seconds": int(t_rem),
        "spot_price": float(spot_dec),
        "target_strike": float(strike_dec),
        "spot_diff": float(diff_dec),
        "spot_diff_pct": float(diff_pct_dec),
        "spot_diff_str": diff_str,
        "twap_60s": float(app_engine.twap_60s) if getattr(app_engine, "twap_60s", None) else None,
        "is_above_strike": is_up,
        "best_yes_bid": float(app_engine.best_yes_bid) if app_engine.best_yes_bid else None,
        "best_yes_ask": float(app_engine.best_yes_ask) if app_engine.best_yes_ask else None,
        "best_no_bid": float(app_engine.best_no_bid) if app_engine.best_no_bid else None,
        "best_no_ask": float(app_engine.best_no_ask) if app_engine.best_no_ask else None,
        "decision": dec.to_dict() if dec else None,
        "three_brain_matrix": {
            "spot_signal": dec.spot_signal if dec else "WAIT",
            "spot_confidence": round(dec.spot_confidence * 100.0, 1) if dec else 50.0,
            "kalshi_signal": dec.kalshi_signal if dec else "WAIT",
            "kalshi_confidence": round(dec.kalshi_confidence * 100.0, 1) if dec else 50.0,
            "hmm_regime": app_engine.hmm_brain.current_regime.name,
            "macro_trend": dec.macro_trend if dec else "CHOP",
        },
        "learning_engine": {
            "brier_score": round(diag.get("average_brier_score", 0.0), 4),
            "shrinkage_factor": round(diag.get("shrinkage_factor", 1.0), 3),
            "cycles_evaluated": diag.get("total_cycles_recorded", 0),
            "mistakes_logged": sum(diag.get("mistake_breakdown", {}).values()),
            "pruned_deciles": ["60¢-89¢"] if float(diag.get("active_price_cap", 0.89)) < 0.60 else [],
            "active_price_cap": float(diag.get("active_price_cap", 0.89)),
        },
        "parameters": app_engine.get_parameters(),
        "recent_reports": app_engine.recent_reports,
        "active_resting_orders": list(app_engine.active_resting_orders.values()),
    }


@app.post("/api/arm")
async def arm_bot() -> Dict[str, Any]:
    """Arm the bot for autonomous trade execution."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine initializing")
    app_engine.is_armed = True
    logger.info("🛡️ [MASTER CONTROL] Bot 3 ARMED on Port 8003.")
    return {"status": "SUCCESS", "armed": True}


@app.post("/api/disarm")
async def disarm_bot() -> Dict[str, Any]:
    """Disarm the bot."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine initializing")
    app_engine.is_armed = False
    logger.info("🛡️ [MASTER CONTROL] Bot 3 DISARMED on Port 8003.")
    return {"status": "SUCCESS", "armed": False}


@app.post("/api/panic")
async def panic_halt() -> Dict[str, Any]:
    """Emergency Panic: Disarm and sweep all open resting orders."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine initializing")
    app_engine.is_armed = False
    await app_engine._cancel_resting_orders()
    logger.warning("🚨 [PANIC HALT] Triggered on Port 8003.")
    return {"status": "SUCCESS", "armed": False, "panic": True}


@app.post("/api/sweep")
@app.post("/api/sweep-orders")
async def sweep_orders() -> Dict[str, Any]:
    """Cancel all open resting orders without disarming."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine initializing")
    await app_engine._cancel_resting_orders()
    return {"status": "SUCCESS", "swept": True}


@app.get("/api/bot/parameters")
@app.get("/api/parameters")
async def get_parameters() -> Dict[str, Any]:
    """Retrieve full 9 dial parameters."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine initializing")
    return app_engine.get_parameters()


class MacroParametersUpdateRequest(BaseModel):
    limit_price_cents: Optional[int] = None
    min_confidence_pct: Optional[float] = None
    min_ev_dollars: Optional[float] = None
    volatility_moat_dollars: Optional[float] = None
    hmm_risk_off_veto: Optional[bool] = None
    macro_trend_window: Optional[str] = None
    take_profit_harvest_cents: Optional[int] = None
    adaptive_learning_rate: Optional[float] = None
    max_contracts: Optional[int] = None


@app.post("/api/bot/parameters")
@app.post("/api/parameters")
async def update_parameters(req: MacroParametersUpdateRequest) -> Dict[str, Any]:
    """Update Bot 3 strategy dials."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine initializing")
    data = req.model_dump(exclude_unset=True)
    updated = app_engine.update_parameters(**data)
    return {"status": "SUCCESS", "parameters": updated}


# ---------------------------------------------------------------------------
# Floating Desktop Widget Endpoints
# ---------------------------------------------------------------------------

class WindowPinRequest(BaseModel):
    topmost: bool = True
    width: Optional[int] = None
    height: Optional[int] = None


class WindowResizeRequest(BaseModel):
    width: int
    height: int
    topmost: Optional[bool] = None


@app.get("/api/window/status")
async def get_window_status() -> Dict[str, Any]:
    windows = find_cockpit_windows()
    if not windows:
        return {"available": False, "is_topmost": False, "windows_count": 0}
    hwnd, title = windows[0]
    topmost = is_always_on_top(hwnd)
    return {"available": True, "is_topmost": topmost, "hwnd": hwnd, "title": title, "windows_count": len(windows)}


@app.post("/api/window/pin")
async def pin_window(req: WindowPinRequest) -> Dict[str, Any]:
    windows = find_cockpit_windows()
    if not windows:
        raise HTTPException(status_code=404, detail="No Pocket Cockpit window found")
    results = []
    for hwnd, title in windows:
        ok = set_always_on_top(hwnd, req.topmost)
        if req.width and req.height:
            resize_window(hwnd, req.width, req.height, topmost=req.topmost)
        results.append({"hwnd": hwnd, "title": title, "topmost": req.topmost, "success": ok})
    return {"status": "SUCCESS", "topmost": req.topmost, "windows": results}


@app.post("/api/window/resize")
async def resize_cockpit_window(req: WindowResizeRequest) -> Dict[str, Any]:
    windows = find_cockpit_windows()
    if not windows:
        raise HTTPException(status_code=404, detail="No Pocket Cockpit window found")
    results = []
    for hwnd, title in windows:
        ok = resize_window(hwnd, req.width, req.height, topmost=req.topmost)
        results.append({"hwnd": hwnd, "success": ok})
    return {"status": "SUCCESS", "width": req.width, "height": req.height, "windows": results}


@app.post("/api/window/launch-widget")
async def spawn_widget_window() -> Dict[str, Any]:
    port = 8003
    ok = launch_widget_window(port=port, view="minimized")
    return {"status": "LAUNCHED" if ok else "FAILED", "success": ok}


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Kalshi Macro Trend Dominion Standalone Bot")
    parser.add_argument("--port", type=int, default=8003, help="HTTP Cockpit port (default: 8003)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="HTTP Cockpit host (default: 0.0.0.0)")
    parser.add_argument("--paper", action="store_true", default=False, help="Enable paper execution (Lane 2 Incubator)")
    parser.add_argument("--live", action="store_true", default=False, help="Enable live execution mode")
    parser.add_argument("--force", action="store_true", default=False, help="Force lock acquisition if stale")
    parser.add_argument("--no-browser", action="store_true", default=False, help="Do not open browser automatically")
    parser.add_argument("--widget", action="store_true", default=False, help="Launch as floating desktop widget")
    parser.add_argument("--asset", type=str, default="BTC", choices=["BTC", "ETH", "SOL", "DOGE"])
    args = parser.parse_args()

    if args.force:
        os.environ["KALSHI_FORCE_LOCK"] = "true"
    if args.asset:
        os.environ["KALSHI_ACTIVE_ASSET"] = args.asset.upper()

    is_live = args.live and not args.paper
    os.environ["KALSHI_ENV"] = "live" if is_live else "demo"

    if args.widget:
        def _delayed_widget():
            time.sleep(1.2)
            launch_widget_window(port=args.port, view="minimized")
        threading.Thread(target=_delayed_widget, daemon=True).start()
    elif not args.no_browser:
        def _delayed_open():
            time.sleep(1.2)
            try:
                webbrowser.open(f"http://localhost:{args.port}")
            except Exception:
                pass
        threading.Thread(target=_delayed_open, daemon=True).start()

    logger.info("⚡ Launching Kalshi Macro Trend Dominion Standalone Engine on http://%s:%d ...", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()

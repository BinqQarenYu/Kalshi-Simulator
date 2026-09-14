"""Kalshi Dual-Brain ONNX Strategy — 24/7 Autonomous Standalone Trading Engine (Port 8002).

Ultra-lean execution daemon that trades 24/7 independently of the main dashboard:
1. Pre-Flight Audit Gate: Certifies strategy through BotDeploymentAuditor across all 4 pillars before live trade routing.
2. Mutual Exclusion & Interlock: Acquires data/trading_engine_onnx.lock. Checks data/trading_engine.lock to ensure single-account capital safety.
3. Dual-Brain Ingestion: Ingests Binance combined orderflow (depth20@100ms + aggTrade) for Brain 1 and Kalshi L2 CLOB for Brain 2.
4. Institutional Guardrails: Enforces 1-contract sizing armor, 1-trade-per-cycle locks, gamma cliff cutoff (90s), and cross-brain temporal skew guard (1000ms).
5. Windows 24/7 Away-Mode: Prevents sleep/suspension when monitor turns off.
6. Ultra-Lean Pocket Cockpit UI: Serves institutional dark-themed cockpit on port 8002 with Master Arm/Disarm, Panic Halt, and Desktop Widget launcher.
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
import threading
import time
from typing import Any, AsyncIterator, Dict, List, Optional
import webbrowser
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
load_dotenv()

import aiohttp
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
from kalshi_sim.ml.dual_onnx_schemas import DualONNXDecision, DualONNXRegime
from kalshi_sim.ml.dual_onnx_strategy import DualONNXArbitrageBot
from kalshi_sim.ml.quolas_core.candle_builder import CandleBuilder
from kalshi_sim.ml.quolas_core.hmm_brain import HMMBrain
from kalshi_sim.order_client import KalshiDemoOrderClient, KalshiLiveOrderClient
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
logger = logging.getLogger("StandaloneONNX")

LOCK_FILE_PATH = Path("data") / "trading_engine_onnx.lock"
DOM_LOCK_FILE_PATH = Path("data") / "trading_engine.lock"
TEMPLATE_PATH = Path(__file__).parent / "templates" / "pocket_cockpit_onnx.html"
ET_ZONE = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# Power Management
# ---------------------------------------------------------------------------

def prevent_windows_sleep() -> None:
    """Keep Windows execution state active 24/7 with monitor off."""
    if sys.platform == "win32":
        try:
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_AWAYMODE_REQUIRED = 0x00000040
            res = ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
            )
            if res != 0:
                logger.info("🛡️ [POWER MANAGEMENT] Windows Sleep Prevention & Away Mode ACTIVE.")
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
# Standalone ONNX Bot Engine
# ---------------------------------------------------------------------------

class StandaloneONNXEngine:
    """Core autonomous trading coordinator for The ONNX Strategy (Port 8002)."""

    def __init__(
        self,
        is_live: bool = True,
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
        self.bot = DualONNXArbitrageBot(
            asset=asset,
            hmm_brain=self.hmm_brain,
            candle_builder=self.candle_builder,
        )

        # 2. Guardrails Setup (Authorized for The ONNX Strategy, strictly 1 contract max)
        self.guardrails = AgentGuardrails(
            min_order_interval_seconds=45.0,
            max_micro_bankroll_contracts=1,
            max_nano_bankroll_contracts=1,
            vpin_toxic_threshold=0.60,
        )
        self.guardrails.authorize_live_bot("the_onnx_strategy")
        self.auditor = BotDeploymentAuditor()
        self.orderbook = OrderBookManager(enforce_consecutive_seq=False)

        # 3. Pre-Flight 4-Pillar Certification Audit
        mode_str = "live" if is_live else "simulated"
        audit_rep = self.auditor.audit_bot("the_onnx_strategy", self.bot, mode=mode_str)
        if not audit_rep.is_certified:
            err_msgs = [f"{p.pillar_name}: {p.message}" for p in audit_rep.pillars if p.status == "FAIL"]
            raise RuntimeError(f"Strategy the_onnx_strategy FAILED pre-flight audit: {'; '.join(err_msgs)}")
        logger.info("✅ [AUDIT CERTIFIED] The ONNX Strategy passed all 4 pillars for %s trading.", mode_str.upper())

        # 4. Exchange Connection Setup
        self.api_key_id = os.getenv("KALSHI_API_KEY_ID", "")
        self.private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")
        self.env = os.getenv("KALSHI_ENV", "live" if is_live else "demo").lower()
        self.rest_base = PROD_REST_BASE if self.env in ("prod", "live") else DEMO_REST_BASE
        self.ws_url = PROD_WS_URL if self.env in ("prod", "live") else DEMO_WS_URL

        self.order_client: Optional[KalshiLiveOrderClient] = None
        if self.api_key_id and self.private_key_path and Path(self.private_key_path).exists():
            self.order_client = KalshiLiveOrderClient(
                api_key_id=self.api_key_id,
                private_key_path=self.private_key_path,
                base_url=self.rest_base,
            )
            logger.info("🔑 [EXCHANGE AUTH] Authenticated KalshiLiveOrderClient initialized.")
        else:
            logger.warning("⚠️ [EXCHANGE AUTH] Live credentials not found in env; read-only market sync active.")

        # 5. Mutual Live Interlock State
        self.dom_bot_live_active: bool = False
        self.interlock_msg: str = "Exclusive Live Execution Authority Active"
        self.execution_mode: str = "LIVE" if self.is_live else "SHADOW"

        # 6. Partitioned Budget & Live Coordinator
        budget_env = os.getenv("KALSHI_ONNX_BUDGET")
        self.budget_dollars: Optional[Decimal] = Decimal(budget_env) if budget_env else None
        self.coordinator = LiveCoordinator()
        logger.info(
            "💰 [BUDGET] Virtual budget cap: %s",
            f"${self.budget_dollars}" if self.budget_dollars else "UNLIMITED (full account)"
        )
        self._check_mutual_interlock()

        # State Variables
        self.current_btc_spot: Decimal = Decimal("0.00")
        self.target_strike: Decimal = Decimal("0.00")
        self.active_ticker: str = ""
        self.active_market_close_dt: Optional[datetime] = None
        self.target_time_str: str = ""
        self.time_window_str: str = ""

        # Live Inside-Touch Quotes
        self.best_yes_bid: Optional[Decimal] = None
        self.best_yes_ask: Optional[Decimal] = None
        self.best_no_bid: Optional[Decimal] = None
        self.best_no_ask: Optional[Decimal] = None

        # Dual Brain Telemetry Caches
        self.last_spot_signal: str = "HOLD"
        self.last_spot_confidence: float = 0.50
        self.last_spot_update_ts: float = 0.0
        self.last_kalshi_signal: str = "HOLD"
        self.last_kalshi_confidence: float = 0.50
        self.last_kalshi_update_ts: float = 0.0

        # Balances & PnL
        self.total_balance_dollars: Decimal = Decimal("0.00")
        self.balance_dollars: Decimal = Decimal("0.00")
        self.today_pnl: Decimal = Decimal("0.00")
        self.settled_cycles: int = 0
        self.today_wins: int = 0
        self.today_losses: int = 0
        self.today_win_rate: float = 0.0
        self.recent_reports: List[Dict[str, Any]] = []

        self.last_decision: Optional[DualONNXDecision] = None
        self.last_eval_time: float = 0.0

        # Database persistence writer
        self.db_writer = DatabaseWriter(db_manager=get_db(self.data_dir / "kalshi_history.db"))
        self.active_resting_orders: Dict[str, Dict[str, Any]] = {}

        # Feeds & Sync
        self.cf_sync: Optional[CFBenchmarksSync] = None
        self.brti_connected: bool = False
        self.binance_connected: bool = False
        self.kalshi_ws_connected: bool = False
        self.coinbase_connected: bool = False
        self.spot_source: str = "Binance/Coinbase"
        self.spot_orderbook = L2BookState("BTCUSDT")
        self.timeframe: str = "15m"
        self._running: bool = False
        self.tasks: List[asyncio.Task] = []
        self._eval_lock = asyncio.Lock()

    def _check_mutual_interlock(self) -> None:
        """Verify if Port 8001 (Dominion) is actively running with live execution authority.

        When budget partitioning is active (--budget flag), both engines can
        trade live simultaneously with virtual budget caps instead of forcing
        SHADOW mode.
        """
        holder = get_active_lock_holder(DOM_LOCK_FILE_PATH)
        if holder:
            owner, pid = holder
            self.dom_bot_live_active = True
            if self.budget_dollars is not None and self.is_live:
                # Partitioned dual-live mode: both bots trade with virtual budgets
                budget_str = f"${self.budget_dollars}"
                self.execution_mode = "LIVE"
                self.interlock_msg = (
                    f"PARTITIONED LIVE: Port 8001 ({owner} PID {pid}) co-active. "
                    f"ONNX budget capped at {budget_str}. CFTC anti-wash coordinator active."
                )
                logger.info("🔀 [PARTITIONED LIVE] %s", self.interlock_msg)
            else:
                # Legacy exclusive interlock: Port 8001 active → force SHADOW
                self.interlock_msg = f"Port 8001 ({owner} PID {pid}) is armed live. Port 8002 running in Lane 2 Shadow Mode."
                if self.is_live:
                    self.execution_mode = "SHADOW"
                logger.info("🛡️ [MUTUAL INTERLOCK] %s", self.interlock_msg)
        else:
            self.dom_bot_live_active = False
            self.interlock_msg = "Exclusive Live Execution Authority Active"
            self.execution_mode = "LIVE" if self.is_live else "SHADOW"

    def get_time_to_expiry(self) -> float:
        """Calculate exact remaining seconds until active contract expiration boundary (Kalshi calibrated)."""
        now_utc = clock_sync.kalshi_now()
        
        if getattr(self, "active_market_close_dt", None):
            delta = (self.active_market_close_dt - now_utc).total_seconds()
            return max(0.0, delta)
            
        cur_min = now_utc.minute
        cur_sec = now_utc.second + now_utc.microsecond / 1_000_000.0
        boundary_min = 15 * (cur_min // 15 + 1)
        secs_left = (boundary_min - cur_min) * 60.0 - cur_sec
        return max(0.0, secs_left)

    def get_parameters(self) -> Dict[str, Any]:
        """Return full 12 ONNX parameters."""
        params = self.bot.get_parameters()
        params["execution_mode"] = self.execution_mode
        params["dom_bot_live_active"] = self.dom_bot_live_active
        params["mutual_interlock_msg"] = self.interlock_msg
        return params

    def update_parameters(self, **kwargs) -> Dict[str, Any]:
        """Update ONNX Strategy dials dynamically."""
        max_contracts = kwargs.get("max_contracts")
        if max_contracts is not None:
            clamped_size = max(1, min(1, int(max_contracts)))
            self.guardrails.max_micro_bankroll_contracts = clamped_size
            self.guardrails.max_nano_bankroll_contracts = clamped_size
            logger.info("🛡️ [GUARDRAIL PARAM UPDATE] Max contracts updated to: %d", clamped_size)
        vpin_thresh = kwargs.get("vpin_toxic_threshold")
        if vpin_thresh is not None:
            self.guardrails.vpin_toxic_threshold = float(vpin_thresh)
        self.bot.update_parameters(**kwargs)
        return self.get_parameters()

    def _sync_kalshi_clock(self) -> None:
        """Perform HTTP round-trip to calculate Kalshi server time drift vs local OS clock."""
        try:
            drift = clock_sync.sync()
            self._clock_drift_seconds = drift
        except Exception as e:
            logger.warning("[NTP SYNC] Clock sync warning on Port 8002: %s", e)
            self._clock_drift_seconds = getattr(self, "_clock_drift_seconds", 0.0)

    async def start(self) -> None:
        """Start all background loops for Port 8002."""
        self._running = True
        prevent_windows_sleep()

        # Synchronize NTP time drift with Kalshi API
        self._sync_kalshi_clock()

        # Start database persistence writer
        await self.db_writer.start()

        # Initial PnL and balance sync
        self.sync_pnl_reports()
        await self.sync_balance()

        # Start background workers
        self.tasks.append(asyncio.create_task(self._cf_spot_feed_loop(), name="cf_spot_feed"))
        self.tasks.append(asyncio.create_task(self._binance_feed_loop(), name="binance_orderflow_feed"))
        self.tasks.append(asyncio.create_task(self._market_discovery_and_book_loop(), name="market_book_sync"))
        self.tasks.append(asyncio.create_task(self._balance_polling_loop(), name="balance_poll"))
        self.tasks.append(asyncio.create_task(self._hmm_evaluation_loop(), name="hmm_regime_eval"))
        self.tasks.append(asyncio.create_task(self._settlement_reconciliation_loop(), name="settlement_sync"))
        logger.info(
            "🚀 [STANDALONE ONNX ACTIVE] Background loops spawned on Port 8002. Status: %s | Mode: %s",
            "ARMED" if self.is_armed else "DISARMED",
            self.execution_mode,
        )

    async def stop(self) -> None:
        """Gracefully stop engine and close HTTP/WS sessions."""
        self._running = False
        for t in self.tasks:
            t.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        await self.db_writer.stop()
        if self.cf_sync:
            await self.cf_sync.stop()
        if self.order_client:
            await self.order_client.close()
        logger.info("🛑 [STANDALONE ONNX STOPPED] Engine shut down cleanly on Port 8002.")

    def sync_pnl_reports(self) -> None:
        """Sync realized PnL and settled cycles from persisted win_loss_reports.json."""
        reports_file = self.data_dir / "win_loss_reports.json"
        if not reports_file.exists():
            return
        try:
            content = reports_file.read_text(encoding="utf-8")
            all_reports = json.loads(content)
            now_utc = datetime.now(timezone.utc)
            today_prefix = now_utc.strftime("%y%b%d").upper()
            today_iso = now_utc.strftime("%Y-%m-%d")

            target_bots = ("dual_onnx", "the_onnx_strategy", "onnx_macro_v2", "dual_onnx_bot")
            today_reports = [
                r for r in all_reports
                if (r.get("bot_type") in target_bots or r.get("strategy_id") in target_bots)
                and (today_prefix in r.get("ticker", "") or today_iso in str(r.get("timestamp_utc", "")))
            ]
            self.settled_cycles = len(today_reports)
            pnl_sum = sum(float(r.get("pnl", 0.0)) for r in today_reports)
            self.today_pnl = Decimal(str(round(pnl_sum, 2)))

            wins = sum(1 for r in today_reports if r.get("outcome") == "win")
            self.today_wins = wins
            self.today_losses = self.settled_cycles - wins
            self.today_win_rate = (wins / self.settled_cycles * 100.0) if self.settled_cycles > 0 else 0.0

            self.recent_reports = [
                {
                    "ticker": r.get("ticker", "N/A"),
                    "side": r.get("side", "N/A").upper(),
                    "contracts": r.get("contracts", 1),
                    "entry_price": r.get("entry_price", 0.0),
                    "outcome": r.get("outcome", "N/A").upper(),
                    "pnl": r.get("pnl", 0.0),
                    "timestamp": r.get("timestamp_utc", ""),
                }
                for r in reversed(today_reports[-5:])
            ]
        except Exception as e:
            logger.debug("Failed reading PnL reports: %s", e)

    async def sync_balance(self) -> None:
        """Fetch real cash balance from Kalshi authenticated REST API.

        When budget partitioning is active (--budget flag), balance_dollars is
        clamped to min(real_balance, budget_cap) so the guardrails see a
        virtual bankroll.
        """
        if not self.order_client:
            return
        try:
            bal_data = await self.order_client.get_balance()
            raw_cents = bal_data.get("balance", 0)
            self.total_balance_dollars = Decimal(str(raw_cents)) / Decimal("100")
            if self.budget_dollars is not None:
                self.balance_dollars = min(self.total_balance_dollars, self.budget_dollars)
            else:
                self.balance_dollars = self.total_balance_dollars
            logger.info("💰 [BALANCE SYNC] Realized: $%s | Virtual: $%s", self.total_balance_dollars, self.balance_dollars)
        except Exception as e:
            logger.debug("Balance sync warning: %s", e)

    async def _balance_polling_loop(self) -> None:
        """Periodic balance and mutual interlock polling loop."""
        while self._running:
            try:
                await self.sync_balance()
                self._check_mutual_interlock()
            except Exception as e:
                logger.debug("Balance polling exception: %s", e)
            await asyncio.sleep(10.0)

    # -------------------------------------------------------------------------
    # Feeds: CF Benchmarks Spot & Binance Orderflow
    # -------------------------------------------------------------------------

    async def _cf_spot_feed_loop(self) -> None:
        """Stream CME CF Benchmarks BRTI spot index at 5Hz (200ms) with Coinbase standby."""
        def _on_cf_asset_update(asset: CryptoAsset, price: Decimal, twap: Optional[Decimal], source: str) -> None:
            if asset == self.active_asset:
                self.current_btc_spot = price
                self.brti_connected = True
                self.spot_source = source

        if self.api_key_id and self.private_key_path and Path(self.private_key_path).exists():
            try:
                self.cf_sync = CFBenchmarksSync(
                    api_key_id=self.api_key_id,
                    private_key_path=self.private_key_path,
                    ws_url=self.ws_url,
                    rest_base=self.rest_base,
                    on_asset_price_update=_on_cf_asset_update,
                )
                await self.cf_sync.start()
                logger.info("📡 [CF BENCHMARKS] Official CME CF Real-Time Index (5Hz WS) active on Port 8002.")
            except Exception as e:
                logger.warning("Could not start CF Benchmarks sync: %s. Using standby feeds.", e)

        # Fallback Coinbase spot worker to ensure continuous spot pricing
        connector = create_aiohttp_connector()
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            while self._running:
                try:
                    if not (self.cf_sync and self.cf_sync.is_connected):
                        async with session.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
                            if resp.status == 200:
                                r_data = await resp.json()
                                amt = r_data.get("data", {}).get("amount")
                                if amt:
                                    self.current_btc_spot = Decimal(str(amt))
                                    self.coinbase_connected = True
                                    self.spot_source = "Coinbase REST BTC-USD (Standby)"
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.debug("Coinbase fallback error: %s", exc)
                await asyncio.sleep(1.0)

    async def _binance_feed_loop(self) -> None:
        """Ingest Binance real-time orderflow (depth20@100ms + aggTrade) into CandleBuilder and spot_orderbook."""
        url = "wss://stream.binance.com:9443/stream?streams=btcusdt@depth20@100ms/btcusdt@aggTrade"
        while self._running:
            try:
                connector = create_aiohttp_connector()
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.ws_connect(url, heartbeat=20.0) as ws:
                        self.binance_connected = True
                        logger.info("✅ [BINANCE WS] Connected to Binance Orderflow stream for Brain 1.")
                        async for msg in ws:
                            if not self._running:
                                break
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                stream = data.get("stream", "")
                                payload = data.get("data", {})
                                if "depth20" in stream:
                                    bids = payload.get("bids", [])
                                    asks = payload.get("asks", [])
                                    self.spot_orderbook.yes_book = {Decimal(str(p)): Decimal(str(q)) for p, q in bids}
                                    self.spot_orderbook.no_book = {Decimal(str(p)): Decimal(str(q)) for p, q in asks}
                                    self.spot_orderbook.last_update = datetime.now(timezone.utc)
                                elif "aggTrade" in stream:
                                    p = float(payload.get("p", 0.0))
                                    q = float(payload.get("q", 0.0))
                                    ts_ms = payload.get("T", int(time.time() * 1000))
                                    is_buyer_maker = payload.get("m", False)
                                    self.candle_builder.process_trade("BTCUSDT", p, q, ts_ms)
                                    # Update Brain 1 Spot Cache
                                    self.last_spot_update_ts = time.time()
                                    if self.current_btc_spot == Decimal("0.00") and p > 0:
                                        self.current_btc_spot = Decimal(str(p))
                            elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                                break
            except Exception as e:
                self.binance_connected = False
                logger.warning("⚠️ [BINANCE WS RECONNECT] Stream disconnected: %s. Retrying in 2s...", e)
                await asyncio.sleep(2.0)

    async def _hmm_evaluation_loop(self) -> None:
        """Periodically evaluate 5-minute candles to update HMM Macro Regime."""
        while self._running:
            try:
                candles = self.candle_builder.get_candles("BTCUSDT", interval_seconds=300, count=50)
                if candles and len(candles) >= 5:
                    self.hmm_brain.predict_regime({"BTCUSDT": candles})
            except Exception as e:
                logger.debug("HMM evaluation tick exception: %s", e)
            await asyncio.sleep(30.0)

    # -------------------------------------------------------------------------
    # Market Discovery, Kalshi Book Sync & Strategy Execution
    # -------------------------------------------------------------------------

    async def _market_discovery_and_book_loop(self) -> None:
        """Discover active Kalshi 15M BTC contracts, ingest L2 orderbook, and execute."""
        connector = create_aiohttp_connector()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
        discovery_counter = 0
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            while self._running:
                try:
                    discovery_counter += 1
                    # Discover or refresh active market
                    if not self.active_ticker or discovery_counter % 10 == 0:
                        await self._discover_active_market(session)

                    # Ingest orderbook for active contract
                    if self.active_ticker:
                        await self._sync_active_orderbook(session)
                        await self._evaluate_and_execute()
                    else:
                        self.kalshi_ws_connected = False
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.debug("[MARKET SYNC] Loop tick error: %s", exc)
                    self.kalshi_ws_connected = False

                await asyncio.sleep(0.5)

    async def _discover_active_market(self, session: aiohttp.ClientSession) -> None:
        """Discover current open 15M BTC contract, or upcoming initialized contract during maintenance."""
        try:
            now_utc = clock_sync.kalshi_now()

            # 0. Primary Sync: Inherit unified market truth from Mother Dash (Port 8000)
            try:
                async with session.get("http://127.0.0.1:8000/api/state", timeout=aiohttp.ClientTimeout(total=0.5)) as resp0:
                    if resp0.status == 200:
                        m_data = await resp0.json()
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
                            t_rem = market.get("expiry_countdown_seconds")
                            if t_rem is not None:
                                self.active_market_close_dt = now_utc + timedelta(seconds=int(t_rem))
                            self.target_time_str = market.get("target_time_str", "")
                            self.time_window_str = market.get("time_window_str", "")
                            return
            except Exception:
                pass

            valid_markets = []

            # 1. Primary: open markets
            open_url = f"{self.rest_base}/markets?series_ticker=KXBTC15M&status=open&limit=15"
            async with session.get(open_url, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for m in data.get("markets", []):
                        c_str = m.get("close_time") or m.get("expiration_time")
                        if c_str:
                            c_dt = datetime.fromisoformat(c_str.replace("Z", "+00:00"))
                            if c_dt > now_utc:
                                valid_markets.append((c_dt, m))

            # 2. Fallback: upcoming initialized contracts (e.g. daily CFTC maintenance 3-5 AM ET)
            if not valid_markets:
                init_url = f"{self.rest_base}/markets?series_ticker=KXBTC15M&limit=100"
                async with session.get(init_url, timeout=aiohttp.ClientTimeout(total=3.0)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for m in data.get("markets", []):
                            if m.get("status") in ("settled", "finalized", "determined"):
                                continue
                            c_str = m.get("close_time") or m.get("expiration_time")
                            if c_str:
                                c_dt = datetime.fromisoformat(c_str.replace("Z", "+00:00"))
                                if c_dt > now_utc:
                                    valid_markets.append((c_dt, m))

            if valid_markets:
                valid_markets.sort(key=lambda x: x[0])
                active_close, active_m = valid_markets[0]
                new_ticker = active_m.get("ticker", "")

                if self.active_ticker and new_ticker != self.active_ticker:
                    logger.info("🔄 [CYCLE ROLLOVER] %s -> %s. Sweeping resting orders...", self.active_ticker, new_ticker)
                    asyncio.create_task(self._cancel_resting_orders())

                self.active_ticker = new_ticker
                self.active_market_close_dt = active_close
                floor = active_m.get("floor_strike") or active_m.get("cap_strike")
                if floor is not None:
                    self.target_strike = Decimal(str(floor))

                close_et = active_close.astimezone(ET_ZONE)
                start_et = close_et - timedelta(minutes=15)
                self.target_time_str = close_et.strftime("%I:%M%p").lower() + " ET"
                self.time_window_str = f"{start_et.strftime('%B %d, %I:%M')} - {close_et.strftime('%I:%M %p')} ET"
        except Exception as e:
            logger.debug("Error discovering active market: %s", e)

    async def _sync_active_orderbook(self, session: aiohttp.ClientSession) -> None:
        """Fetch orderbook snapshot for active ticker via REST and update local state."""
        if not self.active_ticker:
            return
        try:
            ob_url = f"{self.rest_base}/markets/{self.active_ticker}/orderbook"
            async with session.get(ob_url, timeout=aiohttp.ClientTimeout(total=2.0)) as ob_resp:
                if ob_resp.status == 200:
                    ob_data = await ob_resp.json()
                    raw_book = ob_data.get("orderbook_fp") or ob_data.get("orderbook") or {}
                    bids = raw_book.get("yes_dollars") or raw_book.get("yes") or []
                    asks = raw_book.get("no_dollars") or raw_book.get("no") or []

                    book = self.orderbook.get_book(self.active_ticker)
                    if not book:
                        book = L2BookState(self.active_ticker)
                        self.orderbook.set_book(self.active_ticker, book)

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
                    book.last_update = datetime.now(timezone.utc)

                    self.best_yes_bid = book.best_yes_bid
                    self.best_yes_ask = book.best_yes_ask
                    self.best_no_bid = book.best_no_bid
                    self.best_no_ask = book.best_no_ask

                    self.kalshi_ws_connected = True
                    self.last_kalshi_update_ts = time.time()

                    # Derive baseline brain 2 signal if book is populated
                    if book.best_yes_bid and book.best_yes_bid >= Decimal("0.50"):
                        self.last_kalshi_signal = "UP"
                        self.last_kalshi_confidence = float(book.best_yes_bid)
                    elif book.best_no_bid and book.best_no_bid >= Decimal("0.50"):
                        self.last_kalshi_signal = "DOWN"
                        self.last_kalshi_confidence = float(book.best_no_bid)
        except Exception as e:
            logger.debug("Failed book sync for %s: %s", self.active_ticker, e)
            self.kalshi_ws_connected = False

    async def _evaluate_and_execute(self) -> None:
        """Run DualONNXArbitrageBot evaluation and execute with guardrail armor."""
        async with self._eval_lock:
            if not self.active_ticker:
                return

            kalshi_book = self.orderbook.get_book(self.active_ticker)
            if not kalshi_book:
                return

            t_rem = self.get_time_to_expiry()
            if t_rem <= 0:
                return

            # 1. Strategy Evaluation via DualONNXArbitrageBot
            try:
                diff_dollars = float(self.current_btc_spot - self.target_strike) if self.target_strike > 0 else 0.0
                decision = self.bot.evaluate(
                    spot_l2=self.spot_orderbook,
                    kalshi_l2=kalshi_book,
                    time_to_expiry_s=t_rem,
                    spot_diff=diff_dollars,
                )
                self.last_decision = decision
                self.last_eval_time = time.time()

                # Update live telemetry caches from neural decision
                self.last_spot_signal = decision.quolas_signal
                self.last_spot_confidence = decision.quolas_confidence
                self.last_kalshi_signal = decision.kalshi_signal
                self.last_kalshi_confidence = decision.kalshi_confidence
            except Exception as eval_err:
                logger.exception("❌ [EVALUATION ERROR] Error evaluating ONNX strategy: %s", eval_err)
                return

            # Handle Auto-Cancel on Veto or Gamma Cliff
            if decision.cancel_resting_orders:
                await self._cancel_resting_orders()

            if not self.is_armed or not decision.is_trade or not decision.side:
                return

            # Check Signal Recommendation
            rec_side = decision.side.lower()
            rec_size = min(decision.recommended_contracts, 1)  # Strictly 1 contract armor
            est_price = decision.recommended_limit_price
            target_ticker = self.active_ticker

            # 2. Institutional Pre-Trade Guardrail Check
            is_allowed, g_reason, approved_size, _ = self.guardrails.validate_pre_trade_intent(
                ticker=target_ticker,
                side=rec_side,
                requested_size=rec_size,
                est_price=est_price,
                total_equity=self.balance_dollars,
                cycle_id=target_ticker,
                is_bot=True,
                bot_type="the_onnx_strategy",
                is_live=(self.execution_mode == "LIVE"),
            )

            if not is_allowed or approved_size <= 0:
                logger.info("🛡️ [GUARDRAIL BLOCK] %s on %s: %s", rec_side.upper(), target_ticker, g_reason)
                return

            # 3. Execution Dispatch (Live vs Lane 2 Shadow)
            if self.execution_mode == "LIVE" and self.order_client:
                # 3a. Cross-Bot CFTC Anti-Wash Trading Coordinator & Seal Gate Check
                is_permitted, coord_reason = self.coordinator.check_trade_permission(
                    ticker=target_ticker,
                    proposed_side=rec_side,
                    bot_id="the_onnx_strategy",
                    requested_contracts=approved_size,
                    is_live=(self.execution_mode == "LIVE"),
                )
                if not is_permitted:
                    logger.warning("🛡️ [COORDINATOR VETO] %s on %s: %s", rec_side.upper(), target_ticker, coord_reason)
                    return

                try:
                    logger.info(
                        "🚀 [LIVE ORDER INCEPTION] %s %d cts @ $%s on %s | Regime: %s | QuoLas: %s (%.1f%%) | Kalshi: %s (%.1f%%)",
                        rec_side.upper(), approved_size, est_price, target_ticker, decision.regime.value,
                        decision.quolas_signal, decision.quolas_confidence * 100,
                        decision.kalshi_signal, decision.kalshi_confidence * 100,
                    )
                    resp = await self.order_client.place_order(
                        ticker=target_ticker,
                        action="buy",
                        side=rec_side,
                        count=approved_size,
                        order_type="limit",
                        yes_price=int(est_price * 100) if rec_side == "yes" else None,
                        no_price=int(est_price * 100) if rec_side == "no" else None,
                    )
                    order_id = resp.get("order_id", f"live_{int(time.time())}")
                    self.guardrails.record_execution(
                        order_id=order_id,
                        ticker=target_ticker,
                        side=rec_side,
                        size=approved_size,
                        price=est_price,
                        cycle_id=target_ticker,
                        bot_type="the_onnx_strategy",
                    )
                    # Record trade in cross-bot coordinator for anti-wash protection
                    expiry_ts = self.active_market_close_dt.timestamp() if self.active_market_close_dt else None
                    self.coordinator.record_trade(
                        ticker=target_ticker,
                        side=rec_side,
                        contracts=approved_size,
                        price=float(est_price),
                        bot_id="the_onnx_strategy",
                        expiry_ts=expiry_ts,
                    )
                    await self.sync_balance()
                except Exception as ex:
                    logger.error("❌ [LIVE ORDER FAILED] %s: %s", target_ticker, ex)
            else:
                # Lane 2 Shadow Execution
                logger.info(
                    "🔮 [SHADOW ORDER FILL] %s %d cts @ $%s on %s | Regime: %s | QuoLas: %s (%.1f%%) | Kalshi: %s (%.1f%%)",
                    rec_side.upper(), approved_size, est_price, target_ticker, decision.regime.value,
                    decision.quolas_signal, decision.quolas_confidence * 100,
                    decision.kalshi_signal, decision.kalshi_confidence * 100,
                )
                self.guardrails.record_execution(
                    order_id=f"shadow_{int(time.time())}",
                    ticker=target_ticker,
                    side=rec_side,
                    size=approved_size,
                    price=est_price,
                    cycle_id=target_ticker,
                    bot_type="the_onnx_strategy",
                )

    async def _cancel_resting_orders(self) -> None:
        """Cancel open resting orders on exchange and clear local state."""
        if self.order_client and self.active_ticker:
            try:
                orders = await self.order_client.get_open_orders()
                for o in orders:
                    if o.get("ticker") == self.active_ticker:
                        oid = o.get("order_id")
                        if oid:
                            await self.order_client.cancel_order(oid)
                            logger.info("🧹 [SWEEP] Cancelled resting order %s for %s", oid, self.active_ticker)
            except Exception as e:
                logger.debug("Failed cancelling resting orders: %s", e)
        self.active_resting_orders.clear()

    async def _settlement_reconciliation_loop(self) -> None:
        """Reconcile expired cycles and record win/loss statistics."""
        while self._running:
            try:
                self.sync_pnl_reports()
            except Exception as e:
                logger.debug("Settlement reconciliation tick exception: %s", e)
            await asyncio.sleep(30.0)


# ---------------------------------------------------------------------------
# FastAPI Standalone App & Lifecycle (Port 8002)
# ---------------------------------------------------------------------------

app_engine: Optional[StandaloneONNXEngine] = None
engine_lock: Optional[TradingEngineLock] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global app_engine, engine_lock
    if os.getenv("TESTING") == "true":
        yield
        return

    # 1. Acquire Engine Lock for Port 8002
    force_lock = os.getenv("KALSHI_FORCE_LOCK", "false").lower() in ("true", "1", "yes")
    engine_lock = TradingEngineLock(lock_path=LOCK_FILE_PATH, owner_name="standalone_onnx")
    engine_lock.acquire(force=force_lock)

    # 2. Start ONNX Engine
    is_live = os.getenv("KALSHI_ENV", "live").lower() in ("prod", "live")
    init_asset_str = os.getenv("KALSHI_ACTIVE_ASSET", "BTC").upper().strip()
    try:
        init_asset = CryptoAsset(init_asset_str)
    except ValueError:
        init_asset = CryptoAsset.BTC
    app_engine = StandaloneONNXEngine(is_live=is_live, is_armed=True, asset=init_asset)
    await app_engine.start()

    yield

    # 3. Shutdown Engine & Release Lock
    if app_engine:
        await app_engine.stop()
    if engine_lock:
        engine_lock.release()


app = FastAPI(title="Kalshi Dual-Brain ONNX Standalone", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def get_cockpit() -> str:
    """Serve ultra-lean ONNX Pocket Cockpit UI."""
    if TEMPLATE_PATH.exists():
        return TEMPLATE_PATH.read_text(encoding="utf-8")
    return "<h1>ONNX Pocket Cockpit template not found.</h1>"


@app.get("/api/state")
async def get_state() -> Dict[str, Any]:
    """Provide real-time telemetry to ONNX Pocket Cockpit."""
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
    diff_sign = "+" if is_up else "-"
    diff_abs = abs(diff_dec)
    diff_pct_abs = abs(diff_pct_dec)

    diff_str = f"{diff_sign}{cfg.format_price(diff_abs)}"
    moneyness_diff_str = f"{diff_str} ({diff_sign}{diff_pct_abs:.2f}%)"

    dec = app_engine.last_decision
    regime_str = dec.regime.value if dec else "STABLE_RANGE"

    bal = float(app_engine.balance_dollars)

    # Cross-brain latency skew
    now_ts = time.time()
    spot_lag_ms = max(0.0, (now_ts - app_engine.last_spot_update_ts) * 1000.0) if app_engine.last_spot_update_ts > 0 else 0.0
    kalshi_lag_ms = max(0.0, (now_ts - app_engine.last_kalshi_update_ts) * 1000.0) if app_engine.last_kalshi_update_ts > 0 else 0.0
    skew_ms = abs(spot_lag_ms - kalshi_lag_ms)

    params = app_engine.bot.get_parameters()
    cliff_s = float(params.get("gamma_cliff_seconds", 90.0))
    is_cliff_active = t_rem < cliff_s

    return {
        "bot_type": "the_onnx_strategy",
        "bot_name": "The ONNX Strategy (Dual-Brain QuoLas)",
        "armed": app_engine.is_armed,
        "is_live": app_engine.is_live,
        "execution_mode": app_engine.execution_mode,
        "mutual_interlock_active": app_engine.dom_bot_live_active,
        "mutual_interlock_msg": app_engine.interlock_msg,
        "balance": bal,
        "today_pnl": float(app_engine.today_pnl),
        "settled_cycles": app_engine.settled_cycles,
        "today_wins": app_engine.today_wins,
        "today_losses": app_engine.today_losses,
        "today_win_rate": round(app_engine.today_win_rate, 1),
        "active_asset": app_engine.active_asset.value,
        "active_ticker": app_engine.active_ticker,
        "time_remaining_str": t_str,
        "target_time_str": app_engine.target_time_str,
        "time_window_str": app_engine.time_window_str,
        "expiry_countdown_seconds": int(t_rem),
        "spot_price": float(spot_dec),
        "target_strike": float(strike_dec),
        "spot_diff_str": diff_str,
        "moneyness_diff_str": moneyness_diff_str,
        "is_above_strike": is_up,
        "best_yes_bid": float(app_engine.best_yes_bid) if app_engine.best_yes_bid else None,
        "best_yes_ask": float(app_engine.best_yes_ask) if app_engine.best_yes_ask else None,
        "best_no_bid": float(app_engine.best_no_bid) if app_engine.best_no_bid else None,
        "best_no_ask": float(app_engine.best_no_ask) if app_engine.best_no_ask else None,
        # Brain 1 (Spot) Telemetry
        "brain_1_signal": app_engine.last_spot_signal,
        "brain_1_confidence": round(app_engine.last_spot_confidence * 100.0, 1),
        "brain_1_lag_ms": round(spot_lag_ms, 1),
        "brain_1_connected": app_engine.binance_connected,
        # Brain 2 (Kalshi) Telemetry
        "brain_2_signal": app_engine.last_kalshi_signal,
        "brain_2_confidence": round(app_engine.last_kalshi_confidence * 100.0, 1),
        "brain_2_lag_ms": round(kalshi_lag_ms, 1),
        "brain_2_connected": app_engine.kalshi_ws_connected,
        # Armor & Microstructure
        "cross_brain_skew_ms": round(skew_ms, 1),
        "is_temporally_synced": skew_ms <= float(params.get("max_temporal_skew_ms", 1000.0)),
        "gamma_cliff_seconds": cliff_s,
        "is_gamma_cliff_active": is_cliff_active,
        "dynamic_volatility_mode": params.get("dynamic_volatility_mode", "REALIZED_ATR"),
        "current_atr": round(float(params.get("current_atr", 14.0)), 2),
        "hmm_regime": app_engine.hmm_brain.current_regime.name,
        "active_decision": dec.to_dict() if dec else None,
        "recent_reports": app_engine.recent_reports,
    }


@app.post("/api/arm")
async def arm_bot() -> Dict[str, Any]:
    """Arm the bot for autonomous trade execution."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine initializing")
    app_engine.is_armed = True
    logger.info("🛡️ [MASTER CONTROL] Bot ARMED by user on Port 8002.")
    return {"status": "SUCCESS", "armed": True}


@app.post("/api/disarm")
async def disarm_bot() -> Dict[str, Any]:
    """Disarm the bot."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine initializing")
    app_engine.is_armed = False
    logger.info("🛡️ [MASTER CONTROL] Bot DISARMED by user on Port 8002.")
    return {"status": "SUCCESS", "armed": False}


@app.post("/api/panic")
async def panic_halt() -> Dict[str, Any]:
    """Emergency Panic: Disarm and sweep all open resting orders."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine initializing")
    app_engine.is_armed = False
    await app_engine._cancel_resting_orders()
    logger.warning("🚨 [PANIC HALT] Triggered on Port 8002.")
    return {"status": "SUCCESS", "armed": False, "panic": True}


@app.post("/api/sweep")
async def sweep_orders() -> Dict[str, Any]:
    """Cancel all open resting orders without disarming."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine initializing")
    await app_engine._cancel_resting_orders()
    logger.info("🧹 [SWEEP] Resting orders swept on Port 8002.")
    return {"status": "SUCCESS", "swept": True}


@app.get("/api/bot/parameters")
@app.get("/api/parameters")
async def get_parameters() -> Dict[str, Any]:
    """Retrieve full ONNX parameter set."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine initializing")
    return app_engine.get_parameters()


class ONNXParametersUpdateRequest(BaseModel):
    brain_priority_mode: Optional[str] = None
    contract_scaling_mode: Optional[str] = None
    min_confidence: Optional[float] = None
    min_edge_pct: Optional[float] = None
    min_ev_dollars: Optional[float] = None
    entry_discount_depth: Optional[float] = None
    momentum_max_price: Optional[float] = None
    taker_cross_ev_threshold: Optional[float] = None
    tape_confirmation_ticks: Optional[int] = None
    dynamic_moat_multiplier: Optional[float] = None
    max_temporal_skew_ms: Optional[float] = None
    gamma_cliff_seconds: Optional[float] = None
    auto_cancel_on_veto: Optional[bool] = None
    dynamic_volatility_mode: Optional[str] = None
    volatility_floor: Optional[float] = None
    volatility_ceiling: Optional[float] = None
    vpin_toxic_threshold: Optional[float] = None
    max_contracts: Optional[int] = None


@app.post("/api/bot/parameters")
@app.post("/api/parameters")
async def update_parameters(req: ONNXParametersUpdateRequest) -> Dict[str, Any]:
    """Update ONNX strategy parameters."""
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
    port = 8002
    ok = launch_widget_window(port=port, view="minimized")
    return {"status": "LAUNCHED" if ok else "FAILED", "success": ok}


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Kalshi Dual-Brain ONNX Standalone Bot")
    parser.add_argument("--port", type=int, default=8002, help="HTTP Cockpit port (default: 8002)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="HTTP Cockpit host (default: 0.0.0.0)")
    parser.add_argument("--live", action="store_true", default=True, help="Enable live trading mode")
    parser.add_argument("--force", action="store_true", default=False, help="Force lock acquisition if stale")
    parser.add_argument("--no-browser", action="store_true", default=False, help="Do not open browser automatically")
    parser.add_argument("--widget", action="store_true", default=False, help="Launch as a floating desktop widget")
    parser.add_argument("--asset", type=str, default="BTC", choices=["BTC", "ETH", "SOL", "DOGE"], help="Active crypto asset (default: BTC)")
    parser.add_argument("--budget", type=float, default=None, help="Virtual budget cap in USD for partitioned dual-engine live trading")
    args = parser.parse_args()

    if args.force:
        os.environ["KALSHI_FORCE_LOCK"] = "true"
    if args.asset:
        os.environ["KALSHI_ACTIVE_ASSET"] = args.asset.upper()
    if args.budget is not None:
        os.environ["KALSHI_ONNX_BUDGET"] = str(args.budget)

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

    logger.info("⚡ Launching Kalshi Dual-Brain ONNX Standalone Engine on http://%s:%d ...", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()

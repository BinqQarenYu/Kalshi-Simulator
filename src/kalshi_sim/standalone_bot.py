"""Kalshi 3-Step Dominion — 24/7 Autonomous Standalone Trading Engine.

Ultra-lean execution daemon that trades 24/7 independently of the main dashboard:
1. Zero Code Drift: Imports ThreeStepDominationBot, AgentGuardrails, and KalshiLiveOrderClient directly.
2. Pre-Flight Audit Gate: Certifies strategy through BotDeploymentAuditor across all 4 pillars before live trade routing.
3. Mutual Exclusion Lock: Acquires data/trading_engine.lock to prevent dual-execution conflicts with main dashboard.
4. Institutional Guardrails: Enforces 1-2 contract sizing caps, 2-trade-per-cycle locks, VPIN toxicity vetoes, and anti-burst pre-flight checks.
5. Windows 24/7 Away-Mode: Prevents sleep/suspension when monitor turns off.
6. Ultra-Lean Pocket Cockpit UI: Serves minimal single-file HTML cockpit on port 8000 with Master Arm/Disarm switch and Panic Halt.
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
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
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
from kalshi_sim.db import get_db, get_db_writer, DatabaseWriter
from kalshi_sim.live_coordinator import LiveCoordinator
from kalshi_sim.ml.domination_bot import DominationDecision, ThreeStepDominationBot
from kalshi_sim.order_client import KalshiDemoOrderClient, KalshiLiveOrderClient
from kalshi_sim.orderbook import OrderBookManager
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("StandaloneBot")

from kalshi_sim.process_lock import TradingEngineLock, is_pid_running

LOCK_FILE_PATH = Path("data") / "trading_engine.lock"
TEMPLATE_PATH = Path(__file__).parent / "templates" / "pocket_cockpit.html"
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
# Standalone Bot Engine
# ---------------------------------------------------------------------------

class StandaloneBotEngine:
    """Core autonomous trading coordinator for 3-Step Domination."""

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

        # 1. Instantiate Strategy & Guardrails
        self.bot = ThreeStepDominationBot(asset=asset)
        self.guardrails = AgentGuardrails(
            min_order_interval_seconds=45.0,
            max_micro_bankroll_contracts=1,
            max_nano_bankroll_contracts=1,
            vpin_toxic_threshold=0.60,
        )
        self.auditor = BotDeploymentAuditor()
        self.orderbook = OrderBookManager(enforce_consecutive_seq=False)

        # Load user-saved persistent default parameters if present
        self._load_persisted_parameters()

        # 2. Run Pre-Flight Certification Audit
        mode_str = "live" if is_live else "simulated"
        audit_rep = self.auditor.audit_bot("3_step_domination_bot", self.bot, mode=mode_str)
        if not audit_rep.is_certified:
            err_msgs = [f"{p.pillar_name}: {p.message}" for p in audit_rep.pillars if p.status == "FAIL"]
            raise RuntimeError(f"Strategy 3_step_domination_bot FAILED pre-flight audit: {'; '.join(err_msgs)}")
        logger.info("✅ [AUDIT CERTIFIED] 3-Step Domination Bot passed all 4 pillars for %s trading.", mode_str.upper())

        # 3. Exchange Connection Setup
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

        # Balances (Total Portfolio & Active Execution Shard)
        self.total_balance_dollars: Decimal = Decimal("0.00")
        self.shard2_balance_dollars: Decimal = Decimal("0.00")
        self.balance_dollars: Decimal = Decimal("0.00")

        # Settlement & PnL Tracking
        self.today_pnl: Decimal = Decimal("0.00")
        self.settled_cycles: int = 0
        self.today_wins: int = 0
        self.today_losses: int = 0
        self.today_win_rate: float = 0.0
        self.recent_reports: List[Dict[str, Any]] = []

        # Consecutive Loss Streak Breaker (Post-Mortem Fix — 9 consecutive overnight losses)
        self.consecutive_losses: int = 0
        self.max_consecutive_losses: int = 3  # Auto-disarm after 3 consecutive losses
        self.engine_start_time: datetime = datetime.now(timezone.utc)

        self.last_decision: Optional[DominationDecision] = None
        self.last_eval_time: float = 0.0

        # Partitioned Budget & Live Coordinator
        budget_env = os.getenv("KALSHI_DOM_BUDGET")
        self.budget_dollars: Optional[Decimal] = Decimal(budget_env) if budget_env else None
        self.coordinator = LiveCoordinator()
        if self.budget_dollars:
            logger.info("💰 [BUDGET] Virtual budget cap: $%s", self.budget_dollars)

        # Database persistence writer
        self.db_writer = DatabaseWriter(db_manager=get_db(self.data_dir / "kalshi_history.db"))
        self.active_resting_orders: Dict[str, Dict[str, Any]] = {}
        self.active_position: Optional[Dict[str, Any]] = None
        self.coinbase_connected: bool = False
        self.binance_connected: bool = False

        # CF Benchmarks Multi-Asset Index & Health
        self.cf_sync: Optional[CFBenchmarksSync] = None
        self.brti_sync: Optional[CFBenchmarksSync] = None
        self.brti_connected: bool = False
        self.spot_source: str = "Uninitialized"
        self.twap_60s_price: Optional[Decimal] = None
        self.kalshi_ws_connected: bool = False
        self.spot_connected: bool = False
        self.timeframe: str = "15m"
        self._running = False
        self.tasks: List[asyncio.Task] = []
        self._eval_lock = asyncio.Lock()

    def get_current_timeframe(self) -> str:
        """Detect current active contract timeframe (5m or 15m)."""
        if self.active_ticker:
            t_upper = self.active_ticker.upper()
            if "5M" in t_upper or "5MIN" in t_upper:
                return "5m"
        return self.timeframe

    def set_asset(self, asset: CryptoAsset) -> None:
        """Switch active underlying asset in the standalone engine."""
        self.active_asset = asset
        self.active_cfg = get_asset_config(asset)
        self.bot.set_asset(asset)
        self._load_persisted_parameters()
        self.active_ticker = ""
        self.target_strike = Decimal("0.00")
        if self.cf_sync:
            p = self.cf_sync.get_price(asset)
            if p > Decimal("0.00"):
                self.current_btc_spot = p
                self.twap_60s_price = self.cf_sync.get_twap(asset)
        logger.info("Switched Standalone Bot active asset to %s (%s)", self.active_cfg.name, asset.value)

    def _get_params_file_path(self) -> Path:
        """Return the persistent parameters file path."""
        return self.data_dir / "bot_parameters_domination.json"

    def _load_persisted_parameters(self) -> None:
        """Load user-saved parameters from disk to serve as default values."""
        params_file = self._get_params_file_path()
        if not params_file.exists():
            return
        try:
            with open(params_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.warning("⚠️ [PARAM PERSISTENCE] Invalid format in %s, using factory defaults.", params_file)
                return

            asset_key = self.active_asset.value if hasattr(self.active_asset, "value") else str(self.active_asset)
            asset_params = data.get("assets", {}).get(asset_key, {})
            # Merge global params with asset-specific params (excluding asset/active_asset)
            global_params = {k: v for k, v in data.items() if k not in ("assets", "active_asset", "asset", "updated_at")}
            merged = {**global_params, **asset_params}

            if merged:
                # Disallow altering 1-contract sizing armor or resetting selected asset
                merged.pop("max_contracts", None)
                merged.pop("asset", None)
                self.update_parameters(persist=False, **merged)
                logger.info("💾 [PARAM PERSISTENCE] Loaded user defaults from %s for %s: %s", params_file.name, asset_key, merged)
        except Exception as exc:
            logger.warning("⚠️ [PARAM PERSISTENCE] Error loading %s: %s. Using factory defaults.", params_file, exc)

    def _persist_parameters(self) -> None:
        """Atomically persist active parameters to disk as the new defaults."""
        params_file = self._get_params_file_path()
        tmp_file = params_file.with_suffix(".json.tmp")
        try:
            existing_data: Dict[str, Any] = {"assets": {}}
            if params_file.exists():
                try:
                    with open(params_file, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, dict):
                            existing_data = loaded
                            if "assets" not in existing_data:
                                existing_data["assets"] = {}
                except Exception:
                    existing_data = {"assets": {}}

            current_params = self.get_parameters()
            asset_key = self.active_asset.value if hasattr(self.active_asset, "value") else str(self.active_asset)

            # Separate asset-specific moat from global dials
            asset_specific_keys = {"min_spot_diff"}
            asset_data = {k: v for k, v in current_params.items() if k in asset_specific_keys}
            existing_data.setdefault("assets", {})[asset_key] = asset_data

            # Global parameters apply across assets (skip asset/active_asset)
            for k, v in current_params.items():
                if k not in asset_specific_keys and k not in ("asset", "active_asset"):
                    existing_data[k] = v

            existing_data["active_asset"] = asset_key
            existing_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            # Strict Micro-Bankroll invariant
            existing_data["max_contracts"] = 1

            # Atomic write via tempfile swap
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, params_file)
            logger.info("💾 [PARAM PERSISTENCE] Successfully saved active parameters as new defaults to %s", params_file.name)
        except Exception as exc:
            logger.error("❌ [PARAM PERSISTENCE] Failed to persist parameters: %s", exc)
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass

    def get_parameters(self) -> Dict[str, Any]:
        """Return strategy parameters and guardrail thresholds."""
        params = self.bot.get_parameters()
        params["max_contracts"] = self.guardrails.max_micro_bankroll_contracts
        return params

    def update_parameters(self, persist: bool = True, **kwargs) -> Dict[str, Any]:
        """Dynamically update strategy parameters and guardrail caps."""
        max_contracts = kwargs.pop("max_contracts", None)
        if max_contracts is not None:
            clamped_size = max(1, min(1, int(max_contracts)))
            self.guardrails.max_micro_bankroll_contracts = clamped_size
            self.guardrails.max_nano_bankroll_contracts = clamped_size
            logger.info("🛡️ [GUARDRAIL PARAM UPDATE] Max contracts updated to: %d", clamped_size)
        vpin_thresh = kwargs.get("vpin_toxic_threshold")
        if vpin_thresh is not None:
            self.guardrails.vpin_toxic_threshold = float(vpin_thresh)
        self.bot.update_parameters(**kwargs)
        if persist:
            self._persist_parameters()
        return self.get_parameters()

    async def start(self) -> None:
        """Start all background loops."""
        self._running = True
        prevent_windows_sleep()

        # Start database persistence writer
        await self.db_writer.start()

        # Initial PnL and balance sync
        self.sync_pnl_reports()
        await self.sync_balance()

        # Start background workers
        self.tasks.append(asyncio.create_task(self._spot_feed_loop(), name="spot_feed"))
        self.tasks.append(asyncio.create_task(self._market_discovery_and_book_loop(), name="market_book_sync"))
        self.tasks.append(asyncio.create_task(self._balance_polling_loop(), name="balance_poll"))
        self.tasks.append(asyncio.create_task(self._resting_order_watchdog_loop(), name="resting_watchdog"))
        self.tasks.append(asyncio.create_task(self._settlement_reconciliation_loop(), name="settlement_sync"))
        logger.info("🚀 [STANDALONE BOT ACTIVE] Background loops spawned. Bot status: %s", "ARMED" if self.is_armed else "DISARMED")

    async def stop(self) -> None:
        """Gracefully stop engine and close HTTP sessions."""
        self._running = False
        for t in self.tasks:
            t.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        await self.db_writer.stop()
        if self.cf_sync:
            await self.cf_sync.stop()
        elif self.brti_sync:
            await self.brti_sync.stop()
        if self.order_client:
            await self.order_client.close()
        logger.info("🛑 [STANDALONE BOT STOPPED] Engine shut down cleanly.")

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

            today_reports = [
                r for r in all_reports
                if (r.get("execution_mode") == "live" or r.get("bot_type") == "live" or not self.is_live)
                and (today_prefix in r.get("ticker", "") or today_iso in str(r.get("timestamp_utc", "")))
            ]
            self.settled_cycles = len(today_reports)
            pnl_sum = sum(float(r.get("pnl", 0.0)) for r in today_reports)
            self.today_pnl = Decimal(str(round(pnl_sum, 2)))

            wins = sum(1 for r in today_reports if r.get("outcome") == "win")
            self.today_wins = wins
            self.today_losses = self.settled_cycles - wins
            self.today_win_rate = (wins / self.settled_cycles * 100.0) if self.settled_cycles > 0 else 0.0

            # Store recent 5 settlements for display
            self.recent_reports = [
                {
                    "ticker": r.get("ticker", ""),
                    "side": r.get("bot_side", "").upper(),
                    "outcome": r.get("outcome", "").upper(),
                    "pnl": float(r.get("pnl", 0.0)),
                    "strike": float(r.get("strike_price", 0.0)),
                    "settle_price": float(r.get("settlement_btc_price", 0.0)),
                    "contracts": r.get("contracts", 1),
                    "time": r.get("timestamp_utc", "")[:19].replace("T", " "),
                }
                for r in today_reports[:5]
            ]
        except Exception as exc:
            logger.debug("Error syncing PnL reports: %s", exc)

    async def sync_balance(self) -> None:
        """Sync live account balance from Kalshi portfolio.

        When budget partitioning is active (--budget flag), balance_dollars is
        clamped to min(real_balance, budget_cap).
        """
        if self.order_client:
            try:
                data = await self.order_client.get_balance()
                b_all = data.get("balance_dollars")
                if b_all is not None:
                    self.total_balance_dollars = Decimal(str(b_all))
                b2 = self.order_client.shard_balances.get(2)
                if b2 is not None:
                    self.shard2_balance_dollars = b2
                else:
                    self.shard2_balance_dollars = self.total_balance_dollars
                if self.budget_dollars is not None:
                    self.balance_dollars = min(self.total_balance_dollars, self.budget_dollars)
                else:
                    self.balance_dollars = self.total_balance_dollars
            except Exception as e:
                logger.debug("Balance sync error: %s", e)

    async def sync_positions(self) -> None:
        """Sync live open positions from Kalshi exchange to track for take-profit ceiling."""
        if self.order_client:
            try:
                positions = await self.order_client.get_positions()
                found = False
                for p in positions:
                    ticker = p.get("ticker") or p.get("market_ticker")
                    if ticker == self.active_ticker:
                        pos_raw = p.get("position", p.get("position_fp", 0))
                        try:
                            pos_cnt = int(float(str(pos_raw)))
                        except (ValueError, TypeError):
                            pos_cnt = 0
                        if pos_cnt > 0:
                            side_raw = p.get("side", "yes")
                            side = OrderSide.YES if str(side_raw).lower() == "yes" else OrderSide.NO
                            entry_p = self.bot.discount_limit_price
                            if self.active_position and self.active_position.get("entry_price"):
                                entry_p = self.active_position["entry_price"]
                            self.active_position = {
                                "ticker": self.active_ticker,
                                "side": side,
                                "size": pos_cnt,
                                "entry_price": entry_p,
                                "entry_time": self.active_position.get("entry_time", time.time()) if self.active_position else time.time(),
                            }
                            found = True
                            break
                if not found and self.active_position and self.active_position.get("ticker") == self.active_ticker:
                    self.active_position = None
            except Exception as pe:
                logger.debug("Error syncing positions from Kalshi: %s", pe)

    def _record_exit_report(
        self,
        ticker: str,
        side: str,
        size: int,
        entry_price: float,
        exit_price: float,
        net_pnl: float,
        exit_reason: str,
    ) -> None:
        """Persist early take-profit exit report to win_loss_reports.json."""
        reports_file = self.data_dir / "win_loss_reports.json"
        all_reports: List[Dict[str, Any]] = []
        if reports_file.exists():
            try:
                all_reports = json.loads(reports_file.read_text(encoding="utf-8"))
            except Exception:
                all_reports = []

        report_id = f"WLR-TP-{ticker}-{int(time.time())}"
        now_iso = datetime.now(timezone.utc).isoformat()
        report = {
            "report_id": report_id,
            "ticker": ticker,
            "bot_side": side.upper(),
            "outcome": "win",
            "pnl": round(net_pnl, 2),
            "roi_pct": round(((exit_price - entry_price) / max(0.01, entry_price)) * 100.0, 2),
            "contracts": size,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "settlement_price": exit_price,
            "timestamp_utc": now_iso,
            "execution_mode": "live" if self.order_client else "paper",
            "bot_type": "3_step_domination_bot",
            "exit_reason": exit_reason,
        }
        all_reports.insert(0, report)
        try:
            reports_file.write_text(json.dumps(all_reports, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Error writing exit win_loss_report: %s", e)

    async def _balance_polling_loop(self) -> None:
        """Poll balance, positions, and PnL settlements every 5 seconds."""
        while self._running:
            await self.sync_balance()
            await self.sync_positions()
            self.sync_pnl_reports()
            await asyncio.sleep(5.0)

    async def _spot_feed_loop(self) -> None:
        """Stream real-time crypto spot price prioritizing official CF Benchmarks 5Hz feed."""
        def _on_cf_asset_update(asset: CryptoAsset, price: Decimal, twap: Optional[Decimal], source: str) -> None:
            if asset == self.active_asset:
                self.current_btc_spot = price
                if twap is not None:
                    self.twap_60s_price = twap
                self.spot_source = source
                self.spot_connected = True
                self.brti_connected = True
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
        }

        connector = create_aiohttp_connector()
        async with aiohttp.ClientSession(connector=connector) as session:
            async def _coinbase_worker() -> None:
                while self._running:
                    try:
                        async with session.ws_connect("wss://ws-feed.exchange.coinbase.com", timeout=5.0) as ws:
                            await ws.send_json({
                                "type": "subscribe",
                                "product_ids": ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"],
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
                                        if matched_asset == self.active_asset and not (self.cf_sync and self.cf_sync.is_connected):
                                            self.current_btc_spot = Decimal(str(data["price"]))
                                            self.spot_source = f"Coinbase Pro {pid} (Fallback)"
                                            self.brti_connected = False
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
                streams = "btcusdt@ticker/ethusdt@ticker/solusdt@ticker/dogeusdt@ticker"
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
                                        expected_sym = f"{self.active_asset.value}USDT"
                                        if symbol == expected_sym and not (self.cf_sync and self.cf_sync.is_connected) and not self.coinbase_connected:
                                            self.current_btc_spot = Decimal(str(s_data["c"]))
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
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            while self._running:
                try:
                    # 1. Discover current open contract
                    url = f"{self.rest_base}/markets?series_ticker={self.active_cfg.series_ticker_15m}&status=open&limit=15"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3.0)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            markets = data.get("markets", [])
                            if markets:
                                # Pick contract closing earliest in future
                                now_utc = datetime.now(timezone.utc)
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
                                    if self.active_ticker and new_ticker != self.active_ticker:
                                        logger.info("🔄 [CYCLE ROLLOVER] %s -> %s. Sweeping resting orders from finished event...", self.active_ticker, new_ticker)
                                        asyncio.create_task(self.sweep_old_orders(keep_ticker=new_ticker))
                                    self.active_ticker = new_ticker
                                    self.active_market_close_dt = active_close
                                    floor = active_m.get("floor_strike")
                                    if floor is not None:
                                        self.target_strike = Decimal(str(floor))

                                    # ET time formatting
                                    et_zone = ZoneInfo("America/New_York")
                                    close_et = active_close.astimezone(et_zone)
                                    start_et = close_et - timedelta(minutes=15)
                                    self.target_time_str = close_et.strftime("%I:%M%p").lower() + " ET"
                                    self.time_window_str = f"{start_et.strftime('%B %d, %I:%M')} - {close_et.strftime('%I:%M %p')} ET"

                    # 2. Ingest orderbook for active contract
                    if self.active_ticker:
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

                                # Extract inside touch quotes
                                self.best_yes_bid = book.best_yes_bid
                                self.best_yes_ask = book.best_yes_ask
                                self.best_no_bid = book.best_no_bid
                                self.best_no_ask = book.best_no_ask

                                self.kalshi_ws_connected = True
                                await self.evaluate_and_execute()

                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.debug("[MARKET SYNC] Loop tick error: %s", exc)
                    self.kalshi_ws_connected = False

                await asyncio.sleep(0.5)

    def get_time_to_expiry(self) -> float:
        """Return time to contract expiry in seconds."""
        if not self.active_market_close_dt:
            return 0.0
        now_utc = datetime.now(timezone.utc)
        return max(0.0, (self.active_market_close_dt - now_utc).total_seconds())

    async def evaluate_and_execute(self) -> None:
        """Evaluate 3-step domination logic and route live orders through guardrails."""
        if self._eval_lock.locked():
            return
        async with self._eval_lock:
            now_mono = time.monotonic()
            if now_mono - self.last_eval_time < 0.25:
                return
            self.last_eval_time = now_mono

            if not self.active_ticker or self.target_strike <= 0 or self.current_btc_spot <= 0:
                return

            book = self.orderbook.get_book(self.active_ticker)
            if not book or (not book.yes_book and not book.no_book):
                return

            t_rem = self.get_time_to_expiry()
            if t_rem <= 0:
                return

            # 0. Early Exit & Take Profit Price Ceiling Evaluation
            if (
                self.active_position
                and self.active_position.get("ticker") == self.active_ticker
                and self.active_position.get("size", 0) > 0
            ):
                pos = self.active_position
                exit_dec = self.bot.evaluate_exit(
                    side=pos["side"],
                    entry_price=pos["entry_price"],
                    size=pos["size"],
                    book=book,
                    time_to_expiry_s=t_rem,
                    spot_price=float(self.current_btc_spot),
                    target_strike=float(self.target_strike),
                )
                if exit_dec.should_exit:
                    logger.info(
                        "🎯 [TAKE PROFIT TRIGGERED] %s: %s | Net PnL: +$%s | Exit price: $%s",
                        exit_dec.exit_reason,
                        exit_dec.rationale,
                        exit_dec.unrealized_pnl,
                        exit_dec.exit_price,
                    )
                    sold_ok = True
                    if self.is_live and self.order_client:
                        try:
                            sell_res = await self.order_client.place_order(
                                ticker=pos["ticker"],
                                side=pos["side"],
                                count=pos["size"],
                                action="sell",
                                order_type="limit",
                                price_dollars=exit_dec.exit_price,
                                exchange_index=2,
                            )
                            if not sell_res:
                                sold_ok = False
                                logger.error("Failed to execute sell order on Kalshi for %s", pos["ticker"])
                        except Exception as se:
                            sold_ok = False
                            logger.error("Error dispatching sell order: %s", se)

                    if sold_ok:
                        self.db_writer.enqueue_trade(
                            trade_id=f"tp_{int(time.time()*1000)}",
                            ticker=pos["ticker"],
                            side=str(pos["side"]).lower(),
                            size=pos["size"],
                            price=float(exit_dec.exit_price),
                            gross_value=float(exit_dec.exit_price * Decimal(str(pos["size"]))),
                            fees=float(self.bot.fee_per_contract * Decimal(str(pos["size"]))),
                            vpin=0.15,
                            timeframe=self.get_current_timeframe(),
                            bot_type="3_step_domination_bot",
                            execution_mode="live" if (self.is_live and self.order_client) else "paper",
                            status="take_profit_exit",
                        )
                        self.today_pnl += exit_dec.unrealized_pnl
                        self.today_wins += 1
                        self.settled_cycles += 1
                        self.consecutive_losses = 0
                        self._record_exit_report(
                            ticker=pos["ticker"],
                            side=str(pos["side"]).lower(),
                            size=pos["size"],
                            entry_price=float(pos["entry_price"]),
                            exit_price=float(exit_dec.exit_price),
                            net_pnl=float(exit_dec.unrealized_pnl),
                            exit_reason=exit_dec.exit_reason,
                        )
                        self.active_position = None
                        self.sync_pnl_reports()
                        logger.info("✅ [TAKE PROFIT EXECUTED] Position closed at $%s ceiling! Banked +$%s.", exit_dec.exit_price, exit_dec.unrealized_pnl)
                        await self.sync_balance()
                        return
                # Position is held, do not enter again in the same cycle
                return

            # 1. Strategy Evaluation
            try:
                decision = self.bot.evaluate(
                    book=book,
                    spot_price=float(self.current_btc_spot),
                    target_strike=float(self.target_strike),
                    time_to_expiry_s=t_rem,
                    total_equity=self.balance_dollars,
                    max_position_size=1,
                    estimated_vpin=0.15,
                )
                self.last_decision = decision
            except Exception as eval_err:
                logger.exception("❌ [EVALUATION ERROR] Error evaluating strategy: %s", eval_err)
                return

            # 2. Execution Gating: Check Arming
            if not self.is_armed:
                return

            # 3. Check Signal Recommendation
            if decision.recommended_side not in ("yes", "no") or decision.recommended_contracts <= 0:
                return

            # 4. Institutional Pre-Trade Guardrail Check
            rec_side = decision.recommended_side
            rec_size = min(decision.recommended_contracts, 1)  # Strictly 1 contract per trade, max 2 shares per cycle
            est_price = Decimal(str(decision.limit_price))
            target_ticker = self.active_ticker

            is_allowed, g_reason, approved_size, _ = self.guardrails.validate_pre_trade_intent(
                ticker=target_ticker,
                side=rec_side,
                requested_size=rec_size,
                est_price=est_price,
                total_equity=self.balance_dollars,
                vpin=decision.vpin,
                cycle_id=target_ticker,
                is_bot=True,
                bot_type="3_step_domination_bot",
            )

            if not is_allowed or approved_size <= 0:
                logger.info("🛡️ [GUARDRAIL BLOCK] %s on %s: %s", rec_side.upper(), target_ticker, g_reason)
                return

            # 5. Anti-Burst Pre-Flight Check on Kalshi Open Orders
            if self.order_client:
                try:
                    open_orders = await self.order_client.get_open_orders()
                    existing_for_ticker = [o for o in open_orders if o.get("ticker") == target_ticker]
                    if existing_for_ticker:
                        logger.warning("⚠️ [ANTI-BURST] Resting order already active on Kalshi for %s. Suppressing duplicate.", target_ticker)
                        self.guardrails.record_resting_order(
                            order_id=existing_for_ticker[0].get("order_id", "ext_rest"),
                            ticker=target_ticker,
                            side=rec_side,
                            size=approved_size,
                            price=est_price,
                            cycle_id=target_ticker,
                            bot_type="3_step_domination_bot",
                        )
                        return
                except Exception as e:
                    logger.debug("Failed open order anti-burst check: %s", e)

                # 6. Cross-Bot CFTC Anti-Wash Trading Coordinator Check
                is_permitted, coord_reason = self.coordinator.check_trade_permission(
                    ticker=target_ticker,
                    proposed_side=rec_side,
                    bot_id="3_step_domination_bot",
                    requested_contracts=approved_size,
                )
                if not is_permitted:
                    logger.warning("🛡️ [COORDINATOR VETO] %s on %s: %s", rec_side.upper(), target_ticker, coord_reason)
                    self.guardrails.release_in_flight_intent(target_ticker)
                    return

                # 7. Dispatch Live Order
                logger.info(
                    "🚀 [LIVE ORDER INCEPTION] %s %d contracts @ $%s on %s (Playbook: %s, Edge: +%.1f%%)",
                    rec_side.upper(), approved_size, est_price, target_ticker, decision.active_playbook, decision.edge_pct * 100
                )
                try:
                    order_res = await self.order_client.place_order(
                        ticker=target_ticker,
                        side=rec_side,
                        count=approved_size,
                        action="buy",
                        order_type="limit",
                        price_dollars=float(est_price),
                        exchange_index=2,
                    )
                except Exception as exc:
                    self.guardrails.release_in_flight_intent(target_ticker)
                    logger.error("Failed to dispatch live order to Kalshi: %s", exc)
                    return

                if order_res:
                    order_id = order_res.get("order_id", "live_ord")
                    logger.info("✅ [ORDER PLACED] Order ID: %s", order_id)
                    self.guardrails.record_resting_order(
                        order_id=order_id,
                        ticker=target_ticker,
                        side=rec_side,
                        size=approved_size,
                        price=est_price,
                        cycle_id=target_ticker,
                        bot_type="3_step_domination_bot",
                    )
                    fill_cnt = 0
                    try:
                        fill_cnt = int(float(str(order_res.get("fill_count", 0))))
                    except Exception:
                        fill_cnt = 0
                    if fill_cnt > 0 or str(order_res.get("status", "")).lower() in ("executed", "filled"):
                        self.active_position = {
                            "ticker": target_ticker,
                            "side": rec_side,
                            "size": approved_size,
                            "entry_price": est_price,
                            "entry_time": time.time(),
                            "order_id": order_id,
                        }
                        logger.info("⚡ [IMMEDIATE FILL] %s %d contracts @ $%s on %s", rec_side.upper(), approved_size, est_price, target_ticker)
                    else:
                        self.active_resting_orders[order_id] = {
                            "ticker": target_ticker,
                            "side": rec_side,
                            "size": approved_size,
                            "price": est_price,
                            "placed_at": time.time(),
                        }
                    # Record trade in cross-bot coordinator for anti-wash protection
                    expiry_ts = self.active_market_close_dt.timestamp() if self.active_market_close_dt else None
                    self.coordinator.record_trade(
                        ticker=target_ticker,
                        side=rec_side,
                        contracts=approved_size,
                        price=float(est_price),
                        bot_id="3_step_domination_bot",
                        expiry_ts=expiry_ts,
                    )
                    # Persist live trade to SQLite via DatabaseWriter
                    self.db_writer.enqueue_trade(
                        trade_id=f"live_{order_id}",
                        ticker=target_ticker,
                        side=rec_side,
                        size=approved_size,
                        price=float(est_price),
                        gross_value=float(est_price * Decimal(str(approved_size))),
                        fees=0.0,
                        vpin=decision.vpin,
                        timeframe=self.get_current_timeframe(),
                        bot_type="3_step_domination_bot",
                        execution_mode="live",
                        status="resting",
                    )
                    await self.sync_balance()
                else:
                    self.guardrails.release_in_flight_intent(target_ticker)

    async def panic_cancel_all(self) -> int:
        """Cancel all open resting orders on Kalshi exchange and disarm bot."""
        self.is_armed = False
        cancelled_count = 0
        if self.order_client:
            try:
                open_orders = await self.order_client.get_open_orders()
                for o in open_orders:
                    oid = o.get("order_id")
                    if oid:
                        await self.order_client.cancel_order(oid)
                        cancelled_count += 1
                        logger.warning("🛑 [PANIC CANCELLED] Order %s on %s", oid, o.get("ticker"))
                self.active_resting_orders.clear()
            except Exception as e:
                logger.error("Error during panic cancel: %s", e)
        return cancelled_count

    async def sweep_old_orders(self, keep_ticker: Optional[str] = None, force_all: bool = False) -> int:
        """Cancel all open resting orders on Kalshi exchange for finished, expired, or non-active contracts."""
        cancelled = 0
        t_rem = self.get_time_to_expiry()
        # If the active contract has expired or is in the <=45s pre-expiry window, do not keep it
        is_active_expired = (self.active_market_close_dt is not None and t_rem <= 45.0)
        effective_keep = None if (force_all or is_active_expired) else (keep_ticker or self.active_ticker)

        if self.order_client:
            try:
                open_orders = await self.order_client.get_open_orders()
                for o in open_orders:
                    t = o.get("ticker")
                    oid = o.get("order_id")
                    if oid and (not effective_keep or t != effective_keep):
                        try:
                            success = await self.order_client.cancel_order(oid, ticker=t)
                            if success:
                                cancelled += 1
                                logger.warning("🧹 [EXPIRED ORDER SWEEP] Cancelled resting order %s on finished/expired event %s", oid, t)
                        except Exception as ce:
                            logger.error("Error cancelling old order %s on %s: %s", oid, t, ce)
            except Exception as e:
                logger.error("Error fetching open orders during sweep: %s", e)

        if self.active_resting_orders:
            for oid, o_info in list(self.active_resting_orders.items()):
                t = o_info.get("ticker")
                if not effective_keep or t != effective_keep:
                    self.active_resting_orders.pop(oid, None)
                    if not self.order_client:
                        cancelled += 1
                        logger.warning("🧹 [EXPIRED ORDER SWEEP] Cleared virtual resting order %s on finished event %s", oid, t)

        logger.info("🧹 [SWEEP SUMMARY] Cancelled %d resting order(s). Active ticker: %s (t_rem=%.0fs)", cancelled, self.active_ticker, t_rem)
        return cancelled

    async def _resting_order_watchdog_loop(self) -> None:
        """Watch resting limit orders and auto-cancel prior to expiration (t_rem <= 45s or <= 0s) or once event is finished."""
        while self._running:
            try:
                t_rem = self.get_time_to_expiry()
                if self.order_client:
                    # 1. Pre-Expiry & Expired Cleanup for active contract (t_rem <= 45s, including <= 0)
                    if t_rem <= 45.0:
                        if self.active_resting_orders:
                            for oid, o_info in list(self.active_resting_orders.items()):
                                if o_info.get("ticker") == self.active_ticker:
                                    try:
                                        await self.order_client.cancel_order(oid, ticker=self.active_ticker)
                                        self.active_resting_orders.pop(oid, None)
                                        logger.warning(
                                            "🛑 [PRE-EXPIRY CLEANUP] Auto-cancelled unfilled resting order %s on %s at T=%.0fs.",
                                            oid, self.active_ticker, t_rem
                                        )
                                    except Exception as c_err:
                                        logger.debug("Error cancelling resting order %s: %s", oid, c_err)

                        # Check exchange open orders for expiring active ticker
                        try:
                            open_orders = await self.order_client.get_open_orders()
                            for o in open_orders:
                                if o.get("ticker") == self.active_ticker:
                                    oid = o.get("order_id")
                                    if oid:
                                        await self.order_client.cancel_order(oid, ticker=self.active_ticker)
                                        logger.warning(
                                            "🛑 [PRE-EXPIRY CLEANUP] Auto-cancelled exchange open order %s on %s at T=%.0fs.",
                                            oid, self.active_ticker, t_rem
                                        )
                        except Exception as o_err:
                            logger.debug("Error querying open orders in watchdog: %s", o_err)

                    # 1.5 Detect fills on active resting orders
                    if self.active_resting_orders:
                        try:
                            open_orders = await self.order_client.get_open_orders()
                            open_oids = {o.get("order_id") for o in open_orders}
                            for oid, o_info in list(self.active_resting_orders.items()):
                                if oid not in open_oids and o_info.get("ticker") == self.active_ticker:
                                    self.active_position = {
                                        "ticker": self.active_ticker,
                                        "side": o_info.get("side", "yes"),
                                        "size": o_info.get("size", 1),
                                        "entry_price": o_info.get("price", Decimal("0.52")),
                                        "entry_time": time.time(),
                                        "order_id": oid,
                                    }
                                    self.active_resting_orders.pop(oid, None)
                                    logger.info(
                                        "🎉 [ORDER FILLED] Resting order %s on %s FILLED! Position active for Take Profit monitoring.",
                                        oid, self.active_ticker
                                    )
                        except Exception as f_err:
                            logger.debug("Error checking resting order fills: %s", f_err)

                    # 2. Continuous Finished Event Sweep: Cancel resting orders on any non-active or past contracts
                    try:
                        open_orders = await self.order_client.get_open_orders()
                        for o in open_orders:
                            t = o.get("ticker")
                            oid = o.get("order_id")
                            if oid and self.active_ticker and t != self.active_ticker:
                                try:
                                    await self.order_client.cancel_order(oid)
                                    logger.warning(
                                        "🧹 [FINISHED EVENT SWEEP] Auto-cancelled resting order %s on finished event %s (active: %s).",
                                        oid, t, self.active_ticker
                                    )
                                except Exception as c_err:
                                    logger.debug("Error cancelling finished event order %s: %s", oid, c_err)
                    except Exception as sweep_err:
                        logger.debug("Error sweeping non-active ticker orders: %s", sweep_err)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("Watchdog loop error: %s", exc)

            await asyncio.sleep(2.0)

    async def _settlement_reconciliation_loop(self) -> None:
        """Autonomous 24/7 Kalshi portfolio settlement reconciliation loop."""
        while self._running:
            try:
                if self.order_client:
                    settlements = await self.order_client.get_settlements(limit=20)
                    if settlements:
                        reports_file = self.data_dir / "win_loss_reports.json"
                        all_reports: List[Dict[str, Any]] = []
                        if reports_file.exists():
                            try:
                                all_reports = json.loads(reports_file.read_text(encoding="utf-8"))
                            except Exception:
                                all_reports = []

                        existing_ids = {r.get("report_id") for r in all_reports}
                        existing_tickers = {r.get("ticker") for r in all_reports if r.get("execution_mode") == "live"}

                        # Query local SQLite trades for accurate price/size attribution
                        local_trades: Dict[str, Dict[str, Any]] = {}
                        try:
                            async with get_db(self.data_dir / "kalshi_history.db").get_connection() as conn:
                                async with conn.execute(
                                    "SELECT trade_id, ticker, side, size, price, gross_value, timestamp_utc, bot_type FROM trades WHERE execution_mode = 'live'"
                                ) as cursor:
                                    for row in await cursor.fetchall():
                                        local_trades[row[1]] = {
                                            "trade_id": row[0],
                                            "ticker": row[1],
                                            "side": row[2],
                                            "size": row[3],
                                            "price": Decimal(str(row[4])),
                                            "gross_value": Decimal(str(row[5])),
                                            "timestamp_utc": row[6],
                                            "bot_type": row[7] or "3_step_domination_bot",
                                        }
                        except Exception as db_exc:
                            logger.debug("Failed reading trades table in standalone settlement loop: %s", db_exc)

                        new_reconciled = 0
                        for s in settlements:
                            ticker = s.get("ticker", "")
                            report_id = f"WLR-LIVE-{ticker}"
                            if not ticker or report_id in existing_ids or ticker in existing_tickers:
                                continue

                            market_result = (s.get("market_result") or "").lower()
                            if not market_result:
                                continue

                            t_info = local_trades.get(ticker)
                            if t_info:
                                trade_side = t_info["side"].lower()
                                size = t_info["size"]
                                cost = t_info["gross_value"]
                                entry_price = t_info["price"]
                                bot_type = t_info["bot_type"]
                            else:
                                raw_cnt = int(s.get("count", 0))
                                if raw_cnt == 0:
                                    continue
                                raw_rev = s.get("revenue", 0)
                                size = raw_cnt
                                trade_side = market_result if raw_rev > 0 else ("no" if market_result == "yes" else "yes")
                                entry_price = Decimal("0.50")
                                cost = Decimal(str(size)) * entry_price
                                bot_type = "3_step_domination_bot"

                            won = (trade_side == market_result)
                            outcome = "win" if won else "loss"
                            revenue = Decimal(str(size)) * Decimal("1.00") if won else Decimal("0.00")
                            raw_rev = s.get("revenue")
                            if raw_rev is not None:
                                rev_dec = Decimal(str(raw_rev)) / Decimal("100") if isinstance(raw_rev, int) else Decimal(str(raw_rev))
                                if rev_dec > Decimal("0") and won:
                                    revenue = rev_dec

                            pnl = revenue - cost
                            roi_pct = (pnl / cost * Decimal("100.0")) if cost > Decimal("0") else Decimal("0.0")

                            raw_settled_time = s.get("settled_time")
                            is_historical = False
                            if self.is_live and raw_settled_time:
                                try:
                                    dt = datetime.fromisoformat(str(raw_settled_time).replace("Z", "+00:00"))
                                    if dt < self.engine_start_time:
                                        is_historical = True
                                except Exception:
                                    pass

                            settled_ts = raw_settled_time or datetime.now(timezone.utc).isoformat()
                            cycle_time = format_cycle_time_from_iso(settled_ts)

                            # Resolve strike price
                            strike_price = Decimal("0.0")
                            if ticker == self.active_ticker:
                                strike_price = self.target_strike
                            if strike_price <= Decimal("0.0"):
                                if self.current_btc_spot > Decimal("0.0"):
                                    strike_price = self.current_btc_spot
                                else:
                                    fallback_strikes = {
                                        CryptoAsset.BTC: Decimal("80000.00"),
                                        CryptoAsset.ETH: Decimal("2500.00"),
                                        CryptoAsset.SOL: Decimal("150.00"),
                                        CryptoAsset.DOGE: Decimal("0.2000"),
                                    }
                                    strike_price = fallback_strikes.get(self.active_asset, Decimal("80000.00"))

                            step = self.active_cfg.strike_step
                            # Use real spot price at reconciliation time; fabricated strike±step as fallback
                            if self.current_btc_spot > Decimal("0.0"):
                                settlement_spot_price = self.current_btc_spot
                            else:
                                settlement_spot_price = strike_price + (step if market_result == "yes" else -step)
                            balance_after = self.total_balance_dollars if self.total_balance_dollars > 0 else self.balance_dollars

                            rep_tf = "5m" if ("5M" in ticker.upper() or "5MIN" in ticker.upper()) else "15m"
                            rep_asset = self.active_asset.value

                            rep = {
                                "report_id": report_id,
                                "cycle_time": cycle_time,
                                "ticker": ticker,
                                "timeframe": rep_tf,
                                "asset": rep_asset,
                                "strike_price": float(strike_price),
                                "settlement_btc_price": float(settlement_spot_price),
                                "settlement_spot_price": float(settlement_spot_price),
                                "bot_side": trade_side,
                                "contracts": size,
                                "entry_price": float(entry_price),
                                "settlement_price": 1.00 if won else 0.00,
                                "outcome": outcome,
                                "pnl": float(pnl),
                                "roi_pct": float(round(roi_pct, 2)),
                                "ai_confidence": 0.85,
                                "ai_rationale": f"24/7 Standalone Settlement | Result: {market_result.upper()} | Revenue: ${float(revenue):.2f}",
                                "vpin_score": 0.15,
                                "ev_edge": 0.10,
                                "balance_after": float(balance_after),
                                "bot_type": bot_type,
                                "bot_id": "3_step_domination_bot",
                                "strategy_id": "3_step_domination_bot",
                                "execution_mode": "live",
                                "lane": "LANE 1 (LIVE)",
                                "timestamp_utc": settled_ts,
                            }

                            all_reports.insert(0, rep)
                            existing_ids.add(report_id)
                            existing_tickers.add(ticker)
                            new_reconciled += 1

                            # Enqueue settlement to SQLite
                            self.db_writer.enqueue_settlement(
                                settlement_id=report_id,
                                ticker=ticker,
                                side=trade_side,
                                size=size,
                                entry_price=float(entry_price),
                                settlement_price=1.00 if won else 0.00,
                                outcome=outcome,
                                pnl=float(pnl),
                                balance_after=float(balance_after),
                                bot_type=bot_type,
                                execution_mode="live",
                            )

                            # Release cycle lock in Guardrails
                            self.guardrails.record_cycle_settlement(
                                ticker=ticker,
                                outcome=outcome,
                                pnl=pnl,
                                balance_after=balance_after,
                                cycle_id=ticker,
                            )

                            # Consecutive Loss Streak Breaker — auto-disarm after N consecutive losses
                            # Only evaluate for new live settlements that occurred during this running session.
                            if not is_historical:
                                if outcome == "loss":
                                    self.consecutive_losses += 1
                                    if self.consecutive_losses >= self.max_consecutive_losses and self.is_armed:
                                        self.is_armed = False
                                        logger.warning(
                                            "🛑 [STREAK BREAKER] %d consecutive losses reached (max=%d). "
                                            "Bot AUTO-DISARMED to prevent further hemorrhaging. "
                                            "Manual re-arm required via /api/bot/arm.",
                                            self.consecutive_losses, self.max_consecutive_losses,
                                        )
                                else:
                                    if self.consecutive_losses > 0:
                                        logger.info(
                                            "✅ [STREAK RESET] Win breaks %d-loss streak. Counter reset to 0.",
                                            self.consecutive_losses,
                                        )
                                    self.consecutive_losses = 0

                            logger.info(
                                "🏆 [SETTLEMENT RECONCILED] %s: %s | Result: %s | PnL: %+.2f | Streak: %d",
                                ticker, outcome.upper(), market_result.upper(), float(pnl), self.consecutive_losses
                            )

                        if new_reconciled > 0:
                            # Atomic disk persist
                            tmp_file = self.data_dir / "win_loss_reports.tmp"
                            with open(tmp_file, "w", encoding="utf-8") as f:
                                json.dump(all_reports, f, indent=2)
                            tmp_file.replace(reports_file)

                            self.sync_pnl_reports()
                            await self.sync_balance()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("Settlement reconciliation loop error: %s", exc)

            await asyncio.sleep(15.0)


# ---------------------------------------------------------------------------
# FastAPI Pocket Cockpit Server
# ---------------------------------------------------------------------------

app_engine: Optional[StandaloneBotEngine] = None
engine_lock: Optional[TradingEngineLock] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global app_engine, engine_lock
    if os.getenv("TESTING") == "true":
        yield
        return

    # 1. Acquire Engine Lock
    force_lock = os.getenv("KALSHI_FORCE_LOCK", "false").lower() in ("true", "1", "yes")
    engine_lock = TradingEngineLock()
    engine_lock.acquire(force=force_lock)

    # 2. Start Engine
    is_live = os.getenv("KALSHI_ENV", "live").lower() in ("prod", "live")
    init_asset_str = os.getenv("KALSHI_ACTIVE_ASSET", "BTC").upper().strip()
    try:
        init_asset = CryptoAsset(init_asset_str)
    except ValueError:
        init_asset = CryptoAsset.BTC
    app_engine = StandaloneBotEngine(is_live=is_live, is_armed=True, asset=init_asset)
    await app_engine.start()

    yield

    # 3. Shutdown Engine & Release Lock
    if app_engine:
        await app_engine.stop()
    if engine_lock:
        engine_lock.release()


app = FastAPI(title="Kalshi 3-Step Dominion Standalone", lifespan=lifespan)

raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
if raw_origins.strip():
    allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
else:
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://localhost:8001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8001",
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


@app.middleware("http")
async def add_security_headers(request, call_next):
    """SECURITY: Add HTTP response headers to harden against clickjacking, MIME sniffing, and XSS."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.get("/", response_class=HTMLResponse)
async def get_cockpit() -> str:
    """Serve ultra-lean Pocket Cockpit UI."""
    if TEMPLATE_PATH.exists():
        return TEMPLATE_PATH.read_text(encoding="utf-8")
    return "<h1>Pocket Cockpit template not found.</h1>"


@app.get("/api/state")
async def get_state() -> Dict[str, Any]:
    """Provide real-time telemetry to Pocket Cockpit."""
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
    pct_decimals = 4 if diff_pct_abs < Decimal("0.01") else (3 if diff_pct_abs < Decimal("0.10") else 2)
    diff_pct_str = f"{diff_sign}{diff_pct_abs:.{pct_decimals}f}%"
    moneyness_diff_str = f"{diff_str} ({diff_pct_str})"

    dec = app_engine.last_decision
    playbook = dec.active_playbook if dec else "none"
    edge = dec.edge_pct if dec else 0.0
    ev = dec.ev_yes if (dec and dec.recommended_side == "yes") else (dec.ev_no if dec else 0.0)
    vpin = dec.vpin if dec else 0.0
    vpin_safe = dec.vpin_is_safe if dec else True
    rationale = dec.rationale if dec else "Monitoring microstructure order flow..."

    # Position info
    resting_count = len(app_engine.active_resting_orders)
    locked = app_engine.guardrails.is_cycle_locked(app_engine.active_ticker)
    has_pos = bool(app_engine.active_position and app_engine.active_position.get("size", 0) > 0)
    if has_pos:
        pos_data = app_engine.active_position or {}
        pos_side = str(pos_data.get("side", "yes")).upper()
        pos_size = int(pos_data.get("size", 1))
        entry_p = Decimal(str(pos_data.get("entry_price", "0.52")))
        cur_bid = app_engine.best_yes_bid if pos_side == "YES" else app_engine.best_no_bid
        if cur_bid is not None:
            pnl_dec = (cur_bid - entry_p) * Decimal(str(pos_size))
            sign = "+" if pnl_dec >= Decimal("0.00") else "-"
            tp_thresh = app_engine.bot.take_profit_price_threshold
            tp_diff = tp_thresh - cur_bid
            pos_str = f"HOLDING {pos_size} {pos_side} @ ${entry_p:.2f} (Bid: ${cur_bid:.2f} | {sign}${abs(pnl_dec):.2f})"
            if app_engine.bot.enable_take_profit_ceiling:
                if app_engine.bot.require_reversal_for_tp_ceiling:
                    pos_sub = f"TP Ceiling: ${tp_thresh:.2f} · Gated by {app_engine.bot.reverse_indicator_threshold*100:.0f}% Reversal"
                else:
                    pos_sub = f"TP Ceiling: ${tp_thresh:.2f} (Dist: ${tp_diff:.2f}) · Auto-Exit Active"
            elif app_engine.bot.enable_reverse_take_profit_roi:
                pos_sub = f"Holding · Reversal TP ({app_engine.bot.min_take_profit_roi*100:.0f}% @ {app_engine.bot.reverse_indicator_threshold*100:.0f}% Rev) Active"
            else:
                pos_sub = f"Holding to expiry · Auto-Exits Disabled"
        else:
            pos_str = f"HOLDING {pos_size} {pos_side} @ ${entry_p:.2f}"
            pos_sub = f"TP Ceiling: ${app_engine.bot.take_profit_price_threshold:.2f}"
    elif resting_count > 0:
        pos_str = f"MAKER RESTING ({resting_count} active)"
        pos_sub = f"Resting limit order at ${app_engine.bot.discount_limit_price:.2f}"
    elif locked:
        pos_str = "IN CYCLE TRADE"
        pos_sub = "1 cycle entry active"
    else:
        pos_str = "FLAT"
        pos_sub = "0 contracts active"

    # Default to total balance or fallback
    bal = float(app_engine.total_balance_dollars) if app_engine.total_balance_dollars > 0 else float(app_engine.balance_dollars)
    shard2_bal = float(app_engine.shard2_balance_dollars) if app_engine.shard2_balance_dollars > 0 else bal

    return {
        "armed": app_engine.is_armed,
        "balance": bal,
        "shard2_balance": shard2_bal,
        "today_pnl": float(app_engine.today_pnl),
        "settled_cycles": app_engine.settled_cycles,
        "today_wins": app_engine.today_wins,
        "today_losses": app_engine.today_losses,
        "today_win_rate": round(app_engine.today_win_rate, 1),
        "consecutive_losses": app_engine.consecutive_losses,
        "max_consecutive_losses": app_engine.max_consecutive_losses,
        "active_asset": app_engine.active_asset.value,
        "active_asset_name": cfg.name,
        "active_asset_symbol": cfg.symbol,
        "series_ticker": cfg.series_ticker_15m,
        "active_ticker": app_engine.active_ticker,
        "time_remaining_str": t_str,
        "target_time_str": app_engine.target_time_str,
        "time_window_str": app_engine.time_window_str,
        "expiry_countdown_seconds": int(t_rem),
        "position_str": pos_str,
        "position_sub": pos_sub,
        "resting_orders_count": resting_count,
        "spot_price": float(spot_dec),
        "spot_price_str": cfg.format_price(spot_dec),
        "target_strike": float(strike_dec),
        "target_strike_str": cfg.format_price(strike_dec) if strike_dec > 0 else "$0.00",
        "spot_diff": float(round(diff_dec, cfg.price_decimals)),
        "spot_diff_pct": float(round(diff_pct_dec, 3)),
        "spot_diff_str": diff_str,
        "spot_diff_pct_str": diff_pct_str,
        "moneyness_diff_str": moneyness_diff_str,
        "is_above_strike": is_up,
        "best_yes_bid": float(app_engine.best_yes_bid) if app_engine.best_yes_bid is not None else None,
        "best_yes_ask": float(app_engine.best_yes_ask) if app_engine.best_yes_ask is not None else None,
        "best_no_bid": float(app_engine.best_no_bid) if app_engine.best_no_bid is not None else None,
        "best_no_ask": float(app_engine.best_no_ask) if app_engine.best_no_ask is not None else None,
        "playbook": playbook,
        "p_up": float(dec.p_up) if dec else 0.50,
        "p_down": float(dec.p_down) if dec else 0.50,
        "p_wait": float(dec.p_wait) if dec else 0.00,
        "edge_pct": edge,
        "ev": ev,
        "vpin": vpin,
        "vpin_is_safe": vpin_safe,
        "rationale": rationale,
        "spot_source": app_engine.spot_source if app_engine else "Unknown",
        "brti_connected": app_engine.brti_connected if app_engine else False,
        "twap_60s": float(app_engine.twap_60s_price) if (app_engine and app_engine.twap_60s_price) else None,
        "twap_60s_str": cfg.format_price(app_engine.twap_60s_price) if (app_engine and app_engine.twap_60s_price) else None,
        "recent_reports": app_engine.recent_reports,
        "kalshi_ws_connected": app_engine.kalshi_ws_connected,
        "spot_connected": app_engine.spot_connected,
        "coinbase_connected": app_engine.coinbase_connected,
        "binance_connected": app_engine.binance_connected,
        "enable_take_profit_ceiling": app_engine.bot.enable_take_profit_ceiling,
        "take_profit_price_threshold": float(app_engine.bot.take_profit_price_threshold),
        "require_reversal_for_tp_ceiling": app_engine.bot.require_reversal_for_tp_ceiling,
        "enable_reverse_take_profit_roi": app_engine.bot.enable_reverse_take_profit_roi,
        "reverse_indicator_threshold": float(app_engine.bot.reverse_indicator_threshold) * 100.0,
        "min_take_profit_roi": float(app_engine.bot.min_take_profit_roi) * 100.0,
        "has_active_position": has_pos,
        "parameters": app_engine.get_parameters(),
        "orderbook_ladder": [
            {
                "side": "yes",
                "price_cents": f"{float(pr * 100):.1f}¢",
                "price_raw": float(pr),
                "contracts": int(qty),
                "total": f"${float(pr * qty):,.0f}",
                "depth_pct": min(100, max(8, int((float(qty) / (max([float(q) for q in list(b.yes_book.values()) + list(b.no_book.values())] or [1000.0]))) * 100))),
            }
            for b in [app_engine.orderbook.get_book(app_engine.active_ticker)]
            if b
            for pr, qty in sorted(b.yes_book.items(), key=lambda x: x[0], reverse=True)[:8]
        ] + [
            {
                "side": "no",
                "price_cents": f"{float(pr * 100):.1f}¢",
                "price_raw": float(pr),
                "contracts": int(qty),
                "total": f"${float(pr * qty):,.0f}",
                "depth_pct": min(100, max(8, int((float(qty) / (max([float(q) for q in list(b.yes_book.values()) + list(b.no_book.values())] or [1000.0]))) * 100))),
            }
            for b in [app_engine.orderbook.get_book(app_engine.active_ticker)]
            if b
            for pr, qty in sorted(b.no_book.items(), key=lambda x: x[0], reverse=True)[:8]
        ],
    }


class AssetSelectRequest(BaseModel):
    asset: str


@app.get("/api/assets")
async def get_supported_assets() -> Dict[str, Any]:
    """Return supported cryptocurrency assets and live CF Benchmarks prices for Standalone Bot."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    cf_data = app_engine.cf_sync.get_all_state() if app_engine.cf_sync else {}
    assets_list = []
    for a in CryptoAsset:
        cfg = get_asset_config(a)
        quote = cf_data.get(a.value, {})
        assets_list.append({
            "id": a.value,
            "name": cfg.name,
            "series_15m": cfg.series_ticker_15m,
            "cf_index_id": cfg.cf_index_id,
            "price_decimals": cfg.price_decimals,
            "strike_step": float(cfg.strike_step),
            "min_spot_diff": float(cfg.min_spot_diff),
            "price": float(quote.get("price", 0.0)),
            "twap_60s": float(quote.get("twap_60s", 0.0)) if quote.get("twap_60s") else None,
            "is_active": (a == app_engine.active_asset),
        })
    return {
        "active_asset": app_engine.active_asset.value,
        "assets": assets_list,
    }


@app.post("/api/assets/select")
async def select_active_asset(req: AssetSelectRequest) -> Dict[str, Any]:
    """Switch active asset on Standalone Bot (BTC, ETH, SOL, DOGE)."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    try:
        new_asset = CryptoAsset(req.asset.upper().strip())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid asset: '{req.asset}'. Supported assets: {[a.value for a in CryptoAsset]}"
        )
    app_engine.set_asset(new_asset)
    return {
        "status": "SUCCESS",
        "active_asset": app_engine.active_asset.value,
        "active_asset_name": app_engine.active_cfg.name,
        "series_ticker": app_engine.active_cfg.series_ticker_15m,
    }


@app.post("/api/bot/arm")
async def arm_bot() -> Dict[str, Any]:
    """Arm the bot for live execution."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    app_engine.is_armed = True
    app_engine.consecutive_losses = 0  # Reset streak counter on manual re-arm
    logger.info("🟢 [BOT ARMED] Live order execution activated by user. Loss streak reset.")
    return {"status": "ARMED", "armed": True, "consecutive_losses": 0}


@app.post("/api/bot/disarm")
async def disarm_bot() -> Dict[str, Any]:
    """Disarm the bot into standby mode."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    app_engine.is_armed = False
    logger.info("⏸️ [BOT DISARMED] Standby mode activated by user.")
    return {"status": "DISARMED", "armed": False}


@app.post("/api/bot/panic")
async def panic_halt() -> Dict[str, Any]:
    """Emergency halt: disarm bot and cancel all resting orders on exchange."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    cancelled = await app_engine.panic_cancel_all()
    logger.warning("🛑 [PANIC TRIGGERED] Bot disarmed and %d order(s) cancelled.", cancelled)
    return {"status": "PANIC_EXECUTED", "cancelled_orders": cancelled, "armed": False}


class ParametersUpdateRequest(BaseModel):
    discount_limit_price: Optional[float] = Field(default=None, ge=0.10, le=0.65, description="Maker discount limit price ceiling")
    max_contracts: Optional[int] = Field(default=None, ge=1, le=1, description="Max contracts per cycle trade (strictly 1)")
    min_edge_pct: Optional[float] = Field(default=None, ge=1.0, le=50.0, description="Minimum edge percentage")
    min_ev_dollars: Optional[float] = Field(default=None, ge=0.01, le=0.50, description="Minimum net EV dollars per contract")
    min_spot_diff: Optional[float] = Field(default=None, ge=0.0, le=200.0, description="Minimum distance from strike to avoid coin flips")
    vpin_toxic_threshold: Optional[float] = Field(default=None, ge=0.10, le=0.95, description="VPIN toxicity threshold")
    take_profit_price_threshold: Optional[float] = Field(default=None, ge=0.50, le=0.99, description="Take profit ceiling")
    enable_take_profit_ceiling: Optional[bool] = Field(default=None, description="Take profit ceiling enabled toggle")
    require_reversal_for_tp_ceiling: Optional[bool] = Field(default=None, description="Require 85%+ reversal detection to exit at ceiling")
    enable_reverse_take_profit_roi: Optional[bool] = Field(default=None, description="Only take profit on min_take_profit_roi if indicators >= 85% reverse")
    reverse_indicator_threshold: Optional[float] = Field(default=None, ge=50.0, le=99.0, description="Conviction threshold in opposite direction required for take-profit harvest (e.g. 85.0%)")
    min_take_profit_roi: Optional[float] = Field(default=None, ge=5.0, le=100.0, description="Minimum take profit ROI percentage")
    min_confidence: Optional[float] = Field(default=None, ge=0.50, le=0.99, description="Minimum ONNX neural net confidence")
    momentum_max_price: Optional[float] = Field(default=None, ge=0.50, le=0.99, description="Maximum allowable entry price for momentum trades")
    brain_priority_mode: Optional[str] = Field(default=None, description="Brain priority arbitration mode: TREND_ALIGNED_SCALP, CONTRADICTION_SNIPER, UNANIMOUS_CONSENSUS")
    contract_scaling_mode: Optional[str] = Field(default=None, description="Contract sizing mode: TIER_0_STRICT_1, TIER_1_CONVICTION_2, TIER_2_KELLY")
    volatility_floor: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Dead chop cutoff threshold in dollars ($)")
    volatility_ceiling: Optional[float] = Field(default=None, ge=10.0, le=500.0, description="News event / high chaos cutoff in dollars ($)")
    entry_discount_depth: Optional[float] = Field(default=None, ge=0.10, le=0.65, description="Entry discount limit depth ceiling ($0.35 - $0.65)")
    tape_confirmation_ticks: Optional[int] = Field(default=None, ge=1, le=10, description="Number of consecutive orderflow tape ticks required for entry confirmation")
    taker_cross_ev_threshold: Optional[float] = Field(default=None, ge=0.01, le=0.30, description="Minimum EV required to pay taker spread/fee")
    dynamic_moat_multiplier: Optional[float] = Field(default=None, ge=0.5, le=3.0, description="Dynamic moat volatility multiplier")
    max_temporal_skew_ms: Optional[float] = Field(default=None, ge=100.0, le=10000.0, description="Max cross-brain temporal skew in milliseconds")
    gamma_cliff_seconds: Optional[float] = Field(default=None, ge=10.0, le=300.0, description="Gamma cliff late-cycle cutoff in seconds")
    auto_cancel_on_veto: Optional[bool] = Field(default=None, description="Automatically cancel resting orders on veto/cutoff")
    dynamic_volatility_mode: Optional[str] = Field(default=None, description="Volatility mode: REALIZED_ATR or FIXED_14")


@app.get("/api/bot/parameters")
async def get_bot_parameters() -> Dict[str, Any]:
    """Return live strategy parameters and guardrail thresholds."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    return app_engine.get_parameters()


@app.post("/api/bot/parameters")
async def update_bot_parameters(req: ParametersUpdateRequest) -> Dict[str, Any]:
    """Dynamically update strategy parameters and guardrail caps."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    payload = req.model_dump(exclude_none=True)
    res = app_engine.update_parameters(**payload)
    logger.info("⚙️ [PARAMETERS UPDATED] New configuration: %s", res)
    return {"status": "SUCCESS", "parameters": res}


@app.post("/api/bot/sweep-orders")
async def sweep_orders(force: bool = False) -> Dict[str, Any]:
    """Manually sweep and cancel all resting orders on finished or non-active events."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    cancelled = await app_engine.sweep_old_orders(keep_ticker=app_engine.active_ticker, force_all=force)
    t_rem = app_engine.get_time_to_expiry()
    logger.info("🧹 [MANUAL SWEEP] Cancelled %d order(s) for finished/expired events.", cancelled)
    return {
        "status": "SWEEP_COMPLETE",
        "cancelled_orders": cancelled,
        "active_ticker": app_engine.active_ticker,
        "time_to_expiry_s": round(t_rem, 1),
    }


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
    """Check if Cockpit window is found and pinned as Always on Top."""
    windows = find_cockpit_windows()
    if not windows:
        return {"available": False, "is_topmost": False, "windows_count": 0}
    hwnd, title = windows[0]
    topmost = is_always_on_top(hwnd)
    return {
        "available": True,
        "is_topmost": topmost,
        "hwnd": hwnd,
        "title": title,
        "windows_count": len(windows),
    }


@app.post("/api/window/pin")
async def pin_window(req: WindowPinRequest) -> Dict[str, Any]:
    """Toggle Always on Top (HWND_TOPMOST) for Cockpit window."""
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
    """Resize Cockpit window (e.g. for Minimized widget or Expanded mode)."""
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
    """Launch Microsoft Edge or Chrome in chromeless app mode pinned as a floating desktop widget."""
    port = 8001
    ok = launch_widget_window(port=port, view="minimized")
    return {"status": "LAUNCHED" if ok else "FAILED", "success": ok}


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Kalshi 3-Step Dominion Standalone Bot")
    parser.add_argument("--port", type=int, default=8001, help="HTTP Cockpit port (default: 8001)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="HTTP Cockpit host (default: 0.0.0.0)")
    parser.add_argument("--live", action="store_true", default=True, help="Enable live trading mode")
    parser.add_argument("--force", action="store_true", default=False, help="Force lock acquisition if stale")
    parser.add_argument("--no-browser", action="store_true", default=False, help="Do not open browser automatically")
    parser.add_argument("--widget", action="store_true", default=False, help="Launch as a floating desktop widget (app mode + always on top)")
    parser.add_argument("--asset", type=str, default="BTC", choices=["BTC", "ETH", "SOL", "DOGE"], help="Active crypto asset (default: BTC)")
    parser.add_argument("--budget", type=float, default=None, help="Virtual budget cap in USD for partitioned dual-engine live trading")
    args = parser.parse_args()
    if args.force:
        os.environ["KALSHI_FORCE_LOCK"] = "true"
    if args.asset:
        os.environ["KALSHI_ACTIVE_ASSET"] = args.asset.upper()
    if args.budget is not None:
        os.environ["KALSHI_DOM_BUDGET"] = str(args.budget)

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

    logger.info("⚡ Launching Kalshi 3-Step Dominion Standalone Engine [%s] on http://%s:%d ...", args.asset.upper(), args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()

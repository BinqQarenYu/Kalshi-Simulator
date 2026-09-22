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
from collections import defaultdict, deque
from contextlib import asynccontextmanager
import ctypes
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
import logging
import math
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
from fastapi import Body, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from app_3_autonomous_chef.remote_control import RemoteControlManager

from kalshi_sim.agent_guardrails import AgentGuardrails
from shared.auth import (
    DEMO_REST_BASE,
    DEMO_WS_URL,
    PROD_REST_BASE,
    PROD_WS_URL,
    create_aiohttp_connector,
    load_private_key,
)
from app_3_autonomous_chef.bot_deployment_auditor import BotDeploymentAuditor
from shared.cfbenchmarks_sync import CFBenchmarksSync
from shared.clock_sync import clock_sync
from kalshi_sim.db import get_db, get_db_writer, DatabaseWriter
from app_3_autonomous_chef.incubator_manager import get_incubator_manager, IncubatorManager
from app_2_execution_bot.live_coordinator import LiveCoordinator
from app_1_machine_engine.ml.domination_bot import DominationDecision, ThreeStepDominationBot
from app_1_machine_engine.ml.macro_trend_dominion_bot import MacroTrendDominionBot
from app_2_execution_bot.ml.onnx_engine import KalshiONNXEngine
from app_2_execution_bot.order_client import KalshiDemoOrderClient, KalshiLiveOrderClient
from app_2_execution_bot.orderbook import OrderBookManager
from app_3_autonomous_chef.poe_flight_recorder import POEFlightRecorder, POEDecisionRecord
from app_2_execution_bot.rate_limiter import kalshi_rate_limiter
from shared.schemas import (
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

import copy
from kalshi_sim.process_lock import TradingEngineLock, is_pid_running

from app_2_execution_bot.standalone_bot_modules.config import (
    DEFAULT_ASSET_PROFILES,
    ET_ZONE,
    LOCK_FILE_PATH,
    QRCODE_PATH,
    TEMPLATE_PATH,
)
from app_2_execution_bot.standalone_bot_modules.power import (
    format_cycle_time_from_iso,
    prevent_windows_sleep,
)



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
        asset: Optional[CryptoAsset] = None,
    ) -> None:
        self.is_live = is_live
        self.is_armed = is_armed
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        default_asset = asset if asset is not None else CryptoAsset.BTC
        self.active_asset: CryptoAsset = default_asset
        self.active_cfg = get_asset_config(default_asset)

        # 1. Instantiate Strategy & Guardrails (with Brain 1 ONNX & Opening Quarantine)
        try:
            self.onnx_engine: Optional[KalshiONNXEngine] = KalshiONNXEngine()
            logger.info("🧠 [BRAIN 1 ONNX] Initialized QuoLas Nano Microscope inference engine.")
        except Exception as onnx_err:
            logger.warning("⚠️ [BRAIN 1 ONNX] ONNX engine fallback: %s", onnx_err)
            self.onnx_engine = None

        if is_live:
            self.bot_id = "macro_trend_dominion"
            self.bot = MacroTrendDominionBot(
                asset=default_asset,
                opening_quarantine_seconds=90.0,
                onnx_engine=self.onnx_engine,
            )
        else:
            self.bot_id = "3_step_domination_bot"
            self.bot = ThreeStepDominationBot(
                asset=default_asset,
                opening_quarantine_seconds=90.0,
                onnx_engine=self.onnx_engine,
            )
        self.guardrails = AgentGuardrails(
            min_order_interval_seconds=45.0,
            max_micro_bankroll_contracts=1,
            max_nano_bankroll_contracts=1,
            vpin_toxic_threshold=0.60,
        )
        self.auditor = BotDeploymentAuditor()
        self.orderbook = OrderBookManager(enforce_consecutive_seq=False)

        # Multi-Asset Basket State (Option B) - Must be initialized before loading persisted parameters
        self.asset_mode: str = "single"  # "single", "basket", or "all"
        self.active_assets: List[CryptoAsset] = [self.active_asset]
        self.max_concurrent_positions: int = 3  # Micro-bankroll portfolio exposure cap
        self.active_positions: Dict[str, Dict[str, Any]] = {}  # ticker -> position dict
        self.asset_markets: Dict[str, Dict[str, Any]] = {}  # asset_str -> market info dict

        # Initialize per-asset strategy profiles (BTC, ETH, SOL, DOGE, GOLD, HYPER)
        self.asset_profiles: Dict[str, Dict[str, Any]] = copy.deepcopy(DEFAULT_ASSET_PROFILES)

        # Load user-saved persistent default parameters if present
        self._load_persisted_parameters(explicit_asset=asset)

        # 1b. Remote Control pairing & discovery engine
        self.remote_manager = RemoteControlManager(data_dir=self.data_dir, port=8001)

        # 2. Run Pre-Flight Certification Audit & Seal of Excellence Gate
        mode_str = "live" if is_live else "simulated"
        audit_rep = self.auditor.audit_bot(self.bot_id, self.bot, mode=mode_str)
        if not audit_rep.is_certified:
            err_msgs = [f"{p.pillar_name}: {p.message}" for p in audit_rep.pillars if p.status == "FAIL"]
            raise RuntimeError(f"Strategy {self.bot_id} FAILED pre-flight audit: {'; '.join(err_msgs)}")
        if is_live and not self.auditor.has_seal_of_excellence(self.bot_id):
            raise RuntimeError("Strategy {self.bot_id} does not hold an active Seal of Excellence for live order routing.")
        seal_tok = audit_rep.seal.seal_token if audit_rep.seal else "PENDING"
        logger.info("✅ [AUDIT CERTIFIED] 3-Step Domination Bot passed all 5 pillars for %s trading. Seal: %s", mode_str.upper(), seal_tok)

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

        # Multi-Asset Basket State already initialized above and restored from disk

        # Live Inside-Touch Quotes
        self.best_yes_bid: Optional[Decimal] = None
        self.best_yes_ask: Optional[Decimal] = None
        self.best_no_bid: Optional[Decimal] = None
        self.best_no_ask: Optional[Decimal] = None

        # Balances (Total Portfolio & Active Execution Shard)
        self.total_balance_dollars: Decimal = Decimal("0.00")
        self.shard2_balance_dollars: Decimal = Decimal("0.00")
        self.balance_dollars: Decimal = Decimal("0.00")
        self.polymarket_balance_dollars: float = 0.0

        # Settlement & PnL Tracking
        self.today_pnl: Decimal = Decimal("0.00")
        self.settled_cycles: int = 0
        self.today_wins: int = 0
        self.today_losses: int = 0
        self.today_win_rate: float = 0.0
        self.recent_reports: List[Dict[str, Any]] = []

        # Cross-Exchange Arbitrage Scanner (Phase 1/2)
        from kalshi_sim.arbitrage_scanner import CrossExchangeScanner
        self.arb_scanner = CrossExchangeScanner(self)

        # Consecutive Loss Streak Breaker (Multi-Asset Basket calibrated: 7 consecutive losses)
        self.consecutive_losses: int = 0
        self.max_consecutive_losses: int = int(os.getenv("KALSHI_MAX_CONSECUTIVE_LOSSES", "7"))
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

        # Agent POE Empirical Flight Recorder (Ground Truth Ledger)
        self.poe_recorder = POEFlightRecorder(ledger_path=self.data_dir / "poe_flight_ledger.jsonl")
        self._cycle_veto_candidates: Dict[str, Dict[str, Any]] = {}

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
        # High-frequency spot price history (300 ticks / ~60s at 5Hz) for sub-second velocity & front-running
        self._spot_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=300))

        # Modular Engine Coordinators
        from app_2_execution_bot.standalone_bot_modules.standalone_sync import StandaloneSyncCoordinator
        from app_2_execution_bot.standalone_bot_modules.standalone_evaluation import StandaloneEvaluationCoordinator
        from app_2_execution_bot.standalone_bot_modules.standalone_feeds import StandaloneFeedsCoordinator

        self._sync_coordinator = StandaloneSyncCoordinator(self)
        self._eval_coordinator = StandaloneEvaluationCoordinator(self)
        self._feeds_coordinator = StandaloneFeedsCoordinator(self)

    @staticmethod
    def calculate_ols_spot_velocity(
        hist: Optional[deque | list],
        target_window_s: float = 3.0,
    ) -> tuple[float, float, float]:
        """Pure mathematical calculation of rolling OLS regression velocity ($/3s), 60s realized vol ($/1m), and SNR."""
        if not hist or len(hist) < 3:
            return 0.0, 14.0, 0.0

        now_t, current_price = hist[-1]
        target_t = now_t - target_window_s

        # Extract points within target window
        window_pts = [(t, p) for t, p in hist if t >= target_t]
        if len(window_pts) < 3:
            window_pts = list(hist)[-min(len(hist), 15):]

        n = len(window_pts)
        t_bar = sum(t for t, p in window_pts) / n
        p_bar = sum(p for t, p in window_pts) / n
        cov = sum((t - t_bar) * (p - p_bar) for t, p in window_pts)
        var_t = sum((t - t_bar) ** 2 for t, p in window_pts)

        if var_t > 1e-7:
            slope_per_sec = cov / var_t
            res_var = sum((p - (p_bar + slope_per_sec * (t - t_bar))) ** 2 for t, p in window_pts) / max(1, n - 2)
            std_err = math.sqrt(res_var / var_t) if res_var > 0 else 0.0
            snr = abs(slope_per_sec) / std_err if std_err > 1e-6 else 999.0
        else:
            slope_per_sec = 0.0
            snr = 0.0

        vel_3s = slope_per_sec * target_window_s

        # Compute rolling realized volatility (estimated 1-minute dollar vol)
        if len(hist) >= 6:
            diffs = [hist[i][1] - hist[i-1][1] for i in range(1, len(hist))]
            mean_d = sum(diffs) / len(diffs)
            var_d = sum((x - mean_d) ** 2 for x in diffs) / len(diffs)
            dt_total = hist[-1][0] - hist[0][0]
            dt_avg = max(0.05, dt_total / max(1, len(hist) - 1))
            realized_vol_1m = math.sqrt(var_d / dt_avg) * math.sqrt(60.0)
        else:
            realized_vol_1m = 14.0

        return vel_3s, realized_vol_1m, snr

    def get_spot_velocity_stats(self, asset: CryptoAsset | str) -> tuple[float, float, float]:
        """Calculate rolling 3-second OLS regression velocity ($/3s), 60s realized vol ($/1m), and SNR."""
        a_key = asset.value if hasattr(asset, "value") else str(asset)
        hist = self._spot_history.get(a_key)
        return self.calculate_ols_spot_velocity(hist, target_window_s=3.0)

    def get_spot_velocity_3s(self, asset: CryptoAsset | str) -> float:
        """Calculate rolling 3-second spot price velocity from sub-second feed using OLS regression."""
        vel_3s, _, snr = self.get_spot_velocity_stats(asset)
        if snr < 1.2:
            return 0.0
        return vel_3s

    def get_current_timeframe(self) -> str:
        """Detect current active contract timeframe (5m or 15m)."""
        if self.active_ticker:
            t_upper = self.active_ticker.upper()
            if "5M" in t_upper or "5MIN" in t_upper:
                return "5m"
        return self.timeframe

    def set_asset(self, asset: CryptoAsset | str | List[CryptoAsset | str], persist: bool = True) -> None:
        """Switch active underlying asset, custom basket list, or activate ALL omnichannel basket mode."""
        if isinstance(asset, list):
            valid: List[CryptoAsset] = []
            inc_mgr = get_incubator_manager()
            for item in asset:
                item_str = str(item.value if hasattr(item, "value") else item).upper().strip()
                if item_str == "ALL":
                    self.set_asset("ALL", persist=persist)
                    return
                try:
                    c_asset = CryptoAsset(item_str)
                    if self.is_live and inc_mgr.is_locked(c_asset):
                        continue
                    if c_asset not in valid:
                        valid.append(c_asset)
                except ValueError:
                    pass
            if not valid:
                valid = [CryptoAsset.BTC]
            self.active_assets = valid
            if len(self.active_assets) >= len(CryptoAsset):
                self.asset_mode = "all"
            elif len(self.active_assets) == 1:
                self.asset_mode = "single"
            else:
                self.asset_mode = "basket"
            self.active_asset = self.active_assets[0]
            self.active_cfg = get_asset_config(self.active_asset)
            self._apply_asset_profile(self.active_asset)
            self.active_ticker = ""
            self.target_strike = Decimal("0.00")
            if self.cf_sync:
                p = self.cf_sync.get_price(self.active_asset)
                if p > Decimal("0.00"):
                    self.current_btc_spot = p
                    self.twap_60s_price = self.cf_sync.get_twap(self.active_asset)
            logger.info("⚡ [BASKET MODE] Set active assets to %s (mode=%s)", [a.value for a in self.active_assets], self.asset_mode)
            if persist:
                self._persist_parameters()
            return

        asset_str = str(asset.value if hasattr(asset, "value") else asset).upper().strip()
        inc_mgr = get_incubator_manager()
        if asset_str == "ALL":
            self.asset_mode = "all"
            # Omnichannel Basket excludes any assets quarantined in Lane 2 Incubator in LIVE mode
            if self.is_live:
                self.active_assets = [a for a in CryptoAsset if not inc_mgr.is_locked(a)]
            else:
                self.active_assets = list(CryptoAsset)
            if not self.active_assets:
                self.active_assets = [CryptoAsset.BTC]
            self.active_asset = self.active_assets[0]
            self.active_cfg = get_asset_config(self.active_asset)
            self._apply_asset_profile(self.active_asset)
            quarantined = [a.value for a in CryptoAsset if inc_mgr.is_locked(a)]
            logger.info("⚡ [BASKET MODE] Switched Standalone Bot to Omnichannel Basket Mode (ALL) - Scanning %d assets concurrently (Live Quarantined in Incubator: %s).", len(self.active_assets), quarantined)
            if persist:
                self._persist_parameters()
            return

        self.asset_mode = "single"
        if not isinstance(asset, CryptoAsset):
            asset = CryptoAsset(asset_str)
        if self.is_live and inc_mgr.is_locked(asset):
            logger.warning("⚠️ [INCUBATOR VETO] Asset %s is quarantined in Lane 2 Incubator (%s). Defaulting to BTC.", asset.value, inc_mgr.get_lock_reason(asset))
            asset = CryptoAsset.BTC
        self.active_asset = asset
        self.active_assets = [asset]
        self.active_cfg = get_asset_config(asset)
        self._apply_asset_profile(asset)
        self.active_ticker = ""
        self.target_strike = Decimal("0.00")
        if self.cf_sync:
            p = self.cf_sync.get_price(asset)
            if p > Decimal("0.00"):
                self.current_btc_spot = p
                self.twap_60s_price = self.cf_sync.get_twap(asset)
        logger.info("Switched Standalone Bot active asset to %s (%s)", self.active_cfg.name, asset.value)
        if persist:
            self._persist_parameters()

    def _get_params_file_path(self) -> Path:
        """Return the persistent parameters file path."""
        return self.data_dir / "bot_parameters_domination.json"

    def _apply_asset_profile(self, asset: CryptoAsset | str) -> None:
        """Calibrate strategy and load asset-specific dials into domination bot."""
        asset_str = asset.value if hasattr(asset, "value") else str(asset).upper()
        try:
            c_asset = CryptoAsset(asset_str)
        except ValueError:
            c_asset = CryptoAsset.BTC
            asset_str = "BTC"

        if asset_str not in self.asset_profiles:
            self.asset_profiles[asset_str] = copy.deepcopy(DEFAULT_ASSET_PROFILES.get(asset_str, DEFAULT_ASSET_PROFILES["BTC"]))

        # Calibrate baseline asset properties
        self.bot.set_asset(c_asset)

        # Apply asset-specific dial overrides
        profile = copy.deepcopy(self.asset_profiles[asset_str])
        profile.pop("max_contracts", None)
        profile.pop("asset", None)
        self.bot.update_parameters(**profile)

        # Inviolable sizing armor: strictly 1 contract
        self.guardrails.max_micro_bankroll_contracts = 1
        self.guardrails.max_nano_bankroll_contracts = 1
        if "vpin_toxic_threshold" in profile:
            self.guardrails.vpin_toxic_threshold = float(profile["vpin_toxic_threshold"])

    def _load_persisted_parameters(self, explicit_asset: Optional[CryptoAsset] = None) -> None:
        """Load user-saved parameters and state from disk into per-asset profiles."""
        params_file = self._get_params_file_path()
        if not params_file.exists():
            self._apply_asset_profile(self.active_asset)
            return
        try:
            with open(params_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.warning("⚠️ [PARAM PERSISTENCE] Invalid format in %s, using factory defaults.", params_file)
                self._apply_asset_profile(self.active_asset)
                return

            saved_assets = data.get("assets", {})
            if isinstance(saved_assets, dict) and saved_assets:
                for a_key, a_params in saved_assets.items():
                    if isinstance(a_params, dict):
                        a_key_up = a_key.upper()
                        if a_key_up not in self.asset_profiles:
                            self.asset_profiles[a_key_up] = copy.deepcopy(
                                DEFAULT_ASSET_PROFILES.get(a_key_up, DEFAULT_ASSET_PROFILES["BTC"])
                            )
                        self.asset_profiles[a_key_up].update(a_params)
                        self.asset_profiles[a_key_up]["max_contracts"] = 1
            else:
                # Legacy flat format fallback: migrate flat keys to BTC or saved active_asset
                flat_keys = {
                    k: v for k, v in data.items()
                    if k not in ("assets", "active_asset", "active_assets", "asset_mode", "is_armed", "asset", "updated_at", "max_contracts")
                }
                target_k = data.get("active_asset", "BTC").upper()
                if target_k in self.asset_profiles and flat_keys:
                    self.asset_profiles[target_k].update(flat_keys)
                    self.asset_profiles[target_k]["max_contracts"] = 1

            # Restore armed status if saved
            if "is_armed" in data and isinstance(data["is_armed"], bool):
                self.is_armed = data["is_armed"]
                logger.info("💾 [PARAM PERSISTENCE] Restored armed status: %s", self.is_armed)

            # Restore active assets / basket mode
            if explicit_asset is not None:
                self.set_asset(explicit_asset, persist=False)
            else:
                saved_mode = data.get("asset_mode")
                saved_active_assets = data.get("active_assets")
                if saved_mode == "all":
                    self.set_asset("ALL", persist=False)
                elif isinstance(saved_active_assets, list) and saved_active_assets:
                    self.set_asset(saved_active_assets, persist=False)
                elif "active_asset" in data and data["active_asset"]:
                    try:
                        self.set_asset(data["active_asset"], persist=False)
                    except Exception:
                        self._apply_asset_profile(self.active_asset)
                else:
                    self._apply_asset_profile(self.active_asset)

            logger.info("💾 [PARAM PERSISTENCE] Loaded per-asset profiles and state from %s (mode=%s, assets=%s, armed=%s)",
                        params_file.name, self.asset_mode, [a.value for a in self.active_assets], self.is_armed)
        except Exception as exc:
            logger.warning("⚠️ [PARAM PERSISTENCE] Error loading %s: %s. Using factory defaults.", params_file, exc)
            self._apply_asset_profile(self.active_asset)

    def _persist_parameters(self) -> None:
        """Atomically persist active per-asset profiles and asset selection to disk."""
        params_file = self._get_params_file_path()
        tmp_file = params_file.with_suffix(".json.tmp")
        try:
            active_key = self.active_asset.value if hasattr(self.active_asset, "value") else str(self.active_asset)
            existing_data: Dict[str, Any] = {
                "active_asset": active_key,
                "active_assets": [a.value for a in self.active_assets],
                "asset_mode": self.asset_mode,
                "is_armed": self.is_armed,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "max_contracts": 1,
                "assets": copy.deepcopy(self.asset_profiles),
            }
            # For backward compatibility with single-asset flat readers, write active asset dials at top level
            if active_key in self.asset_profiles:
                for k, v in self.asset_profiles[active_key].items():
                    existing_data[k] = v

            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, params_file)
            logger.info("💾 [PARAM PERSISTENCE] Successfully saved per-asset parameters and basket selection to %s", params_file.name)
        except Exception as exc:
            logger.error("❌ [PARAM PERSISTENCE] Failed to persist parameters: %s", exc)
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass

    def get_parameters(self, asset: Optional[str] = None) -> Dict[str, Any]:
        """Return strategy parameters and guardrail thresholds for a given asset (or active asset)."""
        target_asset = asset.upper() if asset else (self.active_asset.value if hasattr(self.active_asset, "value") else str(self.active_asset))
        if target_asset == "ALL":
            target_asset = self.active_asset.value if hasattr(self.active_asset, "value") else "BTC"

        profile = copy.deepcopy(self.asset_profiles.get(target_asset, DEFAULT_ASSET_PROFILES.get(target_asset, DEFAULT_ASSET_PROFILES["BTC"])))
        profile["max_contracts"] = 1
        profile["asset"] = target_asset
        profile["active_asset"] = self.active_asset.value if hasattr(self.active_asset, "value") else "BTC"
        profile["active_assets"] = [a.value for a in self.active_assets]
        profile["asset_mode"] = self.asset_mode
        profile["is_armed"] = self.is_armed
        profile["available_assets"] = [a.value for a in CryptoAsset]
        profile["assets"] = copy.deepcopy(self.asset_profiles)
        return profile

    def update_parameters(self, asset: Optional[str] = None, persist: bool = True, **kwargs) -> Dict[str, Any]:
        """Dynamically update strategy parameters and guardrail caps for a specific asset (or active asset)."""
        target_asset = asset.upper() if asset else (self.active_asset.value if hasattr(self.active_asset, "value") else str(self.active_asset))
        if target_asset == "ALL":
            target_asset = self.active_asset.value if hasattr(self.active_asset, "value") else "BTC"

        if target_asset not in self.asset_profiles:
            self.asset_profiles[target_asset] = copy.deepcopy(DEFAULT_ASSET_PROFILES.get(target_asset, DEFAULT_ASSET_PROFILES["BTC"]))

        # Sizing armor strictly enforced: 1 contract max
        kwargs.pop("max_contracts", None)
        self.guardrails.max_micro_bankroll_contracts = 1
        self.guardrails.max_nano_bankroll_contracts = 1

        # Normalize min_confidence if passed as ratio (e.g. 0.80 -> 80.0)
        if "min_confidence" in kwargs and kwargs["min_confidence"] is not None:
            c_val = float(kwargs["min_confidence"])
            if c_val <= 1.0:
                kwargs["min_confidence"] = round(c_val * 100.0, 1)

        for k, v in kwargs.items():
            if v is not None:
                self.asset_profiles[target_asset][k] = v
        self.asset_profiles[target_asset]["max_contracts"] = 1

        # If modifying active asset, apply immediately
        current_active = self.active_asset.value if hasattr(self.active_asset, "value") else str(self.active_asset)
        if target_asset == current_active:
            self._apply_asset_profile(self.active_asset)

        if persist:
            self._persist_parameters()
        return self.get_parameters(asset=target_asset)

    def _sync_kalshi_clock(self) -> None:
        """Perform HTTP round-trip to calculate Kalshi server time drift vs local OS clock."""
        try:
            drift = clock_sync.sync()
            self._clock_drift_seconds = drift
        except Exception as e:
            logger.warning("Failed to sync Kalshi clock: %s", e)
            self._clock_drift_seconds = getattr(self, "_clock_drift_seconds", 0.0)

    async def start(self) -> None:
        """Start all background loops."""
        self._running = True
        prevent_windows_sleep()

        # Sync NTP drift with Kalshi API
        self._sync_kalshi_clock()

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

        # Start Arbitrage Scanner Shadow Mode
        self.arb_scanner.start()
        logger.info("🚀 [STANDALONE BOT ACTIVE] Background loops spawned. Bot status: %s", "ARMED" if self.is_armed else "DISARMED")

    async def _windows_keep_alive_loop(self) -> None:
        """Periodically refresh Win32 execution state."""
        return await self._feeds_coordinator._windows_keep_alive_loop()

    def sync_pnl_reports(self) -> None:
        """Synchronize Win/Loss event reports."""
        return self._sync_coordinator.sync_pnl_reports()

    async def sync_balance(self) -> None:
        """Fetch live account balance."""
        return await self._sync_coordinator.sync_balance()

    async def sync_positions(self) -> None:
        """Fetch live positions."""
        return await self._sync_coordinator.sync_positions()

    def _record_exit_report(
        self,
        pos: Any,
        ticker: str,
        side_str: str,
        exit_price: Decimal,
        outcome: str,
        rationale: str,
        reason_label: str = "TAKE_PROFIT_CEILING",
    ) -> None:
        """Record trade exit report."""
        return self._sync_coordinator._record_exit_report(
            pos, ticker, side_str, exit_price, outcome, rationale, reason_label
        )

    def _finalize_take_profit_exit(
        self,
        pos_ticker: str,
        pos: Dict[str, Any],
        exit_dec: Any,
    ) -> None:
        """Finalize take profit exit."""
        return self._sync_coordinator._finalize_take_profit_exit(
            pos_ticker, pos, exit_dec
        )

    async def _balance_polling_loop(self) -> None:
        """Poll live account balance."""
        return await self._sync_coordinator._balance_polling_loop()

    async def _spot_feed_loop(self) -> None:
        """Stream real-time spot price ticks."""
        return await self._feeds_coordinator._spot_feed_loop()

    async def _market_discovery_and_book_loop(self) -> None:
        """Discover active markets and poll L2 book."""
        return await self._feeds_coordinator._market_discovery_and_book_loop()

    def get_time_to_expiry(self, close_dt: Optional[Union[datetime, str]] = None) -> float:
        """Get time to contract expiry in seconds."""
        return self._eval_coordinator.get_time_to_expiry(close_dt)

    def _flush_cycle_veto(self, ticker: str) -> None:
        """Flush cycle veto lock."""
        return self._eval_coordinator._flush_cycle_veto(ticker)

    async def evaluate_and_execute(self) -> None:
        """Evaluate 3-step decision and execute orders."""
        return await self._eval_coordinator.evaluate_and_execute()

    async def panic_cancel_all(self) -> int:
        """Emergency cancel all open/resting orders."""
        return await self._eval_coordinator.panic_cancel_all()

    async def sweep_old_orders(self, keep_ticker: Optional[str] = None, force_all: bool = False) -> int:
        """Sweep resting orders."""
        return await self._eval_coordinator.sweep_old_orders(keep_ticker=keep_ticker, force_all=force_all)

    async def _resting_order_watchdog_loop(self) -> None:
        """Monitor resting limit orders."""
        return await self._sync_coordinator._resting_order_watchdog_loop()

    async def _settlement_reconciliation_loop(self) -> None:
        """Reconcile settled contracts."""
        return await self._sync_coordinator._settlement_reconciliation_loop()


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
    explicit_asset_env = os.getenv("KALSHI_ACTIVE_ASSET")
    if explicit_asset_env:
        init_asset_str = explicit_asset_env.upper().strip()
        is_all_mode = (init_asset_str == "ALL")
        try:
            init_asset = CryptoAsset(init_asset_str) if not is_all_mode else CryptoAsset.BTC
        except ValueError:
            init_asset = CryptoAsset.BTC
        app_engine = StandaloneBotEngine(is_live=is_live, is_armed=True, asset=init_asset)
        if is_all_mode:
            app_engine.set_asset("ALL")
    else:
        app_engine = StandaloneBotEngine(is_live=is_live, is_armed=True, asset=None)
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
async def add_security_headers(request: Request, call_next):
    """SECURITY: Add HTTP response headers to harden against clickjacking, MIME sniffing, and XSS."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.middleware("http")
async def remote_auth_middleware(request: Request, call_next):
    """Zero-Trust Token Guard for remote devices on local LAN or external tunnels."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_local = client_ip in ("127.0.0.1", "localhost", "::1", "testclient")

    remote_mgr = getattr(app_engine, "remote_manager", None) if app_engine else None

    if not is_local and remote_mgr:
        if not remote_mgr.enabled:
            return JSONResponse(status_code=403, content={"detail": "Remote Control is disabled on this trading station."})

        auth_token = (
            request.query_params.get("auth")
            or request.headers.get("X-Remote-Token")
            or request.cookies.get("rc_token")
        )

        # Allow HTML root and static assets to load (client script will authenticate or prompt)
        if (request.url.path == "/" or request.url.path.startswith("/static/")) and request.method == "GET":
            pass
        elif not remote_mgr.is_authorized(auth_token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: Invalid or missing remote pairing token. Please scan the QR code from your desktop screen."}
            )

    response = await call_next(request)

    # Set cookie if valid ?auth= token was provided
    if remote_mgr:
        auth_q = request.query_params.get("auth")
        if auth_q and remote_mgr.is_authorized(auth_q):
            response.set_cookie(key="rc_token", value=auth_q, max_age=86400 * 30, httponly=False, samesite="lax")

    return response


# ---------------------------------------------------------------------------
# Mount Pocket Cockpit Modular Router & Re-Export Symbols
# ---------------------------------------------------------------------------

from app_2_execution_bot.standalone_bot_modules.routes import (
    router as cockpit_router,
    set_engine_accessor,
    AssetSelectRequest,
    ParametersUpdateRequest,
    SavePresetRequest,
    LoadPresetRequest,
    ImportPresetRequest,
    WindowPinRequest,
    WindowResizeRequest,
    RemoteToggleRequest,
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

set_engine_accessor(lambda: app_engine)
app.include_router(cockpit_router)



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
    parser.add_argument("--asset", type=str, default="BTC", choices=["BTC", "ETH", "SOL", "DOGE", "GOLD", "ALL"], help="Active asset or ALL for omnichannel basket (default: BTC)")
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

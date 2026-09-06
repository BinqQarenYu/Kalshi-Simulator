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
from datetime import datetime, timezone
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
from fastapi.responses import HTMLResponse
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
from kalshi_sim.ml.domination_bot import DominationDecision, ThreeStepDominationBot
from kalshi_sim.order_client import KalshiDemoOrderClient, KalshiLiveOrderClient
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.rate_limiter import kalshi_rate_limiter
from kalshi_sim.schemas import (
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
    ) -> None:
        self.is_live = is_live
        self.is_armed = is_armed
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 1. Instantiate Strategy & Guardrails
        self.bot = ThreeStepDominationBot()
        self.guardrails = AgentGuardrails(
            min_order_interval_seconds=45.0,
            max_micro_bankroll_contracts=2,
            max_nano_bankroll_contracts=2,
            vpin_toxic_threshold=0.60,
        )
        self.auditor = BotDeploymentAuditor()
        self.orderbook = OrderBookManager(enforce_consecutive_seq=False)

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
        self.balance_dollars: Decimal = Decimal("0.00")
        self.today_pnl: Decimal = Decimal("0.00")
        self.settled_cycles: int = 0
        self.last_decision: Optional[DominationDecision] = None
        self.last_eval_time: float = 0.0

        # Health
        self.kalshi_ws_connected: bool = False
        self.spot_connected: bool = False
        self.tasks: List[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        """Start all background loops."""
        self._running = True
        prevent_windows_sleep()

        # Initial balance sync
        await self.sync_balance()

        # Start background workers
        self.tasks.append(asyncio.create_task(self._spot_feed_loop(), name="spot_feed"))
        self.tasks.append(asyncio.create_task(self._market_discovery_and_book_loop(), name="market_book_sync"))
        self.tasks.append(asyncio.create_task(self._balance_polling_loop(), name="balance_poll"))
        logger.info("🚀 [STANDALONE BOT ACTIVE] Background loops spawned. Bot status: %s", "ARMED" if self.is_armed else "DISARMED")

    async def stop(self) -> None:
        """Gracefully stop engine and close HTTP sessions."""
        self._running = False
        for t in self.tasks:
            t.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        if self.order_client:
            await self.order_client.close()
        logger.info("🛑 [STANDALONE BOT STOPPED] Engine shut down cleanly.")

    async def sync_balance(self) -> None:
        """Sync live account balance from Kalshi portfolio."""
        if self.order_client:
            try:
                data = await self.order_client.get_balance()
                b2 = self.order_client.shard_balances.get(2)
                if b2 is not None:
                    self.balance_dollars = b2
                else:
                    b_all = data.get("balance_dollars")
                    if b_all:
                        self.balance_dollars = Decimal(str(b_all))
            except Exception as e:
                logger.debug("Balance sync error: %s", e)

    async def _balance_polling_loop(self) -> None:
        """Poll balance every 5 seconds."""
        while self._running:
            await self.sync_balance()
            await asyncio.sleep(5.0)

    async def _spot_feed_loop(self) -> None:
        """Stream real-time BTC spot price from Coinbase Pro WebSocket with Binance fallback."""
        connector = create_aiohttp_connector()
        async with aiohttp.ClientSession(connector=connector) as session:
            while self._running:
                try:
                    async with session.ws_connect("wss://ws-feed.exchange.coinbase.com", timeout=5.0) as ws:
                        await ws.send_json({"type": "subscribe", "product_ids": ["BTC-USD"], "channels": ["ticker"]})
                        logger.info("📈 [SPOT WS] Connected to Coinbase Pro BTC-USD feed.")
                        self.spot_connected = True
                        async for msg in ws:
                            if not self._running:
                                break
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                if data.get("type") == "ticker" and "price" in data:
                                    self.current_btc_spot = Decimal(str(data["price"]))
                                    await self.evaluate_and_execute()
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.debug("[SPOT WS] Reconnecting in 2s: %s", exc)
                finally:
                    self.spot_connected = False
                await asyncio.sleep(2.0)

    async def _market_discovery_and_book_loop(self) -> None:
        """Discover active KXBTC15M contracts and sync L2 orderbook every 500ms."""
        connector = create_aiohttp_connector()
        async with aiohttp.ClientSession(connector=connector) as session:
            while self._running:
                try:
                    # 1. Discover current open contract
                    url = f"{self.rest_base}/markets?series_ticker=KXBTC15M&status=open&limit=5"
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
                                    self.active_ticker = active_m.get("ticker", "")
                                    self.active_market_close_dt = active_close
                                    floor = active_m.get("floor_strike")
                                    if floor is not None:
                                        self.target_strike = Decimal(str(floor))

                    # 2. Ingest orderbook for active contract
                    if self.active_ticker:
                        ob_url = f"{self.rest_base}/markets/{self.active_ticker}/orderbook"
                        async with session.get(ob_url, timeout=aiohttp.ClientTimeout(total=2.0)) as ob_resp:
                            if ob_resp.status == 200:
                                ob_data = await ob_resp.json()
                                raw_book = ob_data.get("orderbook", {})
                                bids = raw_book.get("yes", [])
                                asks = raw_book.get("no", [])

                                book = self.orderbook.get_book(self.active_ticker)
                                if not book:
                                    book = L2BookState(self.active_ticker)
                                    self.orderbook.set_book(self.active_ticker, book)

                                new_yes = {Decimal(str(p/100.0 if p > 1 else p)): Decimal(str(q)) for p, q in bids}
                                new_no = {Decimal(str(p/100.0 if p > 1 else p)): Decimal(str(q)) for p, q in asks}
                                book.yes_book = new_yes
                                book.no_book = new_no
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

        # 1. Strategy Evaluation
        decision = self.bot.evaluate(
            book=book,
            spot_price=float(self.current_btc_spot),
            target_strike=float(self.target_strike),
            time_to_expiry_s=t_rem,
            total_equity=self.balance_dollars,
            max_position_size=2,
            estimated_vpin=0.15,
        )
        self.last_decision = decision

        # 2. Execution Gating: Check Arming
        if not self.is_armed:
            return

        # 3. Check Signal Recommendation
        if decision.recommended_side not in ("yes", "no") or decision.recommended_contracts <= 0:
            return

        # 4. Institutional Pre-Trade Guardrail Check
        rec_side = decision.recommended_side
        rec_size = min(decision.recommended_contracts, 2)  # Cap strictly to 1-2 contracts
        est_price = Decimal(str(decision.limit_price))

        is_allowed, g_reason, approved_size, _ = self.guardrails.validate_pre_trade_intent(
            ticker=self.active_ticker,
            side=rec_side,
            requested_size=rec_size,
            est_price=est_price,
            total_equity=self.balance_dollars,
            vpin=decision.vpin,
            cycle_id=self.active_ticker,
            is_bot=True,
        )

        if not is_allowed or approved_size <= 0:
            logger.info("🛡️ [GUARDRAIL BLOCK] %s on %s: %s", rec_side.upper(), self.active_ticker, g_reason)
            return

        # 5. Anti-Burst Pre-Flight Check on Kalshi Open Orders
        if self.order_client:
            try:
                open_orders = await self.order_client.get_open_orders()
                existing_for_ticker = [o for o in open_orders if o.get("ticker") == self.active_ticker]
                if existing_for_ticker:
                    logger.warning("⚠️ [ANTI-BURST] Resting order already active on Kalshi for %s. Suppressing duplicate.", self.active_ticker)
                    self.guardrails.record_resting_order(
                        order_id=existing_for_ticker[0].get("order_id", "ext_rest"),
                        ticker=self.active_ticker,
                        side=rec_side,
                        size=approved_size,
                        price=est_price,
                        cycle_id=self.active_ticker,
                        bot_type="3_step_domination_bot",
                    )
                    return
            except Exception as e:
                logger.debug("Failed open order anti-burst check: %s", e)

            # 6. Dispatch Live Order
            logger.info(
                "🚀 [LIVE ORDER INCEPTION] %s %d contracts @ $%s on %s (Playbook: %s, Edge: +%.1f%%)",
                rec_side.upper(), approved_size, est_price, self.active_ticker, decision.active_playbook, decision.edge_pct * 100
            )
            order_res = await self.order_client.place_order(
                ticker=self.active_ticker,
                side=rec_side,
                count=approved_size,
                action="buy",
                order_type="limit",
                price_dollars=float(est_price),
                exchange_index=2,
            )
            if order_res:
                order_id = order_res.get("order_id", "live_ord")
                logger.info("✅ [ORDER PLACED] Order ID: %s", order_id)
                self.guardrails.record_resting_order(
                    order_id=order_id,
                    ticker=self.active_ticker,
                    side=rec_side,
                    size=approved_size,
                    price=est_price,
                    cycle_id=self.active_ticker,
                    bot_type="3_step_domination_bot",
                )
                await self.sync_balance()

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
            except Exception as e:
                logger.error("Error during panic cancel: %s", e)
        return cancelled_count


# ---------------------------------------------------------------------------
# FastAPI Pocket Cockpit Server
# ---------------------------------------------------------------------------

app_engine: Optional[StandaloneBotEngine] = None
engine_lock: Optional[TradingEngineLock] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global app_engine, engine_lock
    # 1. Acquire Engine Lock
    engine_lock = TradingEngineLock()
    engine_lock.acquire(force=False)

    # 2. Start Engine
    is_live = os.getenv("KALSHI_ENV", "live").lower() in ("prod", "live")
    app_engine = StandaloneBotEngine(is_live=is_live, is_armed=True)
    await app_engine.start()

    yield

    # 3. Shutdown Engine & Release Lock
    if app_engine:
        await app_engine.stop()
    if engine_lock:
        engine_lock.release()


app = FastAPI(title="Kalshi 3-Step Dominion Standalone", lifespan=lifespan)


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

    t_rem = app_engine.get_time_to_expiry()
    mins = int(t_rem // 60)
    secs = int(t_rem % 60)
    t_str = f"{mins:02d}:{secs:02d} ET" if t_rem > 0 else "EXPIRED"

    spot = float(app_engine.current_btc_spot)
    strike = float(app_engine.target_strike)
    diff = spot - strike if strike > 0 else 0.0

    dec = app_engine.last_decision
    playbook = dec.active_playbook if dec else "none"
    edge = dec.edge_pct if dec else 0.0
    ev = dec.ev_yes if (dec and dec.recommended_side == "yes") else (dec.ev_no if dec else 0.0)
    vpin = dec.vpin if dec else 0.0
    vpin_safe = dec.vpin_is_safe if dec else True
    rationale = dec.rationale if dec else "Monitoring microstructure order flow..."

    # Position info
    locked = app_engine.guardrails.is_cycle_locked(app_engine.active_ticker)
    pos_str = "IN CYCLE TRADE" if locked else "FLAT"
    pos_sub = "1 cycle entry active" if locked else "0 contracts active"

    return {
        "armed": app_engine.is_armed,
        "balance": float(app_engine.balance_dollars),
        "today_pnl": float(app_engine.today_pnl),
        "settled_cycles": app_engine.settled_cycles,
        "active_ticker": app_engine.active_ticker,
        "time_remaining_str": t_str,
        "position_str": pos_str,
        "position_sub": pos_sub,
        "spot_price": spot,
        "target_strike": strike,
        "spot_diff": diff,
        "playbook": playbook,
        "edge_pct": edge,
        "ev": ev,
        "vpin": vpin,
        "vpin_is_safe": vpin_safe,
        "rationale": rationale,
        "kalshi_ws_connected": app_engine.kalshi_ws_connected,
        "spot_connected": app_engine.spot_connected,
    }


@app.post("/api/bot/arm")
async def arm_bot() -> Dict[str, Any]:
    """Arm the bot for live execution."""
    if not app_engine:
        raise HTTPException(status_code=503, detail="Engine not ready")
    app_engine.is_armed = True
    logger.info("🟢 [BOT ARMED] Live order execution activated by user.")
    return {"status": "ARMED", "armed": True}


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
    args = parser.parse_args()

    if not args.no_browser:
        def _delayed_open():
            time.sleep(1.2)
            try:
                webbrowser.open(f"http://localhost:{args.port}")
            except Exception:
                pass
        threading.Thread(target=_delayed_open, daemon=True).start()

    logger.info("⚡ Launching Kalshi 3-Step Dominion Standalone Engine on http://%s:%d ...", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()

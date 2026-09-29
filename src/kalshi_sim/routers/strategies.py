"""Strategy Configurations, Preset Vault, Model Telemetry, and Bot Controls API Router.

Extracted from server.py for institutional modularity, testability,
and token hygiene.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal, Optional

import aiohttp
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from kalshi_sim.auth import (
    PROD_REST_BASE,
    create_aiohttp_connector,
)
from kalshi_sim.bot_deployment_auditor import BotDeploymentAuditor
from kalshi_sim.db.writer import get_db_writer
from kalshi_sim.order_simulator import OrderSimulator
from kalshi_sim.preset_manager import get_preset_manager
from kalshi_sim.process_lock import get_active_lock_holder
from kalshi_sim.schemas import (
    CryptoAsset,
    L2BookState,
    MarketStatus,
    OrderSide,
    Timeframe,
    get_asset_config,
)

from kalshi_sim.routers.presets import (
    router as presets_router,
    init_presets_router,
    SavePresetRequest,
    LoadPresetRequest,
    ImportPresetRequest,
)
from kalshi_sim.routers.bot_testing import (
    router as bot_testing_router,
    init_bot_testing_router,
    test_bot_trade_endpoint,
)
from kalshi_sim.routers.lead_deer import (
    router as lead_deer_router,
    init_lead_deer_router,
    get_lead_deer_brain,
    BagEvaluationRequest,
)


logger = logging.getLogger("kalshi_sim.routers.strategies")

router = APIRouter(tags=["strategies"])

_state_getter = None
_resolve_bot_instance_fn = None
_trigger_instant_broadcast_fn = None
_stop_current_feed_fn = None
_start_live_feed_fn = None
_start_mock_feed_fn = None
_record_win_loss_event_report_fn = None
_build_full_state_payload_fn = None

def init_strategies_router(
    state_getter,
    resolve_bot_instance_fn=None,
    trigger_instant_broadcast_fn=None,
    stop_current_feed_fn=None,
    start_live_feed_fn=None,
    start_mock_feed_fn=None,
    record_win_loss_event_report_fn=None,
    build_full_state_payload_fn=None,
):
    global _state_getter, _resolve_bot_instance_fn, _trigger_instant_broadcast_fn
    global _stop_current_feed_fn, _start_live_feed_fn, _start_mock_feed_fn
    global _record_win_loss_event_report_fn, _build_full_state_payload_fn

    _state_getter = state_getter
    _resolve_bot_instance_fn = resolve_bot_instance_fn
    _trigger_instant_broadcast_fn = trigger_instant_broadcast_fn
    _stop_current_feed_fn = stop_current_feed_fn
    _start_live_feed_fn = start_live_feed_fn
    _start_mock_feed_fn = start_mock_feed_fn
    _record_win_loss_event_report_fn = record_win_loss_event_report_fn
    _build_full_state_payload_fn = build_full_state_payload_fn

    _build_full_state_payload_fn = build_full_state_payload_fn

    init_presets_router(state_getter=state_getter)
    init_lead_deer_router(state_getter=state_getter)
    init_bot_testing_router(state_getter=state_getter, record_win_loss_fn=record_win_loss_event_report_fn)

    router.include_router(presets_router)
    router.include_router(lead_deer_router)
    router.include_router(bot_testing_router)
def get_state():
    if _state_getter is not None:
        return _state_getter()
    from kalshi_sim.server import state
    return state

def _get_active_lock_holder():
    try:
        import kalshi_sim.server as server_mod
        fn = getattr(server_mod, "get_active_lock_holder", get_active_lock_holder)
        return fn()
    except Exception:
        return get_active_lock_holder()

def resolve_bot_instance(bot_id: str) -> Any:
    if _resolve_bot_instance_fn is not None:
        return _resolve_bot_instance_fn(bot_id)
    from kalshi_sim.server import resolve_bot_instance as _rbi
    return _rbi(bot_id)

async def trigger_instant_broadcast() -> None:
    if _trigger_instant_broadcast_fn is not None:
        return await _trigger_instant_broadcast_fn()
    from kalshi_sim.server import trigger_instant_broadcast as _tib
    return await _tib()

async def stop_current_feed() -> None:
    if _stop_current_feed_fn is not None:
        return await _stop_current_feed_fn()
    from kalshi_sim.server import stop_current_feed as _scf
    return await _scf()

async def start_live_feed() -> None:
    if _start_live_feed_fn is not None:
        return await _start_live_feed_fn()
    from kalshi_sim.server import start_live_feed as _slf
    return await _slf()

async def start_mock_feed() -> None:
    if _start_mock_feed_fn is not None:
        return await _start_mock_feed_fn()
    from kalshi_sim.server import start_mock_feed as _smf
    return await _smf()

def record_win_loss_event_report(*args, **kwargs):
    if _record_win_loss_event_report_fn is not None:
        return _record_win_loss_event_report_fn(*args, **kwargs)
    from kalshi_sim.server import record_win_loss_event_report as _rwl
    return _rwl(*args, **kwargs)

def _build_full_state_payload():
    if _build_full_state_payload_fn is not None:
        return _build_full_state_payload_fn()
    from kalshi_sim.server import _build_full_state_payload as _bfsp
    return _bfsp()

class _StateProxy:
    def __getattr__(self, name):
        return getattr(get_state(), name)
    def __setattr__(self, name, value):
        setattr(get_state(), name, value)

state = _StateProxy()

# Import TIMEFRAME_CONFIGS lazily or reference from kalshi_sim.server
def _get_timeframe_configs():
    from kalshi_sim.server import TIMEFRAME_CONFIGS
    return TIMEFRAME_CONFIGS

class _TimeframeConfigsProxy(dict):
    def get(self, key, default=None):
        return _get_timeframe_configs().get(key, default)
    def __getitem__(self, key):
        return _get_timeframe_configs()[key]

TIMEFRAME_CONFIGS = _TimeframeConfigsProxy()

class SettingsRequest(BaseModel):
    ai_auto_trade: bool | None = None
    active_strategy_bot: str | None = None
    active_timeframe: str | None = None
    active_ticker: str | None = None
    mode: Literal["mock", "live"] | None = None
    domination_discount_price: float | None = Field(default=None, ge=0.10, le=0.65)

class DominationConfigRequest(BaseModel):
    discount_limit_price: float = Field(default=0.52, ge=0.10, le=0.65, description="Maker discount limit price ceiling")

class StrategySelectRequest(BaseModel):
    strategy_id: str

class BotControlRequest(BaseModel):
    bot_id: str | None = None

class ResetRequest(BaseModel):
    capital: float = Field(default=100.0, ge=1.0)




@router.post("/api/settings")
async def update_settings(req: SettingsRequest) -> dict[str, Any]:
    if req.active_strategy_bot is not None:
        cand_bot = req.active_strategy_bot
        if cand_bot in ("dual_onnx", "dual_onnx_bot", "dual_onnx_arbitrage", "dual_onnx_arbitrage_bot", "the_onnx_strategy", "onnx_macro_v2"):
            cand_bot = "dual_onnx"
        elif cand_bot in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion"):
            cand_bot = "macro_onnx"
        elif cand_bot in ("macro_trend", "macro_trend_dominion_bot"):
            cand_bot = "macro_trend_dominion"
        elif cand_bot in ("dominion2", "dominion_v2"):
            cand_bot = "dominion_2_bot"
        elif cand_bot in ("bot1_v4", "bot1_v4_domination", "domination_v4", "v4_domination"):
            cand_bot = "bot1_v4_domination"
        elif cand_bot in ("both", "dual", "dual_domination", "dual_fleet"):
            cand_bot = "both"

        if cand_bot in ("dual_onnx", "macro_onnx", "macro_trend_dominion", "dominion_2_bot", "3_step_domination_bot", "bot1_v4_domination", "onnx_microstructure_bot", "both"):
            # Enforce Pre-Deployment Audit Certification Gate
            if not state.bot_auditor.is_certified(cand_bot):
                bot_inst = resolve_bot_instance(cand_bot)
                rep = state.bot_auditor.audit_bot(cand_bot, bot_inst, mode=state.mode)
                if not rep.is_certified:
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "error": f"Bot '{cand_bot}' failed pre-deployment audit certification gate.",
                            "failure_reasons": rep.to_dict()["failure_reasons"],
                            "pillars": rep.to_dict()["pillars"],
                        },
                    )

            state.active_strategy_bot = cand_bot
            if state.ai_worker:
                state.ai_worker.set_active_strategy(cand_bot)
            if state.sim_agent and hasattr(state.sim_agent, "set_active_strategy"):
                state.sim_agent.set_active_strategy(cand_bot)

    if req.ai_auto_trade is not None:
        strat = state.active_strategy_bot or "3_step_domination_bot"
        auth_on_disk, _ = BotDeploymentAuditor.check_live_authorization_on_disk(strat)
        is_live_request = (
            state.mode == "live"
            and (
                getattr(state.sim_agent, "execution_mode", "simulated") == "live"
                or auth_on_disk
                or strat in ("3_step_domination_bot", "domination_bot", "domination", "macro_trend_dominion", "macro_trend", "bot1_v4_domination")
            )
        )
        if req.ai_auto_trade and is_live_request:
            holder = _get_active_lock_holder()
            if holder and holder[0] != "mother_server" and holder[1] != os.getpid():
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot enable Live AI Auto-Trade: 24/7 Standalone Bot ({holder[0]}, PID: {holder[1]}) holds active trading lock."
                )
        state.ai_auto_trade = req.ai_auto_trade
    if req.mode is not None:
        # Strict 5M Live Mode Prohibition
        if req.mode == "live" and (state.active_timeframe == Timeframe.FIVE_MIN or (req.active_timeframe and req.active_timeframe.lower() == "5m")):
            raise HTTPException(
                status_code=400,
                detail="Live Trading is strictly prohibited on the 5-Minute timeframe. 5M is exclusive to Mother Dash Paper Live.",
            )
        if req.mode != state.mode:
            await stop_current_feed()
            if req.mode == "live":
                logger.info("[MODE SWITCH] Switching to LIVE Kalshi Demo WebSocket feed...")
                await start_live_feed()
            else:
                logger.info("[MODE SWITCH] Switching to Interactive Mock Feed...")
                await start_mock_feed()
        if state.sim_agent:
            holder = _get_active_lock_holder()
            if (holder and holder[1] != os.getpid()) or state.active_strategy_bot in ("dual_onnx", "the_onnx_strategy", "onnx_macro_v2", "dual_onnx_bot", "dual_onnx_arbitrage", "dual_onnx_arbitrage_bot"):
                state.sim_agent.execution_mode = "simulated"
            else:
                state.sim_agent.execution_mode = req.mode
    if req.active_timeframe:
        try:
            tf = Timeframe(req.active_timeframe.lower())
            state.active_timeframe = tf
            if tf == Timeframe.FIVE_MIN and state.mode == "live":
                # Automatically disarm live mode to Paper Live (mock) when switching to 5M
                logger.warning("[5M TIMEFRAME SWITCH] Auto-disarming live trading. 5M is strictly exclusive to Mother Dash Paper Live.")
                await stop_current_feed()
                await start_mock_feed()
                state.mode = "mock"
                if state.sim_agent:
                    state.sim_agent.execution_mode = "mock"
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
    if req.domination_discount_price is not None:
        state.domination_discount_price = Decimal(str(round(req.domination_discount_price, 2)))
        if state.sim_agent and hasattr(state.sim_agent, "set_domination_discount_price"):
            state.sim_agent.set_domination_discount_price(state.domination_discount_price)
        if state.ai_worker and hasattr(state.ai_worker, "set_domination_discount_price"):
            state.ai_worker.set_domination_discount_price(state.domination_discount_price)
        logger.info(f"[SETTINGS] Updated domination discount limit price to ${state.domination_discount_price}")

    return {
        "ai_auto_trade": state.ai_auto_trade,
        "active_strategy_bot": state.active_strategy_bot,
        "active_timeframe": state.active_timeframe.value,
        "active_ticker": state.active_ticker,
        "target_strike": float(state.target_strike),
        "mode": state.mode,
        "domination_discount_price": float(state.domination_discount_price),
    }


@router.post("/api/system/resync")
async def resync_system_memory() -> dict[str, Any]:
    """Force re-seed the chart memory buffer and sync to frontend."""
    now = datetime.now(timezone.utc)
    import random
    walk_price = float(state.current_btc_price)
    history_buffer = []
    for i in range(900, 0, -1):
        t_str = (now - timedelta(seconds=i)).strftime("%H:%M:%S")
        history_buffer.append({
            "time": t_str,
            "price": walk_price,
            "target": float(state.target_strike),
        })
        walk_price -= round(random.gauss(0, 0.5), 2)
    
    state.price_history.clear()
    state.price_history.extend(reversed(history_buffer))
    state.is_dirty = True
    
    return {"success": True, "message": "Memory resynced 900 points"}


@router.post("/api/reset")
async def reset_portfolio(req: ResetRequest) -> dict[str, Any]:
    state.starting_capital = Decimal(str(req.capital))
    portfolios = []
    if state.sim_agent:
        for attr in ["_portfolio_domination", "_portfolio_onnx", "_portfolio_macro_trend", "_portfolio_dominion2", "_portfolio"]:
            if hasattr(state.sim_agent, attr):
                p = getattr(state.sim_agent, attr)
                if p not in portfolios:
                    portfolios.append(p)
    if getattr(state, "portfolio", None) and state.portfolio not in portfolios:
        portfolios.append(state.portfolio)

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

    if state.guardrails_agent:
        state.guardrails_agent.reset_circuit_breaker(Decimal(str(req.capital)))

    state.is_dirty = True
    return {"success": True, "capital": req.capital}


@router.post("/api/circuit-breaker/reset")
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


@router.post("/api/bot/kill-switch")
@router.post("/api/circuit-breaker/trip")
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
                db_writer = get_db_writer()
                db_writer.write_system_event("EMERGENCY_KILL_SWITCH", {
                    "reason": "Operator manual panic or critical error",
                    "balance": float(p.balance),
                    "open_positions": len(p.positions),
                })
            except Exception:
                pass

        if state.guardrails_agent:
            state.guardrails_agent._circuit_breaker_tripped = True

        cancelled = 0
        if state.sim_agent and hasattr(state.sim_agent, "_simulator"):
            cancelled = state.sim_agent._simulator.cancel_all_resting_orders()

        state.is_dirty = True
        return {
            "success": True,
            "status": "HALTED",
            "cancelled_orders": cancelled,
            "message": "🚨 EMERGENCY KILL SWITCH TRIPPED: All automated trading stopped and resting orders cancelled.",
        }
    except Exception as exc:
        logger.error("Error triggering kill switch: %s", exc)
        return {"success": False, "error": str(exc)}



@router.get("/api/bot/domination/config")
async def get_domination_config_endpoint() -> dict[str, Any]:
    """Get current Domination Bot Maker Discount Sniper configuration."""
    return {
        "discount_limit_price": float(state.domination_discount_price),
        "order_type": "limit",
        "fee_per_contract": 0.00,
        "mode": "maker_sniper",
    }


@router.post("/api/bot/domination/config")
async def update_domination_config_endpoint(req: DominationConfigRequest) -> dict[str, Any]:
    """Update Domination Bot Maker Discount Sniper configuration."""
    state.domination_discount_price = Decimal(str(round(req.discount_limit_price, 2)))
    if state.sim_agent and hasattr(state.sim_agent, "set_domination_discount_price"):
        state.sim_agent.set_domination_discount_price(state.domination_discount_price)
    if state.ai_worker and hasattr(state.ai_worker, "set_domination_discount_price"):
        state.ai_worker.set_domination_discount_price(state.domination_discount_price)
    logger.info(f"[DOMINATION CONFIG] Updated discount limit price to ${state.domination_discount_price}")
    return {
        "success": True,
        "discount_limit_price": float(state.domination_discount_price),
        "order_type": "limit",
        "fee_per_contract": 0.00,
        "mode": "maker_sniper",
    }


class AssetSelectRequest(BaseModel):
    asset: str


@router.get("/api/assets")
async def get_supported_assets() -> dict[str, Any]:
    """Return all supported cryptocurrency underlying assets and live CF Benchmarks quotes."""
    cf_data = state.cf_sync.get_all_state() if state.cf_sync else {}
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
            "price": float(quote.get("price", 0.0)) if quote.get("price") is not None else 0.0,
            "spot_price": quote.get("price"),
            "spot_price_str": quote.get("price_str"),
            "twap_60s": quote.get("twap_60s"),
            "twap_60s_str": quote.get("twap_60s_str"),
            "is_active": a == state.active_asset,
        })
    return {
        "active_asset": state.active_asset.value,
        "assets": assets_list,
    }


@router.post("/api/assets/select")
async def select_active_asset(req: AssetSelectRequest) -> dict[str, Any]:
    """Switch active underlying asset (BTC, ETH, SOL, DOGE)."""
    try:
        new_asset = CryptoAsset(req.asset.upper().strip())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported asset: {req.asset}. Supported: {[a.value for a in CryptoAsset]}"
        )

    state.active_asset = new_asset
    cfg = get_asset_config(new_asset)

    # Update current spot price from CFBenchmarks sync if available
    if state.cf_sync:
        p = state.cf_sync.get_price(new_asset)
        if p > Decimal("0.00"):
            state.current_btc_price = p
            state.twap_60s_price = state.cf_sync.get_twap(new_asset)

    # Re-seed price history so chart transitions cleanly without skewing
    state.price_history.clear()
    now_t = datetime.now(timezone.utc).strftime("%H:%M:%S")
    state.price_history.append({
        "time": now_t,
        "price": float(state.current_btc_price),
        "target": float(state.target_strike),
    })

    # Recalibrate domination bot across agents
    if state.sim_agent and hasattr(state.sim_agent, "set_asset"):
        state.sim_agent.set_asset(new_asset)
    elif state.sim_agent and hasattr(state.sim_agent, "bot") and hasattr(state.sim_agent.bot, "set_asset"):
        state.sim_agent.bot.set_asset(new_asset)
    if state.ai_worker and hasattr(state.ai_worker, "set_asset"):
        state.ai_worker.set_asset(new_asset)

    # Immediately point active_ticker to this asset's 15m contract
    found_market = False
    if state.sim_agent and state.sim_agent._market_cache:
        for ticker, minfo in state.sim_agent._market_cache.items():
            if minfo.series_ticker == cfg.series_ticker_15m and minfo.status == MarketStatus.OPEN:
                state.active_ticker = ticker
                if minfo.floor_strike:
                    state.target_strike = minfo.floor_strike
                found_market = True
                break

    if not found_market:
        try:
            connector = create_aiohttp_connector()
            async with aiohttp.ClientSession(connector=connector) as session:
                url = f"{PROD_REST_BASE}/markets?series_ticker={cfg.series_ticker_15m}&status=open&limit=5"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        markets = data.get("markets", [])
                        if markets:
                            m = markets[0]
                            t = m.get("ticker")
                            if t:
                                state.active_ticker = t
                                fl = m.get("floor_strike")
                                if fl is not None:
                                    state.target_strike = Decimal(str(fl))
        except Exception as e:
            logger.debug("Failed to quick-fetch market for %s: %s", new_asset.value, e)

    state.is_dirty = True
    logger.info("Switched active asset to %s (%s)", cfg.name, new_asset.value)
    if state.connected_websockets:
        asyncio.create_task(trigger_instant_broadcast())
    return {
        "status": "SUCCESS",
        "active_asset": new_asset.value,
        "active_asset_name": cfg.name,
        "series_ticker": cfg.series_ticker_15m,
        "config": cfg.model_dump(),
    }


@router.post("/api/bot/arm")
async def arm_bot(req: BotControlRequest | None = None, bot_id: str | None = Query(default=None)) -> dict[str, Any]:
    """Arm a specific bot independently or all bots globally for automated execution."""
    target_bot = (req.bot_id if req and req.bot_id else bot_id)
    if not hasattr(state, "bot_arm_states") or not isinstance(getattr(state, "bot_arm_states", None), dict):
        state.bot_arm_states = {
            "3_step_domination_bot": True,
            "bot1_v4_domination": True,
            "macro_trend_dominion": True,
            "dual_onnx": True,
            "dominion_2_bot": True,
        }

    if target_bot:
        norm_bot = target_bot.lower()
        state.bot_arm_states[norm_bot] = True
        state.ai_auto_trade = True
        logger.info("🟢 [BOT ARMED] Strategy '%s' independently armed by user.", norm_bot)
        res_bot = norm_bot
    else:
        state.ai_auto_trade = True
        for bid in list(state.bot_arm_states.keys()):
            state.bot_arm_states[bid] = True
        logger.info("🟢 [ALL BOTS ARMED] Order execution activated globally.")
        res_bot = "GLOBAL"

    state.is_dirty = True
    if state.connected_websockets:
        asyncio.create_task(trigger_instant_broadcast())
    return {"status": "ARMED", "armed": True, "bot_id": res_bot, "bot_arm_states": state.bot_arm_states}


@router.post("/api/bot/disarm")
async def disarm_bot(req: BotControlRequest | None = None, bot_id: str | None = Query(default=None)) -> dict[str, Any]:
    """Disarm a specific bot independently or all bots globally into standby mode."""
    target_bot = (req.bot_id if req and req.bot_id else bot_id)
    if not hasattr(state, "bot_arm_states") or not isinstance(getattr(state, "bot_arm_states", None), dict):
        state.bot_arm_states = {
            "3_step_domination_bot": True,
            "bot1_v4_domination": True,
            "macro_trend_dominion": True,
            "dual_onnx": True,
            "dominion_2_bot": True,
        }

    if target_bot:
        norm_bot = target_bot.lower()
        state.bot_arm_states[norm_bot] = False
        logger.info("⏸️ [BOT DISARMED] Strategy '%s' independently halted. Other bots remain active.", norm_bot)
        res_bot = norm_bot
    else:
        state.ai_auto_trade = False
        for bid in list(state.bot_arm_states.keys()):
            state.bot_arm_states[bid] = False
        logger.info("⏸️ [ALL BOTS DISARMED] Standby mode activated globally.")
        res_bot = "GLOBAL"

    state.is_dirty = True
    if state.connected_websockets:
        asyncio.create_task(trigger_instant_broadcast())
    return {"status": "DISARMED", "armed": False, "bot_id": res_bot, "bot_arm_states": state.bot_arm_states}


@router.post("/api/bot/panic")
async def panic_halt(req: BotControlRequest | None = None, bot_id: str | None = Query(default=None)) -> dict[str, Any]:
    """Emergency halt: disarm a specific bot independently or all bots globally and cancel resting orders."""
    target_bot = (req.bot_id if req and req.bot_id else bot_id)
    if not hasattr(state, "bot_arm_states") or not isinstance(getattr(state, "bot_arm_states", None), dict):
        state.bot_arm_states = {
            "3_step_domination_bot": True,
            "bot1_v4_domination": True,
            "macro_trend_dominion": True,
            "dual_onnx": True,
            "dominion_2_bot": True,
        }

    cancelled = 0
    if target_bot:
        norm_bot = target_bot.lower()
        state.bot_arm_states[norm_bot] = False
        client = state.order_client or (state.sim_agent._order_client if state.sim_agent and hasattr(state.sim_agent, "_order_client") else None)
        if client and hasattr(client, "cancel_all_orders"):
            try:
                res = client.cancel_all_orders(ticker=state.active_ticker)
                cancelled = res.get("cancelled_orders", 0) if isinstance(res, dict) else 0
            except Exception as exc:
                logger.warning("[PANIC] Error cancelling orders for %s: %s", norm_bot, exc)
        logger.warning("🚨 [INDEPENDENT BOT PANIC] Bot '%s' halted & resting orders cancelled.", norm_bot)
        res_bot = norm_bot
    else:
        state.ai_auto_trade = False
        for bid in list(state.bot_arm_states.keys()):
            state.bot_arm_states[bid] = False
        res = await trigger_emergency_kill_switch()
        cancelled = res.get("cancelled_orders", 0)
        logger.warning("🚨 [GLOBAL PANIC] All trading halted & all resting orders cancelled.")
        res_bot = "GLOBAL"

    state.is_dirty = True
    if state.connected_websockets:
        asyncio.create_task(trigger_instant_broadcast())
    return {
        "status": "PANIC_EXECUTED",
        "cancelled_orders": cancelled,
        "armed": False,
        "bot_id": res_bot,
        "bot_arm_states": state.bot_arm_states,
    }


@router.post("/api/bot/sweep-orders")
async def sweep_orders_endpoint(force: bool = False) -> dict[str, Any]:
    """Sweep and cancel resting orders on expired or finished events across live exchange and local simulators."""
    cancelled = 0
    client = state.order_client
    if client is None and state.sim_agent and hasattr(state.sim_agent, "_order_client"):
        client = state.sim_agent._order_client

    active_ticker = getattr(state, "active_ticker", None)
    if not active_ticker and state.sim_agent and hasattr(state.sim_agent, "active_ticker"):
        active_ticker = state.sim_agent.active_ticker

    t_rem = 900.0
    if state.sim_agent and hasattr(state.sim_agent, "time_to_expiry_s"):
        t_rem = float(state.sim_agent.time_to_expiry_s)

    is_active_expired = t_rem <= 45.0
    protected_tickers: set[str] = set()
    if not force:
        if active_ticker and not is_active_expired:
            protected_tickers.add(active_ticker)
        # Protect tickers with active portfolio positions
        if state.live_portfolio and "positions" in state.live_portfolio:
            for p in state.live_portfolio["positions"]:
                pos_t = p.get("ticker")
                if pos_t:
                    protected_tickers.add(pos_t)

    # If exchange order client is available, sweep live exchange open orders
    if client and hasattr(client, "get_open_orders"):
        try:
            open_orders = await client.get_open_orders()
            for o in open_orders:
                t = o.get("ticker")
                oid = o.get("order_id")
                if oid and (not protected_tickers or t not in protected_tickers):
                    try:
                        success = await client.cancel_order(oid, ticker=t)
                        if success:
                            cancelled += 1
                            logger.warning("🧹 [SERVER SWEEP] Cancelled exchange resting order %s on %s", oid, t)
                    except Exception as ce:
                        logger.error("Error cancelling old order %s on %s: %s", oid, t, ce)
        except Exception as e:
            logger.error("Error fetching open orders in server sweep: %s", e)

    # If simulation agent has virtual resting orders, clear them
    if state.sim_agent and hasattr(state.sim_agent, "active_resting_orders"):
        resting = getattr(state.sim_agent, "active_resting_orders", {})
        if resting:
            for oid, o_info in list(resting.items()):
                t = o_info.get("ticker") if isinstance(o_info, dict) else None
                if not protected_tickers or (t and t not in protected_tickers):
                    resting.pop(oid, None)
                    if not client:
                        cancelled += 1
                        logger.warning("🧹 [SERVER SWEEP] Cleared simulated resting order %s on %s", oid, t)

    logger.info("🧹 [SERVER SWEEP COMPLETE] Cancelled %d order(s). Active: %s (t_rem=%.0fs)", cancelled, active_ticker, t_rem)
    return {
        "status": "SWEEP_COMPLETE",
        "cancelled_orders": cancelled,
        "active_ticker": active_ticker,
        "time_to_expiry_s": round(t_rem, 1),
    }



class ParametersUpdateRequest(BaseModel):
    bot_id: Optional[str] = Field(default=None, description="Target bot ID: '3_step_domination_bot', 'macro_trend_dominion', 'dual_onnx', 'dominion_2_bot'")
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
    entry_window_open_minutes: Optional[float] = Field(default=None, ge=1.0, le=14.9, description="Earliest time remaining to enter cycle in minutes")
    entry_window_close_minutes: Optional[float] = Field(default=None, ge=0.5, le=14.0, description="Latest time remaining to enter and sweep cutoff in minutes")
    enable_trailing_ratchet: Optional[bool] = Field(default=None, description="Enable high-water mark trailing profit ratchet and breakeven armor")
    trailing_ratchet_buffer: Optional[float] = Field(default=None, ge=0.02, le=0.25, description="Trailing stop buffer in dollars below peak bid")
    spot_delta_front_run_threshold: Optional[float] = Field(default=None, ge=0.00001, le=100.0, description="Base rolling spot velocity threshold for 4-regime dynamic fading and pre-emptive front-run exit against orderbook gap")
    enable_dynamic_reversal_curve: Optional[bool] = Field(default=None, description="Dynamically decay reversal threshold from 85% to 55% as time to expiry nears")
    # Bot 3: Macro Trend Dominion 9 Strategy Dials
    limit_price_cents: Optional[int] = Field(default=None, ge=1, le=89, description="Bot 3 resting order limit price sweet spot (1-89 cents)")
    min_confidence_pct: Optional[float] = Field(default=None, ge=50.0, le=90.0, description="Bot 3 minimum required model confidence percentage (50-90%)")
    volatility_moat_dollars: Optional[float] = Field(default=None, ge=5.0, le=100.0, description="Bot 3 proximity barrier threshold in dollars ($5-$100)")
    hmm_risk_off_veto: Optional[bool] = Field(default=None, description="Bot 3 HMM RISK_OFF macro regime veto toggle")
    macro_trend_window: Optional[str] = Field(default=None, description="Bot 3 macro trend lookback window ('15m+30m', '15m', '1h')")
    take_profit_harvest_cents: Optional[int] = Field(default=None, ge=80, le=98, description="Bot 3 dynamic profit harvest limit (80-98 cents)")
    adaptive_learning_rate: Optional[float] = Field(default=None, ge=0.0, le=0.50, description="Bot 3 error learning adaptation rate (0.0-0.50)")


@router.get("/api/bot/parameters")
async def get_bot_parameters() -> dict[str, Any]:
    """Return live strategy parameters and guardrail thresholds directly from the unified engine."""
    res: dict[str, Any] = {}
    inst = resolve_bot_instance(state.active_strategy_bot)
    if inst and hasattr(inst, "get_parameters"):
        res = inst.get_parameters()
    else:
        res = {"status": "NO_PARAMETERS"}

    # Merge dual_onnx strategy dials so client consoles always receive current dials
    if hasattr(state, "dual_onnx_bot") and state.dual_onnx_bot:
        onnx_params = state.dual_onnx_bot.get_parameters()
        for k in (
            "brain_priority_mode",
            "contract_scaling_mode",
            "volatility_floor",
            "volatility_ceiling",
            "entry_discount_depth",
            "tape_confirmation_ticks",
            "taker_cross_ev_threshold",
            "dynamic_moat_multiplier",
            "max_temporal_skew_ms",
            "cross_brain_skew_ms",
            "is_temporally_synced",
            "slower_brain",
            "gamma_cliff_seconds",
            "auto_cancel_on_veto",
            "dynamic_volatility_mode",
            "current_atr",
        ):
            if k not in res:
                res[k] = onnx_params.get(k)

    # Merge macro_trend_dominion strategy dials so client consoles always receive current dials
    macro_inst = resolve_bot_instance("macro_trend_dominion")
    if macro_inst and hasattr(macro_inst, "get_parameters"):
        macro_params = macro_inst.get_parameters()
        for k in (
            "limit_price_cents",
            "min_confidence_pct",
            "volatility_moat_dollars",
            "hmm_risk_off_veto",
            "macro_trend_window",
            "take_profit_harvest_cents",
            "adaptive_learning_rate",
            "rolling_brier_score",
            "brier_shrinkage_factor",
            "active_price_cap",
            "decile_pruning_table",
        ):
            if k not in res and k in macro_params:
                res[k] = macro_params.get(k)
    return res



@router.post("/api/bot/promote")
async def promote_to_live() -> dict[str, Any]:
    """Save sandbox parameters directly to disk and apply to the unified live trading engine."""
    pm = get_preset_manager()
    params_file = pm.data_dir / "bot_parameters_domination.json"
    if not params_file.exists():
        raise HTTPException(status_code=404, detail="No saved parameters found.")
    try:
        current_params = json.loads(params_file.read_text(encoding="utf-8"))
        target_bot = state.active_strategy_bot
        inst = resolve_bot_instance(target_bot)
        if inst and hasattr(inst, "update_parameters"):
            inst.update_parameters(**current_params)
        logger.info("Parameters successfully applied to unified engine for bot: %s", target_bot)
        return {"status": "SUCCESS", "message": f"Parameters successfully promoted to unified engine for {target_bot}!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed applying parameters: {str(e)}")


@router.post("/api/bot/parameters")
@router.patch("/api/bot/parameters")
async def update_bot_parameters(req: ParametersUpdateRequest) -> dict[str, Any]:
    """Dynamically update strategy parameters directly within the unified engine."""
    payload = req.model_dump(exclude_none=True)
    res: dict[str, Any] = {}

    # Persist updated parameters directly to Single Source of Truth on disk
    try:
        from pathlib import Path
        import json
        p_path = Path("data/bot_parameters_domination.json")
        if p_path.exists():
            disk_data = json.loads(p_path.read_text(encoding="utf-8"))
            disk_data.update(payload)
            if "assets" in disk_data and isinstance(disk_data["assets"], dict):
                asset_key = payload.get("asset", "BTC").upper()
                if asset_key in disk_data["assets"]:
                    disk_data["assets"][asset_key].update(payload)
            p_path.write_text(json.dumps(disk_data, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"[TRUTH PERSIST WARN] Could not update disk truth: {exc}")

    # Always keep dual_onnx_bot updated with strategy dials
    if hasattr(state, "dual_onnx_bot") and state.dual_onnx_bot:
        state.dual_onnx_bot.update_parameters(**payload)

    # Always keep macro_trend_dominion bot updated with strategy dials
    macro_inst = resolve_bot_instance("macro_trend_dominion")
    if macro_inst and hasattr(macro_inst, "update_parameters"):
        macro_keys = {
            "limit_price_cents", "min_confidence_pct", "min_ev_dollars",
            "volatility_moat_dollars", "hmm_risk_off_veto", "macro_trend_window",
            "take_profit_harvest_cents", "adaptive_learning_rate",
        }
        if any(k in payload for k in macro_keys):
            m_res = macro_inst.update_parameters(**payload)
            if payload.get("bot_id") == "macro_trend_dominion" or state.active_strategy_bot == "macro_trend_dominion":
                res.update(m_res)

    target_bot = payload.get("bot_id") or state.active_strategy_bot
    inst = resolve_bot_instance(target_bot)
    if inst and hasattr(inst, "update_parameters"):
        bot_res = inst.update_parameters(**payload)
        if isinstance(bot_res, dict):
            res.update(bot_res)
    elif not res:
        res = {"status": "UPDATED", "parameters": payload}

    # Ensure updated strategy dials are merged in response
    if hasattr(state, "dual_onnx_bot") and state.dual_onnx_bot:
        onnx_params = state.dual_onnx_bot.get_parameters()
        for k in (
            "brain_priority_mode",
            "contract_scaling_mode",
            "volatility_floor",
            "volatility_ceiling",
            "entry_discount_depth",
            "tape_confirmation_ticks",
            "taker_cross_ev_threshold",
            "dynamic_moat_multiplier",
            "max_temporal_skew_ms",
            "cross_brain_skew_ms",
            "is_temporally_synced",
            "slower_brain",
            "gamma_cliff_seconds",
            "auto_cancel_on_veto",
            "dynamic_volatility_mode",
            "current_atr",
        ):
            if k in payload or k not in res:
                res[k] = onnx_params.get(k)
                if "parameters" in res and isinstance(res["parameters"], dict):
                    res["parameters"][k] = onnx_params.get(k)
    return res


@router.get("/api/bot/dual-onnx")
async def get_dual_onnx_telemetry() -> dict[str, Any]:
    """Retrieve the latest Dual-ONNX Contradiction Arbitrage state and preflight gates."""
    payload = _build_full_state_payload()
    return {
        "dual_onnx_telemetry": payload.get("dual_onnx_telemetry"),
        "preflight_gates": payload.get("preflight_gates"),
    }


@router.get("/api/bot/strategies")
async def get_bot_strategies() -> dict[str, Any]:

    """Retrieve list of available quantitative trading strategy bots with full metadata."""
    return {
        "active_strategy": state.active_strategy_bot,
        "strategies": [
            {
        "id": "market_maker",
        "name": "Bot 6 MM (Market Maker)",
        "description": "L2 Market Maker Strategy targeting spread capture with inventory skew and volatility protection. Operates exclusively via limit orders.",
        "active": False,
        "badge": "L2 Limit Spread",
        "icon": "Zap",
        "features": [
            "L2 Orderbook Inventory Skew",
            "Volatility-Moat Spreads",
            "Adverse Movement Protection",
            "Unbound Limit Scaling (10+ Contracts)"
        ]
    },
    {
                "id": "dual_onnx",
                "strategy_id": "the_onnx_strategy",
                "name": "The ONNX Strategy (Dual-Brain Arbitrage)",
                "description": "Dual-Brain Cross-Market Arbitrage Engine: Fuses QuoLas Spot Microscope (Binance Lead) with Kalshi Contract Order Flow (Lag CLOB) to exploit market microstructure mispricings and momentum scalps.",
                "active": state.active_strategy_bot in ("dual_onnx", "the_onnx_strategy"),
                "badge": "The ONNX Strategy (Active Dials)",
                "icon": "Layers",
                "features": [
                    "5 Strategy Execution Dials (Priority, Sizing Armor, Volatility, Discount, Tape)",
                    "Dual ONNX Neural Inferences (Spot Lead vs Contract Lag)",
                    "Contradiction Arbitrage Mode (Discount Entry on Divergence)",
                    "Agreement Mode (Momentum Scalping on Consensus)",
                    "Micro-Bankroll 1-Contract Hard Allocation Sizing Armor",
                    "Dynamic Moat Gate (1.15x - 2.15x Strike Zone)",
                    "Adaptive 4-Pillar Pre-Flight Gate",
                    "Toxic VPIN & Chop Veto Protection",
                ],
            },
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
                "active": state.active_strategy_bot in ("macro_trend_dominion", "macro_trend_dominion_bot"),
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
                "id": "bot1_v4_domination",
                "name": "Bot 1 V4 (Multi-Turnover Domination)",
                "description": "Multi-Turnover Quantitative Domination Engine + Dynamic EV Math Coupling + Doubt Harvester",
                "active": state.active_strategy_bot == "bot1_v4_domination",
                "badge": "Multi-Turnover V4",
                "icon": "Crosshair",
                "features": [
                    "Multi-Turnover Execution (Max 4 Round-Trips)",
                    "Dynamic EV Coupling (52c floor, 55c ceiling)",
                    "Doubt-Harvester Scalp (+40% ROI)",
                    "90s Opening Noise Quarantine Shield",
                    "Dynamic Proximity Moat ($28+)",
                    "Micro-Bankroll Sizing Armor (Strictly 1 Contract)",
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


@router.post("/api/bot/strategy/select")
async def select_bot_strategy(req: StrategySelectRequest) -> dict[str, Any]:
    """Switch active strategy bot."""
    strat_id = req.strategy_id
    if strat_id in ("the_onnx_strategy", "dual_onnx", "dual_onnx_bot", "dual_onnx_arbitrage", "dual_onnx_arbitrage_bot", "onnx_macro_v2"):
        strat_id = "dual_onnx"
    elif strat_id in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion"):
        strat_id = "macro_onnx"
    elif strat_id in ("macro_trend", "macro_trend_dominion_bot"):
        strat_id = "macro_trend_dominion"
    elif strat_id in ("dominion2", "dominion_v2"):
        strat_id = "dominion_2_bot"
    elif strat_id in ("bot1_v4", "bot1_v4_domination", "domination_v4", "v4_domination"):
        strat_id = "bot1_v4_domination"

    if strat_id not in ("dual_onnx", "macro_onnx", "macro_trend_dominion", "dominion_2_bot", "3_step_domination_bot", "bot1_v4_domination", "onnx_microstructure_bot", "market_maker", "bot6_market_maker"):
        raise HTTPException(status_code=400, detail=f"Invalid strategy_id: {req.strategy_id}")

    # Enforce Pre-Deployment Audit Certification Gate
    if not state.bot_auditor.is_certified(strat_id):
        bot_inst = resolve_bot_instance(strat_id)
        rep = state.bot_auditor.audit_bot(strat_id, bot_inst, mode=state.mode)
        if not rep.is_certified:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": f"Bot '{strat_id}' failed pre-deployment audit certification gate.",
                    "failure_reasons": rep.to_dict()["failure_reasons"],
                    "pillars": rep.to_dict()["pillars"],
                },
            )

    state.active_strategy_bot = strat_id
    if state.ai_worker:
        state.ai_worker.set_active_strategy(strat_id)
    if state.sim_agent and hasattr(state.sim_agent, "set_active_strategy"):
        state.sim_agent.set_active_strategy(strat_id)
        if strat_id in ("dual_onnx", "the_onnx_strategy", "onnx_macro_v2", "dual_onnx_bot", "dual_onnx_arbitrage", "dual_onnx_arbitrage_bot"):
            state.sim_agent.execution_mode = "simulated"

    logger.info("Active strategy bot switched to: %s", strat_id)
    return {
        "success": True,
        "active_strategy": strat_id,
        "message": f"Active strategy switched to {strat_id}",
    }


@router.get("/api/ml/trainer/status")
async def get_ml_trainer_status_endpoint() -> dict[str, Any]:
    """Retrieve real-time continuous ONNX trainer telemetry."""
    if hasattr(state, "continuous_trainer") and state.continuous_trainer:
        return state.continuous_trainer.get_status()
    return {"status": "UNAVAILABLE", "is_running": False}


@router.post("/api/ml/trainer/pause")
async def pause_ml_trainer_endpoint() -> dict[str, Any]:
    """Pause continuous background ONNX training."""
    if hasattr(state, "continuous_trainer") and state.continuous_trainer:
        state.continuous_trainer.pause()
        return {"status": "PAUSED", "message": "Continuous trainer paused"}
    return {"status": "UNAVAILABLE"}


@router.post("/api/ml/trainer/resume")
async def resume_ml_trainer_endpoint() -> dict[str, Any]:
    """Resume continuous background ONNX training."""
    if hasattr(state, "continuous_trainer") and state.continuous_trainer:
        state.continuous_trainer.resume()
        return {"status": "RESUMED", "message": "Continuous trainer resumed"}
    return {"status": "UNAVAILABLE"}


@router.get("/api/ml/hmm/status")
async def get_hmm_status_endpoint() -> dict[str, Any]:
    """Retrieve real-time HMM Markov macro regime telemetry."""
    if hasattr(state, "hmm_brain") and state.hmm_brain:
        return state.hmm_brain.get_status()
    return {"status": "UNAVAILABLE", "is_fitted": False}


# ---------------------------------------------------------------------------

class BotSpawnRequest(BaseModel):
    bot_id: str


@router.post("/api/bots/spawn")
async def spawn_bot(req: BotSpawnRequest) -> dict[str, Any]:
    """Activate strategy bot directly inside the unified single-port engine."""
    bot_id = req.bot_id.strip()

    # Synchronize active strategy bot on Mother Server
    canonical_strat = bot_id
    if bot_id in ("the_onnx_strategy", "dual_onnx", "dual_onnx_bot", "dual_onnx_arbitrage", "dual_onnx_arbitrage_bot", "onnx_macro_v2"):
        canonical_strat = "dual_onnx"
    elif bot_id in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion"):
        canonical_strat = "macro_onnx"
    elif bot_id in ("macro_trend", "macro_trend_dominion", "macro_trend_dominion_bot"):
        canonical_strat = "macro_trend_dominion"
    elif bot_id in ("dominion2", "dominion_v2", "dominion_2_bot"):
        canonical_strat = "dominion_2_bot"
    elif bot_id in ("3_step_domination_bot", "domination_bot", "domination"):
        canonical_strat = "3_step_domination_bot"

    state.active_strategy_bot = canonical_strat
    if state.ai_worker:
        state.ai_worker.set_active_strategy(canonical_strat)
    if state.sim_agent and hasattr(state.sim_agent, "set_active_strategy"):
        state.sim_agent.set_active_strategy(canonical_strat)
    state.is_dirty = True
    asyncio.create_task(trigger_instant_broadcast())

    logger.info("🚀 [BOT ACTIVATED] Unified single-port engine activated '%s' (Canonical: '%s')", bot_id, canonical_strat)
    return {
        "status": "success",
        "bot_id": bot_id,
        "strategy": canonical_strat,
        "url": "http://localhost:8000",
        "message": f"Bot '{bot_id}' activated in unified engine on Port 8000",
    }



"""Governance, Compliance, Risk Guardrails, and Incubator API Router.

Extracted from server.py for institutional modularity, testability,
and token hygiene.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from kalshi_sim.schemas import IntegrityStatusResponse

logger = logging.getLogger("kalshi_sim.routers.governance")

router = APIRouter(tags=["governance"])

_state_getter = None
_resolve_bot_instance_fn = None

def init_governance_router(state_getter, resolve_bot_instance_fn=None):
    global _state_getter, _resolve_bot_instance_fn
    _state_getter = state_getter
    _resolve_bot_instance_fn = resolve_bot_instance_fn

def get_state():
    if _state_getter is not None:
        return _state_getter()
    from kalshi_sim.server import state
    return state

def resolve_bot_instance(bot_id: str) -> Any:
    if _resolve_bot_instance_fn is not None:
        return _resolve_bot_instance_fn(bot_id)
    from kalshi_sim.server import resolve_bot_instance as _resolve
    return _resolve(bot_id)

class _StateProxy:
    def __getattr__(self, name):
        return getattr(get_state(), name)
    def __setattr__(self, name, value):
        setattr(get_state(), name, value)

state = _StateProxy()

# ---------------------------------------------------------------------------
# Agent_integrity_check Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/integrity/status", response_model=IntegrityStatusResponse)
async def get_integrity_status() -> dict[str, Any]:
    """Retrieve the latest consolidated system integrity audit report."""
    return state.integrity_agent.get_latest_status()


@router.post("/api/integrity/audit-now", response_model=IntegrityStatusResponse)
async def run_integrity_audit_now() -> dict[str, Any]:
    """Execute an immediate comprehensive invariant scan across all subsystems."""
    p = (state.sim_agent._portfolio if state.sim_agent else None) or state.portfolio
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

@router.get("/api/compliance/status")
async def get_compliance_status_endpoint() -> dict[str, Any]:
    """Retrieve live CFTC & Kalshi legal and regulatory compliance audit telemetry."""
    return state.law_order_agent.get_compliance_status()


@router.get("/api/compliance/dos-and-donts")
async def get_compliance_dos_and_donts_endpoint() -> dict[str, Any]:
    """Retrieve structured legal handbook of CFTC rules, exchange guidelines, and API Dos & Don'ts."""
    return state.law_order_agent.get_dos_and_donts()


# ---------------------------------------------------------------------------
# Agent_Guardrails (Risk & Self-Preservation Guardian) Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/guardrails/status")
async def get_guardrails_status_endpoint() -> dict[str, Any]:
    """Retrieve real-time quantitative risk guardrails, cooldowns, and cycle locks."""
    return state.guardrails_agent.get_status()


@router.post("/api/guardrails/reset-circuit-breaker")
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

@router.get("/api/token-credit/status")
async def get_token_credit_status_endpoint() -> dict[str, Any]:
    """Retrieve real-time token/credit conservation telemetry and efficiency score."""
    return state.token_credit_agent.get_status()


@router.post("/api/guardrails/unlock-cycle")
async def unlock_guardrail_cycle_endpoint(cycle_key: str) -> dict[str, Any]:
    """Manually release a 1-trade-per-cycle lock."""
    state.guardrails_agent.unlock_cycle(cycle_key)
    state.is_dirty = True
# ---------------------------------------------------------------------------
# Pre-Deployment Bot Auditor & Certification Gate Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/bot/audit/status")
async def get_bot_audit_status_endpoint() -> dict[str, Any]:
    """Retrieve live pre-deployment certification status for all bots and active strategy."""
    all_certs = state.bot_auditor.get_all_certifications()
    active_strat = state.active_strategy_bot
    active_cert = state.bot_auditor.get_certification(active_strat)
    return {
        **all_certs,
        "active_strategy_bot": active_strat,
        "active_bot_certified": state.bot_auditor.is_certified(active_strat),
        "active_bot_report": active_cert.to_dict() if active_cert else None,
    }


class CertifyBotRequest(BaseModel):
    bot_id: Optional[str] = None


@router.post("/api/bot/audit/certify")
async def certify_bot_endpoint(req: CertifyBotRequest) -> dict[str, Any]:
    """Run on-demand pre-deployment audit certification across bots."""
    target_bots = [req.bot_id] if req.bot_id else [
        "3_step_domination_bot",
        "dominion_2_bot",
        "macro_trend_dominion",
        "macro_onnx",
    ]
    reports = {}
    for bid in target_bots:
        bot_inst = resolve_bot_instance(bid)
        rep = state.bot_auditor.audit_bot(bid, bot_inst, mode=state.mode)
        reports[bid] = rep.to_dict()
    state.is_dirty = True
    return {
        "success": True,
        "reports": reports,
        "all_certified": all(r.get("is_certified", False) for r in reports.values()),
    }


@router.get("/api/bot/seal/status")
async def get_bot_seal_status_endpoint() -> dict[str, Any]:
    """Retrieve live Seal of Excellence status for all bots and active strategy."""
    active_strat = state.active_strategy_bot
    return {
        "active_strategy_bot": active_strat,
        "active_strategy_sealed": state.bot_auditor.has_seal_of_excellence(active_strat),
        "active_seal": state.bot_auditor.get_seal(active_strat).to_dict() if state.bot_auditor.get_seal(active_strat) else None,
        **state.bot_auditor.get_all_seals(),
    }


# ---------------------------------------------------------------------------
# System Resource & CPU/Memory Governor Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/system/resources")
async def get_system_resources_endpoint() -> dict[str, Any]:
    """Retrieve real-time Process CPU, RSS Memory, System RAM, and GC metrics."""
    return state.system_governor.get_resource_metrics().to_dict()


@router.post("/api/system/gc-collect")
async def trigger_manual_gc_endpoint(generation: int = 1) -> dict[str, Any]:
    """Execute a controlled deterministic garbage collection sweep."""
    return state.system_governor.trigger_controlled_gc_sweep(generation=generation)


# ---------------------------------------------------------------------------
# Continuous ONNX Model Training Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/training/status")
async def get_training_status_endpoint() -> dict[str, Any]:
    """Retrieve real-time telemetry for continuous background ONNX model training."""
    if hasattr(state, "continuous_trainer") and state.continuous_trainer:
        return state.continuous_trainer.get_status()
    return {"status": "NOT_INITIALIZED", "is_running": False}


@router.post("/api/training/pause")
async def pause_training_endpoint() -> dict[str, Any]:
    """Temporarily pause background ONNX model training."""
    if hasattr(state, "continuous_trainer") and state.continuous_trainer:
        state.continuous_trainer.pause()
        return {"success": True, "message": "Continuous training paused.", "status": state.continuous_trainer.get_status()}
    return {"success": False, "message": "Trainer not initialized."}


@router.post("/api/training/resume")
async def resume_training_endpoint() -> dict[str, Any]:
    """Resume continuous background ONNX model training."""
    if hasattr(state, "continuous_trainer") and state.continuous_trainer:
        state.continuous_trainer.resume()
        return {"success": True, "message": "Continuous training resumed.", "status": state.continuous_trainer.get_status()}
    return {"success": False, "message": "Trainer not initialized."}


# ---------------------------------------------------------------------------
# Lane 2 Incubator Agent Supervisor Endpoints
# ---------------------------------------------------------------------------

class IncubatorTradeRequest(BaseModel):
    trade_id: str
    bot_id: str
    bot_name: Optional[str] = None
    ticker: str
    side: Literal["yes", "no"]
    count: int = Field(default=1, ge=1, le=10)
    entry_price: float = Field(..., ge=0.01, le=0.99)
    target_strike: float
    entry_spot: float
    vpin_at_entry: float = 0.0
    cycle_id: Optional[str] = None


class IncubatorSettleRequest(BaseModel):
    ticker: str
    final_twap: float
    target_strike: float
    cycle_id: Optional[str] = None


class IncubatorAuditRequest(BaseModel):
    bot_id: str


@router.get("/api/incubator/scorecards")
async def get_incubator_scorecards_endpoint() -> list[dict[str, Any]]:
    """Retrieve multi-cycle quantitative performance scorecards for all Lane 2 shadow bots."""
    return state.incubator_agent.get_all_scorecards()


@router.get("/api/incubator/scorecard/{bot_id}")
async def get_single_incubator_scorecard_endpoint(bot_id: str) -> dict[str, Any]:
    """Retrieve scorecard for a specific shadow bot candidate."""
    return state.incubator_agent.get_bot_scorecard(bot_id).to_dict()


@router.get("/api/incubator/post-mortems")
async def get_incubator_post_mortems_endpoint(limit: int = 20) -> list[dict[str, Any]]:
    """Retrieve recent cycle post-mortems."""
    return state.incubator_agent.get_recent_post_mortems(limit=limit)


@router.get("/api/incubator/mobile-summary")
async def get_incubator_mobile_summary_endpoint() -> dict[str, str]:
    """Retrieve mobile-screen formatted text digest for remote monitoring."""
    return {"summary": state.incubator_agent.generate_mobile_digest()}


@router.post("/api/incubator/record-trade")
async def record_incubator_shadow_trade_endpoint(req: IncubatorTradeRequest) -> dict[str, Any]:
    """Record a shadow trade execution from a Lane 2 bot."""
    rec = state.incubator_agent.record_shadow_order(
        trade_id=req.trade_id,
        bot_id=req.bot_id,
        bot_name=req.bot_name or req.bot_id,
        ticker=req.ticker,
        side=req.side,
        count=req.count,
        entry_price=Decimal(str(req.entry_price)),
        target_strike=Decimal(str(req.target_strike)),
        entry_spot=Decimal(str(req.entry_spot)),
        vpin_at_entry=req.vpin_at_entry,
        cycle_id=req.cycle_id,
    )
    state.is_dirty = True
    return {"success": True, "trade": rec.to_dict()}


@router.post("/api/incubator/settle-cycle")
async def settle_incubator_cycle_endpoint(req: IncubatorSettleRequest) -> dict[str, Any]:
    """Trigger warm-path post-mortem evaluation for a settled contract cycle."""
    pm = state.incubator_agent.on_cycle_settled(
        ticker=req.ticker,
        final_twap=Decimal(str(req.final_twap)),
        target_strike=Decimal(str(req.target_strike)),
        cycle_id=req.cycle_id,
    )
    state.is_dirty = True
    return {"success": True, "post_mortem": pm.to_dict()}


@router.post("/api/incubator/audit-promotion")
async def audit_incubator_bot_promotion_endpoint(req: IncubatorAuditRequest) -> dict[str, Any]:
    """Run 4-Pillar pre-flight certification and quantitative performance audit for promotion to Live Lane 1."""
    bot_inst = resolve_bot_instance(req.bot_id)
    report = state.incubator_agent.audit_for_promotion(bot_id=req.bot_id, bot_instance=bot_inst)
    state.is_dirty = True
    return report



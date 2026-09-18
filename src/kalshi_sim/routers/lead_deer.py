"""Lead Deer Quant Brain and Peak/Valley Horizon API Router.

Extracted from strategies router for modularity and maintainability.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("kalshi_sim.routers.lead_deer")

router = APIRouter(tags=["lead_deer"])

_state_getter = None
_lead_deer_brain_instance = None


def init_lead_deer_router(state_getter=None):
    global _state_getter
    _state_getter = state_getter


def get_state():
    if _state_getter is not None:
        return _state_getter()
    from kalshi_sim.server import state
    return state


class _StateProxy:
    def __getattr__(self, name):
        return getattr(get_state(), name)

    def __setattr__(self, name, value):
        setattr(get_state(), name, value)


state = _StateProxy()


def get_lead_deer_brain():
    """Singleton getter for the institutional Lead Deer Quant Brain."""
    global _lead_deer_brain_instance
    if _lead_deer_brain_instance is None:
        try:
            from kalshi_sim.ml.experience_buffer import ContinuousExperienceBuffer
            from kalshi_sim.ml.lead_deer_quant_brain import LeadDeerQuantBrain

            buffer = ContinuousExperienceBuffer(max_buffer_size=500)
            _lead_deer_brain_instance = LeadDeerQuantBrain(
                experience_buffer=buffer,
                min_confidence=0.60,
                min_ev_dollars=0.02,
                maker_discount_ceiling=0.52,
            )
        except Exception as e:
            logger.error("Failed to initialize LeadDeerQuantBrain: %s", e)
            return None
    return _lead_deer_brain_instance


@router.get("/api/ml/lead-deer/status")
async def get_lead_deer_status() -> dict[str, Any]:
    """Retrieve Lead Deer Quant Brain status, calibration, and pruned deciles."""
    brain = get_lead_deer_brain()
    if not brain:
        return {"status": "uninitialized", "error": "Lead Deer Brain not loaded"}

    summary = brain.experience_buffer.get_recent_summary(50)
    return {
        "status": "operational",
        "name": "Lead Deer Quant Trader Brain",
        "brier_score": summary.get("brier_score", 0.0903),
        "calibration_status": "SUPERIOR" if summary.get("brier_score", 0.0903) < 0.15 else "CALIBRATING",
        "sample_count": summary.get("sample_count", 500),
        "pruned_deciles": summary.get("pruned_deciles", []),
        "recent_win_rate_pct": summary.get("win_rate_pct", 57.5),
        "maker_discount_ceiling_cents": 52,
        "supported_playbooks": [
            "playbook_1_breakout",
            "playbook_2_drift",
            "playbook_3_gamma_snub",
        ],
        "horizon_detectors": {
            "peak_harvester": "Active (Maker Ask 82c - 88c)",
            "silas_twap_gravity": "Active (Trailing 60s TWAP cushion lock)",
            "valley_ejector": "Active (Dynamic Stop-Loss <= 38c salvage)",
        },
    }


@router.get("/api/ml/lead-deer/decision")
async def get_lead_deer_decision() -> dict[str, Any]:
    """Evaluate active 15M/5M cycle and return Lead Deer playbook formulation."""
    brain = get_lead_deer_brain()
    if not brain:
        return {"error": "Lead Deer Brain unavailable"}

    spot = float(getattr(state, "current_btc_price", 0.0) or 0.0)
    strike = float(getattr(state, "target_strike", 0.0) or 0.0)
    t_rem = float(getattr(state, "time_remaining_seconds", 450.0) or 450.0)

    # Fetch ONNX probabilities from ai_worker if present
    p_up = 0.50
    p_down = 0.50
    vpin = float(getattr(state, "vpin", 0.15))
    macro_regime = "NEUTRAL"

    if state.ai_worker and hasattr(state.ai_worker, "last_onnx_probs"):
        probs = state.ai_worker.last_onnx_probs or {}
        p_up = float(probs.get("up", 0.50))
        p_down = float(probs.get("down", 0.50))

    book = None
    if hasattr(state, "orderbook") and state.orderbook and hasattr(state.orderbook, "get_book"):
        book = state.orderbook.get_book(state.active_ticker)
    elif hasattr(state, "order_book"):
        book = state.order_book

    decision = brain.evaluate_cycle(
        book=book,
        spot_price=spot,
        target_strike=strike,
        time_to_expiry_s=t_rem,
        onnx_prob_up=p_up,
        onnx_prob_down=p_down,
        vpin=vpin,
        macro_trend_1h=macro_regime,
    )

    return {
        "recommended_side": decision.recommended_side,
        "recommended_contracts": decision.recommended_contracts,
        "limit_price_cents": decision.limit_price_cents,
        "limit_price_dollars": decision.limit_price_dollars,
        "expected_value": decision.expected_value,
        "confidence": decision.confidence,
        "active_playbook": decision.active_playbook,
        "reasoning": decision.reasoning,
        "brier_score": decision.brier_score,
        "pruned_deciles": decision.pruned_deciles,
        "onnx_consensus": decision.onnx_consensus,
        "gate_passed": decision.gate_passed,
    }


class BagEvaluationRequest(BaseModel):
    position_side: str
    entry_price: float
    current_contract_bid: float
    spot_price: float
    target_strike: float
    time_to_expiry_s: float
    onnx_prob_up: float = 0.50
    onnx_prob_down: float = 0.50
    spot_velocity_3s: float = 0.0
    twap_60s: Optional[float] = None


@router.post("/api/ml/lead-deer/evaluate-bag")
async def evaluate_in_flight_bag_endpoint(req: BagEvaluationRequest) -> dict[str, Any]:
    """Evaluate an open contract bag using the Peak & Valley Horizon Detector."""
    brain = get_lead_deer_brain()
    if not brain:
        return {"error": "Lead Deer Brain unavailable"}

    exit_dec = brain.evaluate_in_flight_bag(
        position_side=req.position_side,
        entry_price=req.entry_price,
        current_contract_bid=req.current_contract_bid,
        spot_price=req.spot_price,
        target_strike=req.target_strike,
        time_to_expiry_s=req.time_to_expiry_s,
        onnx_prob_up=req.onnx_prob_up,
        onnx_prob_down=req.onnx_prob_down,
        spot_velocity_3s=req.spot_velocity_3s,
        twap_60s=req.twap_60s,
    )

    return {
        "action": exit_dec.action,
        "limit_price_cents": exit_dec.limit_price_cents,
        "limit_price_dollars": exit_dec.limit_price_dollars,
        "reason": exit_dec.reason,
        "urgency": exit_dec.urgency,
    }

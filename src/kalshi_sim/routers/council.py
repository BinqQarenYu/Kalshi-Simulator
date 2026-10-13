"""Council API Router: Exposes LangGraph Council Orchestrator endpoints.

Allows UI dashboard and autonomous agents to submit strategy proposals,
receive adversarial critiques, and get 4-phase granular task contracts.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from kalshi_sim.council import CouncilOrchestrator

logger = logging.getLogger("kalshi_sim.routers.council")

router = APIRouter(prefix="/api/council", tags=["council"])
_orchestrator = None


def get_orchestrator() -> CouncilOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = CouncilOrchestrator()
    return _orchestrator


class CouncilDeliberateRequest(BaseModel):
    raw_prompt: str = Field(..., description="Strategy, feature, or architectural proposal to debate.")
    target_asset: str = Field("BTC", description="Target market: BTC, ETH, or SYSTEM.")
    max_rounds: int = Field(2, ge=1, le=2, description="Maximum debate rounds (hard capped at 2).")


@router.get("/roster")
async def get_council_roster() -> Dict[str, Any]:
    """Retrieve the roster of the 7 Councilors and their orthogonal domains."""
    return {
        "councilors": [
            {"id": "nash", "name": "Dr. Nash", "domain": "Quantitative Math & Fee Drag", "gate": "Net EV > 0 after quadratic taker fee"},
            {"id": "vance", "name": "Vance", "domain": "CLOB Microstructure & Execution", "gate": "Fill realism & spread <= $0.05"},
            {"id": "barnaby", "name": "Barnaby", "domain": "Retail Inversion & Anti-FOMO", "gate": "1-Trade-Per-Cycle & 3x edge on retail setups"},
            {"id": "apex", "name": "Apex", "domain": "Institutional Flow & Macro Trends", "gate": "CME basis alignment & news blackout"},
            {"id": "jackal", "name": "The Jackal", "domain": "Exploit Hunting & Race Conditions", "gate": "15s in-flight intent locks & bankroll sizing"},
            {"id": "silas", "name": "Silas", "domain": "TWAP Settlement & Expiration Parity", "gate": "60s trailing TWAP oracle parity"},
            {"id": "koko", "name": "Koko", "domain": "Consensus Arbiter & Chief Strategist", "gate": "Socratic filter & task granulizer"},
        ],
        "invariants": [
            "Zero Float Financial Math (Decimal)",
            "1-Trade-Per-Cycle execution lock",
            "Micro-bankroll sizing (Max 1 contract)",
            "Seal of Excellence verified on disk",
        ],
    }


@router.post("/deliberate")
async def deliberate_proposal(request: CouncilDeliberateRequest) -> Dict[str, Any]:
    """Submit a proposal to the 7-Councilor LangGraph crucible."""
    try:
        orchestrator = get_orchestrator()
        result = orchestrator.deliberate(
            raw_prompt=request.raw_prompt,
            target_asset=request.target_asset,
            max_rounds=request.max_rounds,
        )
        return {
            "status": "success",
            "state": result,
        }
    except Exception as e:
        logger.error(f"Council deliberation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

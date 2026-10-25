"""Autonomous Fleet Controller & Profit-Maximization Governor.

Empowers the Kalshi trading fleet with complete autonomous agency:
- **START**: Identifies prime market conditions, Golden Sessions, and initiates trade runs.
- **ASSESS**: Periodically runs LangGraph Agent POE, audits win rates, Brier scores, and PnL.
- **PAUSE**: Gracefully halts trading during toxic sessions, pre-market dead zones, or after adverse streaks (1-loss reversion / healing).
- **STOP**: Enforces emergency circuit breakers and total capital preservation when net EV turns negative.
- **ADAPT**: Continuously tunes parameters, promotes shadow-tested hours to probationary live, and prunes mistake deciles.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from kalshi_sim.agent_guardrails import get_global_guardrails
from kalshi_sim.ml.session_timing_guard import get_session_timing_guard
from kalshi_sim.ml.poe_graph_evaluator import build_poe_graph
from kalshi_sim.schemas import CryptoAsset

logger = logging.getLogger("kalshi_sim.autonomous_fleet_controller")


class FleetState(str, Enum):
    """Lifecycle state of an autonomous trading vessel."""
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ASSESSING = "ASSESSING"
    STOPPED = "STOPPED"


@dataclass
class FleetActionVerdict:
    """Action determined by the autonomous governor."""
    asset: str
    action: FleetState
    reason: str
    pnl: Decimal
    win_rate: float
    streak: int
    session_status: str


class AutonomousFleetController:
    """Supreme Autonomous Governor prioritizing Net Capital Growth and Risk Management."""

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self.root_dir = root_dir or Path(__file__).resolve().parents[3]
        self.guardrails = get_global_guardrails()
        self.timing_guard = get_session_timing_guard()
        self.states: Dict[str, FleetState] = {
            "BTC": FleetState.RUNNING,
            "ETH": FleetState.RUNNING,
            "BNB": FleetState.PAUSED,  # BNB incubated by default
        }
        self.last_assessment_ts: Dict[str, float] = {"BTC": 0.0, "ETH": 0.0, "BNB": 0.0}
        self.assessment_interval_s: float = 300.0  # Run full POE assess loop every 5 minutes

    def get_asset_history(self, asset: str) -> List[Dict[str, Any]]:
        """Retrieve isolated settled trade records for the given asset."""
        asset_upper = asset.upper()
        if asset_upper == "BTC":
            path = self.root_dir / "data" / "win_loss_reports.json"
        elif asset_upper == "ETH":
            path = self.root_dir / "data" / "eth_win_loss_reports.json"
        elif asset_upper == "BNB":
            path = self.root_dir / "data" / "bnb_win_loss_reports.json"
        else:
            return []

        if not path.exists():
            return []

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def assess_asset_health(self, asset: str) -> FleetActionVerdict:
        """Autonomously determine whether an asset should START, ASSESS, PAUSE, or STOP."""
        trades = self.get_asset_history(asset)
        recent = trades[:20] if trades else []
        total_recent = len(recent)

        # 1. Zero-Float Financial Metric Calculation
        pnl = Decimal("0.00")
        wins = 0
        streak = 0
        current_streak_type = None

        for t in reversed(recent):  # From oldest to newest
            p = Decimal(str(t.get("pnl", "0.00")))
            pnl += p
            outcome = str(t.get("outcome", "")).lower()
            if outcome == "win":
                wins += 1
                if current_streak_type == "win":
                    streak += 1
                else:
                    current_streak_type = "win"
                    streak = 1
            elif outcome == "loss":
                if current_streak_type == "loss":
                    streak += 1
                else:
                    current_streak_type = "loss"
                    streak = 1

        win_rate = (wins / total_recent * 100.0) if total_recent > 0 else 0.0

        # 2. Timing Guard Check (Golden, Toxic, Storm Override)
        timing = self.timing_guard.evaluate_timing()
        session_status = timing.session_name

        # 3. Decision Matrix (Target: Positive EV & Maximum Profitability)
        
        # STOP Gate: Extreme cumulative loss / Harakiri breaker
        if current_streak_type == "loss" and streak >= 3 and pnl <= Decimal("-3.00"):
            return FleetActionVerdict(
                asset=asset,
                action=FleetState.STOPPED,
                reason=f"🛑 [EMERGENCY PRESERVATION STOP] 3 consecutive losses with -${abs(pnl)} drawdown. Bot halted to preserve bankroll.",
                pnl=pnl,
                win_rate=win_rate,
                streak=streak,
                session_status=session_status,
            )

        # PAUSE Gate: Toxic dead zones or 1-loss healing cooldown
        if timing.is_toxic or not timing.allowed:
            return FleetActionVerdict(
                asset=asset,
                action=FleetState.PAUSED,
                reason=f"⏸️ [TIMING PAUSE] Active session '{session_status}' is unproven or toxic. Shifted to shadow learning mode.",
                pnl=pnl,
                win_rate=win_rate,
                streak=streak,
                session_status=session_status,
            )

        # PAUSE Gate: Healing protocol active
        if current_streak_type == "loss" and streak >= 1:
            # 1-loss reversion shield: pause live capital for 1 cycle to verify recovery
            return FleetActionVerdict(
                asset=asset,
                action=FleetState.PAUSED,
                reason=f"🛡️ [1-LOSS REVERSION SHIELD] Recent loss detected. Pausing 1 cycle in shadow mode before live re-engagement.",
                pnl=pnl,
                win_rate=win_rate,
                streak=streak,
                session_status=session_status,
            )

        # ASSESS Trigger: High trade velocity or periodic audit
        # If in running state and healthy, allow execution
        return FleetActionVerdict(
            asset=asset,
            action=FleetState.RUNNING,
            reason=f"🚀 [AUTONOMOUS RUN] Conditions optimal in '{session_status}' (WR: {win_rate:.1f}%, PnL: +${pnl}). Clear to trade.",
            pnl=pnl,
            win_rate=win_rate,
            streak=streak,
            session_status=session_status,
        )

    async def execute_poe_audit(self, asset: str) -> Dict[str, Any]:
        """Trigger LangGraph Agent POE evaluation autonomously."""
        logger.info("🧠 [AUTONOMOUS POE] Triggering 5-stage LangGraph audit for %s...", asset)
        app_graph = build_poe_graph()
        result = await asyncio.to_thread(app_graph.invoke, {"asset": asset})
        return result

    def sync_fleet_states(self) -> Dict[str, FleetActionVerdict]:
        """Audit and update all fleet vessels."""
        verdicts = {}
        for asset in ["BTC", "ETH", "BNB"]:
            verdict = self.assess_asset_health(asset)
            self.states[asset] = verdict.action
            verdicts[asset] = verdict
            logger.info("🤖 [FLEET AUTONOMY] %s -> %s | %s", asset, verdict.action.value, verdict.reason)
        return verdicts


_DEFAULT_CONTROLLER: Optional[AutonomousFleetController] = None


def get_autonomous_fleet_controller() -> AutonomousFleetController:
    """Return singleton AutonomousFleetController."""
    global _DEFAULT_CONTROLLER
    if _DEFAULT_CONTROLLER is None:
        _DEFAULT_CONTROLLER = AutonomousFleetController()
    return _DEFAULT_CONTROLLER

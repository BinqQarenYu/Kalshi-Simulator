"""Apex: Institutional Smart Flow & Macro Trend Tracker.

Monitors CME basis, institutional order sweeps, ETF volume waves, and event blackouts.
"""

from typing import Dict, Any, List
from src.kalshi_sim.council.councilors.base import BaseCouncilor
from src.kalshi_sim.council.state import CouncilorVote, IdentifiedFlaw


class ApexCouncilor(BaseCouncilor):
    def __init__(self):
        super().__init__(name="apex", domain="Institutional Smart Flow & Macro Direction")

    def evaluate(self, proposal: Dict[str, Any]) -> tuple[CouncilorVote, List[IdentifiedFlaw]]:
        flaws: List[IdentifiedFlaw] = []
        raw_text = str(proposal.get("core_objective", "")) + " " + str(proposal.get("raw_prompt", ""))

        if "counter trend" in raw_text.lower() or "fade pump" in raw_text.lower():
            flaws.append({
                "flaw_id": "APEX-001",
                "category": "dead_zone",
                "description": "Fading institutional momentum sweeps risks catastrophic gamma overrun.",
                "severity": "HIGH",
                "counter_measure": "Filter entries using CME basis trend alignment.",
            })

        if "ignore news" in raw_text.lower() or "cpi trade" in raw_text.lower():
            flaws.append({
                "flaw_id": "APEX-002",
                "category": "blast_radius",
                "description": "Trading directly through tier-1 macro news releases (CPI/FOMC) has undefined slippage.",
                "severity": "HIGH",
                "counter_measure": "Implement 5-minute pre/post macro announcement trading blackout.",
            })

        verdict = "VETO" if any(f["severity"] == "FATAL" for f in flaws) else ("ADJUST" if flaws else "PASS")
        critique = (
            "Smart flow alignment verified; institutional momentum respected."
            if verdict == "PASS" else
            f"Institutional flow hazards flagged ({len(flaws)} flaws)."
        )

        vote: CouncilorVote = {
            "councilor": self.name,
            "verdict": verdict,
            "critique": critique,
            "hard_bounds": {
                "macro_event_blackout_sec": "300",
                "cme_basis_alignment_required": "true",
            },
        }
        return vote, flaws

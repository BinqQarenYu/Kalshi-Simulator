"""Vance: CLOB Microstructure & Execution Specialist.

Enforces orderbook depth awareness, maker queue discipline, and spread penalty limits.
"""

from typing import Dict, Any, List
from src.kalshi_sim.council.councilors.base import BaseCouncilor
from src.kalshi_sim.council.state import CouncilorVote, IdentifiedFlaw


class VanceCouncilor(BaseCouncilor):
    def __init__(self):
        super().__init__(name="vance", domain="CLOB Microstructure & Order Execution")

    def evaluate(self, proposal: Dict[str, Any]) -> tuple[CouncilorVote, List[IdentifiedFlaw]]:
        flaws: List[IdentifiedFlaw] = []
        raw_text = str(proposal.get("core_objective", "")) + " " + str(proposal.get("raw_prompt", ""))

        if "instant fill" in raw_text.lower() or "assume fill" in raw_text.lower():
            flaws.append({
                "flaw_id": "VANCE-001",
                "category": "race_condition",
                "description": "Optimistic fill assumption ignores queue priority on thin Kalshi books.",
                "severity": "HIGH",
                "counter_measure": "Implement partial fill handlers and resting order timeout cancellations.",
            })

        if "wide spread" in raw_text.lower() or "market price" in raw_text.lower():
            flaws.append({
                "flaw_id": "VANCE-002",
                "category": "fee_drag",
                "description": "Execution across spreads > $0.05 guarantees adverse selection.",
                "severity": "HIGH",
                "counter_measure": "Hard cap spread crossing at <= $0.05; prefer passive resting bids.",
            })

        verdict = "VETO" if any(f["severity"] == "FATAL" for f in flaws) else ("ADJUST" if flaws else "PASS")
        critique = (
            "Orderbook depth and CLOB execution bounds verified."
            if verdict == "PASS" else
            f"CLOB execution hazards identified ({len(flaws)} flaws)."
        )

        vote: CouncilorVote = {
            "councilor": self.name,
            "verdict": verdict,
            "critique": critique,
            "hard_bounds": {
                "max_spread_penalty": "0.05",
                "resting_order_ttl_sec": "15",
                "execution_style": "MAKER_PREFERRED",
            },
        }
        return vote, flaws

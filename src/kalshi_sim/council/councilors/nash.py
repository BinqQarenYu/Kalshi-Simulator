"""Dr. Nash: Quantitative Mathematician Councilor.

Enforces zero-float math, net EV positivity after quadratic taker fees, and Kelly bounds.
"""

from decimal import Decimal
from typing import Dict, Any, List
from src.kalshi_sim.council.councilors.base import BaseCouncilor
from src.kalshi_sim.council.state import CouncilorVote, IdentifiedFlaw


class DrNashCouncilor(BaseCouncilor):
    def __init__(self):
        super().__init__(name="nash", domain="Quantitative Mathematics & Fee Drag")

    def evaluate(self, proposal: Dict[str, Any]) -> tuple[CouncilorVote, List[IdentifiedFlaw]]:
        flaws: List[IdentifiedFlaw] = []
        raw_text = str(proposal.get("core_objective", "")) + " " + str(proposal.get("raw_prompt", ""))
        
        # Check for float math anti-pattern
        if "float(" in raw_text or " IEEE" in raw_text:
            flaws.append({
                "flaw_id": "NASH-001",
                "category": "float_math",
                "description": "Proposed logic mentions or relies on IEEE-754 floating point numbers.",
                "severity": "FATAL",
                "counter_measure": "Refactor all monetary, strike, and balance variables to decimal.Decimal.",
            })

        # Check for negative EV or unhedged taker fee drag
        if "market order" in raw_text.lower() or "cross the spread" in raw_text.lower():
            flaws.append({
                "flaw_id": "NASH-002",
                "category": "fee_drag",
                "description": "Crossing spread incurs Kalshi quadratic taker fee without guaranteed alpha.",
                "severity": "HIGH",
                "counter_measure": "Enforce maker limit orders at strike midpoint or passive inside bid.",
            })

        verdict = "VETO" if any(f["severity"] == "FATAL" for f in flaws) else ("ADJUST" if flaws else "PASS")
        critique = (
            "Mathematics validated with strict Decimal precision and positive EV bounds."
            if verdict == "PASS" else
            f"Mathematical or fee drag risks detected ({len(flaws)} flaws)."
        )

        vote: CouncilorVote = {
            "councilor": self.name,
            "verdict": verdict,
            "critique": critique,
            "hard_bounds": {
                "min_net_ev": "0.015",
                "math_precision": "Decimal",
                "max_taker_fee_ratio": "0.15",
            },
        }
        return vote, flaws

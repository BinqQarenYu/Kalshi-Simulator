"""Barnaby: Inverted Retail Trader Indicator.

Identifies retail herd traps, FOMO momentum chasing, and panic-selling vulnerabilities.
"""

from typing import Dict, Any, List
from src.kalshi_sim.council.councilors.base import BaseCouncilor
from src.kalshi_sim.council.state import CouncilorVote, IdentifiedFlaw


class BarnabyCouncilor(BaseCouncilor):
    def __init__(self):
        super().__init__(name="barnaby", domain="Retail Inversion & Anti-FOMO Guardrails")

    def evaluate(self, proposal: Dict[str, Any]) -> tuple[CouncilorVote, List[IdentifiedFlaw]]:
        flaws: List[IdentifiedFlaw] = []
        raw_text = str(proposal.get("core_objective", "")) + " " + str(proposal.get("raw_prompt", ""))

        if "chase" in raw_text.lower() or "breakout buy" in raw_text.lower():
            flaws.append({
                "flaw_id": "BARNABY-001",
                "category": "dead_zone",
                "description": "Entering into multi-bar extended surges creates retail exit liquidity.",
                "severity": "HIGH",
                "counter_measure": "Require mean-reversion confirmation or 3x statistical edge threshold.",
            })

        if "trade every" in raw_text.lower() or "continuous" in raw_text.lower() or "every tick" in raw_text.lower():
            flaws.append({
                "flaw_id": "BARNABY-002",
                "category": "dead_zone",
                "description": "Overtrading without regime filtering drains bankroll to fees.",
                "severity": "FATAL",
                "counter_measure": "Enforce 1-Trade-Per-Cycle lock and 60-second minimum cooldown.",
            })

        verdict = "VETO" if any(f["severity"] == "FATAL" for f in flaws) else ("ADJUST" if flaws else "PASS")
        critique = (
            "Anti-retail safeguards respected; zero emotional FOMO indicators detected."
            if verdict == "PASS" else
            f"Retail vulnerability detected ({len(flaws)} flaws)."
        )

        vote: CouncilorVote = {
            "councilor": self.name,
            "verdict": verdict,
            "critique": critique,
            "hard_bounds": {
                "max_trades_per_cycle": "1",
                "anti_fomo_min_cooldown_sec": "60",
                "retail_inversion_multiplier": "3.0",
            },
        }
        return vote, flaws

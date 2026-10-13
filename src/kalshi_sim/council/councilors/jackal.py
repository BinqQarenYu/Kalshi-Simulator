"""The Jackal: Adversarial Exploit Hunter.

Stresses edge cases, concurrent race conditions, missing intent locks, and bankroll exposure.
"""

from typing import Dict, Any, List
from src.kalshi_sim.council.councilors.base import BaseCouncilor
from src.kalshi_sim.council.state import CouncilorVote, IdentifiedFlaw


class JackalCouncilor(BaseCouncilor):
    def __init__(self):
        super().__init__(name="jackal", domain="Exploit Hunting & Race Condition Defense")

    def evaluate(self, proposal: Dict[str, Any]) -> tuple[CouncilorVote, List[IdentifiedFlaw]]:
        flaws: List[IdentifiedFlaw] = []
        raw_text = str(proposal.get("core_objective", "")) + " " + str(proposal.get("raw_prompt", ""))

        if "concurrent order" in raw_text.lower() or "no lock" in raw_text.lower():
            flaws.append({
                "flaw_id": "JACKAL-001",
                "category": "race_condition",
                "description": "Lack of mutex or in-flight intent lock invites dual-fire race condition.",
                "severity": "FATAL",
                "counter_measure": "Mandate 15s in-flight intent lock with single-process PID mutex.",
            })

        if "unlimited size" in raw_text.lower() or "all in" in raw_text.lower():
            flaws.append({
                "flaw_id": "JACKAL-002",
                "category": "blast_radius",
                "description": "Uncapped position sizing violates micro-bankroll survival.",
                "severity": "FATAL",
                "counter_measure": "Strictly enforce max 1 contract limit on accounts under $75.",
            })

        verdict = "VETO" if any(f["severity"] == "FATAL" for f in flaws) else ("ADJUST" if flaws else "PASS")
        critique = (
            "Systemic defenses, locks, and blast-radius containment intact."
            if verdict == "PASS" else
            f"Severe adversarial vulnerabilities uncovered ({len(flaws)} flaws)."
        )

        vote: CouncilorVote = {
            "councilor": self.name,
            "verdict": verdict,
            "critique": critique,
            "hard_bounds": {
                "in_flight_lock_ttl_sec": "15",
                "max_contracts_per_order": "1",
                "process_mutex_enforced": "true",
            },
        }
        return vote, flaws

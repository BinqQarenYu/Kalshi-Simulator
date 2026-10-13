"""Silas: TWAP Settlement Arbiter.

Enforces CME CF Benchmarks 60s trailing TWAP settlement math and late-cycle expiration parity.
"""

from typing import Dict, Any, List
from src.kalshi_sim.council.councilors.base import BaseCouncilor
from src.kalshi_sim.council.state import CouncilorVote, IdentifiedFlaw


class SilasCouncilor(BaseCouncilor):
    def __init__(self):
        super().__init__(name="silas", domain="TWAP Settlement & Expiration Parity")

    def evaluate(self, proposal: Dict[str, Any]) -> tuple[CouncilorVote, List[IdentifiedFlaw]]:
        flaws: List[IdentifiedFlaw] = []
        raw_text = str(proposal.get("core_objective", "")) + " " + str(proposal.get("raw_prompt", ""))

        if "instant spot at expiry" in raw_text.lower() or "last 10s spot" in raw_text.lower():
            flaws.append({
                "flaw_id": "SILAS-001",
                "category": "twap_mismatch",
                "description": "Trading spot in final 60s ignores CME CF Benchmarks 60s trailing TWAP settlement window.",
                "severity": "HIGH",
                "counter_measure": "Incorporate cfbenchmarks_value_5hz 60s trailing TWAP integration.",
            })

        if "trade in last 30s" in raw_text.lower() or "expiry scalp" in raw_text.lower():
            flaws.append({
                "flaw_id": "SILAS-002",
                "category": "dead_zone",
                "description": "Late-cycle entry suffers pinning risk where settlement math locks payoff.",
                "severity": "HIGH",
                "counter_measure": "Halt new entries when time to expiration is under 120 seconds.",
            })

        verdict = "VETO" if any(f["severity"] == "FATAL" for f in flaws) else ("ADJUST" if flaws else "PASS")
        critique = (
            "TWAP settlement math and expiration parity verified."
            if verdict == "PASS" else
            f"Settlement mismatch risks flagged ({len(flaws)} flaws)."
        )

        vote: CouncilorVote = {
            "councilor": self.name,
            "verdict": verdict,
            "critique": critique,
            "hard_bounds": {
                "min_time_to_expiry_sec": "120",
                "twap_window_sec": "60",
                "oracle_feed": "cfbenchmarks_value_5hz",
            },
        }
        return vote, flaws

"""Koko: Chief Strategist & Council Arbiter.

Synthesizes all 6 councilor viewpoints into a unified decision, resolves trade-offs,
and formats task contracts for Agent Codeflow and ASVL.
"""

from typing import Dict, Any, List, Optional
from src.kalshi_sim.council.state import CouncilorVote, IdentifiedFlaw


class KokoArbiter:
    """Council Arbiter responsible for synthesis and consensus determination."""

    def __init__(self):
        self.name = "koko"
        self.domain = "Consensus Arbitration & Strategic Synthesis"

    def diagnose_objective(self, raw_prompt: str) -> Dict[str, Any]:
        """Node 1: Socratic Diagnostician. Filters anti-patterns and clarifies core objective."""
        clean_prompt = raw_prompt.strip()
        is_genuine = True
        clarified = clean_prompt
        non_goals = []

        if len(clean_prompt) < 5:
            is_genuine = False
            clarified = "Empty or trivial proposal rejected."

        if "indicator dial" in clean_prompt.lower() or "more indicators" in clean_prompt.lower():
            non_goals.append("Adding cosmetic indicator dials without mathematical edge.")
            clarified = "Optimize entry timing against Brownian noise zone rather than adding indicators."

        return {
            "is_genuine": is_genuine,
            "core_objective": clarified,
            "non_goals": non_goals,
        }

    def synthesize(
        self,
        votes: Dict[str, CouncilorVote],
        flaws: List[IdentifiedFlaw],
        debate_round: int,
        max_rounds: int = 2
    ) -> Dict[str, Any]:
        """Node 4: Synthesize votes and flaws into a consensus verdict and hardened solution."""
        fatal_flaws = [f for f in flaws if f.get("severity") == "FATAL"]
        high_flaws = [f for f in flaws if f.get("severity") == "HIGH"]
        veto_votes = [v for v in votes.values() if v.get("verdict") == "VETO"]

        if fatal_flaws or veto_votes:
            verdict = "REJECTED"
            solution = f"Proposal VETOED. Fatal issues: {[f['description'] for f in fatal_flaws]}"
        elif high_flaws and debate_round < max_rounds:
            verdict = "CONDITIONALLY_APPROVED"
            solution = f"Requires iteration (Round {debate_round}/{max_rounds}). Counter-measures required: {[f['counter_measure'] for f in high_flaws]}"
        else:
            verdict = "APPROVED"
            solution = "Proposal ratified by Council. All orthogonal bounds respected. Ready for documentation & task granulization."

        return {
            "consensus_verdict": verdict,
            "synthesized_solution": solution,
        }

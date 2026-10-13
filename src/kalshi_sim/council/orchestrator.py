"""Council Orchestrator: High-level interface to the LangGraph decision engine.

Enforces Rule 8 (Anti-Blackhole Token Conservation) with support for Fast-Track mode
and deterministic state checkpointing.
"""

from typing import Dict, Any, Optional
from src.kalshi_sim.council.state import create_initial_state, CouncilState
from src.kalshi_sim.council.graph import build_council_graph


class CouncilOrchestrator:
    """Master orchestrator executing the 3-Stage Engineering Pipeline."""

    def __init__(self):
        self.app = build_council_graph()

    def deliberate(
        self,
        raw_prompt: str,
        target_asset: str = "BTC",
        max_rounds: int = 2
    ) -> CouncilState:
        """Execute the LangGraph Council deliberation loop.
        
        Args:
            raw_prompt: The strategy or architectural proposal to evaluate.
            target_asset: "BTC", "ETH", or "SYSTEM".
            max_rounds: Hard cap on debate cycles (default 2 to prevent token burning).
            
        Returns:
            The final CouncilState containing consensus, flaw registry, and task contract.
        """
        initial_state = create_initial_state(
            raw_prompt=raw_prompt,
            core_objective=raw_prompt,
            target_asset=target_asset,
            max_rounds=max_rounds,
        )

        final_state: CouncilState = self.app.invoke(initial_state)
        return final_state

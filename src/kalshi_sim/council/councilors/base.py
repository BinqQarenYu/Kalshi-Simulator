"""Base Councilor definition and contract.

Every Councilor is an orthogonal domain expert evaluating proposals strictly
against their domain invariants.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from src.kalshi_sim.council.state import CouncilorVote, IdentifiedFlaw


class BaseCouncilor(ABC):
    """Abstract base class for all Council members."""

    def __init__(self, name: str, domain: str):
        self.name = name
        self.domain = domain

    @abstractmethod
    def evaluate(self, proposal: Dict[str, Any]) -> tuple[CouncilorVote, List[IdentifiedFlaw]]:
        """Evaluate a proposal and return a vote and zero or more identified flaws.
        
        Args:
            proposal: Dictionary containing proposal details (objective, target_asset, params, etc.)
            
        Returns:
            Tuple of (CouncilorVote, List[IdentifiedFlaw])
        """
        pass

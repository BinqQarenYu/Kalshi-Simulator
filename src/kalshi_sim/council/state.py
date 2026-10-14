"""LangGraph Council State schemas and typed containers.

Enforces zero-float math invariants and structured state reducers.
"""

from typing import TypedDict, List, Dict, Optional, Literal, Annotated, Any
import operator


class CouncilorVote(TypedDict, total=False):
    councilor: str                     # "nash", "vance", "barnaby", "apex", "jackal", "silas"
    verdict: Literal["PASS", "VETO", "ADJUST"]
    critique: str                      # Concise 1-2 sentence core reasoning
    hard_bounds: Dict[str, str]        # Quantitative constraints enforced (strings to ensure Decimal precision)


class IdentifiedFlaw(TypedDict, total=False):
    flaw_id: str
    category: Literal["fee_drag", "dead_zone", "race_condition", "blast_radius", "float_math", "twap_mismatch"]
    description: str
    severity: Literal["FATAL", "HIGH", "MEDIUM", "LOW"]
    counter_measure: str


class GranularTaskStep(TypedDict, total=False):
    step_id: int
    phase: Literal["1_schemas", "2_core_logic", "3_ui_state", "4_verification"]
    target_file: str
    allowed_access: Literal["write", "append", "read_only"]
    action_description: str
    definition_of_done: str


def merge_votes(
    left: Optional[Dict[str, CouncilorVote]], 
    right: Optional[Dict[str, CouncilorVote]]
) -> Dict[str, CouncilorVote]:
    """Reducer function to merge councilor votes without losing prior votes."""
    merged = dict(left) if left else {}
    if right:
        merged.update(right)
    return merged


class CouncilState(TypedDict, total=False):
    # Input
    raw_prompt: str
    core_objective: str
    target_asset: str                  # "BTC", "ETH", "SYSTEM"
    
    # Deliberation State
    debate_round: Annotated[int, operator.add]
    max_rounds: int                    # Hard cap = 2 (Rule 8: Anti-Blackhole Token Conservation)
    council_votes: Annotated[Dict[str, CouncilorVote], merge_votes]
    flaw_registry: Annotated[List[IdentifiedFlaw], operator.add]
    
    # Consensus
    consensus_verdict: Optional[Literal["APPROVED", "REJECTED", "CONDITIONALLY_APPROVED"]]
    synthesized_solution: Optional[str]
    non_negotiable_invariants: List[str]
    kev_evaluation: Optional[Dict[str, Any]]
    
    # Documentation & Task Contract
    specification_document_path: Optional[str]
    file_boundary_matrix: Dict[str, Literal["write", "append", "read_only", "forbidden"]]
    task_contract: List[GranularTaskStep]
    
    # Verification State
    verification_status: Literal["PENDING", "IN_PROGRESS", "PASSED", "FAILED"]
    test_results: Dict[str, bool]


def create_initial_state(
    raw_prompt: str,
    core_objective: str,
    target_asset: str = "BTC",
    max_rounds: int = 2
) -> CouncilState:
    """Helper to initialize a clean CouncilState with default zero values."""
    return {
        "raw_prompt": raw_prompt,
        "core_objective": core_objective,
        "target_asset": target_asset,
        "debate_round": 0,
        "max_rounds": max_rounds,
        "council_votes": {},
        "flaw_registry": [],
        "consensus_verdict": None,
        "synthesized_solution": None,
        "non_negotiable_invariants": [
            "Zero Float Financial Math (Decimal)",
            "1-Trade-Per-Cycle execution lock",
            "Micro-bankroll sizing (Max 1 contract)",
            "Seal of Excellence verified on disk",
        ],
        "specification_document_path": None,
        "file_boundary_matrix": {},
        "task_contract": [],
        "verification_status": "PENDING",
        "test_results": {},
    }

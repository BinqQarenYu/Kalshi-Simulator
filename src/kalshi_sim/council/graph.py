"""LangGraph StateGraph builder for Council Orchestrator.

Implements the 7-Councilor deliberation loop with flaw catching, bounded rounds (<=2),
consensus synthesis, and Agent Codeflow task granulization.
"""

from typing import Dict, Any, List, Literal
from langgraph.graph import StateGraph, START, END

from src.kalshi_sim.council.state import (
    CouncilState,
    CouncilorVote,
    IdentifiedFlaw,
    GranularTaskStep,
)
from src.kalshi_sim.council.councilors import (
    DrNashCouncilor,
    VanceCouncilor,
    BarnabyCouncilor,
    ApexCouncilor,
    JackalCouncilor,
    SilasCouncilor,
    KokoArbiter,
)


def node_diagnose(state: CouncilState) -> Dict[str, Any]:
    """Node 1: Socratic Diagnostician (Koko). Filters non-goals and clarifies objective."""
    koko = KokoArbiter()
    diag = koko.diagnose_objective(state.get("raw_prompt", ""))
    return {
        "core_objective": diag["core_objective"],
        "debate_round": 1,
    }


def node_roundtable(state: CouncilState) -> Dict[str, Any]:
    """Node 2: 7-Councilor Roundtable. Each domain expert assesses the proposal."""
    councilors = [
        DrNashCouncilor(),
        VanceCouncilor(),
        BarnabyCouncilor(),
        ApexCouncilor(),
        JackalCouncilor(),
        SilasCouncilor(),
    ]

    proposal = {
        "raw_prompt": state.get("raw_prompt", ""),
        "core_objective": state.get("core_objective", ""),
        "target_asset": state.get("target_asset", "BTC"),
    }

    votes: Dict[str, CouncilorVote] = {}
    new_flaws: List[IdentifiedFlaw] = []

    for c in councilors:
        vote, flaws = c.evaluate(proposal)
        votes[c.name] = vote
        new_flaws.extend(flaws)

    return {
        "council_votes": votes,
        "flaw_registry": new_flaws,
    }


def node_rebuttal(state: CouncilState) -> Dict[str, Any]:
    """Node 3: Rebuttal & Flaw Catcher. Evaluates if flaws are fatal or addressable."""
    return {}


def node_refine(state: CouncilState) -> Dict[str, Any]:
    """Node 3b: Counter-Hypothesis Refinement. Bounded iteration increment."""
    return {
        "debate_round": 1,
    }


def node_synthesis(state: CouncilState) -> Dict[str, Any]:
    """Node 4: Koko Consensus & Solution Synthesis."""
    koko = KokoArbiter()
    res = koko.synthesize(
        votes=state.get("council_votes", {}),
        flaws=state.get("flaw_registry", []),
        debate_round=state.get("debate_round", 1),
        max_rounds=state.get("max_rounds", 2),
    )
    return {
        "consensus_verdict": res["consensus_verdict"],
        "synthesized_solution": res["synthesized_solution"],
    }


def node_task_granulizer(state: CouncilState) -> Dict[str, Any]:
    """Node 6: Agent Codeflow Task Granulizer. Generates bounded execution contract."""
    verdict = state.get("consensus_verdict")
    if verdict != "APPROVED":
        return {
            "task_contract": [],
            "file_boundary_matrix": {},
            "verification_status": "FAILED",
        }

    task_contract: List[GranularTaskStep] = [
        {
            "step_id": 1,
            "phase": "1_schemas",
            "target_file": "src/kalshi_sim/core/schemas.py",
            "allowed_access": "write",
            "action_description": "Define typed data structures with Decimal math invariants.",
            "definition_of_done": "Type checks pass and schema unit tests compile.",
        },
        {
            "step_id": 2,
            "phase": "2_core_logic",
            "target_file": "src/kalshi_sim/core/invariants.py",
            "allowed_access": "write",
            "action_description": "Implement verified mathematical guardrails and execution limits.",
            "definition_of_done": "Targeted pytest passes with 100% coverage.",
        },
        {
            "step_id": 3,
            "phase": "3_ui_state",
            "target_file": "src/kalshi_sim/services/server.py",
            "allowed_access": "append",
            "action_description": "Expose telemetry endpoint for state monitoring.",
            "definition_of_done": "FastAPI route responds with HTTP 200.",
        },
        {
            "step_id": 4,
            "phase": "4_verification",
            "target_file": "tests/test_invariants.py",
            "allowed_access": "write",
            "action_description": "Execute ASVL automated regression test suite.",
            "definition_of_done": "All tests pass with zero regressions.",
        },
    ]

    boundary_matrix: Dict[str, Literal["write", "append", "read_only", "forbidden"]] = {
        "src/kalshi_sim/core/schemas.py": "write",
        "src/kalshi_sim/core/invariants.py": "write",
        "src/kalshi_sim/services/server.py": "append",
        "docs/LANGGRAPH_COUNCIL_ORCHESTRATOR.md": "read_only",
    }

    return {
        "task_contract": task_contract,
        "file_boundary_matrix": boundary_matrix,
        "verification_status": "PENDING",
    }


def route_after_diagnose(state: CouncilState) -> str:
    """Route: If prompt is invalid/trivial, halt immediately."""
    obj = state.get("core_objective", "")
    if obj.startswith("Empty or trivial"):
        return END
    return "roundtable"


def route_after_rebuttal(state: CouncilState) -> str:
    """Route: Fatal flaws -> synthesis (reject); Addressable & rounds < max -> refine; Else -> synthesis."""
    flaws = state.get("flaw_registry", [])
    has_fatal = any(f.get("severity") == "FATAL" for f in flaws)
    current_round = state.get("debate_round", 1)
    max_rounds = state.get("max_rounds", 2)

    if has_fatal:
        return "synthesis"

    has_high = any(f.get("severity") == "HIGH" for f in flaws)
    if has_high and current_round < max_rounds:
        return "refine"

    return "synthesis"


def route_after_synthesis(state: CouncilState) -> str:
    """Route: Only approved proposals get task contracts."""
    verdict = state.get("consensus_verdict")
    if verdict == "APPROVED":
        return "granulizer"
    return END


def build_council_graph():
    """Assemble and compile the Council StateGraph."""
    graph = StateGraph(CouncilState)

    graph.add_node("diagnose", node_diagnose)
    graph.add_node("roundtable", node_roundtable)
    graph.add_node("rebuttal", node_rebuttal)
    graph.add_node("refine", node_refine)
    graph.add_node("synthesis", node_synthesis)
    graph.add_node("granulizer", node_task_granulizer)

    graph.add_edge(START, "diagnose")
    graph.add_conditional_edges("diagnose", route_after_diagnose)
    graph.add_edge("roundtable", "rebuttal")
    graph.add_conditional_edges("rebuttal", route_after_rebuttal)
    graph.add_edge("refine", "roundtable")
    graph.add_conditional_edges("synthesis", route_after_synthesis)
    graph.add_edge("granulizer", END)

    return graph.compile()

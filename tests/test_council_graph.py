"""Targeted test suite for LangGraph Council StateGraph and Orchestrator."""

import pytest
from src.kalshi_sim.council import (
    CouncilOrchestrator,
    build_council_graph,
    create_initial_state,
)


def test_build_council_graph_compiles():
    app = build_council_graph()
    assert app is not None


def test_council_deliberation_approved():
    orchestrator = CouncilOrchestrator()
    proposal = "Deploy passive maker limit order with Decimal math and 1-contract micro-bankroll"
    
    state = orchestrator.deliberate(proposal, target_asset="BTC")
    
    assert state["consensus_verdict"] == "APPROVED"
    assert "ratified" in state["synthesized_solution"].lower()
    assert len(state["task_contract"]) == 4
    assert state["task_contract"][0]["phase"] == "1_schemas"
    assert state["task_contract"][1]["phase"] == "2_core_logic"
    assert state["task_contract"][2]["phase"] == "3_ui_state"
    assert state["task_contract"][3]["phase"] == "4_verification"
    assert "src/kalshi_sim/core/schemas.py" in state["file_boundary_matrix"]


def test_council_deliberation_rejected_on_fatal_flaw():
    orchestrator = CouncilOrchestrator()
    proposal = "Use float(price) and cross the wide spread instantly with no lock"
    
    state = orchestrator.deliberate(proposal, target_asset="BTC")
    
    assert state["consensus_verdict"] == "REJECTED"
    assert len(state["flaw_registry"]) > 0
    assert any(f["severity"] == "FATAL" for f in state["flaw_registry"])
    # Should not produce a task contract on rejected proposal
    assert len(state["task_contract"]) == 0


def test_council_trivial_proposal_halt():
    orchestrator = CouncilOrchestrator()
    trivial_proposal = "hi"
    
    state = orchestrator.deliberate(trivial_proposal, target_asset="BTC")
    
    # Should halt at Node 1 without running roundtable
    assert state["core_objective"] == "Empty or trivial proposal rejected."
    assert state["consensus_verdict"] is None

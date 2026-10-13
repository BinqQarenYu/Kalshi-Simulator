"""Targeted unit tests for CouncilState and schemas."""

import pytest
from src.kalshi_sim.council.state import (
    create_initial_state,
    merge_votes,
    CouncilState,
    CouncilorVote,
    IdentifiedFlaw,
)


def test_create_initial_state():
    state = create_initial_state(
        raw_prompt="Test proposal",
        core_objective="Validate state schema",
        target_asset="BTC",
        max_rounds=2,
    )
    assert state["raw_prompt"] == "Test proposal"
    assert state["core_objective"] == "Validate state schema"
    assert state["target_asset"] == "BTC"
    assert state["debate_round"] == 0
    assert state["max_rounds"] == 2
    assert state["council_votes"] == {}
    assert state["flaw_registry"] == []
    assert state["consensus_verdict"] is None
    assert state["verification_status"] == "PENDING"
    assert len(state["non_negotiable_invariants"]) == 4


def test_merge_votes_reducer():
    v1: dict[str, CouncilorVote] = {
        "nash": {
            "councilor": "nash",
            "verdict": "PASS",
            "critique": "EV positive",
            "hard_bounds": {"min_ev": "0.02"},
        }
    }
    v2: dict[str, CouncilorVote] = {
        "vance": {
            "councilor": "vance",
            "verdict": "ADJUST",
            "critique": "Spread too wide",
            "hard_bounds": {"max_spread": "0.05"},
        }
    }
    merged = merge_votes(v1, v2)
    assert "nash" in merged
    assert "vance" in merged
    assert merged["nash"]["verdict"] == "PASS"
    assert merged["vance"]["verdict"] == "ADJUST"


def test_flaw_registry_entry():
    flaw: IdentifiedFlaw = {
        "flaw_id": "FLAW-001",
        "category": "fee_drag",
        "description": "Taker fees consume 80% of expected return",
        "severity": "HIGH",
        "counter_measure": "Enforce maker-only limit orders",
    }
    assert flaw["flaw_id"] == "FLAW-001"
    assert flaw["severity"] == "HIGH"

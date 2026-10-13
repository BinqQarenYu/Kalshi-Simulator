"""Targeted unit tests for Councilors domain evaluators and Koko Arbiter."""

import pytest
from src.kalshi_sim.council.councilors import (
    DrNashCouncilor,
    VanceCouncilor,
    BarnabyCouncilor,
    ApexCouncilor,
    JackalCouncilor,
    SilasCouncilor,
    KokoArbiter,
)


def test_dr_nash_float_veto():
    nash = DrNashCouncilor()
    vote, flaws = nash.evaluate({"raw_prompt": "Use float(price) for calculation"})
    assert vote["verdict"] == "VETO"
    assert any(f["category"] == "float_math" for f in flaws)


def test_dr_nash_pass():
    nash = DrNashCouncilor()
    vote, flaws = nash.evaluate({"raw_prompt": "Use Decimal('0.50') and maker limit order"})
    assert vote["verdict"] == "PASS"
    assert len(flaws) == 0


def test_vance_spread_check():
    vance = VanceCouncilor()
    vote, flaws = vance.evaluate({"raw_prompt": "Cross the wide spread instantly"})
    assert vote["verdict"] == "ADJUST"
    assert any(f["category"] == "fee_drag" for f in flaws)


def test_barnaby_retail_fomo_veto():
    barnaby = BarnabyCouncilor()
    vote, flaws = barnaby.evaluate({"raw_prompt": "Trade continuously every tick"})
    assert vote["verdict"] == "VETO"
    assert any(f["flaw_id"] == "BARNABY-002" for f in flaws)


def test_apex_smart_flow():
    apex = ApexCouncilor()
    vote, flaws = apex.evaluate({"raw_prompt": "Execute counter trend order against institutional pump"})
    assert vote["verdict"] == "ADJUST"
    assert any(f["category"] == "dead_zone" for f in flaws)


def test_jackal_race_condition_veto():
    jackal = JackalCouncilor()
    vote, flaws = jackal.evaluate({"raw_prompt": "Fire concurrent order with no lock"})
    assert vote["verdict"] == "VETO"
    assert any(f["category"] == "race_condition" for f in flaws)


def test_silas_settlement_twap():
    silas = SilasCouncilor()
    vote, flaws = silas.evaluate({"raw_prompt": "Place trade in last 30s before expiration"})
    assert vote["verdict"] == "ADJUST"
    assert any(f["category"] == "dead_zone" for f in flaws)


def test_koko_diagnosis_and_synthesis():
    koko = KokoArbiter()
    diag = koko.diagnose_objective("Please add more indicator dials to the chart")
    assert "Brownian noise" in diag["core_objective"]
    assert len(diag["non_goals"]) > 0

    # Test synthesis on approved votes
    synth_pass = koko.synthesize(
        votes={"nash": {"councilor": "nash", "verdict": "PASS", "critique": "OK", "hard_bounds": {}}},
        flaws=[],
        debate_round=1,
    )
    assert synth_pass["consensus_verdict"] == "APPROVED"

    # Test synthesis on fatal flaw
    synth_reject = koko.synthesize(
        votes={"jackal": {"councilor": "jackal", "verdict": "VETO", "critique": "Vetoed", "hard_bounds": {}}},
        flaws=[{"flaw_id": "JACKAL-001", "category": "race_condition", "description": "Race", "severity": "FATAL", "counter_measure": "Lock"}],
        debate_round=1,
    )
    assert synth_reject["consensus_verdict"] == "REJECTED"

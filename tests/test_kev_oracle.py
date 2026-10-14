"""ASVL Verification Test Battery for Kev AI Decision Oracle Integration.

Verifies:
1. Strict Zero Float Financial Math (Decimal probabilities).
2. Typed question definitions and prefill-only single-pass contracts.
3. Sub-80ms circuit-breaker fallback when local server is offline.
4. LangGraph Council Orchestrator integration (node_kev_evaluation).
5. Non-invasive shadow-mode integration into EthBot1V4Engine.
"""

from decimal import Decimal
from pathlib import Path
import pytest

from kalshi_sim.ml.kev_oracle import (
    KevDecisionOracle,
    KevDecisionResult,
    KevQuestion,
    KevQuestionType,
)
from kalshi_sim.council.orchestrator import CouncilOrchestrator
from kalshi_sim.ml.eth_bot1v4.eth_bot1v4_engine import EthBot1V4Engine


def test_kev_question_and_types_initialization():
    """Verify KevQuestion constructs valid typed question schemas."""
    q_bool = KevQuestion("is_toxic", "Is orderflow toxic?", KevQuestionType.BOOLEAN)
    assert q_bool.key == "is_toxic"
    assert q_bool.question_type == KevQuestionType.BOOLEAN
    assert q_bool.options == ["true", "false"]

    q_choice = KevQuestion("regime", "Select regime", KevQuestionType.CHOICE, ["CHOP", "STORM", "BLEED"])
    assert q_choice.key == "regime"
    assert q_choice.question_type == KevQuestionType.CHOICE
    assert len(q_choice.options) == 3

    d = q_choice.to_dict()
    assert d["type"] == "choice"
    assert d["options"] == ["CHOP", "STORM", "BLEED"]


def test_kev_decision_result_zero_float_math():
    """Verify KevDecisionResult strictly stores Decimal probabilities and confidence."""
    probs = {
        "YES": Decimal("0.8500"),
        "NO": Decimal("0.0500"),
        "WAIT": Decimal("0.1000"),
    }
    res = KevDecisionResult(
        key="direction",
        question_type=KevQuestionType.CHOICE,
        selected_option="YES",
        probabilities=probs,
        confidence=Decimal("0.8500"),
        latency_ms=12.5,
        source="test",
    )

    assert isinstance(res.confidence, Decimal)
    assert res.confidence == Decimal("0.8500")
    for k, v in res.probabilities.items():
        assert isinstance(v, Decimal), f"Probability for {k} is not Decimal: {type(v)}"

    d = res.to_dict()
    assert d["selected_option"] == "YES"
    assert d["confidence"] == 0.85
    assert d["probabilities"]["YES"] == 0.85


def test_kev_context_builder():
    """Verify build_market_context constructs standard deterministic telemetry string."""
    ctx = KevDecisionOracle.build_market_context(
        asset="ETH",
        spot_price=Decimal("2505.50"),
        target_strike=Decimal("2502.50"),
        time_to_expiry_s=360,
        ofi=0.75,
        vpin=0.18,
        spread_cents=0.03,
        current_regime="CHOP",
        macro_slope=0.002,
        recent_trade_count=4,
    )

    assert "Asset: ETH" in ctx
    assert "Spot: $2505.50" in ctx
    assert "Strike: $2502.50" in ctx
    assert "Diff: +3.00" in ctx
    assert "Tau: 360s" in ctx
    assert "CLOB Spread: $0.03" in ctx
    assert "VPIN: 0.18" in ctx


@pytest.mark.asyncio
async def test_kev_oracle_circuit_breaker_offline_fallback():
    """Verify KevDecisionOracle gracefully falls back to deterministic heuristics when server is offline."""
    # Point to an unreachable port to guarantee connection refusal
    oracle = KevDecisionOracle(base_url="http://127.0.0.1:59999", timeout_seconds=0.05)

    ctx = oracle.build_market_context(
        asset="ETH",
        spot_price=2506.00,
        target_strike=2502.50,
        time_to_expiry_s=240,
        ofi=0.60,
        vpin=0.15,
        spread_cents=0.02,
        current_regime="CHOP",
    )

    questions = [
        KevQuestion("is_toxic_sweep", "Is toxic?", KevQuestionType.BOOLEAN),
        KevQuestion("trade_direction", "Direction?", KevQuestionType.CHOICE, ["YES", "NO", "WAIT"]),
        KevQuestion("regime", "Regime?", KevQuestionType.CHOICE, ["CHOP", "STORM", "BLEED"]),
    ]

    res = await oracle.evaluate(ctx, questions)

    assert len(res) == 3
    assert "is_toxic_sweep" in res
    assert "trade_direction" in res
    assert "regime" in res

    # Check zero float math
    direction_res = res["trade_direction"]
    assert direction_res.source == "heuristic_fallback"
    assert isinstance(direction_res.confidence, Decimal)
    for p in direction_res.probabilities.values():
        assert isinstance(p, Decimal)

    # In ITM case with positive OFI, YES should be favored
    assert direction_res.selected_option == "YES"
    assert direction_res.probabilities["YES"] > direction_res.probabilities["NO"]


def test_langgraph_council_with_kev_node():
    """Verify LangGraph Council Orchestrator executes through node_kev_evaluation."""
    orchestrator = CouncilOrchestrator()
    final_state = orchestrator.deliberate(
        raw_prompt="Deploy Kev AI decision oracle in LangGraph Council and live trading",
        target_asset="ETH",
    )

    assert final_state["consensus_verdict"] == "APPROVED"
    assert "kev_evaluation" in final_state
    kev_eval = final_state["kev_evaluation"]
    assert "is_proposal_viable" in kev_eval
    assert "consensus_verdict" in kev_eval


def test_eth_bot1v4_has_kev_oracle(tmp_path: Path):
    """Verify EthBot1V4Engine initializes KevDecisionOracle for shadow evaluation."""
    hist = tmp_path / "eth_win_loss_reports.json"
    engine = EthBot1V4Engine(history_file=hist)

    assert hasattr(engine, "kev_oracle")
    assert isinstance(engine.kev_oracle, KevDecisionOracle)
    assert engine.kev_oracle.timeout_seconds == 0.08

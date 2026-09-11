"""Unit Tests for Per-Bot and Per-Mode Win/Loss Performance Reports."""

from decimal import Decimal
import pytest
from kalshi_sim.server import _calculate_15m_metrics, _matches_bot_id


def test_matches_bot_id_onnx_macro():
    """Verify alias resolution for ONNX Macro v2 / The ONNX Strategy / Dual ONNX."""
    r1 = {"bot_id": "onnx_macro_v2", "bot_type": "onnx_macro_v2"}
    r2 = {"bot_type": "dual_onnx", "strategy_id": "dual_onnx"}
    r3 = {"bot_type": "the_onnx_strategy"}
    r4 = {"bot_type": "macro_onnx", "ai_rationale": "Dual ONNX Contradiction Arbitrage"}
    r5 = {"bot_type": "3_step_domination_bot", "ai_rationale": "Playbook 2: OFI Trend Drift"}

    assert _matches_bot_id(r1, "onnx_macro_v2") is True
    assert _matches_bot_id(r2, "onnx_macro_v2") is True
    assert _matches_bot_id(r3, "onnx_macro_v2") is True
    assert _matches_bot_id(r4, "onnx_macro_v2") is True
    assert _matches_bot_id(r5, "onnx_macro_v2") is False

    # Check query with "the_onnx_strategy"
    assert _matches_bot_id(r1, "the_onnx_strategy") is True
    assert _matches_bot_id(r2, "dual_onnx") is True


def test_matches_bot_id_3_step_domination():
    """Verify alias resolution for 3-Step Domination."""
    r1 = {"bot_id": "3_step_domination_bot", "bot_type": "3_step_domination_bot"}
    r2 = {"bot_type": "domination", "ai_rationale": "Domination Bot Early Momentum"}
    r3 = {"bot_type": "dominion_2_bot", "ai_rationale": "Dominion 2 Anti-Pin Scalper"}
    r4 = {"bot_type": "dual_onnx"}

    assert _matches_bot_id(r1, "3_step_domination_bot") is True
    assert _matches_bot_id(r2, "3_step_domination_bot") is True
    assert _matches_bot_id(r3, "3_step_domination_bot") is False
    assert _matches_bot_id(r4, "3_step_domination_bot") is False


def test_matches_bot_id_dominion2():
    """Verify alias resolution for Dominion 2."""
    r1 = {"bot_id": "dominion_2_bot", "bot_type": "dominion_2_bot"}
    r2 = {"bot_type": "dominion2"}
    r3 = {"bot_type": "3_step_domination_bot"}

    assert _matches_bot_id(r1, "dominion_2_bot") is True
    assert _matches_bot_id(r2, "dominion_2_bot") is True
    assert _matches_bot_id(r3, "dominion_2_bot") is False


def test_calculate_15m_metrics_math():
    """Verify performance metrics calculation and profit factor."""
    sample_reports = [
        {"outcome": "win", "pnl": 0.52},
        {"outcome": "win", "pnl": 0.50},
        {"outcome": "loss", "pnl": -0.48},
    ]
    m = _calculate_15m_metrics(sample_reports)
    assert m["total_events"] == 3
    assert m["wins"] == 2
    assert m["losses"] == 1
    assert m["win_rate_pct"] == 66.7
    assert m["total_pnl"] == 0.54
    assert m["profit_factor"] == round(1.02 / 0.48, 2)
    assert m["avg_pnl_per_cycle"] == round(0.54 / 3, 2)


def test_calculate_15m_metrics_empty():
    """Verify clean fallback for empty report list."""
    m = _calculate_15m_metrics([])
    assert m["total_events"] == 0
    assert m["wins"] == 0
    assert m["losses"] == 0
    assert m["win_rate_pct"] == 0.0
    assert m["total_pnl"] == 0.0
    assert m["profit_factor"] == 1.0
    assert m["avg_pnl_per_cycle"] == 0.0

import json
from decimal import Decimal
from pathlib import Path
import pytest
from kalshi_sim.ai_assessor import (
    ALLOWED_PARAMETER_BOUNDS,
    extract_json_payload,
    build_assessment_markdown_report,
    apply_validated_tweaks,
)


def test_extract_json_payload():
    md = """Here is the assessment:
```json
{
  "verdict": "PASSED",
  "executive_summary": "Great run.",
  "allowed_tweaks": {"discount_limit_price": 0.46}
}
```
"""
    parsed = extract_json_payload(md)
    assert parsed is not None
    assert parsed["verdict"] == "PASSED"
    assert parsed["allowed_tweaks"]["discount_limit_price"] == 0.46


def test_allowed_parameter_bounds():
    assert "discount_limit_price" in ALLOWED_PARAMETER_BOUNDS
    min_p, max_p = ALLOWED_PARAMETER_BOUNDS["discount_limit_price"]
    assert min_p <= 0.44 <= max_p


def test_build_assessment_markdown_report():
    recent_trades = [
        {
            "ticker": "KXBTC15M-26OCT120000-00",
            "bot_side": "yes",
            "contracts": 1,
            "entry_price": 0.48,
            "settlement_price": 1.00,
            "outcome": "win",
            "net_pnl": 0.52,
            "balance_after": 45.23,
        }
    ]
    gemini_data = {
        "verdict": "PASSED",
        "executive_summary": "Clean victory on high momentum.",
        "winning_trades_autopsy": "Perfect entry timing.",
        "losing_trades_autopsy": "No losses recorded.",
        "probability_calibration_review": "Brier score solid.",
        "validated_tweaks": {"discount_limit_price": 0.46},
        "tweaks_rationale": "Tightened discount floor slightly.",
    }
    report = build_assessment_markdown_report(
        batch_num=109,
        recent_trades=recent_trades,
        batch_pnl=Decimal("0.52"),
        batch_wins=1,
        batch_losses=0,
        pre_balance=Decimal("44.71"),
        post_balance=Decimal("45.23"),
        gemini_data=gemini_data,
        macro_sample={"cumulative_trades": 1, "cumulative_pnl": "0.52", "macro_win_rate": 100.0},
    )
    assert "Batch #109" in report
    assert "Clean victory on high momentum." in report
    assert "`discount_limit_price` = 0.46" in report

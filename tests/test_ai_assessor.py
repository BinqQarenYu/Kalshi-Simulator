import json
from decimal import Decimal
from pathlib import Path
import pytest
from kalshi_sim.ai_assessor import (
    ALLOWED_PARAMETER_BOUNDS,
    extract_json_payload,
    build_assessment_markdown_report,
    apply_validated_tweaks,
    compute_batch_sweetspot_profile,
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


def test_compute_batch_sweetspot_profile():
    recent_trades = [
        {"entry_price": 0.45, "time_to_expiry_s": 420.0, "outcome": "win", "pnl": 0.55, "bot_side": "yes"},
        {"entry_price": 0.46, "time_to_expiry_s": 350.0, "outcome": "win", "pnl": 0.54, "bot_side": "yes"},
        {"entry_price": 0.40, "time_to_expiry_s": 700.0, "outcome": "win", "pnl": 0.60, "bot_side": "no"},
        {"entry_price": 0.55, "time_to_expiry_s": 120.0, "outcome": "loss", "pnl": -0.55, "bot_side": "yes"},
        {"entry_price": 0.54, "time_to_expiry_s": 150.0, "outcome": "loss", "pnl": -0.54, "bot_side": "yes"},
        {"entry_price": 0.47, "time_to_expiry_s": 480.0, "outcome": "win", "pnl": 0.53, "bot_side": "no"},
    ]
    profile = compute_batch_sweetspot_profile(recent_trades, asset="BTC")
    assert profile["asset"] == "BTC"
    assert "PRIME_SWEETSPOT ($0.44-$0.48)" in profile["price_buckets"]
    prime = profile["price_buckets"]["PRIME_SWEETSPOT ($0.44-$0.48)"]
    assert prime["wins"] == 3
    assert prime["losses"] == 0
    assert Decimal(prime["pnl"]) == Decimal("1.62")

    high = profile["price_buckets"]["HIGH_CEILING (>$0.52)"]
    assert high["wins"] == 0
    assert high["losses"] == 2

    assert "PRIME_SWEETSPOT" in profile["best_price_corridor"]
    assert "HIGH_CEILING" in profile["worst_price_corridor"]
    assert "PIN_ZONE" in profile["worst_tau_window"]
    assert profile["yes_record"] == "2W - 2L"
    assert profile["no_record"] == "2W - 0L"
    assert 0.44 <= profile["avg_win_entry"] <= 0.48
    assert 0.54 <= profile["avg_loss_entry"] <= 0.55


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
            "time_to_expiry_s": 450.0,
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
    assert "2.2. Empirical Sweetspot & Orderbook Corridor Profile" in report
    assert "Optimal Entry Sweetspot:" in report
    assert "Optimal Tau Timing Window:" in report

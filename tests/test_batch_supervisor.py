import asyncio
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.batch_supervisor import AutonomousBatchSupervisor


@pytest.mark.asyncio
async def test_batch_supervisor_workflow(tmp_path):
    guard = AgentGuardrails()
    guard.batch_trades_completed = 6
    guard.batch_trades_quota = 6
    guard.batch_pnl = Decimal("0.85")
    guard.batch_wins = 4
    guard.batch_losses = 2

    # Mock parameters file
    params_file = tmp_path / "bot_parameters_domination.json"
    params_file.write_text(
        json.dumps({
            "assets": {
                "BTC": {
                    "discount_limit_price": 0.44,
                    "min_confidence": 79.0,
                    "min_ev_dollars": 0.02,
                }
            }
        }),
        encoding="utf-8"
    )

    # Mock win_loss reports
    wl_file = tmp_path / "win_loss_reports.json"
    wl_file.write_text(
        json.dumps([
            {
                "ticker": f"KXBTC15M-T{i}",
                "bot_side": "yes",
                "contracts": 1,
                "entry_price": 0.48,
                "settlement_price": 1.00 if i <= 4 else 0.00,
                "outcome": "win" if i <= 4 else "loss",
                "pnl": 0.52 if i <= 4 else -0.48,
                "balance_after": 40.0 + i,
            }
            for i in range(1, 7)
        ]),
        encoding="utf-8"
    )

    supervisor = AutonomousBatchSupervisor(
        guardrails=guard,
        bot_parameters_path=params_file,
        win_loss_path=wl_file,
        eval_batch_size=6,
    )

    # Mock Gemini call
    mock_gemini_res = {
        "verdict": "PASSED",
        "executive_summary": "6 trades executed with 4 wins, batch +$0.85 profit.",
        "winning_trades_autopsy": "Strong edge captured.",
        "losing_trades_autopsy": "Normal chop variance.",
        "probability_calibration_review": "Brier score healthy.",
        "allowed_tweaks": {"discount_limit_price": 0.46},
        "validated_tweaks": {"discount_limit_price": 0.46},
        "tweaks_rationale": "Tightened entry discount floor to capture more fills.",
    }

    with patch("kalshi_sim.ai_assessor.run_gemini_batch_assessment", AsyncMock(return_value=mock_gemini_res)):
        with patch("kalshi_sim.aws_email_mailer.async_send_assessment_email", AsyncMock(return_value=True)):
            await supervisor._evaluate_and_evolve_batch()

    # Verify quota reset & re-arm
    assert guard.batch_trades_completed == 0
    assert guard.is_bot_armed is True
    assert supervisor.cumulative_trades == 6
    assert supervisor.cumulative_wins == 4

    # Verify parameter tweak applied to disk
    updated_params = json.loads(params_file.read_text(encoding="utf-8"))
    assert updated_params["assets"]["BTC"]["discount_limit_price"] == 0.46

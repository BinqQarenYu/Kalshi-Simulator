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
        docs_dir=tmp_path / "docs",
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

    mock_mailer = AsyncMock(return_value=True)
    with patch("kalshi_sim.ai_assessor.run_gemini_batch_assessment", AsyncMock(return_value=mock_gemini_res)):
        with patch("kalshi_sim.aws_email_mailer.async_send_assessment_email", mock_mailer):
            await supervisor._evaluate_and_evolve_batch()

    # Verify mailer called with market condition in subject and kwargs
    assert mock_mailer.called
    call_kwargs = mock_mailer.call_args.kwargs
    assert "market_condition" in call_kwargs
    assert call_kwargs["market_condition"] in ("CHOPPY", "STORMY", "BLEED", "HEALING")
    subject = mock_mailer.call_args.kwargs.get("subject", "")
    assert "Condition:" in subject

    # Verify quota reset & re-arm
    assert guard.batch_trades_completed == 0
    assert guard.is_bot_armed is True
    assert supervisor.cumulative_trades == 6
    assert supervisor.cumulative_wins == 4

    # Verify parameter tweak applied to disk
    updated_params = json.loads(params_file.read_text(encoding="utf-8"))
    assert updated_params["assets"]["BTC"]["discount_limit_price"] == 0.46


@pytest.mark.asyncio
async def test_batch_supervisor_trade_id_persistence_and_backlog_draining(tmp_path):
    """Verify unique trade ID persistence survives restarts and drains backlogs in 6-trade batches."""
    params_file = tmp_path / "bot_parameters_domination.json"
    params_file.write_text(json.dumps({"assets": {"BTC": {"discount_limit_price": 0.45}}}), encoding="utf-8")

    # 15 total trades (Backlog: Batch 1 has trades 1-6, Batch 2 has trades 7-12, remaining: 13-15)
    trades = [
        {
            "report_id": f"WLR-BTC-TEST-{i:03d}",
            "ticker": f"KXBTC15M-T{i}",
            "outcome": "win" if i % 2 == 0 else "loss",
            "pnl": 0.50 if i % 2 == 0 else -0.50,
            "balance_after": 25.0 + (0.50 if i % 2 == 0 else -0.50),
            "timestamp_utc": f"2026-10-19T01:{i:02d}:00Z",
        }
        for i in range(1, 16)
    ]
    # Win-loss reports stored newest first
    wl_file = tmp_path / "win_loss_reports.json"
    wl_file.write_text(json.dumps(list(reversed(trades))), encoding="utf-8")

    supervisor = AutonomousBatchSupervisor(
        bot_parameters_path=params_file,
        win_loss_path=wl_file,
        docs_dir=tmp_path / "docs",
        eval_batch_size=6,
        asset="BTC",
    )

    unprocessed = supervisor._get_unprocessed_trades()
    assert len(unprocessed) == 15
    # Chronological sort verification: oldest trade is first
    assert unprocessed[0]["report_id"] == "WLR-BTC-TEST-001"
    assert unprocessed[-1]["report_id"] == "WLR-BTC-TEST-015"

    mock_gemini = AsyncMock(return_value={"verdict": "PASSED", "executive_summary": "Passed batch."})
    mock_mailer = AsyncMock(return_value=True)

    # Process Batch 1
    batch1 = unprocessed[:6]
    with patch("kalshi_sim.ai_assessor.run_gemini_batch_assessment", mock_gemini), \
         patch("kalshi_sim.aws_email_mailer.async_send_assessment_email", mock_mailer):
        await supervisor._evaluate_and_evolve_batch(batch_trades=batch1)

    # Check state file persisted
    state_file = tmp_path / "supervisor_processed_trades_btc.json"
    assert state_file.exists()
    persisted_ids = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(persisted_ids) == 6
    assert "WLR-BTC-TEST-001" in persisted_ids

    # Unprocessed trades should now be 9
    remaining = supervisor._get_unprocessed_trades()
    assert len(remaining) == 9
    assert remaining[0]["report_id"] == "WLR-BTC-TEST-007"

    # Simulate process restart by instantiating new supervisor
    supervisor_restarted = AutonomousBatchSupervisor(
        bot_parameters_path=params_file,
        win_loss_path=wl_file,
        docs_dir=tmp_path / "docs",
        eval_batch_size=6,
        asset="BTC",
    )
    assert len(supervisor_restarted._processed_trade_ids) == 6
    unprocessed_after_restart = supervisor_restarted._get_unprocessed_trades()
    assert len(unprocessed_after_restart) == 9

    # Process Batch 2
    batch2 = unprocessed_after_restart[:6]
    with patch("kalshi_sim.ai_assessor.run_gemini_batch_assessment", mock_gemini), \
         patch("kalshi_sim.aws_email_mailer.async_send_assessment_email", mock_mailer):
        await supervisor_restarted._evaluate_and_evolve_batch(batch_trades=batch2)

    # Remaining should now be 3 (< 6, waiting for next cycle)
    final_remaining = supervisor_restarted._get_unprocessed_trades()
    assert len(final_remaining) == 3


@pytest.mark.asyncio
async def test_batch_supervisor_eth_isolation_and_zero_float(tmp_path):
    """Verify ETH supervisor strictly isolates ETH contracts and enforces Zero Float Decimal math."""
    params_file = tmp_path / "bot_parameters_domination.json"
    params_file.write_text(json.dumps({"eth_bot1_v4": {"discount_limit_price": 0.46}}), encoding="utf-8")

    mixed_trades = [
        # 6 ETH trades
        {
            "report_id": f"WLR-ETH-{i}",
            "ticker": f"KXETH15M-T{i}",
            "asset": "ETH",
            "outcome": "win",
            "pnl": 0.10,
            "balance_after": 25.0 + (i * 0.10),
            "timestamp_utc": f"2026-10-19T02:{i:02d}:00Z",
        }
        for i in range(1, 7)
    ] + [
        # 6 BTC trades that should be ignored by ETH supervisor
        {
            "report_id": f"WLR-BTC-{i}",
            "ticker": f"KXBTC15M-T{i}",
            "asset": "BTC",
            "outcome": "loss",
            "pnl": -0.50,
            "balance_after": 20.0,
            "timestamp_utc": f"2026-10-19T02:{i:02d}:30Z",
        }
        for i in range(1, 7)
    ]

    eth_wl_file = tmp_path / "eth_win_loss_reports.json"
    eth_wl_file.write_text(json.dumps(mixed_trades), encoding="utf-8")

    eth_supervisor = AutonomousBatchSupervisor(
        bot_parameters_path=params_file,
        win_loss_path=eth_wl_file,
        docs_dir=tmp_path / "docs",
        eval_batch_size=6,
        asset="ETH",
    )

    unprocessed = eth_supervisor._get_unprocessed_trades()
    assert len(unprocessed) == 6
    assert all("ETH" in t["ticker"] for t in unprocessed)

    mock_gemini = AsyncMock(return_value={"verdict": "PASSED", "executive_summary": "ETH batch passed."})
    mock_mailer = AsyncMock(return_value=True)

    with patch("kalshi_sim.ai_assessor.run_gemini_batch_assessment", mock_gemini), \
         patch("kalshi_sim.aws_email_mailer.async_send_assessment_email", mock_mailer):
        await eth_supervisor._evaluate_and_evolve_batch(batch_trades=unprocessed)

    # Check Zero Float Decimal Math (0.10 * 6 = 0.60 exactly, not 0.6000000000000001)
    assert eth_supervisor.cumulative_pnl == Decimal("0.60")
    assert eth_supervisor.cumulative_wins == 6
    assert eth_supervisor.cumulative_losses == 0

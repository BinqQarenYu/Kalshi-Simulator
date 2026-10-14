"""Unit tests for strict asset-level isolation across historical assessment, buffers, and queries.

Enforces Council Law & User Directives:
- BTC 15M bots must never fetch or be calibrated by ETH historical data.
- ETH bots must never fetch or be calibrated by BTC historical data.
- Batch supervisor, experience buffer, historical query service, and analytics routers
  must strictly exclude unrelated assets.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from kalshi_sim.db.queries import HistoricalQueryService
from kalshi_sim.ml.experience_buffer import ContinuousExperienceBuffer, CycleExperience
from kalshi_sim.batch_supervisor import AutonomousBatchSupervisor
from kalshi_sim.ai_assessor import build_assessment_markdown_report
from kalshi_sim.routers.analytics import _is_asset_match


def test_experience_buffer_asset_isolation(tmp_path: Path) -> None:
    """Verify that ContinuousExperienceBuffer strictly filters initial load and live updates by asset."""
    hist_file = tmp_path / "mixed_win_loss_reports.json"
    buffer_file = tmp_path / "test_buffer.json"

    # Mixed history with both BTC and ETH
    mixed_data = [
        {"report_id": "r_btc_1", "ticker": "KXBTC15M-26OCT14-T68000", "asset": "BTC", "outcome": "win", "pnl": 0.50},
        {"report_id": "r_eth_1", "ticker": "KXETH15M-26OCT14-T2600", "asset": "ETH", "outcome": "loss", "pnl": -0.40},
        {"report_id": "r_btc_2", "ticker": "KXBTC15M-26OCT14-T68200", "asset": "BTC", "outcome": "win", "pnl": 0.45},
        {"report_id": "r_eth_2", "ticker": "KXETH15M-26OCT14-T2620", "asset": "ETH", "outcome": "win", "pnl": 0.60},
    ]
    hist_file.write_text(json.dumps(mixed_data), encoding="utf-8")

    # 1. Initialize BTC Buffer
    btc_buf = ContinuousExperienceBuffer(
        max_buffer_size=50,
        history_file=hist_file,
        asset="BTC",
    )
    # Verify initial load contains ONLY BTC
    assert len(btc_buf.experiences) == 2
    for exp in btc_buf.experiences:
        assert "BTC" in exp.ticker
        assert "ETH" not in exp.ticker

    # Test live rejection of ETH experience in BTC buffer
    eth_exp = CycleExperience(
        cycle_id="c_eth_test",
        ticker="KXETH15M-26OCT14-T2650",
        timestamp_utc="2026-10-14T10:00:00Z",
        strike_price=2650.0,
        settlement_spot=2655.0,
        spot_diff=5.0,
        bot_side="yes",
        entry_price=0.40,
        contracts=1,
        predicted_prob=0.8,
        outcome="win",
        net_pnl=0.60,
        fees=0.01,
        execution_mode="live",
    )
    btc_buf.record_settled_cycle(eth_exp)
    assert len(btc_buf.experiences) == 2  # Not added!

    btc_exp = CycleExperience(
        cycle_id="c_btc_test",
        ticker="KXBTC15M-26OCT14-T69000",
        timestamp_utc="2026-10-14T10:00:00Z",
        strike_price=69000.0,
        settlement_spot=69050.0,
        spot_diff=50.0,
        bot_side="yes",
        entry_price=0.45,
        contracts=1,
        predicted_prob=0.75,
        outcome="win",
        net_pnl=0.55,
        fees=0.01,
        execution_mode="live",
    )
    btc_buf.record_settled_cycle(btc_exp)
    assert len(btc_buf.experiences) == 3  # Successfully added!

    # 2. Initialize ETH Buffer
    eth_buf = ContinuousExperienceBuffer(
        max_buffer_size=50,
        history_file=hist_file,
        asset="ETH",
    )
    # Verify initial load contains ONLY ETH
    assert len(eth_buf.experiences) == 2
    for exp in eth_buf.experiences:
        assert "ETH" in exp.ticker
        assert "BTC" not in exp.ticker

    # Test live rejection of BTC experience in ETH buffer
    eth_buf.record_settled_cycle(btc_exp)
    assert len(eth_buf.experiences) == 2  # Not added!

    eth_buf.record_settled_cycle(eth_exp)
    assert len(eth_buf.experiences) == 3  # Successfully added!


def test_batch_supervisor_asset_isolation(tmp_path: Path) -> None:
    """Verify that AutonomousBatchSupervisor filters out trades from foreign assets."""
    mock_guardrails = MagicMock()
    btc_supervisor = AutonomousBatchSupervisor(
        guardrails=mock_guardrails,
        win_loss_path=tmp_path / "win_loss.json",
        eval_batch_size=6,
        asset="BTC",
    )
    eth_supervisor = AutonomousBatchSupervisor(
        guardrails=mock_guardrails,
        win_loss_path=tmp_path / "eth_win_loss.json",
        eval_batch_size=6,
        asset="ETH",
    )

    btc_trade = {"ticker": "KXBTC15M-26OCT14-T68000", "asset": "BTC"}
    eth_trade = {"ticker": "KXETH15M-26OCT14-T2600", "asset": "ETH"}

    # BTC Supervisor checks
    assert btc_supervisor._is_asset_match(btc_trade) is True
    assert btc_supervisor._is_asset_match(eth_trade) is False

    # ETH Supervisor checks
    assert eth_supervisor._is_asset_match(btc_trade) is False
    assert eth_supervisor._is_asset_match(eth_trade) is True


def test_historical_query_service_db_routing() -> None:
    """Verify that HistoricalQueryService dynamically resolves the correct DB manager based on asset."""
    qs = HistoricalQueryService()

    # Default / BTC routes to kalshi_history.db
    btc_mgr = qs._resolve_db_manager(asset="BTC")
    assert "kalshi_history.db" in str(btc_mgr.db_path)
    assert "kalshi_history_eth.db" not in str(btc_mgr.db_path)

    # ETH routes to kalshi_history_eth.db
    eth_mgr = qs._resolve_db_manager(asset="ETH")
    assert "kalshi_history_eth.db" in str(eth_mgr.db_path)

    # Ticker-based routing
    btc_ticker_mgr = qs._resolve_db_manager(ticker="KXBTC15M-26OCT14-T68000")
    assert "kalshi_history.db" in str(btc_ticker_mgr.db_path)
    assert "kalshi_history_eth.db" not in str(btc_ticker_mgr.db_path)

    eth_ticker_mgr = qs._resolve_db_manager(ticker="KXETH15M-26OCT14-T2600")
    assert "kalshi_history_eth.db" in str(eth_ticker_mgr.db_path)

    # Bot-type based routing
    eth_bot_mgr = qs._resolve_db_manager(bot_type="eth_bot1v4")
    assert "kalshi_history_eth.db" in str(eth_bot_mgr.db_path)


def test_analytics_router_asset_matching() -> None:
    """Verify that _is_asset_match strictly isolates BTC vs ETH reports."""
    btc_report = {"ticker": "KXBTC15M-26OCT14-T68000", "asset": "BTC", "bot_type": "3_step_domination_bot"}
    eth_report = {"ticker": "KXETH15M-26OCT14-T2600", "asset": "ETH", "bot_type": "eth_bot1v4"}

    # BTC isolation
    assert _is_asset_match(btc_report, "BTC") is True
    assert _is_asset_match(eth_report, "BTC") is False

    # ETH isolation
    assert _is_asset_match(btc_report, "ETH") is False
    assert _is_asset_match(eth_report, "ETH") is True


def test_ai_assessor_markdown_report_asset_headers() -> None:
    """Verify that markdown reports are tailored to target asset."""
    sample_trades = [
        {"ticker": "KXETH15M-26OCT14-T2600", "bot_side": "YES", "contracts": 1, "entry_price": 0.40, "pnl": 0.60, "outcome": "win"}
    ]
    gemini_data = {
        "verdict": "PASSED",
        "executive_summary": "ETH test assessment passed.",
    }

    report = build_assessment_markdown_report(
        batch_num=1,
        recent_trades=sample_trades,
        batch_pnl=Decimal("0.60"),
        batch_wins=1,
        batch_losses=0,
        pre_balance=Decimal("35.00"),
        post_balance=Decimal("35.60"),
        gemini_data=gemini_data,
        macro_sample={},
        asset="ETH",
    )

    assert "Batch #1 (ETH)" in report
    assert "Ethereum Binary Options" in report
    assert "Bot 1 V4 (ETH Domination Engine)" in report
    assert "Bitcoin Binary Options" not in report

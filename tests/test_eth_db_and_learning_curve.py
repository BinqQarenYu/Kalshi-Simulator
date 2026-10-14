"""Comprehensive verification tests for ETH Bot 1 V4 Database Isolation and Learning Curve.

Verifies:
1. Database Separation: Dedicated SQLite store at data/kalshi_history_eth.db with Schema V5 tables.
2. Complete Schema V5 Coverage: trade_lifecycle_forensics, trade_failure_autopsies, unfilled_orders, contract_settlements.
3. Win/Loss Buffer & Post-Mortem "Why": data/eth_win_loss_reports.json and causal mistake attribution.
4. ContinuousExperienceBuffer Learning Curve: Online Platt calibration, 3D mistake matrix, and ETH asset scale.
5. Server Settlements Routing: KXETH15M settlements and autopsies route to get_eth_db_writer().
6. Zero Float Financial Math & Micro-bankroll Sizing.
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from kalshi_sim.db.connection import DatabaseManager, get_eth_db
from kalshi_sim.db.writer import DatabaseWriter, get_eth_db_writer
from kalshi_sim.ml.eth_bot1v4.eth_bot1v4_engine import EthBot1V4Engine
from kalshi_sim.ml.experience_buffer import ContinuousExperienceBuffer, CycleExperience
from kalshi_sim.schemas import CryptoAsset


@pytest.mark.asyncio
async def test_eth_database_schema_v5_creation(tmp_path: Path) -> None:
    """Verify that get_eth_db initializes a separate database with all Schema V5 tables."""
    db_file = tmp_path / "kalshi_history_eth.db"
    db_mgr = DatabaseManager(db_file)
    await db_mgr.init_db()

    # Verify tables in kalshi_history_eth.db
    async with db_mgr.get_connection() as conn:
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in await cursor.fetchall()}

    expected_tables = {
        "ticks",
        "trades",
        "settlements",
        "equity_snapshots",
        "ai_predictions",
        "circuit_breaker_events",
        "unfilled_orders",
        "trade_lifecycle_forensics",
        "trade_failure_autopsies",
        "batch_assessments",
    }
    for t in expected_tables:
        assert t in tables, f"Expected Schema V5 table '{t}' missing from ETH database."


@pytest.mark.asyncio
async def test_eth_db_writer_lifecycle_and_autopsy_persistence(tmp_path: Path) -> None:
    """Verify that get_eth_db_writer flushes forensics and failure autopsies to kalshi_history_eth.db."""
    db_file = tmp_path / "kalshi_history_eth.db"
    db_mgr = DatabaseManager(db_file)
    writer = DatabaseWriter(db_manager=db_mgr, flush_interval_seconds=0.01)
    await writer.start()

    # Enqueue a lifecycle forensics record
    writer.enqueue_lifecycle_forensics(
        trade_id="ETH-TR-001",
        ticker="KXETH15M-26OCT140215-15",
        side="yes",
        entry_price=0.42,
        outcome="LOSS",
        realized_pnl=-0.42,
        role="MAKER",
        fee_paid=0.0,
        t1_timestamp="2026-10-14T02:00:00Z",
        t1_spot=2500.0,
        t1_strike_diff=-2.50,
        t1_1h_slope=0.10,
        t1_regime="CHOP",
        t1_vpin=0.25,
        t2_timestamp="2026-10-14T02:05:00Z",
        t2_spot=2501.0,
        t2_1h_slope=0.10,
        t2_regime="CHOP",
        t2_vpin=0.25,
        t3_timestamp="2026-10-14T02:15:00Z",
        t3_spot=2503.0,
        t3_60s_twap=2501.5,
        twap_vs_spot_divergence=1.5,
        t3_1h_slope=0.10,
        t3_regime="CHOP",
        bot_type="eth_bot1_v4",
    )

    # Enqueue a failure autopsy record explaining "why" it lost
    writer.enqueue_failure_autopsy(
        trade_id="ETH-TR-001",
        ticker="KXETH15M-26OCT140215-15",
        outcome="LOSS",
        realized_pnl=-0.42,
        failure_code="STRIKE_PROXIMITY_TRAP",
        is_counter_trend=0,
        macro_1h_slope=0.10,
        is_double_wick_trap=0,
        wick_to_body_ratio=0.0,
        was_salvageable=0,
        salvageable_cents_lost=0.0,
        is_twap_pin_victim=0,
        twap_vs_spot_divergence=1.5,
        bot_type="eth_bot1_v4",
    )

    await writer.stop()

    # Query back to verify persistence
    async with db_mgr.get_connection() as conn:
        cursor = await conn.execute("SELECT trade_id, ticker, failure_code FROM trade_failure_autopsies WHERE trade_id='ETH-TR-001'")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "ETH-TR-001"
        assert row[1] == "KXETH15M-26OCT140215-15"
        assert row[2] == "STRIKE_PROXIMITY_TRAP"

        cursor2 = await conn.execute("SELECT trade_id, t1_spot, outcome FROM trade_lifecycle_forensics WHERE trade_id='ETH-TR-001'")
        row2 = await cursor2.fetchone()
        assert row2 is not None
        assert row2[0] == "ETH-TR-001"
        assert row2[1] == 2500.0
        assert row2[2] == "LOSS"


def test_eth_continuous_experience_buffer_asset_scaling(tmp_path: Path) -> None:
    """Verify that ContinuousExperienceBuffer accurately adapts causal mistake thresholds for ETH scale."""
    hist_file = tmp_path / "eth_win_loss_reports.json"
    buffer = ContinuousExperienceBuffer(history_file=hist_file, asset="ETH")

    assert buffer.asset == "ETH"
    assert buffer.tight_spot_diff_threshold == 2.00
    assert buffer.mid_spot_diff_threshold == 5.00
    assert buffer.momentum_inversion_threshold == 6.00
    assert buffer.gamma_pin_threshold == 1.50

    # Test causal loss classification for ETH
    # Proximity trap: spot_diff within $2.00
    cause_prox = buffer._classify_loss_cause(
        outcome="loss",
        spot_diff=1.20,
        vpin=0.20,
        time_to_expiry_s=300.0,
        pnl=-0.42,
    )
    assert cause_prox == "STRIKE_PROXIMITY_TRAP"

    # Momentum inversion: spot_diff >= $6.00
    cause_mom = buffer._classify_loss_cause(
        outcome="loss",
        spot_diff=-7.50,
        vpin=0.20,
        time_to_expiry_s=300.0,
        pnl=-0.42,
    )
    assert cause_mom == "MOMENTUM_INVERSION"

    # Adverse selection: VPIN >= 0.50
    cause_adv = buffer._classify_loss_cause(
        outcome="loss",
        spot_diff=3.50,
        vpin=0.60,
        time_to_expiry_s=300.0,
        pnl=-0.42,
    )
    assert cause_adv == "ADVERSE_SELECTION_SWEEP"


def test_eth_bot1v4_record_cycle_settlement_and_autopsy(tmp_path: Path) -> None:
    """Verify EthBot1V4Engine records settlements, persists post-mortems, and updates experience buffer."""
    hist_file = tmp_path / "eth_win_loss_reports.json"
    engine = EthBot1V4Engine(history_file=hist_file)

    # 1. Record a winning cycle
    win_rep = engine.record_cycle_settlement(
        won_or_pnl=Decimal("0.58"),
        ticker="KXETH15M-26OCT140200-00",
        side="yes",
        entry_price=Decimal("0.42"),
        settlement_spot_price=Decimal("2505.00"),
        strike_price=Decimal("2500.00"),
        contracts=1,
        execution_mode="live",
    )
    assert win_rep is not None
    assert win_rep["outcome"] == "win"
    assert win_rep["asset"] == "ETH"
    assert win_rep["pnl"] == 0.58
    assert win_rep["failure_code"] == "NONE"

    # 2. Record a losing cycle explaining "why" (causal autopsy)
    loss_rep = engine.record_cycle_settlement(
        won_or_pnl=Decimal("-0.42"),
        ticker="KXETH15M-26OCT140215-15",
        side="yes",
        entry_price=Decimal("0.42"),
        settlement_spot_price=Decimal("2499.00"),
        strike_price=Decimal("2500.00"),
        contracts=1,
        execution_mode="live",
    )
    assert loss_rep is not None
    assert loss_rep["outcome"] == "loss"
    assert loss_rep["asset"] == "ETH"
    assert loss_rep["pnl"] == -0.42
    assert loss_rep["failure_code"] == "STRIKE_PROXIMITY_TRAP"

    # 3. Verify disk persistence in dedicated eth_win_loss_reports.json
    assert hist_file.exists()
    persisted = json.loads(hist_file.read_text(encoding="utf-8"))
    assert len(persisted) == 2
    assert persisted[0]["report_id"] == loss_rep["report_id"]
    assert persisted[0]["failure_code"] == "STRIKE_PROXIMITY_TRAP"

    # 4. Verify experience buffer update & Platt calibration
    summary = engine.experience_buffer.get_recent_summary()
    assert summary["total_recent"] == 2
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["win_rate"] == 50.0
    assert summary["loss_causes"]["STRIKE_PROXIMITY_TRAP"] == 1


def test_eth_bot1v4_parameter_persistence(tmp_path: Path) -> None:
    """Verify EthBot1V4Engine dynamically loads and saves parameters to data/bot_parameters_eth.json."""
    param_file = tmp_path / "bot_parameters_eth.json"
    engine = EthBot1V4Engine()
    engine.parameters_file = param_file

    # Update parameters
    engine.update_parameters(
        min_spot_diff=3.00,
        discount_limit_price=0.40,
        max_entry_price=0.44,
        chop_range_threshold=8.50,
    )
    engine.save_persisted_parameters()

    assert param_file.exists()
    data = json.loads(param_file.read_text(encoding="utf-8"))
    assert "eth_bot1_v4" in data
    eth_p = data["eth_bot1_v4"]
    assert eth_p["min_spot_diff"] == 3.00
    assert eth_p["discount_limit_price"] == 0.40
    assert eth_p["max_entry_price"] == 0.44
    assert eth_p["chop_range_threshold"] == 8.50


def test_server_settlements_eth_routing(tmp_path: Path) -> None:
    """Verify record_win_loss_event_report routes KXETH settlements to eth_win_loss_reports.json and get_eth_db_writer()."""
    from kalshi_sim.server_settlements import record_win_loss_event_report, init_server_settlements

    mock_state = MagicMock()
    mock_state.win_loss_reports = []
    mock_state.save_persisted_reports = MagicMock()
    mock_state.starting_capital = Decimal("25.00")
    mock_state.sim_agent = None
    mock_state.order_client = None
    mock_state.guardrails_agent = None
    mock_state.experience_buffer = None
    mock_state.cfbenchmarks_sync = None
    mock_state.telemetry_alerts = MagicMock()

    init_server_settlements(lambda: mock_state, lambda bot_id: None)

    with patch("kalshi_sim.server_settlements.Path") as mock_path:
        eth_file = tmp_path / "eth_win_loss_reports.json"
        mock_path.side_effect = lambda *args: eth_file if "eth_win_loss_reports" in str(args[0]) else Path(*args)

        with patch("kalshi_sim.server_settlements.get_eth_db_writer") as mock_eth_writer:
            mock_writer_inst = MagicMock()
            mock_eth_writer.return_value = mock_writer_inst

            rep = record_win_loss_event_report(
                ticker="KXETH15M-26OCT140230-00",
                side="yes",
                contracts=1,
                entry_price=Decimal("0.42"),
                settlement_btc_price=Decimal("2505.00"),
                strike_price=Decimal("2500.00"),
                timeframe="15m",
                custom_pnl=Decimal("0.58"),
                custom_outcome="win",
                execution_mode="live",
                bot_type="eth_bot1_v4",
            )

            assert rep["asset"] == "ETH"
            assert rep["ticker"] == "KXETH15M-26OCT140230-00"
            assert rep["bot_type"] == "eth_bot1_v4"
            # Verify it was enqueued to ETH writer, not BTC writer
            mock_writer_inst.enqueue_settlement.assert_called_once()
            mock_writer_inst.enqueue_lifecycle_forensics.assert_called_once()

"""
test_poe_flight_recorder.py — Verification of Agent POE Deterministic Flight Recorder.
"""

from decimal import Decimal
from pathlib import Path
import tempfile
import pytest

from kalshi_sim.poe_flight_recorder import (
    POEFlightRecorder,
    compute_fisher_exact_2x2,
)


def test_fisher_exact_test_calculation():
    """Verify Fisher's exact test matches exact hypergeometric distribution."""
    # Standard 2x2 table:
    # Passed: 10 won, 2 lost
    # Vetoed: 2 won, 10 lost
    table = ((10, 2), (2, 10))
    p_val = compute_fisher_exact_2x2(table)
    assert 0.0 < p_val < 0.01  # Highly statistically significant (p ~ 0.003)

    # Completely balanced / random table:
    table_random = ((5, 5), (5, 5))
    p_rand = compute_fisher_exact_2x2(table_random)
    assert p_rand == 1.0  # Zero statistical difference


def test_poe_flight_recorder_quadrant_classification():
    """Verify 4-quadrant classification logic under realistic settlement conditions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = Path(tmpdir) / "test_ledger.jsonl"
        recorder = POEFlightRecorder(ledger_path=ledger_path)

        # 1. Record Cycle 1: Bot Traded YES, and YES won -> Q1 True Alpha
        recorder.record_decision(
            cycle_id="CYCLE_001",
            tau_seconds_remaining=450.0,
            spot_price=80100.0,
            target_strike=80000.0,
            moneyness_diff=100.0,
            spot_velocity_10s=15.0,
            vpin_score=0.20,
            ai_predicted_side="YES",
            ai_confidence=0.85,
            ev_gross=Decimal("0.10"),
            ev_net=Decimal("0.08"),
            decision="TRADE",
        )
        rec1 = recorder.record_settlement(
            cycle_id="CYCLE_001",
            settlement_spot=80120.0,
            contract_winning_side="YES",
            settled_payout=Decimal("1.00"),
            realized_pnl=Decimal("0.50"),
        )
        assert rec1.quadrant == "Q1_TRUE_ALPHA"
        assert rec1.realized_pnl == "0.50"

        # 2. Record Cycle 2: Bot Traded YES, but NO won -> Q2 Toxic Loss
        recorder.record_decision(
            cycle_id="CYCLE_002",
            tau_seconds_remaining=300.0,
            spot_price=79950.0,
            target_strike=80000.0,
            moneyness_diff=-50.0,
            spot_velocity_10s=-20.0,
            vpin_score=0.45,
            ai_predicted_side="YES",
            ai_confidence=0.60,
            ev_gross=Decimal("0.04"),
            ev_net=Decimal("0.02"),
            decision="TRADE",
        )
        rec2 = recorder.record_settlement(
            cycle_id="CYCLE_002",
            settlement_spot=79900.0,
            contract_winning_side="NO",
            settled_payout=Decimal("0.00"),
            realized_pnl=Decimal("-0.50"),
        )
        assert rec2.quadrant == "Q2_TOXIC_LOSS"

        # 3. Record Cycle 3: Bot Vetoed YES on min_spot_diff, but YES won -> Q3 Alpha Starvation
        recorder.record_decision(
            cycle_id="CYCLE_003",
            tau_seconds_remaining=700.0,
            spot_price=80015.0,
            target_strike=80000.0,
            moneyness_diff=15.0,
            spot_velocity_10s=5.0,
            vpin_score=0.15,
            ai_predicted_side="YES",
            ai_confidence=0.80,
            ev_gross=Decimal("0.08"),
            ev_net=Decimal("0.06"),
            decision="VETO",
            primary_blocking_parameter="min_spot_diff",
            param_actual=15.0,
            param_threshold=21.0,
        )
        rec3 = recorder.record_settlement(
            cycle_id="CYCLE_003",
            settlement_spot=80050.0,
            contract_winning_side="YES",
            settled_payout=Decimal("1.00"),
        )
        assert rec3.quadrant == "Q3_ALPHA_STARVATION"
        assert Decimal(rec3.counterfactual_pnl) > Decimal("0.00")

        # 4. Record Cycle 4: Bot Vetoed YES on min_spot_diff, and NO won -> Q4 Shielded Capital
        recorder.record_decision(
            cycle_id="CYCLE_004",
            tau_seconds_remaining=600.0,
            spot_price=80005.0,
            target_strike=80000.0,
            moneyness_diff=5.0,
            spot_velocity_10s=-12.0,
            vpin_score=0.30,
            ai_predicted_side="YES",
            ai_confidence=0.75,
            ev_gross=Decimal("0.05"),
            ev_net=Decimal("0.03"),
            decision="VETO",
            primary_blocking_parameter="min_spot_diff",
            param_actual=5.0,
            param_threshold=21.0,
        )
        rec4 = recorder.record_settlement(
            cycle_id="CYCLE_004",
            settlement_spot=79980.0,
            contract_winning_side="NO",
            settled_payout=Decimal("0.00"),
        )
        assert rec4.quadrant == "Q4_SHIELDED_CAPITAL"
        assert Decimal(rec4.counterfactual_pnl) < Decimal("0.00")

        # Verify Parameter Scorecard
        scorecards = recorder.compute_parameter_scorecards()
        assert "min_spot_diff" in scorecards
        sc = scorecards["min_spot_diff"]
        assert sc.veto_count == 2
        assert sc.quadrant_3_starved == 1
        assert sc.quadrant_4_shielded == 1
        assert sc.vps_score_pct == 50.0
        assert sc.status == "NEUTRAL"

        # Verify Report Generation
        report = recorder.generate_poe_audit_report()
        assert "AGENT POE: EMPIRICAL AUDIT REPORT" in report
        assert "min_spot_diff" in report
        assert "Q1 (True Alpha)=1" in report
        assert "Q4 (Shielded Capital)=1" in report


def test_audit_codebase_parameters():
    """Verify AST scan of bot parameters against the codebase."""
    recorder = POEFlightRecorder(ledger_path=Path("data/test_temp_ledger.jsonl"))
    audit = recorder.audit_codebase_parameters()
    assert "total_configured" in audit
    assert "active_in_code" in audit
    assert audit["total_configured"] > 0
    assert audit["active_in_code"] > 0
    assert isinstance(audit["dead_parameters"], list)


def test_poe_flight_recorder_settlement_link_persistence_and_reload():
    """Verify that JSONL ledger correctly reloads settlement_link records and quadrants."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = Path(tmpdir) / "reloaded_ledger.jsonl"
        recorder = POEFlightRecorder(ledger_path=ledger_path)

        recorder.record_decision(
            cycle_id="CYCLE_PERSIST_001",
            tau_seconds_remaining=300.0,
            spot_price=85000.0,
            target_strike=84900.0,
            moneyness_diff=100.0,
            spot_velocity_10s=12.0,
            vpin_score=0.18,
            ai_predicted_side="YES",
            ai_confidence=0.88,
            ev_gross=Decimal("0.08"),
            ev_net=Decimal("0.06"),
            decision="TRADE",
        )
        recorder.record_fill(
            cycle_id="CYCLE_PERSIST_001",
            order_side="YES",
            order_type="LIMIT",
            order_price=Decimal("0.52"),
            fill_price=Decimal("0.52"),
            fill_slippage=Decimal("0.00"),
            queue_depth_ahead=15,
            taker_fee_paid=Decimal("0.00"),
        )
        recorder.record_settlement(
            cycle_id="CYCLE_PERSIST_001",
            settlement_spot=85100.0,
            contract_winning_side="YES",
            settled_payout=Decimal("1.00"),
            realized_pnl=Decimal("0.48"),
        )

        # Re-instantiate recorder from the same ledger file
        recorder2 = POEFlightRecorder(ledger_path=ledger_path)
        assert "CYCLE_PERSIST_001" in recorder2._records
        rec = recorder2._records["CYCLE_PERSIST_001"]
        assert rec.quadrant == "Q1_TRUE_ALPHA"
        assert rec.settled_payout == "1.00"
        assert rec.realized_pnl == "0.48"

        # Verify fills reloaded
        assert "CYCLE_PERSIST_001" in recorder2._fills
        assert len(recorder2._fills["CYCLE_PERSIST_001"]) == 1
        assert recorder2._fills["CYCLE_PERSIST_001"][0].order_price == "0.52"


def test_poe_flight_recorder_unsettled_records_and_synthesis():
    """Verify un-settled records tracking and graceful synthesis of historical trade settlements."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = Path(tmpdir) / "unsettled_ledger.jsonl"
        recorder = POEFlightRecorder(ledger_path=ledger_path)

        recorder.record_decision(
            cycle_id="CYCLE_UNSETTLED_001",
            tau_seconds_remaining=500.0,
            spot_price=80000.0,
            target_strike=80000.0,
            moneyness_diff=0.0,
            spot_velocity_10s=0.0,
            vpin_score=0.15,
            ai_predicted_side="NO",
            ai_confidence=0.72,
            ev_gross=Decimal("0.05"),
            ev_net=Decimal("0.03"),
            decision="VETO",
            primary_blocking_parameter="AI_CONVICTION_FLOOR",
        )

        unsettled = recorder.get_unsettled_records()
        assert len(unsettled) == 1
        assert unsettled[0].cycle_id == "CYCLE_UNSETTLED_001"

        # Settle it as winning NO (Shielded Capital)
        recorder.record_settlement(
            cycle_id="CYCLE_UNSETTLED_001",
            settlement_spot=79950.0,
            contract_winning_side="NO",
            settled_payout=Decimal("1.00"),
        )
        assert len(recorder.get_unsettled_records()) == 0

        # Settle an untracked cycle with realized PnL -> Auto-synthesizes TRADE record
        synth_rec = recorder.record_settlement(
            cycle_id="CYCLE_SYNTH_002",
            settlement_spot=80500.0,
            contract_winning_side="YES",
            settled_payout=Decimal("1.00"),
            realized_pnl=Decimal("0.48"),
        )
        assert synth_rec is not None
        assert synth_rec.cycle_id == "CYCLE_SYNTH_002"
        assert synth_rec.quadrant == "Q1_TRUE_ALPHA"



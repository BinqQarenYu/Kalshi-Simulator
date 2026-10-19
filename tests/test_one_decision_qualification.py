"""Unit and Integration Tests for Unified One-Decision Qualification Sweet Spot.

Validates the 3 Golden Gates:
- Gate 1: Contract Truth & Expiry Parity (Spot/Strike validity & Silas T <= 120s TWAP Pinning Blackout)
- Gate 5: Vance Executable Book Depth & OTM Floor (CLOB depth >= 1 contract & ask >= $0.38)
- Gate 12: Adverse Execution 1-Tick Slippage Stress Test (+ $0.01 shock retains net EV > $0.00)
- Micro-Bankroll Clamp: Exactly <= 1 contract approved
- Zero Float: All financial values strictly Decimal in QualificationTicket
- Counterfactual Regret: Skipped candidate trades logged for 6-trade AI assessor
"""

import json
from decimal import Decimal
import pytest

from kalshi_sim.schemas import CryptoAsset, L2BookState, QualificationTicket
from kalshi_sim.ml.bot1_v4_engine import Bot1V4DominationEngine, Bot1V4Decision
from kalshi_sim.ai_assessor import build_assessment_markdown_report


class DummyONNXEngine:
    def process_orderbook_tick(self, l2_book):
        return {
            "signal": "BUY_YES",
            "prob_long": 0.85,
            "prob_short": 0.10,
            "prob_wait": 0.05,
            "confidence": 0.85,
            "vpin_score": 0.15,
            "vpin_veto": False,
        }


def make_l2_book(best_yes_bid=Decimal("0.44"), best_yes_ask=Decimal("0.46"), yes_ask_qty=10):
    book = L2BookState(market_ticker="KXBTC15M-T65000")
    book.yes_book = {best_yes_bid: Decimal("50")}
    book.no_book = {Decimal("1.00") - best_yes_ask: Decimal(str(yes_ask_qty))}
    return book


def test_gate1_contract_truth_invalid_spot_or_strike():
    engine = Bot1V4DominationEngine(asset=CryptoAsset.BTC)
    book = make_l2_book()

    # Zero/negative spot price
    decision = engine.evaluate_market_opportunity(
        spot_price=0.0,
        target_strike=65000.0,
        time_to_expiry_s=400.0,
        l2_book=book,
    )
    assert decision.recommended_side == "wait"
    assert decision.first_failed_gate == "G1_CONTRACT_TRUTH"
    assert not decision.contract_truth_verified

    ticket = engine.get_latest_qualification_ticket()
    assert ticket is not None
    assert ticket.action == "WAIT"
    assert ticket.first_failed_gate == "G1_CONTRACT_TRUTH"


def test_gate1_contract_truth_silas_twap_pinning_blackout():
    engine = Bot1V4DominationEngine(asset=CryptoAsset.BTC)
    book = make_l2_book()

    # T <= 120s remaining
    decision = engine.evaluate_market_opportunity(
        spot_price=65100.0,
        target_strike=65000.0,
        time_to_expiry_s=119.0,
        l2_book=book,
    )
    assert decision.recommended_side == "wait"
    assert decision.first_failed_gate == "G1_CONTRACT_TRUTH_PINNING"
    assert "Silas TWAP Pinning Veto" in decision.rationale

    ticket = engine.get_latest_qualification_ticket()
    assert ticket is not None
    assert ticket.action == "WAIT"
    assert ticket.first_failed_gate == "G1_CONTRACT_TRUTH_PINNING"


def test_gate5_executable_depth_veto():
    engine = Bot1V4DominationEngine(asset=CryptoAsset.BTC)
    engine.onnx_engine = DummyONNXEngine()
    engine.min_confidence = 0.50

    # Book with 0 depth available
    book = L2BookState(market_ticker="KXBTC15M-T65000")
    book.yes_book = {}
    book.no_book = {}

    decision = engine.evaluate_market_opportunity(
        spot_price=65200.0,
        target_strike=65000.0,
        time_to_expiry_s=500.0,
        l2_book=book,
    )

    # Empty book must veto trade with G5_NOT_EXECUTABLE
    assert decision.recommended_side == "wait"
    if decision.candidate_side in ("yes", "no"):
        assert decision.first_failed_gate == "G5_NOT_EXECUTABLE"
        assert decision.clob_depth_available == 0


def test_gate5_adverse_otm_floor_veto():
    engine = Bot1V4DominationEngine(asset=CryptoAsset.BTC)
    engine.onnx_engine = DummyONNXEngine()
    engine.min_confidence = 0.50

    # Ask is $0.30 (< $0.38 minimum viable ask floor)
    book = L2BookState(market_ticker="KXBTC15M-T65000")
    book.yes_book = {Decimal("0.28"): Decimal("10")}
    book.no_book = {Decimal("0.70"): Decimal("10")}

    decision = engine.evaluate_market_opportunity(
        spot_price=65200.0,
        target_strike=65000.0,
        time_to_expiry_s=500.0,
        l2_book=book,
    )

    assert decision.recommended_side == "wait"
    if decision.candidate_side == "yes":
        assert decision.first_failed_gate in ("G5_ADVERSE_OTM_FLOOR", "G5_NOT_EXECUTABLE", "G8_EDGE_TOO_SMALL")


def test_gate12_adverse_execution_1_tick_stress_test():
    engine = Bot1V4DominationEngine(asset=CryptoAsset.BTC)
    engine.onnx_engine = DummyONNXEngine()
    engine.min_confidence = 0.50
    # High fee ensures +$0.01 slippage drops net EV <= 0.00
    engine.fee_per_contract = Decimal("0.55")

    book = make_l2_book(best_yes_bid=Decimal("0.44"), best_yes_ask=Decimal("0.46"), yes_ask_qty=20)

    decision = engine.evaluate_market_opportunity(
        spot_price=65200.0,
        target_strike=65000.0,
        time_to_expiry_s=500.0,
        l2_book=book,
    )

    # Must be vetoed by G12 Adverse Execution Stress Test
    assert decision.recommended_side == "wait"
    assert decision.first_failed_gate == "G12_ADVERSE_EXECUTION"
    assert decision.adverse_ev is not None
    assert decision.adverse_ev <= 0.0
    assert "Adverse 1-Tick Slippage Veto" in decision.rationale


def test_micro_bankroll_clamp_max_one_contract():
    engine = Bot1V4DominationEngine(asset=CryptoAsset.BTC)
    engine.onnx_engine = DummyONNXEngine()
    book = make_l2_book(best_yes_bid=Decimal("0.40"), best_yes_ask=Decimal("0.44"), yes_ask_qty=50)

    decision = engine.evaluate_market_opportunity(
        spot_price=65500.0,
        target_strike=65000.0,
        time_to_expiry_s=500.0,
        l2_book=book,
        total_equity=Decimal("5000.00"),  # Even with massive equity
    )

    # Regardless of equity or conviction, contracts must NEVER exceed 1
    assert decision.recommended_contracts <= 1

    ticket = engine.get_latest_qualification_ticket()
    assert ticket is not None
    assert ticket.approved_contracts <= 1


def test_zero_float_qualification_ticket_schema():
    ticket = QualificationTicket(
        ticket_id="TICK-BTC-TEST-001",
        timestamp_iso="2026-10-19T12:00:00Z",
        asset="BTC",
        ticker="KXBTC15M-TEST",
        action="BUY_YES",
        first_failed_gate="NONE",
        first_failed_reason="",
        candidate_side="yes",
        calibrated_probability=0.8250,
        executable_price=Decimal("0.44"),
        net_ev=Decimal("0.0520"),
        required_edge=Decimal("0.0200"),
        approved_contracts=1,
        spot_price=Decimal("65432.10"),
        target_strike=Decimal("65400.00"),
        time_to_expiry_s=450.0,
        vpin=0.180,
        l2_spread=Decimal("0.02"),
        adverse_ev=Decimal("0.0310"),
        evidence_hashes={"strategy_id": "bot1_v4_btc"},
    )

    # Financial fields must strictly be Decimal
    assert isinstance(ticket.executable_price, Decimal)
    assert isinstance(ticket.net_ev, Decimal)
    assert isinstance(ticket.required_edge, Decimal)
    assert isinstance(ticket.spot_price, Decimal)
    assert isinstance(ticket.target_strike, Decimal)
    assert isinstance(ticket.l2_spread, Decimal)
    assert isinstance(ticket.adverse_ev, Decimal)

    # Pydantic JSON serialization roundtrip
    dumped = ticket.model_dump_json()
    assert "TICK-BTC-TEST-001" in dumped
    assert "0.44" in dumped


def test_counterfactual_regret_tracking():
    engine = Bot1V4DominationEngine(asset=CryptoAsset.BTC)
    book = make_l2_book()

    # Clear any past skipped
    engine._skipped_qualification_tickets.clear()

    # Trigger a decision that sets candidate_side but recommended_side == wait
    # e.g. T <= 120s
    decision = engine.evaluate_market_opportunity(
        spot_price=65300.0,
        target_strike=65000.0,
        time_to_expiry_s=100.0,
        l2_book=book,
    )
    assert decision.recommended_side == "wait"

    # Verify skipped tickets buffer
    skipped = engine.get_skipped_qualification_tickets(limit=10)
    assert len(skipped) >= 1
    st = skipped[-1]
    assert st.action == "WAIT"
    assert st.first_failed_gate == "G1_CONTRACT_TRUTH_PINNING"

    # Test report builder accepts skipped tickets without error
    batch_summary = {
        "batch_index": 1,
        "batch_trades_completed": 6,
        "batch_wins": 4,
        "batch_losses": 2,
        "batch_pnl": 0.85,
        "win_rate": 0.667,
    }
    assessment_result = {
        "summary": "Passed with 4-2 record.",
        "parameter_adjustments": {},
        "council_verdicts": {},
        "learning_updates": {},
        "counterfactual_regret_review": {
            "regret_detected": False,
            "missed_high_ev_trades": 0,
            "false_rejections": [],
            "gate_calibration_recommendation": "G1 Silas pinning working as intended.",
        },
    }

    report_md = build_assessment_markdown_report(
        batch_num=1,
        recent_trades=[],
        batch_pnl=Decimal("0.85"),
        batch_wins=4,
        batch_losses=2,
        pre_balance=Decimal("35.00"),
        post_balance=Decimal("35.85"),
        gemini_data=assessment_result,
        macro_sample={},
        asset="BTC",
        skipped_tickets=[t.model_dump() for t in skipped],
    )
    assert "Unified One-Decision Qualification & Counterfactual Regret Audit" in report_md
    assert "G1_CONTRACT_TRUTH_PINNING" in report_md

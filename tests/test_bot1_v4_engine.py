"""Unit tests for Bot 1 Version 4 (Multi-Turnover Domination Engine)."""

from decimal import Decimal
import pytest
from kalshi_sim.ml.bot1_v4_engine import Bot1V4DominationEngine
from kalshi_sim.schemas import L2BookState


def test_bot1_v4_ev_coupling() -> None:
    engine = Bot1V4DominationEngine(
        min_ev_hurdle_dollars=Decimal("0.02"),
        discount_limit_price=Decimal("0.52"),
    )
    req_win = engine.compute_required_win_probability(Decimal("0.52"))
    assert abs(req_win - 0.54) < 1e-4


def test_bot1_v4_max_turnover_cap() -> None:
    engine = Bot1V4DominationEngine(max_turnover_per_event=3)
    l2 = L2BookState("KXBTC15M-TEST")
    
    # Record 3 turnovers
    cycle_id = "CYCLE_TEST_101"
    engine.reset_cycle_turnover(cycle_id)
    assert engine.get_completed_turnovers(cycle_id) == 0

    engine.record_completed_turnover(cycle_id)
    engine.record_completed_turnover(cycle_id)
    engine.record_completed_turnover(cycle_id)
    assert engine.get_completed_turnovers(cycle_id) == 3

    # Opportunity evaluation should hit max turnover cap
    decision = engine.evaluate_market_opportunity(
        spot_price=85000.0,
        target_strike=84900.0,
        time_to_expiry_s=300.0,
        l2_book=l2,
        cycle_id=cycle_id,
    )
    assert decision.recommended_side == "wait"
    assert "Max Turnover Cap Hit" in decision.rationale

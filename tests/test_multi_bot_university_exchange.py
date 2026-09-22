"""Tests for Multi-Bot Concurrency, LiveCoordinator Anti-Wash Protection, Quant University, and ExchangeRouter."""

from decimal import Decimal
import pytest
import time

from kalshi_sim.live_coordinator import LiveCoordinator
from kalshi_sim.incubator_agent import IncubatorAgent, ShadowTradeRecord
from kalshi_sim.exchange_router import ExchangeRouter, SpotExchangeAdapter
from kalshi_sim.base_engine import TradeIntent
from kalshi_sim.schemas import OrderSide, OrderType


def test_live_coordinator_anti_wash_and_same_direction(tmp_path):
    coord_file = tmp_path / "test_coordination.json"
    coord = LiveCoordinator(coord_path=coord_file)

    ticker = "KXBTC15M-26SEP160115-15"

    # Bot 1 executes YES
    coord.record_trade_execution(
        ticker=ticker,
        side="yes",
        bot_id="3_step_domination_bot",
        contracts=1,
        price=Decimal("0.52"),
        expiry_ts=time.time() + 600.0,
    )

    # 1. Opposing side from Bot 3 (NO) must be vetoed under CFTC wash-trading / anti-cannibalism rule
    is_ok, rationale = coord.check_trade_permission(
        ticker=ticker,
        proposed_side="no",
        bot_id="macro_trend_dominion",
        requested_contracts=1,
        is_live=True,
    )
    assert not is_ok
    assert "CFTC ANTI-WASH TRADING VETO" in rationale

    # 2. Same direction (YES) within combined limit of 2 contracts must be permitted
    is_ok2, rationale2 = coord.check_trade_permission(
        ticker=ticker,
        proposed_side="yes",
        bot_id="macro_trend_dominion",
        requested_contracts=1,
        max_combined_contracts=2,
        is_live=True,
    )
    assert is_ok2
    assert "PERMITTED_COOPERATIVE" in rationale2


def test_university_academic_standing_and_exam(tmp_path):
    state_file = tmp_path / "incubator_test_state.json"
    seal_file = tmp_path / "seal_test_state.json"
    from kalshi_sim.bot_deployment_auditor import BotDeploymentAuditor
    auditor = BotDeploymentAuditor(seal_path=seal_file)
    incubator = IncubatorAgent(auditor=auditor, state_path=state_file)

    # Enroll a bot with 12 trades (Sophomore)
    for i in range(12):
        t = ShadowTradeRecord(
            trade_id=f"t_{i}",
            bot_id="test_candidate_bot",
            bot_name="Test Candidate Bot",
            ticker=f"KXBTC_{i}",
            side="yes",
            count=1,
            entry_price=Decimal("0.50"),
            target_strike=Decimal("78000.00"),
            entry_spot=Decimal("78100.00"),
        )
        t.settle(final_twap=Decimal("78150.00"), target_strike=Decimal("78000.00"))
        incubator._trades.append(t)

    scorecard = incubator.get_bot_scorecard("test_candidate_bot")
    assert scorecard.academic_standing == "Sophomore (Lab Trials)"
    assert scorecard.curriculum_progress_pct == 40  # 12/30 = 40%
    assert not scorecard.graduation_eligible

    # Exam fails before 30 cycles
    exam_res = incubator.take_certification_exam("test_candidate_bot")
    assert not exam_res["graduated"]
    assert any("Insufficient shadow sample size" in r for r in exam_res["reasons"])


def test_exchange_router_health():
    import asyncio

    async def _run_test():
        router = ExchangeRouter()
        spot_adapter = SpotExchangeAdapter(
            exchange_id="mock_spot",
            exchange_name="Mock Spot Reference",
            spot_getter=lambda: 91250.50,
        )
        router.register_exchange(spot_adapter, is_primary=True)

        status = await router.get_all_status()
        assert status["total_venues"] == 1
        assert status["primary_exchange"] == "mock_spot"
        assert "mock_spot" in status["venues"]
        assert status["venues"]["mock_spot"]["healthy"] is True
        assert "91,250.50" in status["venues"]["mock_spot"]["status_message"]

    asyncio.run(_run_test())

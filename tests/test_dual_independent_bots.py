"""Unit tests verifying Dual Independent Bot Execution with CFTC Directional Harmony and Per-Bot Cycle Locks."""

from decimal import Decimal
import pytest
from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.live_coordinator import LiveCoordinator


def test_dual_independent_bots_same_direction_approved():
    """Verify Bot 1 and Bot 1 V4 can both place 1 contract independently when agreeing on direction."""
    guard = AgentGuardrails(min_order_interval_seconds=0.0)
    cycle = "KXBTC15M-TEST-CYCLE-1"

    # Bot 1 places YES order
    ok1, reason1, size1, _ = guard.validate_pre_trade_intent(
        ticker=cycle,
        side="yes",
        requested_size=1,
        est_price=Decimal("0.52"),
        total_equity=Decimal("100.00"),
        bot_type="3_step_domination_bot",
    )
    assert ok1 is True
    assert size1 == 1

    guard.record_trade_inception(
        trade_id="tr_bot1",
        ticker=cycle,
        side="yes",
        size=1,
        price=Decimal("0.52"),
        cost=Decimal("0.52"),
        fee=Decimal("0.01"),
        bot_type="3_step_domination_bot",
        execution_mode="live",
        rationale="Bot 1 Momentum Breakout",
        vpin=0.10,
        ai_prob=0.75,
    )

    # Bot 1 V4 evaluates independently and also wants YES -> MUST BE APPROVED
    ok2, reason2, size2, _ = guard.validate_pre_trade_intent(
        ticker=cycle,
        side="yes",
        requested_size=1,
        est_price=Decimal("0.53"),
        total_equity=Decimal("100.00"),
        bot_type="bot1_v4_domination",
    )
    assert ok2 is True, f"Bot 1 V4 should be permitted to trade independently: {reason2}"
    assert size2 == 1

    guard.record_trade_inception(
        trade_id="tr_bot1_v4",
        ticker=cycle,
        side="yes",
        size=1,
        price=Decimal("0.53"),
        cost=Decimal("0.53"),
        fee=Decimal("0.01"),
        bot_type="bot1_v4_domination",
        execution_mode="live",
        rationale="Bot 1 V4 EV Maker",
        vpin=0.10,
        ai_prob=0.78,
    )


def test_dual_independent_bots_cftc_anti_wash_veto():
    """Verify that if Bot 1 enters YES, Bot 1 V4 attempting NO is strictly vetoed under CFTC wash rules."""
    guard = AgentGuardrails(min_order_interval_seconds=0.0)
    cycle = "KXBTC15M-TEST-CYCLE-2"

    # Bot 1 enters YES
    guard.record_trade_inception(
        trade_id="tr_bot1",
        ticker=cycle,
        side="yes",
        size=1,
        price=Decimal("0.52"),
        cost=Decimal("0.52"),
        fee=Decimal("0.01"),
        bot_type="3_step_domination_bot",
        execution_mode="live",
        rationale="Bot 1 Momentum Breakout",
        vpin=0.10,
        ai_prob=0.75,
    )

    # Bot 1 V4 proposes NO on the same cycle -> HARD VETO
    ok, reason, size, diag = guard.validate_pre_trade_intent(
        ticker=cycle,
        side="no",
        requested_size=1,
        est_price=Decimal("0.48"),
        total_equity=Decimal("100.00"),
        bot_type="bot1_v4_domination",
    )
    assert ok is False
    assert "CFTC ANTI-WASH TRADING VETO" in reason
    assert size == 0


def test_per_bot_single_trade_per_cycle_lockout():
    """Verify that a single bot cannot trade twice in the same cycle, even if fleet capacity remains."""
    guard = AgentGuardrails(min_order_interval_seconds=0.0)
    cycle = "KXBTC15M-TEST-CYCLE-3"

    # Bot 1 enters 1 contract
    guard.record_trade_inception(
        trade_id="tr_bot1_1",
        ticker=cycle,
        side="yes",
        size=1,
        price=Decimal("0.52"),
        cost=Decimal("0.52"),
        fee=Decimal("0.01"),
        bot_type="3_step_domination_bot",
        execution_mode="live",
        rationale="Bot 1 Entry",
        vpin=0.10,
        ai_prob=0.75,
    )

    # Bot 1 tries to enter a 2nd time -> VETOED by 1-trade-per-cycle
    ok, reason, size, _ = guard.validate_pre_trade_intent(
        ticker=cycle,
        side="yes",
        requested_size=1,
        est_price=Decimal("0.52"),
        total_equity=Decimal("100.00"),
        bot_type="3_step_domination_bot",
    )
    assert ok is False
    assert "1-TRADE-PER-CYCLE LOCKOUT" in reason
    assert size == 0


def test_cycle_exposure_cap_blocks_third_contract():
    """Verify fleet maximum of 2 contracts per cycle is strictly enforced under $50 equity."""
    guard = AgentGuardrails(min_order_interval_seconds=0.0)
    cycle = "KXBTC15M-TEST-CYCLE-4"

    # Bot 1 enters 1 ct
    guard.record_trade_inception(
        trade_id="tr_1", ticker=cycle, side="yes", size=1, price=Decimal("0.50"),
        cost=Decimal("0.50"), fee=Decimal("0.01"), bot_type="3_step_domination_bot",
        execution_mode="live", rationale="", vpin=0.1, ai_prob=0.7,
    )

    # Bot 1 V4 enters 1 ct
    guard.record_trade_inception(
        trade_id="tr_2", ticker=cycle, side="yes", size=1, price=Decimal("0.50"),
        cost=Decimal("0.50"), fee=Decimal("0.01"), bot_type="bot1_v4_domination",
        execution_mode="live", rationale="", vpin=0.1, ai_prob=0.7,
    )

    # A 3rd attempt by any bot is blocked by max cycle exposure when equity < $50 (cap is 2)
    ok, reason, size, _ = guard.validate_pre_trade_intent(
        ticker=cycle,
        side="yes",
        requested_size=1,
        est_price=Decimal("0.50"),
        total_equity=Decimal("40.00"),
        bot_type="macro_trend_dominion",
    )
    assert ok is False
    assert "CYCLE EXPOSURE CAP" in reason

"""Tests for Agent_Guardrails — Pre-trade validation, cycle locks, cooldowns, and risk sizing."""

from decimal import Decimal
import time
import pytest

from kalshi_sim.agent_guardrails import AgentGuardrails


def test_guardrail_allows_valid_order() -> None:
    guardrails = AgentGuardrails(min_order_interval_seconds=10.0)
    ok, reason, size, diag = guardrails.validate_pre_trade_intent(
        ticker="KXBTC15M-T78650",
        side="yes",
        requested_size=10,
        est_price=Decimal("0.50"),
        total_equity=Decimal("100.00"),
        vpin=0.15,
    )
    assert ok is True
    assert reason == "PASSED_GUARDRAILS"
    # Equity $100 * 8% risk = $8.00 / $0.50 = 16, but micro bankroll cap is 2 contracts
    assert size == 2
    assert diag["is_tapered"] is False


def test_1_trade_per_cycle_lock() -> None:
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    ticker = "KXBTC15M-26AUG301545-45"
    
    # 1. First order passes
    ok, _, size, _ = guardrails.validate_pre_trade_intent(
        ticker=ticker,
        side="yes",
        requested_size=2,
        est_price=Decimal("0.50"),
        total_equity=Decimal("50.00"),
        vpin=0.15,
    )
    assert ok is True
    
    # Record inception
    guardrails.record_trade_inception(
        trade_id="tr_1001",
        ticker=ticker,
        side="yes",
        size=size,
        price=Decimal("0.50"),
        cost=Decimal("1.00"),
        fee=Decimal("0.02"),
        bot_type="3_step_domination_bot",
        execution_mode="simulated",
        rationale="OFI Momentum Breakout",
        vpin=0.15,
        ai_prob=0.75,
    )
    
    # 2. Second order in same cycle is REJECTED by 1-trade-per-cycle lock
    ok2, reason2, size2, _ = guardrails.validate_pre_trade_intent(
        ticker=ticker,
        side="yes",
        requested_size=2,
        est_price=Decimal("0.50"),
        total_equity=Decimal("50.00"),
        vpin=0.15,
    )
    assert ok2 is False
    assert "1-TRADE-PER-CYCLE LOCKOUT" in reason2
    assert size2 == 0


def test_cooldown_throttle() -> None:
    guardrails = AgentGuardrails(min_order_interval_seconds=30.0)
    
    # Record inception
    guardrails.record_trade_inception(
        trade_id="tr_1002",
        ticker="KXBTC15M-T78650",
        side="yes",
        size=2,
        price=Decimal("0.50"),
        cost=Decimal("1.00"),
        fee=Decimal("0.02"),
        bot_type="3_step_domination_bot",
        execution_mode="simulated",
        rationale="Signal",
        vpin=0.15,
        ai_prob=0.75,
    )
    
    # Order on a different ticker within cooldown window
    ok, reason, size, _ = guardrails.validate_pre_trade_intent(
        ticker="KXBTC5M-T78600",
        side="yes",
        requested_size=2,
        est_price=Decimal("0.50"),
        total_equity=Decimal("50.00"),
        vpin=0.15,
    )
    assert ok is False
    assert "COOLDOWN THROTTLE" in reason
    assert size == 0


def test_bankroll_sizing_caps() -> None:
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    
    # Nano bankroll <= $25
    ok, _, size, _ = guardrails.validate_pre_trade_intent(
        ticker="KXBTC15M-T1",
        side="yes",
        requested_size=10,
        est_price=Decimal("0.40"),
        total_equity=Decimal("20.00"),
        vpin=0.10,
    )
    assert ok is True
    # $20 * 8% = $1.60 / $0.40 = 4, but nano cap is 2
    assert size <= 2


def test_vpin_toxicity_veto() -> None:
    guardrails = AgentGuardrails(vpin_toxic_threshold=0.65)
    ok, reason, size, _ = guardrails.validate_pre_trade_intent(
        ticker="KXBTC15M-T1",
        side="yes",
        requested_size=2,
        est_price=Decimal("0.50"),
        total_equity=Decimal("100.00"),
        vpin=0.72,  # Toxic
    )
    assert ok is False
    assert "VPIN TOXICITY VETO" in reason
    assert size == 0


def test_loss_streak_taper() -> None:
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0, consecutive_loss_taper_threshold=2)
    # Establish peak equity at $100
    guardrails.validate_pre_trade_intent("T0", "yes", 1, Decimal("0.50"), total_equity=Decimal("100.00"))
    
    # Record 2 losses
    guardrails.record_cycle_settlement("T1", outcome="loss", pnl=Decimal("-2.00"), balance_after=Decimal("98.00"))
    guardrails.record_cycle_settlement("T2", outcome="loss", pnl=Decimal("-2.00"), balance_after=Decimal("96.00"))
    
    ok, reason, size, diag = guardrails.validate_pre_trade_intent(
        ticker="KXBTC15M-T3",
        side="yes",
        requested_size=10,
        est_price=Decimal("0.50"),
        total_equity=Decimal("96.00"),
        vpin=0.10,
    )
    assert ok is True
    assert diag["is_tapered"] is True
    # Taper enforces 1 contract max
    assert size == 1


def test_circuit_breaker_drawdown() -> None:
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0, emergency_drawdown_limit=Decimal("0.25"))
    # Establish peak equity at $100
    guardrails.validate_pre_trade_intent("T0", "yes", 1, Decimal("0.50"), total_equity=Decimal("100.00"))
    
    # Balance dropped from $100 to $70 (30% drawdown)
    guardrails.record_cycle_settlement("T1", outcome="loss", pnl=Decimal("-30.00"), balance_after=Decimal("70.00"))
    
    ok, reason, size, _ = guardrails.validate_pre_trade_intent(
        ticker="KXBTC15M-T4",
        side="yes",
        requested_size=2,
        est_price=Decimal("0.50"),
        total_equity=Decimal("70.00"),
        vpin=0.10,
    )
    assert ok is False
    assert "EMERGENCY CIRCUIT BREAKER" in reason


def test_settlement_unlocks_cycle() -> None:
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    ticker = "KXBTC15M-T78650"
    
    # Inception locks cycle
    guardrails.record_trade_inception(
        trade_id="tr_1003",
        ticker=ticker,
        side="yes",
        size=2,
        price=Decimal("0.50"),
        cost=Decimal("1.00"),
        fee=Decimal("0.02"),
        bot_type="3_step_domination_bot",
        execution_mode="simulated",
        rationale="Signal",
        vpin=0.15,
        ai_prob=0.75,
    )
    assert ticker in guardrails._cycle_locks
    
    # Settlement unlocks cycle
    guardrails.record_cycle_settlement(ticker=ticker, outcome="win", pnl=Decimal("1.00"), balance_after=Decimal("101.00"))
    assert ticker not in guardrails._cycle_locks
    
    # Can enter again for next cycle
    ok, reason, size, _ = guardrails.validate_pre_trade_intent(
        ticker=ticker,
        side="yes",
        requested_size=2,
        est_price=Decimal("0.50"),
        total_equity=Decimal("101.00"),
        vpin=0.10,
    )
    assert ok is True


def test_multi_asset_cycle_lock_isolation() -> None:
    """Verify that 1-trade-per-cycle lock on one asset (e.g. BTC) does not block trades on other assets (ETH, SOL, DOGE)."""
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    btc_ticker = "KXBTC15M-26AUG290315-15"
    eth_ticker = "KXETH15M-26AUG290315-15"
    sol_ticker = "KXSOL15M-26AUG290315-15"
    doge_ticker = "KXDOGE15M-26AUG290315-15"

    # Inception on BTC
    guardrails.record_trade_inception(
        trade_id="tr_btc_1",
        ticker=btc_ticker,
        side="yes",
        size=2,
        price=Decimal("0.45"),
        cost=Decimal("0.90"),
        fee=Decimal("0.02"),
        bot_type="3_step_domination_bot",
        execution_mode="simulated",
        rationale="BTC Momentum",
        vpin=0.12,
        ai_prob=0.70,
    )

    # BTC is now locked
    ok_btc, reason_btc, _, _ = guardrails.validate_pre_trade_intent(
        ticker=btc_ticker,
        side="yes",
        requested_size=2,
        est_price=Decimal("0.45"),
        total_equity=Decimal("100.00"),
        vpin=0.12,
    )
    assert ok_btc is False
    assert "1-TRADE-PER-CYCLE LOCKOUT" in reason_btc

    # ETH, SOL, DOGE are NOT locked and can enter
    for ticker in [eth_ticker, sol_ticker, doge_ticker]:
        ok, reason, size, _ = guardrails.validate_pre_trade_intent(
            ticker=ticker,
            side="yes",
            requested_size=2,
            est_price=Decimal("0.45"),
            total_equity=Decimal("100.00"),
            vpin=0.12,
        )
        assert ok is True, f"Expected {ticker} to be allowed, but rejected: {reason}"
        assert size == 2


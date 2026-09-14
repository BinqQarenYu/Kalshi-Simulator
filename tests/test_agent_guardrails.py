"""Tests for Agent_Guardrails — Pre-trade validation, cycle locks, cooldowns, and risk sizing."""

from decimal import Decimal
import time
from unittest.mock import patch
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
    # Micro bankroll cap is strictly 1 contract for each asset
    assert size == 1
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
        assert size == 1


def test_guardrail_3step_domination_sole_authorization_and_one_contract() -> None:
    """Verify that only 3-Step Dominion is authorized to trade (strictly 1 contract per asset), and all other bots are rejected."""
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)

    # 1. All other bots must be REJECTED (prohibited from trading)
    other_bot_types = [
        "dominion_2_bot",
        "onnx_microstructure_bot",
        "scalp",
        "momentum",
        "swing",
        "experimental_candidate_bot",
    ]

    for b_type in other_bot_types:
        ok, reason, size, diag = guardrails.validate_pre_trade_intent(
            ticker=f"KXBTC15M-T-{b_type}",
            side="yes",
            requested_size=1,
            est_price=Decimal("0.50"),
            total_equity=Decimal("500.00"),
            vpin=0.10,
            is_bot=True,
            bot_type=b_type,
        )
        assert ok is False, f"Expected {b_type} to be prohibited, but was allowed!"
        assert "BOT TRADING PROHIBITED" in reason
        assert size == 0

    # 2. 3-Step Domination bot is the ONLY authorized bot, strictly capped at 1 contract across equity tiers
    for equity in [Decimal("20.00"), Decimal("50.00"), Decimal("100.00"), Decimal("500.00"), Decimal("10000.00")]:
        for primary_type in ["3_step_domination_bot", "3_step_domination", "domination", None]:
            g_test = AgentGuardrails(min_order_interval_seconds=0.0)
            ok, reason, size, diag = g_test.validate_pre_trade_intent(
                ticker="KXBTC15M-T-PRIMARY",
                side="yes",
                requested_size=10,
                est_price=Decimal("0.50"),
                total_equity=equity,
                vpin=0.10,
                is_bot=True,
                bot_type=primary_type,
            )
            assert ok is True
            assert size == 1, f"Expected 3-Step Dominion ({primary_type}) to receive strictly 1 contract, got {size}"

    # 3. 3-Step Domination receives strictly 1 contract across all 4 crypto assets (BTC, ETH, SOL, DOGE)
    for asset_ticker in ["KXBTC15M-T1", "KXETH15M-T1", "KXSOL15M-T1", "KXDOGE15M-T1"]:
        g_asset = AgentGuardrails(min_order_interval_seconds=0.0)
        ok, reason, size, diag = g_asset.validate_pre_trade_intent(
            ticker=asset_ticker,
            side="yes",
            requested_size=5,
            est_price=Decimal("0.50"),
            total_equity=Decimal("100.00"),
            vpin=0.10,
            is_bot=True,
            bot_type="3_step_domination_bot",
        )
        assert ok is True
        assert size == 1, f"Expected 1 contract for {asset_ticker}, got {size}"


def test_guardrail_in_flight_concurrency_lockout() -> None:
    """Verify that an order in flight immediately blocks concurrent orders on the same cycle."""
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    cycle = "KXDOGE15M-26SEP071200-00"

    # 1. First order pre-trade intent validation succeeds and places in-flight reservation
    ok1, reason1, size1, _ = guardrails.validate_pre_trade_intent(
        ticker=cycle,
        side="yes",
        requested_size=1,
        est_price=Decimal("0.48"),
        total_equity=Decimal("25.00"),
        vpin=0.10,
        is_bot=True,
    )
    assert ok1 is True
    assert size1 == 1

    # 2. Concurrent invocation during network dispatch is immediately BLOCKED
    ok2, reason2, size2, _ = guardrails.validate_pre_trade_intent(
        ticker=cycle,
        side="yes",
        requested_size=1,
        est_price=Decimal("0.48"),
        total_equity=Decimal("25.00"),
        vpin=0.10,
        is_bot=True,
    )
    assert ok2 is False
    assert "IN-FLIGHT ORDER LOCKOUT" in reason2
    assert size2 == 0

    # 3. If dispatch fails and is released, next order is permitted
    guardrails.release_in_flight_intent(cycle)
    ok3, reason3, size3, _ = guardrails.validate_pre_trade_intent(
        ticker=cycle,
        side="yes",
        requested_size=1,
        est_price=Decimal("0.48"),
        total_equity=Decimal("25.00"),
        vpin=0.10,
        is_bot=True,
    )
    assert ok3 is True
    assert size3 == 1


def test_guardrail_max_2_contracts_per_cycle() -> None:
    """Verify strictly 1 contract per trade and hard-capped maximum of 2 contracts per cycle."""
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    cycle = "KXBTC15M-26SEP071200-00"

    # Trade 1: Requested 5 contracts, clamped strictly to 1 contract
    ok1, _, size1, _ = guardrails.validate_pre_trade_intent(
        ticker=cycle,
        side="yes",
        requested_size=5,
        est_price=Decimal("0.48"),
        total_equity=Decimal("25.00"),
        vpin=0.10,
        is_bot=True,
    )
    assert ok1 is True
    assert size1 == 1
    guardrails.record_resting_order("ord_1", cycle, "yes", size1, Decimal("0.48"))

    # Unlock cycle lock to test second entry up to max 2 shares
    guardrails._cycle_locks.pop(cycle, None)

    # Trade 2: Requested 2 contracts, clamped to 1 (2 - 1 = 1 remaining capacity)
    ok2, _, size2, _ = guardrails.validate_pre_trade_intent(
        ticker=cycle,
        side="yes",
        requested_size=2,
        est_price=Decimal("0.48"),
        total_equity=Decimal("25.00"),
        vpin=0.10,
        is_bot=True,
    )
    assert ok2 is True
    assert size2 == 1
    guardrails.record_resting_order("ord_2", cycle, "yes", size2, Decimal("0.48"))

    # Trade 3: Total is now 2 contracts. Further entries are strictly rejected
    ok3, reason3, size3, _ = guardrails.validate_pre_trade_intent(
        ticker=cycle,
        side="yes",
        requested_size=1,
        est_price=Decimal("0.48"),
        total_equity=Decimal("25.00"),
        vpin=0.10,
        is_bot=True,
    )
    assert ok3 is False
    assert "CYCLE" in reason3
    assert size3 == 0


def test_onnx_strategy_paper_authorization_and_live_blocking() -> None:
    """Verify Lane 2 isolation: The ONNX Strategy is authorized in paper mode, but strictly blocked in live mode."""
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    cycle = "KXBTC15M-26SEP091745-45"

    for onnx_alias in ("onnx_macro_v2", "dual_onnx", "the_onnx_strategy"):
        # 1. In Paper Mode (is_live=False): Authorized and capped to 1 contract
        ok_paper, reason_paper, size_paper, _ = guardrails.validate_pre_trade_intent(
            ticker=f"{cycle}-{onnx_alias}-paper",
            side="yes",
            requested_size=5,
            est_price=Decimal("0.48"),
            total_equity=Decimal("25.00"),
            vpin=0.10,
            is_bot=True,
            bot_type=onnx_alias,
            is_live=False,
        )
        assert ok_paper is True, f"Failed for {onnx_alias} in paper mode: {reason_paper}"
        assert size_paper == 1

        # 2. In Live Mode (is_live=True): Prohibited, only 3-Step Dominion allowed
        ok_live, reason_live, size_live, _ = guardrails.validate_pre_trade_intent(
            ticker=f"{cycle}-{onnx_alias}-live",
            side="yes",
            requested_size=1,
            est_price=Decimal("0.48"),
            total_equity=Decimal("25.00"),
            vpin=0.10,
            is_bot=True,
            bot_type=onnx_alias,
            is_live=True,
        )
        assert ok_live is False, f"Expected {onnx_alias} to be blocked in live mode!"
        assert "LIVE BOT TRADING PROHIBITED" in reason_live
        assert size_live == 0


def test_onnx_strategy_promoted_live_authorization() -> None:
    """Verify that once authorized for Live Mode, The ONNX Strategy can route live orders under micro-bankroll cap."""
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    cycle = "KXBTC15M-26SEP091800-00"

    # Promote and authorize ONNX strategy
    guardrails.authorize_live_bot("the_onnx_strategy")

    for onnx_alias in ("the_onnx_strategy", "dual_onnx", "dual_onnx_bot"):
        ok_live, reason_live, size_live, _ = guardrails.validate_pre_trade_intent(
            ticker=f"{cycle}-{onnx_alias}-promoted-live",
            side="yes",
            requested_size=5,  # Requests 5
            est_price=Decimal("0.48"),
            total_equity=Decimal("20.51"),  # Nano-bankroll ($20.51)
            vpin=0.10,
            is_bot=True,
            bot_type=onnx_alias,
            is_live=True,
        )
        assert ok_live is True, f"Failed for {onnx_alias} promoted in live mode: {reason_live}"
        # Strictly hard-capped to 1 contract under nano-bankroll armor
        assert size_live == 1


def test_macro_trend_dominion_paper_authorization_and_live_blocking() -> None:
    """Verify Lane 2 isolation: Macro Trend Dominion is authorized in paper mode, but strictly blocked in live mode when unsealed."""
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    cycle = "KXBTC15M-26SEP101800-00"

    # Simulate unsealed state on disk
    with patch("kalshi_sim.bot_deployment_auditor.BotDeploymentAuditor.check_live_authorization_on_disk", return_value=(False, "UNSEALED")):
        for macro_alias in ("macro_trend_dominion", "macro_onnx", "macro_trend"):
            # 1. In Paper Mode (is_live=False): Authorized and capped to 1 contract
            ok_paper, reason_paper, size_paper, _ = guardrails.validate_pre_trade_intent(
                ticker=f"{cycle}-{macro_alias}-paper",
                side="yes",
                requested_size=5,
                est_price=Decimal("0.48"),
                total_equity=Decimal("25.00"),
                vpin=0.10,
                is_bot=True,
                bot_type=macro_alias,
                is_live=False,
            )
            assert ok_paper is True, f"Failed for {macro_alias} in paper mode: {reason_paper}"
            assert size_paper == 1

            # 2. In Live Mode (is_live=True): Prohibited without explicit promotion or seal
            ok_live, reason_live, size_live, _ = guardrails.validate_pre_trade_intent(
                ticker=f"{cycle}-{macro_alias}-live",
                side="yes",
                requested_size=1,
                est_price=Decimal("0.48"),
                total_equity=Decimal("25.00"),
                vpin=0.10,
                is_bot=True,
                bot_type=macro_alias,
                is_live=True,
            )
            assert ok_live is False, f"Expected {macro_alias} to be blocked in live mode when unsealed!"
            assert "LIVE BOT TRADING PROHIBITED" in reason_live
            assert size_live == 0


def test_macro_trend_dominion_promoted_live_authorization() -> None:
    """Verify that once authorized for Live Mode, Macro Trend Dominion can route live orders under micro-bankroll cap."""
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    cycle = "KXBTC15M-26SEP101815-15"

    # Promote and authorize Macro Trend Dominion
    guardrails.authorize_live_bot("macro_trend_dominion")

    for macro_alias in ("macro_trend_dominion", "macro_onnx", "macro_trend"):
        ok_live, reason_live, size_live, _ = guardrails.validate_pre_trade_intent(
            ticker=f"{cycle}-{macro_alias}-promoted-live",
            side="yes",
            requested_size=5,
            est_price=Decimal("0.48"),
            total_equity=Decimal("20.51"),
            vpin=0.10,
            is_bot=True,
            bot_type=macro_alias,
            is_live=True,
        )
        assert ok_live is True, f"Failed for {macro_alias} promoted in live mode: {reason_live}"
        assert size_live == 1





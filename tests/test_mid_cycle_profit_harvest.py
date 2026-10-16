"""Unit tests for Mid-Cycle Asymmetric Profit Harvesting and Open-Position Exit Locks.

Tests:
1. Rule 0: Bargain High-ROI Harvest at T=420s (7 minutes left, entry 38c, bid 80c -> immediate exit).
2. Rule 0: Deep Bid Peak (bid >= 85c) unconditional harvest without requiring adverse reversal.
3. StrategyEvaluator: Cycle lock allows open position exit evaluation (anti-lockout gate).
4. StrategyEvaluator: Dynamic Regime Strategy delegates open positions to exit evaluator.
5. StrategyEvaluator: High-water mark peak bid tracking and trailing ratchet execution.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
from kalshi_sim.ml.domination_exit_evaluator import DominationExitEvaluator
from kalshi_sim.ml.dynamic_regime_strategy import DynamicRegimeStrategy
from kalshi_sim.portfolio import Portfolio
from kalshi_sim.schemas import CryptoAsset, L2BookState, MarketInfo, OrderSide, SimulatedFill, Timeframe
from kalshi_sim.strategy_evaluator import StrategyEvaluationCoordinator


def test_rule_0_mid_cycle_bargain_harvest() -> None:
    """A bargain entry (38c) that reaches 80c (+110% ROI) with 7 minutes left MUST harvest immediately."""
    bot = ThreeStepDominationBot(
        take_profit_price_threshold=Decimal("0.85"),
        require_reversal_for_tp_ceiling=True,  # Even if True, Rule 0 must bypass and harvest!
    )
    evaluator = DominationExitEvaluator(bot)

    book = L2BookState("KXBTC15M-TEST")
    book.yes_book = {Decimal("0.80"): Decimal("10")}
    book.no_book = {Decimal("0.19"): Decimal("10")}

    decision = evaluator.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.38"),
        size=1,
        book=book,
        time_to_expiry_s=420.0,  # 7 minutes remaining!
        spot_price=82050.0,
        target_strike=82023.0,
        spot_velocity_3s=0.5,
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "ASYMMETRIC_PEAK_HARVEST"
    assert decision.exit_price == Decimal("0.80")
    assert decision.profit_pct > 100.0
    assert "ASYMMETRIC PROFIT HARVEST" in decision.rationale


def test_rule_0_deep_bid_peak_harvest_without_reversal() -> None:
    """When best bid hits 85c+, it must harvest unconditionally without waiting for adverse reversal."""
    bot = ThreeStepDominationBot(
        take_profit_price_threshold=Decimal("0.88"),
        require_reversal_for_tp_ceiling=True,
    )
    # Market probability indicates strong bullish momentum (95% YES, 5% NO -> no reversal!)
    bot.compute_market_probabilities = MagicMock(return_value=(0.95, 0.05))
    evaluator = DominationExitEvaluator(bot)

    book = L2BookState("KXBTC15M-TEST")
    book.yes_book = {Decimal("0.85"): Decimal("25")}
    book.no_book = {Decimal("0.14"): Decimal("25")}

    decision = evaluator.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.48"),
        size=1,
        book=book,
        time_to_expiry_s=360.0,
        spot_price=82100.0,
        target_strike=82000.0,
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "ASYMMETRIC_PEAK_HARVEST"
    assert decision.exit_price == Decimal("0.85")


@pytest.mark.asyncio
async def test_strategy_evaluator_cycle_lock_allows_exit() -> None:
    """When a cycle is locked in guardrails, StrategyEvaluator must NOT return if an open position exists."""
    guardrails = MagicMock()
    guardrails._cycle_locks = {"KXBTC15M-CYCLE-1": "ORDER_1"}

    simulator = MagicMock()
    db_writer = MagicMock()
    evaluator = StrategyEvaluationCoordinator(
        guardrails=guardrails,
        simulator=simulator,
        db_writer=db_writer,
        onnx_engine=MagicMock(),
        ev_engine=MagicMock(),
        macro_trend_bot=MagicMock(),
        dominion2_bot=MagicMock(),
        domination_bot=ThreeStepDominationBot(take_profit_price_threshold=Decimal("0.85")),
        dual_onnx_bot=MagicMock(),
        btc_orderflow_feed=MagicMock(),
    )

    p_dom = Portfolio(starting_balance=Decimal("50.00"))
    fill = SimulatedFill(
        order_id="FILL_1",
        ticker="KXBTC15M-CYCLE-1",
        side=OrderSide.YES,
        size=1,
        fill_price=Decimal("0.38"),
        cost=Decimal("0.38"),
        fee=Decimal("0.01"),
    )
    p_dom.open_position(fill, Timeframe.FIFTEEN_MIN)

    book = L2BookState("KXBTC15M-CYCLE-1")
    book.yes_book = {Decimal("0.80"): Decimal("10")}
    book.no_book = {Decimal("0.19"): Decimal("10")}

    now_utc = datetime.now(timezone.utc)
    exp_time = now_utc + timedelta(seconds=420)
    market_info = MarketInfo(
        ticker="KXBTC15M-CYCLE-1",
        event_ticker="KXBTC15M-CYCLE-1",
        expiration_time=exp_time,
        target_strike=Decimal("82000.00"),
    )
    market_cache = {"KXBTC15M-CYCLE-1": market_info}

    place_order_mock = AsyncMock()

    with patch("kalshi_sim.strategy_evaluator.get_active_lock_holder", return_value=None):
        await evaluator.evaluate_market(
            ticker="KXBTC15M-CYCLE-1",
            book=book,
            active_strategy_bot="bot1_v4_domination",
            execution_mode="live",
            market_cache=market_cache,
            recent_trades={},
            ticker_timeframe_map={},
            portfolio_macro_trend=Portfolio(starting_balance=Decimal("50.00")),
            portfolio_dominion2=Portfolio(starting_balance=Decimal("50.00")),
            portfolio_domination=p_dom,
            portfolio_onnx=Portfolio(starting_balance=Decimal("50.00")),
            portfolio_dual_onnx=Portfolio(starting_balance=Decimal("50.00")),
            portfolio_market_maker=Portfolio(starting_balance=Decimal("50.00")),
            place_order_fn=place_order_mock,
        )

    # place_order_mock MUST be called with action='sell' and limit_price=Decimal('0.80')!
    assert place_order_mock.await_count == 1
    call_kwargs = place_order_mock.call_args.kwargs
    assert call_kwargs["action"] == "sell"
    assert call_kwargs["limit_price"] == Decimal("0.80")
    assert call_kwargs["ticker"] == "KXBTC15M-CYCLE-1"


@pytest.mark.asyncio
async def test_dynamic_regime_delegates_to_exit_evaluator() -> None:
    """When active bot is dynamic_trading_strategy and position exists, it must evaluate exit and sell."""
    guardrails = MagicMock()
    guardrails._cycle_locks = {}

    simulator = MagicMock()
    db_writer = MagicMock()
    evaluator = StrategyEvaluationCoordinator(
        guardrails=guardrails,
        simulator=simulator,
        db_writer=db_writer,
        onnx_engine=MagicMock(),
        ev_engine=MagicMock(),
        macro_trend_bot=MagicMock(),
        dominion2_bot=MagicMock(),
        domination_bot=ThreeStepDominationBot(take_profit_price_threshold=Decimal("0.85")),
        dual_onnx_bot=MagicMock(),
        btc_orderflow_feed=MagicMock(),
    )

    p_dom = Portfolio(starting_balance=Decimal("50.00"))
    fill = SimulatedFill(
        order_id="FILL_2",
        ticker="KXBTC15M-CYCLE-2",
        side=OrderSide.YES,
        size=1,
        fill_price=Decimal("0.40"),
        cost=Decimal("0.40"),
        fee=Decimal("0.01"),
    )
    p_dom.open_position(fill, Timeframe.FIFTEEN_MIN)

    book = L2BookState("KXBTC15M-CYCLE-2")
    book.yes_book = {Decimal("0.85"): Decimal("10")}
    book.no_book = {Decimal("0.14"): Decimal("10")}

    now_utc = datetime.now(timezone.utc)
    exp_time = now_utc + timedelta(seconds=420)
    market_info2 = MarketInfo(
        ticker="KXBTC15M-CYCLE-2",
        event_ticker="KXBTC15M-CYCLE-2",
        expiration_time=exp_time,
        target_strike=Decimal("82000.00"),
    )
    market_cache = {"KXBTC15M-CYCLE-2": market_info2}

    place_order_mock = AsyncMock()

    with patch("kalshi_sim.strategy_evaluator.get_active_lock_holder", return_value=None):
        await evaluator.evaluate_market(
            ticker="KXBTC15M-CYCLE-2",
            book=book,
            active_strategy_bot="dynamic_trading_strategy",
            execution_mode="live",
            market_cache=market_cache,
            recent_trades={},
            ticker_timeframe_map={},
            portfolio_macro_trend=Portfolio(starting_balance=Decimal("50.00")),
            portfolio_dominion2=Portfolio(starting_balance=Decimal("50.00")),
            portfolio_domination=p_dom,
            portfolio_onnx=Portfolio(starting_balance=Decimal("50.00")),
            portfolio_dual_onnx=Portfolio(starting_balance=Decimal("50.00")),
            portfolio_market_maker=Portfolio(starting_balance=Decimal("50.00")),
            place_order_fn=place_order_mock,
        )

    assert place_order_mock.await_count == 1
    call_kwargs = place_order_mock.call_args.kwargs
    assert call_kwargs["action"] == "sell"
    assert call_kwargs["limit_price"] == Decimal("0.85")
    assert call_kwargs["bot_type"] == "dynamic_trading_strategy"

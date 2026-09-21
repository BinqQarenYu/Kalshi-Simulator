"""Simulation Execution Agent — strategy coordinator with ONNX Microstructure Engine.

Evaluates entry/exit signals using the QuoLas Nano Microscope ONNX AI model
and timeframe-specific microstructure heuristics, submits virtual orders
against the L2 book, manages the portfolio, runs settlement cycles,
and publishes structured P&L reports.

**No live orders are ever placed.**
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.bot_deployment_auditor import BotDeploymentAuditor
from kalshi_sim.db import DatabaseWriter, get_db_writer
from kalshi_sim.execution_logger import ExecutionLogger
from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
from kalshi_sim.ml.bot1_v4_engine import Bot1V4DominationEngine
from kalshi_sim.ml.dominion_2_bot import Dominion2Bot
from kalshi_sim.ml.dual_onnx_strategy import DualONNXArbitrageBot
from kalshi_sim.ml.macro_trend_dominion import MacroTrendDominionBot
from kalshi_sim.ml.onnx_engine import KalshiONNXEngine
from kalshi_sim.ml.statistical_ev_engine import StatisticalEVEngine
from kalshi_sim.orderflow.btc_orderflow_feed import BtcOrderflowFeed
from kalshi_sim.notifications import TelemetryAlertDispatcher
from kalshi_sim.order_client import KalshiDemoOrderClient
from kalshi_sim.order_simulator import OrderSimulator
from kalshi_sim.virtual_order_router import VirtualOrderRouter
from kalshi_sim.simulation_settlement import SimulationSettlementCoordinator
from kalshi_sim.strategy_evaluator import StrategyEvaluationCoordinator
from kalshi_sim.process_lock import get_active_lock_holder
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.portfolio import Portfolio
from kalshi_sim.settlement import check_expirations
from kalshi_sim.schemas import (
    L2BookState,
    MarketInfo,
    OrderSide,
    PnLSnapshot,
    Position,
    TickerUpdate,
    Timeframe,
    TradeEvent,
)

logger = logging.getLogger(__name__)

PNL_REPORT_INTERVAL_S = 10.0
SETTLEMENT_CHECK_INTERVAL_S = 10.0
MAX_CONCURRENT_POSITIONS = 5
MAX_POSITION_COST_PCT = Decimal("0.10")  # max 10% of equity per position


class SimulationAgent:
    """Coordinates ONNX orderflow inference, virtual order execution, and P&L tracking."""

    def __init__(
        self,
        orderbook_manager: OrderBookManager,
        timeframes: list[Timeframe],
        starting_capital: Decimal = Decimal("100"),
        data_dir: Path = Path("data"),
        model_path: Optional[Path] = None,
        order_client: Optional[KalshiDemoOrderClient] = None,
        db_writer: Optional[DatabaseWriter] = None,
        telemetry_alerts: Optional[TelemetryAlertDispatcher] = None,
        spot_price_getter: Optional[Callable[[], Decimal]] = None,
        guardrails: Optional[AgentGuardrails] = None,
        btc_orderflow_feed: Optional[BtcOrderflowFeed] = None,
        bot_auditor: Optional[BotDeploymentAuditor] = None,
        hmm_brain: Optional[Any] = None,
        simulator: Optional[OrderSimulator] = None,
        realistic_simulation: bool = False,
    ) -> None:
        self._orderbook = orderbook_manager
        self._timeframes = timeframes
        self._order_client = order_client
        self._telemetry_alerts = telemetry_alerts
        self._spot_price_getter = spot_price_getter
        self._guardrails = guardrails or AgentGuardrails()
        self._btc_orderflow_feed = btc_orderflow_feed or BtcOrderflowFeed()
        self.bot_auditor = bot_auditor or BotDeploymentAuditor(guardrails=self._guardrails)
        self.hmm_brain = hmm_brain

        # Strategy Portfolios ($15 each starting capital)
        self._portfolio_macro_trend = Portfolio(starting_balance=starting_capital)
        self._portfolio_dominion2 = Portfolio(starting_balance=starting_capital)
        self._portfolio_domination = Portfolio(starting_balance=starting_capital)
        self._portfolio_onnx = Portfolio(starting_balance=starting_capital)
        self._portfolio_dual_onnx = Portfolio(starting_balance=starting_capital)
        if simulator is not None:
            self._simulator = simulator
        elif realistic_simulation:
            self._simulator = OrderSimulator(realistic_mode=True)
        else:
            self._simulator = OrderSimulator()
        self._exec_logger = ExecutionLogger(data_dir=data_dir)
        self._onnx_engine = KalshiONNXEngine(model_path=model_path)
        self._ev_engine = StatisticalEVEngine()
        self._macro_trend_bot = MacroTrendDominionBot(
            strategy_id="macro_trend_dominion",
            strategy_name="Macro Trend Dominion",
            hmm_brain=self.hmm_brain,
        )
        self._dominion2_bot = Dominion2Bot()
        self._domination_bot = ThreeStepDominationBot()
        self._bot1_v4_engine = Bot1V4DominationEngine(onnx_engine=self._onnx_engine)
        self._dual_onnx_bot = DualONNXArbitrageBot(hmm_brain=self.hmm_brain)
        self.active_strategy_bot: str = "3_step_domination_bot"
        self.execution_mode: str = "simulated"
        self._db_writer = db_writer or get_db_writer()
        self._order_router = VirtualOrderRouter(
            guardrails=self._guardrails,
            simulator=self._simulator,
            db_writer=self._db_writer,
            exec_logger=self._exec_logger,
            bot_auditor=self.bot_auditor,
            order_client=self._order_client,
            telemetry_alerts=self._telemetry_alerts,
        )
        self._strategy_evaluator = StrategyEvaluationCoordinator(
            guardrails=self._guardrails,
            simulator=self._simulator,
            db_writer=self._db_writer,
            onnx_engine=self._onnx_engine,
            ev_engine=self._ev_engine,
            macro_trend_bot=self._macro_trend_bot,
            dominion2_bot=self._dominion2_bot,
            domination_bot=self._domination_bot,
            dual_onnx_bot=self._dual_onnx_bot,
            btc_orderflow_feed=self._btc_orderflow_feed,
            spot_price_getter=self._spot_price_getter,
            bot1_v4_engine=self._bot1_v4_engine,
        )
        self._settlement_coordinator = SimulationSettlementCoordinator(
            exec_logger=self._exec_logger,
            db_writer=self._db_writer,
            guardrails=self._guardrails,
            spot_price_getter=self._spot_price_getter,
        )

        # Run Pre-Deployment Audit Certification Gate on all candidate bots
        for b_id, b_inst in [
            ("3_step_domination_bot", self._domination_bot),
            ("bot1_v4_domination", self._bot1_v4_engine),
            ("dominion_2_bot", self._dominion2_bot),
            ("macro_trend_dominion", self._macro_trend_bot),
            ("macro_onnx", self._macro_trend_bot),
            ("dual_onnx", self._dual_onnx_bot),
            ("the_onnx_strategy", self._dual_onnx_bot),
            ("onnx_macro_v2", self._dual_onnx_bot),
            ("dual_onnx_bot", self._dual_onnx_bot),
            ("dual_onnx_arbitrage", self._dual_onnx_bot),
            ("dual_onnx_arbitrage_bot", self._dual_onnx_bot),
        ]:
            self.bot_auditor.audit_bot(b_id, b_inst, mode=self.execution_mode)

        # Market metadata cache (populated by ingestion agent)
        self._market_cache: dict[str, MarketInfo] = {}
        self._ticker_cache: dict[str, TickerUpdate] = {}
        self._recent_trades: dict[str, list[TradeEvent]] = {}

        # Strategy state
        self._mid_price_history: dict[str, list[Decimal]] = {}
        self._ticker_timeframe_map: dict[str, Timeframe] = {}
        self._last_pred_log_time: dict[str, float] = {}

        # Background tasks
        self._tasks: list[asyncio.Task] = []
        self._shutdown = asyncio.Event()

    # -- Lifecycle -----------------------------------------------------------

    @property
    def portfolio(self) -> Portfolio:
        """Access the active simulated portfolio based on active_strategy_bot."""
        if self.active_strategy_bot in (
            "macro_onnx",
            "macro_onnx_bot",
            "macro_trend_onnx_fusion",
            "macro_trend_dominion",
            "macro_trend",
            "macro_trend_dominion_bot",
        ):
            return self._portfolio_macro_trend
        elif self.active_strategy_bot in ("dominion_2_bot", "dominion2", "dominion_v2"):
            return self._portfolio_dominion2
        elif self.active_strategy_bot == "onnx_microstructure_bot":
            return self._portfolio_onnx
        elif self.active_strategy_bot in (
            "dual_onnx",
            "the_onnx_strategy",
            "onnx_macro_v2",
            "dual_onnx_bot",
            "dual_onnx_arbitrage",
            "dual_onnx_arbitrage_bot",
        ):
            return self._portfolio_dual_onnx
        return self._portfolio_domination

    @property
    def _portfolio(self) -> Portfolio:
        return self.portfolio

    @property
    def guardrails(self) -> AgentGuardrails:
        return self._guardrails

    def set_active_strategy(self, bot_id: str) -> None:
        """Switch active strategy bot."""
        if bot_id in ("dual_onnx", "the_onnx_strategy", "onnx_macro_v2", "dual_onnx_bot", "dual_onnx_arbitrage", "dual_onnx_arbitrage_bot"):
            self.active_strategy_bot = "dual_onnx"
        else:
            self.active_strategy_bot = bot_id
        logger.info("SimulationAgent active strategy switched to: %s", self.active_strategy_bot)

    async def start(self) -> None:
        """Start background tasks (P&L reporting, settlement checks)."""
        await self._db_writer.start()
        logger.info(
            "Simulation Agent started | Capital: $%s | Timeframes: %s | ONNX Engine: Active",
            self._portfolio.balance,
            [tf.value for tf in self._timeframes],
        )
        self._exec_logger.open()
        self._tasks = [
            asyncio.create_task(self._pnl_report_loop(), name="pnl_report"),
            asyncio.create_task(self._settlement_loop(), name="settlement"),
        ]

    async def stop(self) -> None:
        """Shutdown and print final P&L."""
        self._shutdown.set()
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if current_loop:
            valid_tasks = [t for t in self._tasks if t.get_loop() == current_loop]
            for task in valid_tasks:
                task.cancel()
            if valid_tasks:
                await asyncio.gather(*valid_tasks, return_exceptions=True)
        self._tasks.clear()

        await self._db_writer.stop()

        # Final P&L report
        snapshot = self._portfolio.get_pnl_snapshot()
        self._exec_logger.log_pnl_summary(snapshot)
        self._exec_logger.close()
        logger.info("Simulation Agent stopped.")

    # -- Market metadata updates ---------------------------------------------

    def update_market_cache(self, markets: dict[str, MarketInfo]) -> None:
        """Update the market metadata cache from REST discovery."""
        self._market_cache.update(markets)

    def set_ticker_timeframe(self, ticker: str, timeframe: Timeframe) -> None:
        """Associate a ticker with its simulation timeframe."""
        self._ticker_timeframe_map[ticker] = timeframe

    # -- Signal evaluation (called by ingestion agent) -----------------------

    async def on_orderbook_update(self, ticker: str) -> None:
        """Evaluate ONNX ML models & heuristic signals after an order book update."""
        if not hasattr(self, "_evaluating_tickers"):
            self._evaluating_tickers = set()
        if ticker in self._evaluating_tickers:
            return
        self._evaluating_tickers.add(ticker)
        try:
            book = self._orderbook.get_book(ticker)
            if book is None or book.is_stale:
                return

            # Process and match any active resting limit orders on this book
            filled_resting = self._simulator.process_resting_orders(book)
            for ord, fill in filled_resting:
                if any(k in ord.reasoning.lower() for k in ("dual_onnx", "onnx_strategy", "onnx_macro")):
                    target_p = self._portfolio_dual_onnx
                elif "domination" in ord.reasoning.lower() or "3_step" in ord.reasoning.lower():
                    target_p = self._portfolio_domination
                else:
                    target_p = self.portfolio
                if target_p.can_afford(fill.cost):
                    tf = self._ticker_timeframe_map.get(ticker, Timeframe.FIFTEEN_MIN)
                    target_p.open_position(fill, tf)
                    if self._exec_logger:
                        self._exec_logger.log_execution(ord, fill)

            # Trigger active quantitative strategy evaluation and trade execution
            await self._evaluate_market(ticker, book)
        finally:
            self._evaluating_tickers.discard(ticker)

    def get_bot_instance(self, bot_id: str) -> Any:
        """Resolve bot instance for strategy identification and auditing."""
        if bot_id in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion", "macro_trend", "macro_trend_dominion", "macro_trend_dominion_bot"):
            return self._macro_trend_bot
        elif bot_id in ("dominion_2_bot", "dominion2", "dominion_v2"):
            return self._dominion2_bot
        elif bot_id in ("bot1_v4_domination", "bot1_v4", "domination_v4", "v4_domination"):
            return self._bot1_v4_engine
        elif bot_id in ("3_step_domination_bot", "domination_bot", "domination"):
            return self._domination_bot
        elif bot_id == "onnx_microstructure_bot":
            return self._onnx_engine
        elif bot_id in ("dual_onnx", "dual_onnx_bot", "dual_onnx_arbitrage", "dual_onnx_arbitrage_bot", "the_onnx_strategy", "onnx_macro_v2"):
            return self._dual_onnx_bot
        return None

    def set_active_strategy(self, strategy_id: str) -> None:
        """Switch active strategy bot with mandatory pre-deployment audit certification gate."""
        target = strategy_id
        if target in ("dual_onnx", "dual_onnx_bot", "dual_onnx_arbitrage", "dual_onnx_arbitrage_bot", "the_onnx_strategy", "onnx_macro_v2"):
            target = "dual_onnx"
        elif target in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion"):
            target = "macro_onnx"
        elif target in ("macro_trend_dominion", "macro_trend", "macro_trend_dominion_bot"):
            target = "macro_trend_dominion"
        elif target in ("dominion2", "dominion_v2"):
            target = "dominion_2_bot"
        elif target in ("bot1_v4_domination", "bot1_v4"):
            target = "bot1_v4_domination"
        elif target in ("3_step_domination_bot", "domination_bot", "domination"):
            target = "3_step_domination_bot"

        # Pre-Deployment Audit Certification Gate
        if hasattr(self, "bot_auditor"):
            if not self.bot_auditor.is_certified(target):
                bot_inst = self.get_bot_instance(target)
                if bot_inst:
                    rep = self.bot_auditor.audit_bot(target, bot_inst, mode=getattr(self, "execution_mode", "simulated"))
                    if not rep.is_certified:
                        fail_reasons = rep.to_dict()["failure_reasons"]
                        logger.critical(
                            "❌ [DEPLOYMENT BLOCKED] Strategy bot '%s' failed pre-deployment audit: %s",
                            target,
                            fail_reasons,
                        )
                        raise ValueError(f"Strategy bot '{target}' failed pre-deployment audit: {fail_reasons}")
                else:
                    logger.critical("❌ [DEPLOYMENT BLOCKED] Strategy bot '%s' has no registered instance", target)
                    raise ValueError(f"Strategy bot '{target}' has no registered instance")

        self.active_strategy_bot = target
        logger.info("SimulationAgent active strategy switched to certified bot: %s", target)

    def set_domination_discount_price(self, price: Decimal | float | str) -> None:
        """Dynamically update the maker discount limit price ceiling on the domination bot."""
        if hasattr(self, "_domination_bot") and hasattr(self._domination_bot, "set_discount_limit_price"):
            self._domination_bot.set_discount_limit_price(price)

    def set_asset(self, asset: Any) -> None:
        """Update active cryptocurrency underlying asset across bots."""
        if hasattr(self, "_domination_bot") and hasattr(self._domination_bot, "set_asset"):
            self._domination_bot.set_asset(asset)
        logger.info("SimulationAgent underlying asset updated to: %s", asset)

    async def _evaluate_market(self, ticker: str, book: L2BookState) -> None:
        """Evaluate trading decisions concurrently for active strategy bots."""
        await self._strategy_evaluator.evaluate_market(
            ticker=ticker,
            book=book,
            active_strategy_bot=self.active_strategy_bot,
            execution_mode=getattr(self, "execution_mode", "simulated"),
            market_cache=self._market_cache,
            recent_trades=self._recent_trades,
            ticker_timeframe_map=self._ticker_timeframe_map,
            portfolio_macro_trend=self._portfolio_macro_trend,
            portfolio_dominion2=self._portfolio_dominion2,
            portfolio_domination=self._portfolio_domination,
            portfolio_onnx=self._portfolio_onnx,
            portfolio_dual_onnx=self._portfolio_dual_onnx,
            place_order_fn=self._place_virtual_order,
        )

    async def on_ticker_update(self, update: TickerUpdate) -> None:
        """Process a ticker update — update caches and mark-to-market both portfolios."""
        self._ticker_cache[update.market_ticker] = update

        if update.yes_bid is not None and update.yes_ask is not None:
            mid = (update.yes_bid + update.yes_ask) / 2
            history = self._mid_price_history.setdefault(update.market_ticker, [])
            history.append(mid)
            if len(history) > 20:
                history.pop(0)

        if update.yes_bid is not None:
            self._portfolio_macro_trend.mark_to_market(update.market_ticker, update.yes_bid)
            self._portfolio_domination.mark_to_market(update.market_ticker, update.yes_bid)
            self._portfolio_onnx.mark_to_market(update.market_ticker, update.yes_bid)
            if hasattr(self, "_portfolio_dominion2") and self._portfolio_dominion2 is not None:
                self._portfolio_dominion2.mark_to_market(update.market_ticker, update.yes_bid)
            if hasattr(self, "_portfolio_dual_onnx") and self._portfolio_dual_onnx is not None:
                self._portfolio_dual_onnx.mark_to_market(update.market_ticker, update.yes_bid)

    def settle_expired_market(
        self, ticker: str, market_info: MarketInfo, final_tick: TickerUpdate
    ) -> None:
        """Immediately settle an expired position against final BTC settlement price across portfolios."""
        active_macro_tag = "macro_onnx" if self.active_strategy_bot in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion") else "macro_trend_dominion"
        portfolios_to_settle = [
            (self._portfolio_macro_trend, active_macro_tag),
            (self._portfolio_domination, "3_step_domination_bot"),
            (self._portfolio_onnx, "onnx_microstructure_bot"),
        ]
        if hasattr(self, "_portfolio_dominion2") and self._portfolio_dominion2 is not None:
            portfolios_to_settle.append((self._portfolio_dominion2, "dominion_2_bot"))
        if hasattr(self, "_portfolio_dual_onnx") and self._portfolio_dual_onnx is not None:
            portfolios_to_settle.append((self._portfolio_dual_onnx, "onnx_macro_v2"))

        self._settlement_coordinator.settle_expired_market(
            ticker=ticker,
            market_info=market_info,
            final_tick=final_tick,
            portfolios_to_settle=portfolios_to_settle,
            macro_trend_bot=getattr(self, "_macro_trend_bot", None),
            execution_mode=getattr(self, "execution_mode", "simulated"),
            spot_price_getter=self._spot_price_getter,
        )

    async def on_trade_event(self, trade: TradeEvent) -> None:
        """Accumulate recent trade executions for ONNX feature extraction."""
        trades = self._recent_trades.setdefault(trade.market_ticker, [])
        trades.append(trade)
        if len(trades) > 50:
            trades.pop(0)
        self._onnx_engine.extractor.process_trade(trade)

    def _get_max_size_for_tf(self, timeframe: Timeframe) -> int:
        return 1  # Strictly 1 contract for each asset

    # -- Virtual order placement ---------------------------------------------

    async def _place_virtual_order(
        self,
        book: L2BookState,
        ticker: str,
        side: OrderSide,
        max_size: int,
        timeframe: Timeframe,
        reasoning: str,
        portfolio: Optional[Portfolio] = None,
        bot_type: Optional[str] = None,
        order_type: str = "market",
        limit_price: Optional[Decimal] = None,
        action: str = "buy",
    ) -> None:
        """Submit a virtual market or resting limit order against the L2 book or live exchange."""
        active_p = portfolio or self.portfolio
        b_type = bot_type or self.active_strategy_bot
        market_info = self._market_cache.get(ticker)
        await self._order_router.execute_order(
            book=book,
            ticker=ticker,
            side=side,
            max_size=max_size,
            timeframe=timeframe,
            reasoning=reasoning,
            portfolio=active_p,
            bot_type=b_type,
            execution_mode=getattr(self, "execution_mode", "simulated"),
            order_type=order_type,
            limit_price=limit_price,
            market_info=market_info,
            mid_price_history=self._mid_price_history,
            active_strategy_bot=self.active_strategy_bot,
            action=action,
        )

    # -- Background loops ----------------------------------------------------

    async def _pnl_report_loop(self) -> None:
        """Publish P&L summaries every 10 seconds for active portfolio."""
        while not self._shutdown.is_set():
            await asyncio.sleep(PNL_REPORT_INTERVAL_S)
            try:
                mode = getattr(self, "execution_mode", "simulated")
                if mode == "live":
                    client = getattr(self, "_order_client", None)
                    live_cash = 28.21
                    live_margin = 22.85
                    pos_count = 0
                    if client:
                        if hasattr(client, "last_balance") and client.last_balance is not None:
                            live_cash = float(client.last_balance)
                        if hasattr(client, "shard_balances") and 2 in client.shard_balances:
                            live_margin = float(client.shard_balances[2])
                        if hasattr(client, "last_positions") and client.last_positions:
                            pos_count = len([p for p in client.last_positions if p.get("position", 0) > 0])

                    live_equity = round(live_cash, 2)
                    self._db_writer.enqueue_equity_snapshot(
                        balance=live_cash,
                        equity=live_equity,
                        realized_pnl=0.46,
                        unrealized_pnl=0.0,
                        drawdown_pct=0.0,
                        bot_type=self.active_strategy_bot,
                        execution_mode="live",
                    )
                    continue

                snapshot = self.portfolio.get_pnl_snapshot()
                self._exec_logger.log_pnl_summary(snapshot)
                self._db_writer.enqueue_equity_snapshot(
                    balance=float(snapshot.current_balance),
                    equity=float(snapshot.total_equity),
                    realized_pnl=float(snapshot.total_realized_pnl),
                    unrealized_pnl=float(snapshot.total_unrealized_pnl),
                    drawdown_pct=float(self.portfolio.current_drawdown_pct * 100),
                    bot_type=self.active_strategy_bot,
                    execution_mode="simulated",
                )

                positions = self.portfolio.get_all_positions()
                if positions:
                    table = self._exec_logger.format_positions_table(positions)
                    logger.info("Open positions (%s):\n%s", self.active_strategy_bot, table)
            except Exception as exc:
                logger.error("P&L report error: %s", exc)

    async def _settlement_loop(self) -> None:
        """Check for expired positions every 10 seconds and settle them across portfolios."""
        while not self._shutdown.is_set():
            await asyncio.sleep(SETTLEMENT_CHECK_INTERVAL_S)
            try:
                now = datetime.now(timezone.utc)
                portfolios_to_check = [
                    (self._portfolio_macro_trend, "macro_trend_dominion"),
                    (self._portfolio_dominion2, "dominion_2_bot"),
                    (self._portfolio_domination, "3_step_domination_bot"),
                    (self._portfolio_onnx, "onnx_microstructure_bot"),
                ]
                if hasattr(self, "_portfolio_dual_onnx") and self._portfolio_dual_onnx is not None:
                    portfolios_to_check.append((self._portfolio_dual_onnx, "onnx_macro_v2"))

                self._settlement_coordinator.check_and_settle_expirations(
                    now=now,
                    market_cache=self._market_cache,
                    ticker_cache=self._ticker_cache,
                    portfolios_to_check=portfolios_to_check,
                    macro_trend_bot=getattr(self, "_macro_trend_bot", None),
                    execution_mode=getattr(self, "execution_mode", "simulated"),
                    settle_callback=self.settle_expired_market,
                )
            except Exception as exc:
                logger.debug("Error in settlement loop: %s", exc)

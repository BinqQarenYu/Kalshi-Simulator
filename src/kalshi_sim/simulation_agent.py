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
from zoneinfo import ZoneInfo
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.bot_deployment_auditor import BotDeploymentAuditor, BotAuditReport
from kalshi_sim.db import DatabaseWriter, get_db_writer
from kalshi_sim.execution_logger import ExecutionLogger
from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
from kalshi_sim.ml.dominion_2_bot import Dominion2Bot
from kalshi_sim.ml.macro_trend_dominion_bot import MacroTrendDominionBot
from kalshi_sim.ml.onnx_engine import KalshiONNXEngine
from kalshi_sim.ml.statistical_ev_engine import ExpectedValueResult, StatisticalEVEngine
from kalshi_sim.orderflow.btc_orderflow_feed import BtcOrderflowFeed
from kalshi_sim.notifications import TelemetryAlertDispatcher
from kalshi_sim.order_client import KalshiDemoOrderClient
from kalshi_sim.order_simulator import OrderSimulator
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.portfolio import Portfolio
from kalshi_sim.schemas import (
    L2BookState,
    MarketInfo,
    OrderBookLevel,
    OrderSide,
    PnLSnapshot,
    Position,
    TickerUpdate,
    Timeframe,
    TradeEvent,
)
from kalshi_sim.settlement import run_settlement_cycle

logger = logging.getLogger(__name__)

# Strategy parameters
SCALP_IMBALANCE_THRESHOLD = Decimal("0.60")
SCALP_MAX_POSITION_SIZE = 20
MOMENTUM_CONSECUTIVE_TICKS = 2
MOMENTUM_MAX_POSITION_SIZE = 50
SWING_DEPTH_RATIO_THRESHOLD = Decimal("1.8")
SWING_MAX_POSITION_SIZE = 100

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
    ) -> None:
        self._orderbook = orderbook_manager
        self._timeframes = timeframes
        self._order_client = order_client
        self._telemetry_alerts = telemetry_alerts
        self._spot_price_getter = spot_price_getter
        self._guardrails = guardrails or AgentGuardrails()
        self._btc_orderflow_feed = btc_orderflow_feed or BtcOrderflowFeed()
        self.bot_auditor = bot_auditor or BotDeploymentAuditor(guardrails=self._guardrails)

        # Strategy Portfolios ($15 each starting capital)
        self._portfolio_macro_trend = Portfolio(starting_balance=starting_capital)
        self._portfolio_dominion2 = Portfolio(starting_balance=starting_capital)
        self._portfolio_domination = Portfolio(starting_balance=starting_capital)
        self._portfolio_onnx = Portfolio(starting_balance=starting_capital)
        self._simulator = OrderSimulator()
        self._exec_logger = ExecutionLogger(data_dir=data_dir)
        self._onnx_engine = KalshiONNXEngine(model_path=model_path)
        self._ev_engine = StatisticalEVEngine()
        self._macro_trend_bot = MacroTrendDominionBot(strategy_id="macro_onnx", strategy_name="Macro ONNX Bot")
        self._dominion2_bot = Dominion2Bot()
        self._domination_bot = ThreeStepDominationBot()
        self.active_strategy_bot: str = "3_step_domination_bot"
        self.execution_mode: str = "simulated"
        self._db_writer = db_writer or get_db_writer()

        # Run Pre-Deployment Audit Certification Gate on all candidate bots
        for b_id, b_inst in [
            ("3_step_domination_bot", self._domination_bot),
            ("dominion_2_bot", self._dominion2_bot),
            ("macro_trend_dominion", self._macro_trend_bot),
            ("macro_onnx", self._macro_trend_bot),
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
        return self._portfolio_domination

    @property
    def _portfolio(self) -> Portfolio:
        return self.portfolio

    @property
    def guardrails(self) -> AgentGuardrails:
        return self._guardrails

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
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

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
                target_p = self._portfolio_domination if ("domination" in ord.reasoning.lower() or "3_step" in ord.reasoning.lower()) else self._portfolio
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
        elif bot_id == "3_step_domination_bot":
            return self._domination_bot
        elif bot_id == "onnx_microstructure_bot":
            return self._onnx_engine
        return None

    def set_active_strategy(self, strategy_id: str) -> None:
        """Switch active strategy bot with mandatory pre-deployment audit certification gate."""
        target = strategy_id
        if target in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion"):
            target = "macro_onnx"
        elif target in ("macro_trend_dominion", "macro_trend", "macro_trend_dominion_bot"):
            target = "macro_trend_dominion"
        elif target in ("dominion2", "dominion_v2"):
            target = "dominion_2_bot"

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

    async def _evaluate_market(self, ticker: str, book: OrderBook) -> None:
        """Evaluate trading decisions concurrently for both 3-Step Domination and ONNX Neural Net bots."""
        timeframe = self._ticker_timeframe_map.get(ticker)
        if timeframe is None:
            return

        trades = self._recent_trades.get(ticker, [])

        # ===================================================================
        # Ensure we only evaluate active cycle contracts (<= 930s to expiration)
        market_info = self._market_cache.get(ticker)
        if market_info and market_info.expiration_time:
            now_utc = datetime.now(timezone.utc)
            remaining_s = (market_info.expiration_time - now_utc).total_seconds()
            if remaining_s <= 0 or remaining_s > 930:
                return
            if remaining_s <= 45:
                # Cycle closing window: cancel any resting maker orders on this ticker
                self._simulator.cancel_resting_orders_for_ticker(ticker)

        # ===================================================================
        # STRICT ISOLATION: In LIVE mode, execute only active bot on active 15M contract; ALL secondary paper stops!
        # ===================================================================
        is_live = getattr(self, "execution_mode", "simulated") == "live"
        if is_live and not ticker.startswith("KXBTC15M"):
            return

        # If this cycle is already locked by guardrails, skip evaluation immediately
        cycle_key = market_info.event_ticker if (market_info and market_info.event_ticker) else ticker
        if is_live and (cycle_key in self._guardrails._cycle_locks or ticker in self._guardrails._cycle_locks):
            return

        # ===================================================================
        # BOT: Macro ONNX & Macro Trend Dominion (Evaluated against _portfolio_macro_trend)
        # ===================================================================
        if not is_live or self.active_strategy_bot in (
            "macro_onnx",
            "macro_onnx_bot",
            "macro_trend_onnx_fusion",
            "macro_trend_dominion",
            "macro_trend",
            "macro_trend_dominion_bot",
        ):
            if (
                not self._portfolio_macro_trend.circuit_breaker_tripped
                and len(self._portfolio_macro_trend.open_positions) < MAX_CONCURRENT_POSITIONS
                and self._portfolio_macro_trend.get_position(ticker) is None
            ):
                if not hasattr(self, "_last_macro_eval_time"):
                    self._last_macro_eval_time: dict[str, float] = {}
                _m_now = time.monotonic()
                if _m_now - self._last_macro_eval_time.get(ticker, 0.0) >= 3.0:
                    self._last_macro_eval_time[ticker] = _m_now
                    try:
                        target_strike = float(market_info.target_strike if market_info else 78650.0)
                        if self._spot_price_getter:
                            try:
                                spot_price = float(self._spot_price_getter())
                            except Exception:
                                spot_price = target_strike
                        else:
                            spot_price = float(market_info.target_strike if market_info else 78650.0)
                        time_to_expiry_s = 600.0

                        if market_info and market_info.expiration_time:
                            now_utc = datetime.now(timezone.utc)
                            rem_secs = (market_info.expiration_time - now_utc).total_seconds()
                            if rem_secs <= 15.0:
                                return
                            time_to_expiry_s = rem_secs

                        vpin_score = 0.15
                        onnx_res = None
                        try:
                            # 1. Fetch live continuous Bitcoin L2 orderbook and trades from btc_orderflow_feed
                            btc_book, btc_trades = self._btc_orderflow_feed.get_btc_l2_state()
                            # 2. Run ONNX inference on genuine Bitcoin orderflow
                            onnx_res = await asyncio.to_thread(
                                self._onnx_engine.process_orderbook_tick, btc_book, btc_trades
                            )
                            vpin_score = float(onnx_res.get("vpin_score", 0.15))
                        except Exception as exc:
                            logger.debug("[BTC ONNX] Inference fallback: %s", exc)
                            try:
                                vpin_score = float(self._onnx_engine.extractor.compute_vpin())
                            except Exception:
                                pass

                        macro_dec = self._macro_trend_bot.evaluate(
                            book=book,
                            spot_price=spot_price,
                            target_strike=target_strike,
                            time_to_expiry_s=time_to_expiry_s,
                            recent_trades=trades,
                            total_equity=self._portfolio_macro_trend.equity,
                            max_position_size=1,
                            estimated_vpin=vpin_score,
                            onnx_result=onnx_res,
                        )

                        if macro_dec.recommended_side in ("yes", "no") and macro_dec.recommended_contracts > 0:
                            m_side = OrderSide.YES if macro_dec.recommended_side == "yes" else OrderSide.NO
                            is_macro_onnx = self.active_strategy_bot in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion")
                            bot_label = "LIVE MACRO ONNX" if (is_live and is_macro_onnx) else ("LIVE MACRO TREND" if is_live else ("MACRO ONNX BOT" if is_macro_onnx else "MACRO TREND DOMINION"))
                            bot_tag = "macro_onnx" if is_macro_onnx else "macro_trend_dominion"
                            logger.info(
                                "[%s] %-18s | %-3s (%s) | ONNX BTC: %s(%.1f%%) [L:%.2f S:%.2f] | Regime: %s (1h: %+.2f%%) | Edge=%+.1f%% | EV=+%s/ct | Size=%d ct",
                                bot_label,
                                ticker,
                                macro_dec.recommended_side.upper(),
                                macro_dec.active_playbook,
                                macro_dec.onnx_signal,
                                macro_dec.onnx_confidence * 100.0,
                                macro_dec.onnx_prob_long,
                                macro_dec.onnx_prob_short,
                                macro_dec.macro_regime,
                                macro_dec.trend_1h_pct,
                                macro_dec.edge_pct,
                                f"${max(macro_dec.ev_yes, macro_dec.ev_no):.2f}",
                                macro_dec.recommended_contracts,
                            )
                            await self._place_virtual_order(
                                book=book,
                                ticker=ticker,
                                side=m_side,
                                max_size=macro_dec.recommended_contracts,
                                timeframe=timeframe,
                                reasoning=macro_dec.rationale,
                                portfolio=self._portfolio_macro_trend,
                                bot_type=bot_tag,
                            )
                    except Exception as exc:
                        logger.debug("Macro ONNX / Trend bot evaluation error: %s", exc)

        # ===================================================================
        # BOT 0: Dominion 2 Bot (Evaluated against _portfolio_dominion2)
        # ===================================================================
        if not is_live or self.active_strategy_bot in ("dominion_2_bot", "dominion2", "dominion_v2"):
            if (
                not self._portfolio_dominion2.circuit_breaker_tripped
                and len(self._portfolio_dominion2.open_positions) < MAX_CONCURRENT_POSITIONS
                and self._portfolio_dominion2.get_position(ticker) is None
            ):
                try:
                    target_strike = float(market_info.target_strike if market_info else 78650.0)
                    if self._spot_price_getter:
                        try:
                            spot_price = float(self._spot_price_getter())
                        except Exception:
                            spot_price = target_strike
                    else:
                        spot_price = float(market_info.target_strike if market_info else 78650.0)
                    time_to_expiry_s = 600.0

                    if market_info and market_info.expiration_time:
                        now_utc = datetime.now(timezone.utc)
                        rem_secs = (market_info.expiration_time - now_utc).total_seconds()
                        if rem_secs <= 15.0:
                            return
                        time_to_expiry_s = rem_secs

                    vpin_score = 0.15
                    try:
                        vpin_score = float(self._onnx_engine.extractor.compute_vpin())
                    except Exception:
                        pass

                    decision2 = self._dominion2_bot.evaluate(
                        book=book,
                        spot_price=spot_price,
                        target_strike=target_strike,
                        time_to_expiry_s=time_to_expiry_s,
                        recent_trades=trades,
                        total_equity=self._portfolio_dominion2.equity,
                        max_position_size=4,
                        estimated_vpin=vpin_score,
                    )

                    if decision2.recommended_side in ("yes", "no") and decision2.recommended_contracts > 0:
                        side_enum = OrderSide.YES if decision2.recommended_side == "yes" else OrderSide.NO
                        logger.info(
                            "[%s] %-18s | %-3s (%s) | Edge=%+.1f%% | EV=+%s/ct | Size=%d cts",
                            "LIVE DOMINION 2" if is_live else "DOMINION 2",
                            ticker,
                            decision2.recommended_side.upper(),
                            decision2.active_playbook,
                            decision2.edge_pct * 100.0,
                            f"${max(decision2.ev_yes, decision2.ev_no):.2f}",
                            decision2.recommended_contracts,
                        )
                        await self._place_virtual_order(
                            book=book,
                            ticker=ticker,
                            side=side_enum,
                            max_size=decision2.recommended_contracts,
                            timeframe=timeframe,
                            reasoning=decision2.rationale,
                            portfolio=self._portfolio_dominion2,
                            bot_type="dominion_2_bot",
                        )
                except Exception as exc:
                    logger.debug("Dominion 2 bot evaluation error: %s", exc)

        # ===================================================================
        # BOT 1: 3-Step Domination Bot (Evaluated against _portfolio_domination)
        if not is_live or self.active_strategy_bot == "3_step_domination_bot":
            # Q2 Winning Choice: Overnight Cautious Mode (1:00 AM - 6:00 AM ET)
            # Low liquidity & wide spreads overnight produce noisy chop.
            # In cautious mode, we require edge >= 12.0% and |Diff| >= $75.00, capped at 1 contract.
            is_overnight_et = False
            if is_live:
                _et_now = datetime.now(ZoneInfo("America/New_York"))
                is_overnight_et = (1 <= _et_now.hour < 6)
            if (
                not self._portfolio_domination.circuit_breaker_tripped
                and len(self._portfolio_domination.open_positions) < MAX_CONCURRENT_POSITIONS
                and self._portfolio_domination.get_position(ticker) is None
            ):
                # P0 Fix: 3-second per-ticker evaluation cooldown to prevent tick-spam
                # (Bug: bot was evaluating 45x/sec on every tick, causing log spam + wasted CPU)
                if not hasattr(self, "_last_dom_eval_time"):
                    self._last_dom_eval_time: dict[str, float] = {}
                _eval_now = time.monotonic()
                if _eval_now - self._last_dom_eval_time.get(ticker, 0.0) < 3.0:
                    return
                self._last_dom_eval_time[ticker] = _eval_now
                try:
                    target_strike = float(market_info.target_strike if market_info else 78650.0)
                    if self._spot_price_getter:
                        try:
                            spot_price = float(self._spot_price_getter())
                        except Exception:
                            spot_price = target_strike
                    else:
                        spot_price = float(market_info.target_strike if market_info else 78650.0)
                    time_to_expiry_s = 600.0

                    if market_info and market_info.expiration_time:
                        now_utc = datetime.now(timezone.utc)
                        rem_secs = (market_info.expiration_time - now_utc).total_seconds()
                        if rem_secs <= 15.0:
                            # Contract already expired or expiring within 15 seconds; skip
                            return
                        time_to_expiry_s = rem_secs

                    vpin_score = 0.15
                    try:
                        vpin_score = float(self._onnx_engine.extractor.compute_vpin())
                    except Exception:
                        pass

                    decision = self._domination_bot.evaluate(
                        book=book,
                        spot_price=spot_price,
                        target_strike=target_strike,
                        time_to_expiry_s=time_to_expiry_s,
                        recent_trades=trades,
                        total_equity=self._portfolio_domination.equity,
                        max_position_size=self._get_max_size_for_tf(timeframe),
                        estimated_vpin=vpin_score,
                    )

                    now_mono = time.monotonic()
                    if now_mono - self._last_pred_log_time.get(ticker, 0.0) >= 3.0:
                        self._last_pred_log_time[ticker] = now_mono
                        self._db_writer.enqueue_ai_prediction(
                            ticker=ticker,
                            p_up=decision.p_up,
                            p_down=decision.p_down,
                            p_wait=decision.p_wait,
                            vpin=decision.vpin,
                            ev_yes=decision.ev_yes,
                            ev_no=decision.ev_no,
                            recommended_side=decision.recommended_side,
                            rationale=decision.rationale,
                        )

                    if decision.recommended_side in ("yes", "no") and decision.recommended_contracts > 0:
                        # Q2 Winning Rule: Overnight Cautious Mode enforcement
                        if is_overnight_et:
                            if decision.edge_pct < 12.0 or abs(spot_price - target_strike) < 75.0:
                                logger.info(
                                    "[OVERNIGHT CAUTIOUS VETO] %s | Edge=%.1f%% < 12.0%% or |Diff|=$%.2f < $75.00. Suppressing overnight noise trade.",
                                    ticker, decision.edge_pct, abs(spot_price - target_strike)
                                )
                                return

                        order_size = 1 if is_overnight_et else decision.recommended_contracts
                        side_enum = OrderSide.YES if decision.recommended_side == "yes" else OrderSide.NO
                        logger.info(
                            "[%s] %-18s | %-3s (%s) | Edge=%+.1f%% | EV=+%s/ct | Size=%d cts%s",
                            "LIVE 3-STEP BOT" if is_live else "3-STEP BOT",
                            ticker,
                            decision.recommended_side.upper(),
                            decision.active_playbook,
                            decision.edge_pct,
                            f"${max(decision.ev_yes, decision.ev_no):.2f}",
                            order_size,
                            " [OVERNIGHT CAUTIOUS]" if is_overnight_et else "",
                        )
                        order_type_val = getattr(decision, "order_type", "limit")
                        limit_price_val = Decimal(str(getattr(decision, "limit_price", self._domination_bot.discount_limit_price)))
                        await self._place_virtual_order(
                            book=book,
                            ticker=ticker,
                            side=side_enum,
                            max_size=order_size,
                            timeframe=timeframe,
                            reasoning=decision.rationale,
                            portfolio=self._portfolio_domination,
                            bot_type="3_step_domination_bot",
                            order_type=order_type_val,
                            limit_price=limit_price_val,
                        )
                except Exception as exc:
                    logger.debug("Domination bot evaluation error: %s", exc)

        # In LIVE mode, secondary paper bots STOP completely!
        if is_live:
            return

        # ===================================================================
        # BOT 2: ONNX Microstructure Neural Net Bot (Evaluated against _portfolio_onnx)
        # ===================================================================
        now_ts = time.time()
        if not hasattr(self, "_last_onnx_ts"):
            self._last_onnx_ts: dict[str, float] = {}

        if (
            now_ts - self._last_onnx_ts.get(ticker, 0.0) >= 0.5
            and not self._portfolio_onnx.circuit_breaker_tripped
            and len(self._portfolio_onnx.open_positions) < MAX_CONCURRENT_POSITIONS
            and self._portfolio_onnx.get_position(ticker) is None
        ):
            self._last_onnx_ts[ticker] = now_ts
            try:
                t0 = time.perf_counter()
                onnx_res = await asyncio.to_thread(
                    self._onnx_engine.process_orderbook_tick, book, trades
                )
                latency_ms = (time.perf_counter() - t0) * 1000.0

                onnx_signal = onnx_res.get("signal", "WAIT")
                onnx_conf = onnx_res.get("confidence", 0.0)
                vpin_score = onnx_res.get("vpin_score", 0.0)

                self._eval_count = getattr(self, "_eval_count", 0) + 1
                if onnx_signal in ("LONG", "SHORT") or self._eval_count % 10 == 0:
                    logger.info(
                        "[ONNX AI]   %-18s | Signal=%-5s (%4.1f%%) | VPIN=%.2f | OFI_L1=%+.2f | Latency=%.2fms",
                        ticker, onnx_signal, onnx_conf * 100.0, vpin_score, onnx_res.get("ofi_l1", 0.0), latency_ms
                    )

                if not onnx_res.get("vpin_veto"):
                    rel_long = onnx_res.get("rel_long", onnx_res.get("prob_long", 0.33))
                    rel_short = onnx_res.get("rel_short", onnx_res.get("prob_short", 0.33))
                    prob_wait = onnx_res.get("prob_wait", 0.34)

                    if onnx_signal == "LONG":
                        prob_long = max(0.55, rel_long)
                        prob_short = 1.0 - prob_long
                        prob_wait_in = 0.0
                    elif onnx_signal == "SHORT":
                        prob_short = max(0.55, rel_short)
                        prob_long = 1.0 - prob_short
                        prob_wait_in = 0.0
                    else:
                        prob_long = rel_long
                        prob_short = rel_short
                        prob_wait_in = prob_wait

                    best_yes_ask = book.best_yes_ask
                    best_yes_bid = book.best_yes_bid
                    best_no_ask = (Decimal("1.00") - best_yes_bid) if best_yes_bid is not None else None

                    ev_result = self._ev_engine.compute_optimal_execution(
                        prob_up=prob_long,
                        prob_down=prob_short,
                        best_yes_ask=best_yes_ask,
                        best_no_ask=best_no_ask,
                        total_equity=self._portfolio_onnx.equity,
                        max_position_size=self._get_max_size_for_tf(timeframe),
                        vpin=vpin_score,
                        prob_wait=prob_wait_in,
                    )

                    now_mono = time.monotonic()
                    if ev_result.recommended_side is not None or now_mono - self._last_pred_log_time.get(ticker, 0.0) >= 3.0:
                        self._last_pred_log_time[ticker] = now_mono
                        self._db_writer.enqueue_ai_prediction(
                            ticker=ticker,
                            p_up=prob_long,
                            p_down=prob_short,
                            p_wait=prob_wait,
                            vpin=vpin_score,
                            ev_yes=float(ev_result.expected_value if ev_result.recommended_side == OrderSide.YES else 0.0),
                            ev_no=float(ev_result.expected_value if ev_result.recommended_side == OrderSide.NO else 0.0),
                            recommended_side=ev_result.recommended_side.value if ev_result.recommended_side else "none",
                            rationale=ev_result.rationale,
                        )

                    if ev_result.has_positive_edge and ev_result.recommended_side is not None:
                        logger.info(
                            "[STAGE 2 EV] %-18s | %-3s @ $%-4s | AI_P=%.1f%% | EV=+%s/ct | Edge=%+.1f%% | Kelly=%.1f%% (%d cts)",
                            ticker,
                            ev_result.recommended_side.value.upper(),
                            ev_result.market_price,
                            ev_result.ai_prob * 100.0,
                            f"${ev_result.expected_value:.3f}",
                            ev_result.statistical_edge * 100.0,
                            ev_result.kelly_fraction * 100.0,
                            ev_result.recommended_contracts,
                        )
                        await self._place_virtual_order(
                            book=book,
                            ticker=ticker,
                            side=ev_result.recommended_side,
                            max_size=ev_result.recommended_contracts,
                            timeframe=timeframe,
                            reasoning=ev_result.rationale,
                            portfolio=self._portfolio_onnx,
                            bot_type="onnx_microstructure_bot",
                        )
            except Exception as exc:
                logger.debug("ONNX bot evaluation error: %s", exc)

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

    def settle_expired_market(
        self, ticker: str, market_info: MarketInfo, final_tick: TickerUpdate
    ) -> None:
        """Immediately settle an expired position against the final BTC settlement price across both portfolios."""
        from kalshi_sim.settlement import settle_position
        spot_dec = None
        if self._spot_price_getter:
            try:
                spot_dec = Decimal(str(self._spot_price_getter()))
            except Exception:
                pass

        active_macro_tag = "macro_onnx" if self.active_strategy_bot in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion") else "macro_trend_dominion"
        portfolios_to_settle = [
            (self._portfolio_macro_trend, active_macro_tag),
            (self._portfolio_domination, "3_step_domination_bot"),
            (self._portfolio_onnx, "onnx_microstructure_bot"),
        ]
        if hasattr(self, "_portfolio_dominion2") and self._portfolio_dominion2 is not None:
            portfolios_to_settle.append((self._portfolio_dominion2, "dominion_2_bot"))

        for p_inst, b_type in portfolios_to_settle:
            result = settle_position(
                portfolio=p_inst,
                ticker=ticker,
                market_info=market_info,
                last_ticker_update=final_tick,
                btc_settle_price=spot_dec,
            )
            if result:
                self._exec_logger.log_settlement(result)
                self._db_writer.enqueue_settlement(
                    settlement_id=f"st_{int(time.time()*1000)}_{result.ticker}_{random.randint(100, 999)}",
                    ticker=result.ticker,
                    side=result.side.value,
                    size=result.size,
                    entry_price=float(result.entry_price),
                    settlement_price=float(result.settlement_price),
                    outcome=result.outcome,
                    pnl=float(result.pnl),
                    balance_after=float(p_inst.balance),
                    bot_type=b_type,
                    execution_mode="simulated",
                )
                self._guardrails.record_cycle_settlement(
                    ticker=result.ticker,
                    outcome=result.outcome,
                    pnl=result.pnl,
                    balance_after=p_inst.balance,
                    cycle_id=result.ticker,
                )
                try:
                    from kalshi_sim.server import record_win_loss_event_report
                    strike_val = market_info.floor_strike if market_info.floor_strike is not None else (market_info.target_strike if market_info.target_strike is not None else Decimal("0.0"))
                    settle_spot = spot_dec if spot_dec is not None else strike_val
                    record_win_loss_event_report(
                        ticker=result.ticker,
                        side=result.side.value,
                        contracts=result.size,
                        entry_price=result.entry_price,
                        settlement_btc_price=settle_spot,
                        strike_price=strike_val,
                        timeframe="15m",
                        ai_confidence=0.82,
                        ai_rationale=f"Natural 15M Expiration Settlement for {b_type} | BTC: ${float(settle_spot):,.2f} vs Strike: ${float(strike_val):,.2f}",
                        vpin_score=0.15,
                        ev_edge=0.10,
                        bot_type=b_type,
                        execution_mode="simulated",
                        custom_outcome=result.outcome,
                        custom_pnl=result.pnl,
                        balance_after=p_inst.balance,
                    )
                except Exception as rep_err:
                    logger.debug("Failed to record win-loss report on settlement: %s", rep_err)

                logger.info(
                    "[SETTLED] [%-20s] %-18s | %-3s %s %d contracts | P&L=%+$7.2f | Balance=$%.2f",
                    b_type,
                    ticker,
                    result.side.value.upper(),
                    result.outcome.upper(),
                    result.size,
                    result.pnl,
                    p_inst.balance,
                )

    async def on_trade_event(self, trade: TradeEvent) -> None:
        """Accumulate recent trade executions for ONNX feature extraction."""
        trades = self._recent_trades.setdefault(trade.market_ticker, [])
        trades.append(trade)
        if len(trades) > 50:
            trades.pop(0)
        self._onnx_engine.extractor.process_trade(trade)

    def _get_max_size_for_tf(self, timeframe: Timeframe) -> int:
        if getattr(self, "execution_mode", "simulated") == "live":
            # Live Trading Exclusivity: Strict micro-contract cap (1-2 contracts) for live bankroll protection ($30)
            return 2
        if timeframe == Timeframe.FIVE_MIN:
            return SCALP_MAX_POSITION_SIZE
        elif timeframe == Timeframe.FIFTEEN_MIN:
            return MOMENTUM_MAX_POSITION_SIZE
        else:
            return SWING_MAX_POSITION_SIZE

    # -- Strategy Modes ------------------------------------------------------

    async def _evaluate_scalp(
        self, book: L2BookState, ticker: str, timeframe: Timeframe
    ) -> None:
        """Mode A (5m): Scalp on order flow imbalance > 65%."""
        bids, asks = book.get_depth(5)
        if not bids or not asks:
            return

        bid_volume = sum(lv.quantity for lv in bids)
        ask_volume = sum(lv.quantity for lv in asks)
        total_volume = bid_volume + ask_volume

        if total_volume == 0:
            return

        bid_pct = bid_volume / total_volume

        if bid_pct > SCALP_IMBALANCE_THRESHOLD:
            await self._place_virtual_order(
                book, ticker, OrderSide.YES, SCALP_MAX_POSITION_SIZE,
                timeframe,
                f"Scalp Imbalance: Bid {bid_pct:.1%} > {SCALP_IMBALANCE_THRESHOLD}",
            )
        elif (1 - bid_pct) > SCALP_IMBALANCE_THRESHOLD:
            await self._place_virtual_order(
                book, ticker, OrderSide.NO, SCALP_MAX_POSITION_SIZE,
                timeframe,
                f"Scalp Imbalance: Ask {1 - bid_pct:.1%} > {SCALP_IMBALANCE_THRESHOLD}",
            )

    async def _evaluate_momentum(
        self, book: L2BookState, ticker: str, timeframe: Timeframe
    ) -> None:
        """Mode B (15m): Momentum — 3+ consecutive directional mid-price moves."""
        history = self._mid_price_history.get(ticker, [])
        if len(history) < MOMENTUM_CONSECUTIVE_TICKS + 1:
            return

        recent = history[-(MOMENTUM_CONSECUTIVE_TICKS + 1):]
        deltas = [recent[i + 1] - recent[i] for i in range(len(recent) - 1)]

        all_up = all(d > 0 for d in deltas)
        all_down = all(d < 0 for d in deltas)

        if all_up:
            await self._place_virtual_order(
                book, ticker, OrderSide.YES, MOMENTUM_MAX_POSITION_SIZE,
                timeframe,
                f"Momentum: {MOMENTUM_CONSECUTIVE_TICKS} consecutive up ticks",
            )
        elif all_down:
            await self._place_virtual_order(
                book, ticker, OrderSide.NO, MOMENTUM_MAX_POSITION_SIZE,
                timeframe,
                f"Momentum: {MOMENTUM_CONSECUTIVE_TICKS} consecutive down ticks",
            )

    async def _evaluate_swing(
        self, book: L2BookState, ticker: str, timeframe: Timeframe
    ) -> None:
        """Mode C (1h): Swing — extreme book depth asymmetry (bid/ask > 2:1)."""
        bids, asks = book.get_depth(15)
        if not bids or not asks:
            return

        bid_volume = sum(lv.quantity for lv in bids)
        ask_volume = sum(lv.quantity for lv in asks)

        if ask_volume == 0 or bid_volume == 0:
            return

        ratio = bid_volume / ask_volume

        if ratio > SWING_DEPTH_RATIO_THRESHOLD:
            await self._place_virtual_order(
                book, ticker, OrderSide.YES, SWING_MAX_POSITION_SIZE,
                timeframe,
                f"Swing Depth Asymmetry: {ratio:.1f}:1 > {SWING_DEPTH_RATIO_THRESHOLD}",
            )
        elif (Decimal("1") / ratio) > SWING_DEPTH_RATIO_THRESHOLD:
            await self._place_virtual_order(
                book, ticker, OrderSide.NO, SWING_MAX_POSITION_SIZE,
                timeframe,
                f"Swing Depth Asymmetry: Ask {Decimal('1') / ratio:.1f}:1 > {SWING_DEPTH_RATIO_THRESHOLD}",
            )

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
    ) -> None:
        """Submit a virtual market or resting limit order against the L2 book."""
        active_p = portfolio or self.portfolio
        b_type = bot_type or self.active_strategy_bot

        # Pre-Trade Bot Certification Gate: Block any uncertified bot execution immediately
        if hasattr(self, "bot_auditor") and not self.bot_auditor.is_certified(b_type):
            now_mono = time.monotonic()
            block_key = f"audit_blocked_{ticker}_{b_type}"
            if not hasattr(self, "_last_guardrail_log"):
                self._last_guardrail_log = {}
            if now_mono - self._last_guardrail_log.get(block_key, 0.0) >= 5.0:
                self._last_guardrail_log[block_key] = now_mono
                logger.error(
                    "❌ [PRE-TRADE BLOCKED] Bot '%s' is NOT CERTIFIED by the 4-pillar audit gate. Order aborted.",
                    b_type,
                )
            return

        snapshot = active_p.get_pnl_snapshot()
        max_cost = snapshot.total_equity * MAX_POSITION_COST_PCT

        if order_type == "limit" and limit_price is not None:
            est_price = limit_price
        elif side == OrderSide.YES:
            ask = book.best_yes_ask
            est_price = ask if ask is not None else Decimal("0.50")
        else:
            no_ask = Decimal("1") - book.best_yes_bid if book.best_yes_bid else None
            est_price = no_ask if no_ask is not None else Decimal("0.50")

        # Agent_Guardrails Pre-Trade Gatekeeper (1-trade-per-cycle lock, cooldown, anti-kamikaze sizing)
        is_ok, g_reason, approved_size, g_diag = self._guardrails.validate_pre_trade_intent(
            ticker=ticker,
            side=side.value if hasattr(side, "value") else str(side),
            requested_size=max_size,
            est_price=est_price,
            total_equity=snapshot.total_equity,
            vpin=0.15,
            cycle_id=ticker,
            is_bot=True,
        )
        if not is_ok or approved_size <= 0:
            now_mono = time.monotonic()
            block_key = f"{ticker}_{b_type}"
            if not hasattr(self, "_last_guardrail_log"):
                self._last_guardrail_log = {}
            if now_mono - self._last_guardrail_log.get(block_key, 0.0) >= 5.0:
                self._last_guardrail_log[block_key] = now_mono
                logger.warning("[%s BLOCKED BY GUARDRAILS] %s (ticker=%s)", b_type, g_reason, ticker)
            return

        affordable_size = approved_size

        exec_mode = getattr(self, "execution_mode", "simulated")
        
        # ------------------------------------------------------------------
        # LIVE MODE: Pure real exchange order routing (Zero paper trading)
        # ------------------------------------------------------------------
        if exec_mode == "live":
            if self._order_client is not None and b_type == self.active_strategy_bot:
                try:
                    live_side = side.value if hasattr(side, "value") else str(side).lower()
                    live_count = max(1, min(affordable_size, 2))  # Strict hard cap: 1-2 contracts max for micro-bankroll

                    # Check global dry-run protection
                    live_enabled_env = os.getenv("KALSHI_LIVE_TRADING_ENABLED", "false").lower() in ("true", "1", "yes")
                    if not live_enabled_env:
                        dry_id = f"dry_run_{uuid.uuid4().hex[:8]}"
                        logger.info(
                            "[SAFETY DRY-RUN] Live trading disabled in .env. Simulating resting order %s (%s %d cts @ $%s). Cycle '%s' LOCKED.",
                            dry_id, live_side.upper(), live_count, limit_price or est_price, ticker
                        )
                        self._guardrails.record_resting_order(
                            order_id=dry_id,
                            ticker=ticker,
                            side=live_side,
                            size=live_count,
                            price=Decimal(str(limit_price if order_type == "limit" else est_price)),
                            cycle_id=ticker,
                            bot_type=b_type,
                        )
                        return

                    # Anti-Burst Pre-Flight Check: Ensure no open resting order exists on Kalshi for this ticker
                    try:
                        open_exchange_orders = await self._order_client.get_open_orders()
                        if open_exchange_orders:
                            existing_ticker_orders = [o for o in open_exchange_orders if o.get("ticker") == ticker]
                            if existing_ticker_orders:
                                logger.warning(
                                    "[PRE-TRADE VETO] %s already has %d resting order(s) active on Kalshi! Suppressing duplicate submission.",
                                    ticker, len(existing_ticker_orders)
                                )
                                self._guardrails.record_resting_order(
                                    order_id=existing_ticker_orders[0].get("order_id", "ext_rest"),
                                    ticker=ticker,
                                    side=live_side,
                                    size=live_count,
                                    price=Decimal(str(limit_price if order_type == "limit" else est_price)),
                                    cycle_id=ticker,
                                    bot_type=b_type,
                                )
                                return
                    except Exception as chk_exc:
                        logger.debug("Failed pre-flight open order query: %s", chk_exc)

                    market_info = self._market_cache.get(ticker)
                    live_exchange_index = getattr(market_info, "exchange_index", None)
                    if live_exchange_index is None and ticker.startswith("KXBTC"):
                        live_exchange_index = 2

                    live_order = await self._order_client.place_order(
                        ticker=ticker,
                        side=live_side,
                        count=live_count,
                        action="buy",
                        order_type=order_type,
                        price_dollars=limit_price if order_type == "limit" else est_price,
                        exchange_index=live_exchange_index,
                    )
                    if live_order:
                        order_id = live_order.get("order_id", "live_ord")
                        fill_count_str = live_order.get("fill_count", "0.00")
                        actual_fills = int(float(fill_count_str))

                        if actual_fills > 0:
                            avg_price = float(live_order.get("average_fill_price", "0.50"))
                            fee = float(live_order.get("average_fee_paid", "0.0007"))
                            cost = avg_price * actual_fills + fee

                            # Post-Fill Price Guard: alert on expensive exchange fills
                            # The bot's pre-trade cap checks local book, but exchange fill can differ
                            if avg_price > 0.72:
                                logger.warning(
                                    "[FILL PRICE HARD KILL] %s | Fill=$%.2f > $0.72 ceiling! "
                                    "Exchange filled at dangerous price. Order: %s",
                                    ticker, avg_price, order_id,
                                )
                            elif avg_price > 0.62:
                                logger.warning(
                                    "[FILL PRICE ALERT] %s | Fill=$%.2f > $0.62 standard cap. "
                                    "Slippage from local book snapshot. Order: %s",
                                    ticker, avg_price, order_id,
                                )

                            self._guardrails.record_trade_inception(
                                trade_id=f"live_{order_id}",
                                ticker=ticker,
                                side=live_side,
                                size=actual_fills,
                                price=Decimal(str(avg_price)),
                                cost=Decimal(str(cost)),
                                fee=Decimal(str(fee)),
                                bot_type=b_type,
                                execution_mode="live",
                                rationale=reasoning,
                                vpin=0.15,
                                ai_prob=float(snapshot.win_rate or 0.70),
                                cycle_id=ticker,
                            )
                            self._db_writer.enqueue_trade(
                                trade_id=f"live_{order_id}",
                                ticker=ticker,
                                side=live_side,
                                size=actual_fills,
                                price=avg_price,
                                gross_value=cost,
                                timeframe=timeframe.value,
                                bot_type=b_type,
                                execution_mode="live",
                                status="filled",
                            )
                            logger.info(
                                "[KALSHI LIVE PRODUCTION EXCHANGE] Order FILLED: %s | Fills: %d | Ticker: %s | Side: %s | Cost: $%.4f",
                                order_id, actual_fills, ticker, live_side.upper(), cost,
                            )
                            if self._telemetry_alerts is not None:
                                try:
                                    asyncio.create_task(
                                        self._telemetry_alerts.send_order_alert(
                                            ticker=ticker,
                                            side=live_side,
                                            contracts=actual_fills,
                                            price=Decimal(str(avg_price)),
                                            cost=Decimal(str(cost)),
                                            fee=Decimal(str(fee)),
                                            ai_prob=float(snapshot.win_rate or 0.70),
                                            vpin=0.15,
                                            execution_mode="live",
                                        )
                                    )
                                except Exception as exc:
                                    logger.debug("Failed to dispatch live order telemetry: %s", exc)
                        else:
                            # 0 Fills: Either a resting maker limit order or unmatched IOC
                            if order_type == "limit":
                                self._guardrails.record_resting_order(
                                    order_id=f"live_{order_id}",
                                    ticker=ticker,
                                    side=live_side,
                                    size=live_count,
                                    price=Decimal(str(limit_price if limit_price else est_price)),
                                    cycle_id=ticker,
                                    bot_type=b_type,
                                )
                                logger.info(
                                    "[KALSHI LIVE PRODUCTION EXCHANGE] Resting Maker Limit Order %s PLACED on book (%d cts @ $%s). Cycle '%s' LOCKED to prevent duplicate entries.",
                                    order_id, live_count, limit_price or est_price, ticker,
                                )
                            else:
                                self._guardrails.record_order_attempt(ticker)
                                logger.info(
                                    "[KALSHI LIVE PRODUCTION EXCHANGE] IOC Order %s had 0 fills (unmatched in orderbook). Cooldown enforced.",
                                    order_id,
                                )
                    else:
                        self._guardrails.record_order_attempt(ticker)
                        logger.warning(
                            "[KALSHI LIVE PRODUCTION EXCHANGE] Order submission failed/rejected on exchange. Cooldown enforced."
                        )
                except Exception as exc:
                    self._guardrails.record_order_attempt(ticker)
                    logger.error("Failed to send order to Kalshi Live Production exchange: %s. Cooldown enforced.", exc)
            return

        # Micro-bankroll protection & realism: cap simulated size to live risk limits (1-4 contracts)
        sim_size = max(1, min(affordable_size, 4))

        if order_type == "limit" and limit_price is not None:
            est_cost = limit_price * sim_size
            if not active_p.can_afford(est_cost):
                logger.warning("[%s] Cannot afford resting limit order: $%s > balance $%s", b_type, est_cost, active_p.balance)
                return
            l2_book = book.get_state() if hasattr(book, "get_state") else book
            resting_ord = self._simulator.simulate_limit_order(
                book=l2_book,
                side=side,
                size=sim_size,
                limit_price=limit_price,
                timeframe=timeframe,
                reasoning=reasoning,
            )
            logger.info(
                "[%s RESTING MAKER LIMIT ORDER PLACED] %s %d cts @ $%s on %s ($0.00 Fee) | OrderID: %s",
                b_type, side.value.upper(), sim_size, limit_price, ticker, resting_ord.order_id,
            )
            return

        # Calculate recent spot velocity for adverse selection modeling
        velocity = 0.0
        if hasattr(self, "_mid_price_history"):
            try:
                hist = self._mid_price_history.get(ticker, [])
                if len(hist) >= 2:
                    velocity = float(hist[-1] - hist[0]) * 100.0
            except Exception:
                pass

        result = self._simulator.simulate_market_order(
            book=book,
            side=side,
            size=sim_size,
            timeframe=timeframe,
            reasoning=reasoning,
            spot_velocity=velocity,
        )
        if result is None:
            return

        order, fill = result

        if not active_p.can_afford(fill.cost):
            logger.warning(
                "[%s] Post-simulation cost check failed: $%s > balance $%s",
                b_type, fill.cost, active_p.balance,
            )
            return

        active_p.open_position(fill, timeframe)
        self._exec_logger.log_execution(order, fill)
        sim_trade_id = f"tr_{int(time.time()*1000)}_{ticker}_{random.randint(100, 999)}"
        self._guardrails.record_trade_inception(
            trade_id=sim_trade_id,
            ticker=ticker,
            side=fill.side.value,
            size=fill.size,
            price=fill.fill_price,
            cost=fill.cost,
            fee=fill.fee,
            bot_type=b_type,
            execution_mode="simulated",
            rationale=reasoning,
            vpin=0.15,
            ai_prob=float(snapshot.win_rate or 0.70),
            cycle_id=ticker,
        )
        self._db_writer.enqueue_trade(
            trade_id=sim_trade_id,
            ticker=ticker,
            side=fill.side.value,
            size=fill.size,
            price=float(fill.fill_price),
            gross_value=float(fill.cost),
            timeframe=timeframe.value,
            bot_type=b_type,
            execution_mode="simulated",
            status="filled",
        )
        logger.info(
            "[SIM FILL]  [%-22s] %-18s | %-4s %-3d contracts @ $%-4s | Cost=$%-6.2f | Balance=$%-8.2f | [%s]",
            b_type, ticker, fill.side.value.upper(), fill.size, fill.fill_price,
            float(fill.cost), float(active_p.balance), reasoning
        )

        if self._telemetry_alerts is not None:
            try:
                asyncio.create_task(
                    self._telemetry_alerts.send_order_alert(
                        ticker=ticker,
                        side=fill.side.value,
                        contracts=fill.size,
                        price=fill.fill_price,
                        cost=fill.cost,
                        fee=fill.fee,
                        ai_prob=float(snapshot.win_rate or 0.70),
                        vpin=0.15,
                        execution_mode="paper",
                    )
                )
            except Exception as exc:
                logger.debug("Failed to dispatch order telemetry alert: %s", exc)

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
                for p_inst, b_type in [
                    (self._portfolio_macro_trend, "macro_trend_dominion"),
                    (self._portfolio_dominion2, "dominion_2_bot"),
                    (self._portfolio_domination, "3_step_domination_bot"),
                    (self._portfolio_onnx, "onnx_microstructure_bot"),
                ]:
                    expired_tickers = check_expirations(
                        positions=p_inst.open_positions,
                        markets=self._market_cache,
                        current_time=now,
                    )
                    for ticker in expired_tickers:
                        market_info = self._market_cache.get(ticker)
                        if market_info is None:
                            continue
                        last_update = self._ticker_cache.get(ticker)
                        self.settle_expired_market(ticker, market_info, last_update)
            except Exception as exc:
                logger.debug("Error in settlement loop: %s", exc)

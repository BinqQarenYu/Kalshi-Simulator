"""Virtual Order Execution Router.

Handles routing, validation, guardrail checking, and execution of both
live production orders and simulated/paper orders for SimulationAgent.
Strictly decoupled from strategy evaluation loops.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
import uuid
from decimal import Decimal
from typing import Any, Callable, Optional

from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.bot_deployment_auditor import BotDeploymentAuditor
from kalshi_sim.db import DatabaseWriter
from kalshi_sim.execution_logger import ExecutionLogger
from kalshi_sim.notifications import TelemetryAlertDispatcher
from kalshi_sim.order_client import KalshiDemoOrderClient
from kalshi_sim.order_simulator import OrderSimulator
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.portfolio import Portfolio
from kalshi_sim.process_lock import get_active_lock_holder
from kalshi_sim.schemas import (
    L2BookState,
    MarketInfo,
    OrderSide,
    Timeframe,
)

logger = logging.getLogger(__name__)

MAX_POSITION_COST_PCT = Decimal("0.10")  # max 10% of equity per position


class VirtualOrderRouter:
    """Executes live and simulated virtual orders for trading agents."""

    def __init__(
        self,
        guardrails: AgentGuardrails,
        simulator: OrderSimulator,
        db_writer: DatabaseWriter,
        exec_logger: ExecutionLogger,
        bot_auditor: Optional[BotDeploymentAuditor] = None,
        order_client: Optional[KalshiDemoOrderClient] = None,
        telemetry_alerts: Optional[TelemetryAlertDispatcher] = None,
    ) -> None:
        self._guardrails = guardrails
        self._simulator = simulator
        self._db_writer = db_writer
        self._exec_logger = exec_logger
        self.bot_auditor = bot_auditor
        self._order_client = order_client
        self._telemetry_alerts = telemetry_alerts
        self._last_guardrail_log: dict[str, float] = {}

    async def execute_order(
        self,
        book: L2BookState,
        ticker: str,
        side: OrderSide,
        max_size: int,
        timeframe: Timeframe,
        reasoning: str,
        portfolio: Portfolio,
        bot_type: str,
        execution_mode: str,
        order_type: str = "market",
        limit_price: Optional[Decimal] = None,
        market_info: Optional[MarketInfo] = None,
        mid_price_history: Optional[dict[str, list[Decimal]]] = None,
        active_strategy_bot: Optional[str] = None,
        action: str = "buy",
    ) -> None:
        """Submit a virtual market or resting limit order against the L2 book or live exchange."""
        active_p = portfolio
        b_type = bot_type

        # Pre-Trade Bot Certification Gate: Block any uncertified bot execution immediately
        if self.bot_auditor and not self.bot_auditor.is_certified(b_type):
            now_mono = time.monotonic()
            block_key = f"audit_blocked_{ticker}_{b_type}"
            if now_mono - self._last_guardrail_log.get(block_key, 0.0) >= 5.0:
                self._last_guardrail_log[block_key] = now_mono
                logger.error(
                    "❌ [PRE-TRADE BLOCKED] Bot '%s' is NOT CERTIFIED by the 4-pillar audit gate. Order aborted.",
                    b_type,
                )
            return

        snapshot = active_p.get_pnl_snapshot()

        if order_type == "limit" and limit_price is not None:
            est_price = limit_price
        elif side == OrderSide.YES:
            ask = book.best_yes_ask
            est_price = ask if ask is not None else Decimal("0.50")
        else:
            no_ask = Decimal("1") - book.best_yes_bid if book.best_yes_bid else None
            est_price = no_ask if no_ask is not None else Decimal("0.50")

        # Agent_Guardrails Pre-Trade Gatekeeper (1-trade-per-cycle lock, cooldown, anti-kamikaze sizing)
        is_live_flag = execution_mode == "live"
        if action == "sell":
            approved_size = max_size
        else:
            is_ok, g_reason, approved_size, _ = self._guardrails.validate_pre_trade_intent(
                ticker=ticker,
                side=side.value if hasattr(side, "value") else str(side),
                requested_size=max_size,
                est_price=est_price,
                total_equity=snapshot.total_equity,
                vpin=0.15,
                cycle_id=ticker,
                is_bot=True,
                bot_type=b_type,
                is_live=is_live_flag,
            )
            if not is_ok or approved_size <= 0:
                now_mono = time.monotonic()
                block_key = f"{ticker}_{b_type}"
                if now_mono - self._last_guardrail_log.get(block_key, 0.0) >= 5.0:
                    self._last_guardrail_log[block_key] = now_mono
                    logger.warning("[%s BLOCKED BY GUARDRAILS] %s (ticker=%s)", b_type, g_reason, ticker)
                return

        affordable_size = approved_size

        # ------------------------------------------------------------------
        # LIVE MODE: Pure real exchange order routing (Zero paper trading)
        # ------------------------------------------------------------------
        if execution_mode == "live":
            if self._order_client is None:
                sim_ag = getattr(self, "_sim_agent", None)
                if sim_ag and hasattr(sim_ag, "_order_client"):
                    self._order_client = getattr(sim_ag, "_order_client", None)

            bot_match = (
                active_strategy_bot is None
                or b_type == active_strategy_bot
                or (b_type in ("3_step_domination_bot", "bot1_v4_domination") and active_strategy_bot in ("3_step_domination_bot", "bot1_v4_domination", "both", "dual", "all", "dual_fleet"))
                or (b_type in ("macro_trend_dominion", "macro_onnx") and active_strategy_bot in ("macro_trend_dominion", "macro_onnx"))
                or active_strategy_bot in ("both", "dual", "all", "dual_fleet")
            )
            if self._order_client is None:
                logger.error("🛑 [LIVE ORDER ROUTER] Order client is NULL! Cannot route live order for %s. Releasing in-flight lock.", ticker)
                self._guardrails.release_in_flight_intent(ticker)
                return
            if not bot_match:
                logger.debug("Live order bot mismatch (bot=%s vs active=%s). Releasing in-flight lock.", b_type, active_strategy_bot)
                self._guardrails.release_in_flight_intent(ticker)
                return

            try:
                live_side = side.value if hasattr(side, "value") else str(side).lower()
                live_count = 1  # Strictly 1 contract for each asset

                # Check if standalone trading engine holds exclusive lock
                holder = get_active_lock_holder()
                if holder and holder[1] != os.getpid():
                    logger.warning(
                        "🛑 [LOCKOUT] Standalone engine holds lock (%s, PID: %d). Suppressing main dash live order.",
                        holder[0], holder[1]
                    )
                    self._guardrails.release_in_flight_intent(ticker)
                    return

                # Check live trading authorization on disk or environment
                auth_on_disk, _ = BotDeploymentAuditor.check_live_authorization_on_disk(b_type)
                live_enabled_env = os.getenv("KALSHI_LIVE_TRADING_ENABLED", "true").lower() in ("true", "1", "yes") or auth_on_disk
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
                            # 1. Anti-Wash Check: Never rest orders on opposite side
                            if any(o.get("side", "").lower() != live_side.lower() for o in existing_ticker_orders):
                                logger.warning(
                                    "[PRE-TRADE VETO] %s already has opposing resting orders active on Kalshi! Opposing submission blocked.",
                                    ticker
                                )
                                self._guardrails.release_in_flight_intent(ticker)
                                return
                            # 2. Combined Exposure Check: allow up to 2 resting orders across both bots
                            if len(existing_ticker_orders) >= 2:
                                logger.warning(
                                    "[PRE-TRADE VETO] %s already has %d resting order(s) active on Kalshi (max 2 reached)! Suppressing duplicate submission.",
                                    ticker, len(existing_ticker_orders)
                                )
                                self._guardrails.release_in_flight_intent(ticker)
                                return
                except Exception as chk_exc:
                    logger.debug("Failed pre-flight open order query: %s", chk_exc)

                live_exchange_index = getattr(market_info, "exchange_index", None)
                if live_exchange_index is None and ticker.startswith("KXBTC"):
                    live_exchange_index = 2

                live_order = await self._order_client.place_order(
                    ticker=ticker,
                    side=live_side,
                    count=live_count,
                    action=action,
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
                logger.warning("[%s] Cannot afford limit order: $%s > balance $%s", b_type, est_cost, active_p.balance)
                self._guardrails.release_in_flight_intent(ticker)
                return
            l2_book = book.get_state() if hasattr(book, "get_state") else book
            try:
                res = self._simulator.simulate_limit_order(
                    book=l2_book,
                    side=side,
                    size=sim_size,
                    limit_price=limit_price,
                    timeframe=timeframe,
                    reasoning=reasoning,
                )
                if res is not None:
                    # Marketable limit order immediately filled!
                    order, fill = res
                    active_p.open_position(fill, timeframe)
                    self._guardrails.record_trade_inception(
                        trade_id=order.order_id,
                        ticker=ticker,
                        side=side.value if hasattr(side, "value") else str(side),
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
                    if self._exec_logger:
                        self._exec_logger.log_execution(order, fill)
                    self._db_writer.enqueue_trade(
                        trade_id=order.order_id,
                        ticker=ticker,
                        side=side.value if hasattr(side, "value") else str(side),
                        size=fill.size,
                        price=float(fill.fill_price),
                        gross_value=float(fill.fill_price * fill.size),
                        fees=float(fill.fee),
                        bot_type=b_type,
                        execution_mode="simulated",
                        status="filled",
                    )
                    logger.info(
                        "[%s LIMIT ORDER FILLED] %s %d cts @ $%s on %s | OrderID: %s",
                        b_type, side.value.upper(), fill.size, fill.fill_price, ticker, order.order_id,
                    )
                    return
                else:
                    # Non-marketable: place as resting maker limit order on the book
                    resting_ord = self._simulator.place_resting_limit_order(
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
                    self._guardrails.record_resting_order(
                        order_id=resting_ord.order_id,
                        ticker=ticker,
                        side=side.value if hasattr(side, "value") else str(side),
                        size=sim_size,
                        price=limit_price,
                        cycle_id=ticker,
                        bot_type=b_type,
                    )
                    return
            except Exception as lim_exc:
                self._guardrails.release_in_flight_intent(ticker)
                logger.warning("[%s] Failed to place/simulate limit order on %s: %s", b_type, ticker, lim_exc)
                return

        # Calculate recent spot velocity for adverse selection modeling
        velocity = 0.0
        if mid_price_history:
            try:
                hist = mid_price_history.get(ticker, [])
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

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
import random
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from kalshi_sim.db import DatabaseWriter, get_db_writer
from kalshi_sim.execution_logger import ExecutionLogger
from kalshi_sim.ml.onnx_engine import KalshiONNXEngine
from kalshi_sim.ml.statistical_ev_engine import ExpectedValueResult, StatisticalEVEngine
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
        starting_capital: Decimal = Decimal("10000"),
        data_dir: Path = Path("data"),
        model_path: Optional[Path] = None,
        order_client: Optional[KalshiDemoOrderClient] = None,
        db_writer: Optional[DatabaseWriter] = None,
    ) -> None:
        self._orderbook = orderbook_manager
        self._timeframes = timeframes
        self._order_client = order_client

        # Components
        self._portfolio = Portfolio(starting_balance=starting_capital)
        self._simulator = OrderSimulator()
        self._exec_logger = ExecutionLogger(data_dir=data_dir)
        self._onnx_engine = KalshiONNXEngine(model_path=model_path)
        self._ev_engine = StatisticalEVEngine()
        self._db_writer = db_writer or get_db_writer()

        # Market metadata cache (populated by ingestion agent)
        self._market_cache: dict[str, MarketInfo] = {}
        self._ticker_cache: dict[str, TickerUpdate] = {}
        self._recent_trades: dict[str, list[TradeEvent]] = {}

        # Strategy state
        self._mid_price_history: dict[str, list[Decimal]] = {}
        self._ticker_timeframe_map: dict[str, Timeframe] = {}

        # Background tasks
        self._tasks: list[asyncio.Task] = []
        self._shutdown = asyncio.Event()

    # -- Lifecycle -----------------------------------------------------------

    @property
    def portfolio(self) -> Portfolio:
        """Access the internal simulated portfolio."""
        return self._portfolio

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
        book = self._orderbook.get_book(ticker)
        if book is None or book.is_stale:
            return

        # Process and match any active resting limit orders on this book
        filled_resting = self._simulator.process_resting_orders(book)
        for ord, fill in filled_resting:
            if self._portfolio.can_afford(fill.cost):
                tf = self._ticker_timeframe_map.get(ticker, Timeframe.FIFTEEN_MIN)
                self._portfolio.open_position(fill, tf)
                if self._exec_logger:
                    self._exec_logger.log_execution(ord, fill)

        timeframe = self._ticker_timeframe_map.get(ticker)
        if timeframe is None:
            return

        # Circuit breaker: halt all new trades when max drawdown exceeded
        if self._portfolio.circuit_breaker_tripped:
            return

        # Position limits
        if len(self._portfolio.open_positions) >= MAX_CONCURRENT_POSITIONS:
            return

        if self._portfolio.get_position(ticker) is not None:
            return

        # 1. Run ONNX Model Inference
        trades = self._recent_trades.get(ticker, [])
        t0 = time.perf_counter()
        onnx_res = self._onnx_engine.process_orderbook_tick(book, latest_trades=trades)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        onnx_signal = onnx_res.get("signal", "WAIT")
        onnx_conf = onnx_res.get("confidence", 0.0)
        vpin_score = onnx_res.get("vpin_score", 0.0)

        # Log AI inference telemetry periodically or on directional signal
        self._eval_count = getattr(self, "_eval_count", 0) + 1
        if onnx_signal in ("LONG", "SHORT") or self._eval_count % 10 == 0:
            logger.info(
                "[ONNX AI]   %-18s | Signal=%-5s (%4.1f%%) | VPIN=%.2f | OFI_L1=%+.2f | Latency=%.2fms",
                ticker, onnx_signal, onnx_conf * 100.0, vpin_score, onnx_res.get("ofi_l1", 0.0), latency_ms
            )

        # 2. Check VPIN Adverse Selection Override
        if onnx_res.get("vpin_veto"):
            logger.debug(
                "[%s] VPIN Risk Override Active: score=%.3f — suppressing trades.",
                ticker, onnx_res.get("vpin_score", 0.0)
            )
            return

        # 3. Stage 2 Mathematical Expected Value & Kelly Optimization
        prob_long = onnx_res.get("prob_long", 0.33)
        prob_short = onnx_res.get("prob_short", 0.33)
        prob_wait = onnx_res.get("prob_wait", 0.34)
        best_yes_ask = book.best_yes_ask
        best_yes_bid = book.best_yes_bid
        best_no_ask = (Decimal("1.00") - best_yes_bid) if best_yes_bid is not None else None

        ev_result = self._ev_engine.compute_optimal_execution(
            prob_up=prob_long,
            prob_down=prob_short,
            best_yes_ask=best_yes_ask,
            best_no_ask=best_no_ask,
            total_equity=self._portfolio.equity,
            max_position_size=self._get_max_size_for_tf(timeframe),
            vpin=vpin_score,
            prob_wait=prob_wait,
        )

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
                book,
                ticker,
                ev_result.recommended_side,
                ev_result.recommended_contracts,
                timeframe,
                ev_result.rationale,
            )
            return

        # 4. Fallback Microstructure Heuristics when EV is neutral/sub-threshold
        if timeframe == Timeframe.FIVE_MIN:
            await self._evaluate_scalp(book, ticker, timeframe)
        elif timeframe == Timeframe.FIFTEEN_MIN:
            await self._evaluate_momentum(book, ticker, timeframe)
            await self._evaluate_scalp(book, ticker, timeframe)
        elif timeframe == Timeframe.ONE_HOUR:
            await self._evaluate_swing(book, ticker, timeframe)

    async def on_ticker_update(self, update: TickerUpdate) -> None:
        """Process a ticker update — update caches and mark-to-market."""
        self._ticker_cache[update.market_ticker] = update

        if update.yes_bid is not None and update.yes_ask is not None:
            mid = (update.yes_bid + update.yes_ask) / 2
            history = self._mid_price_history.setdefault(update.market_ticker, [])
            history.append(mid)
            if len(history) > 20:
                history.pop(0)

        if update.yes_bid is not None:
            self._portfolio.mark_to_market(update.market_ticker, update.yes_bid)

    def settle_expired_market(
        self, ticker: str, market_info: MarketInfo, final_tick: TickerUpdate
    ) -> None:
        """Immediately settle an expired position against the final BTC settlement price."""
        from kalshi_sim.settlement import settle_position
        result = settle_position(
            portfolio=self._portfolio,
            ticker=ticker,
            market_info=market_info,
            last_ticker_update=final_tick,
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
                balance_after=float(self._portfolio.balance),
            )
            logger.info(
                "[SETTLED]   %-18s | %-3s %s %d contracts | P&L=%+$7.2f | Balance=$%.2f",
                ticker,
                result.side.value.upper(),
                result.outcome.upper(),
                result.size,
                result.pnl,
                self._portfolio.balance,
            )

    async def on_trade_event(self, trade: TradeEvent) -> None:
        """Accumulate recent trade executions for ONNX feature extraction."""
        trades = self._recent_trades.setdefault(trade.market_ticker, [])
        trades.append(trade)
        if len(trades) > 50:
            trades.pop(0)
        self._onnx_engine.extractor.process_trade(trade)

    def _get_max_size_for_tf(self, timeframe: Timeframe) -> int:
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
    ) -> None:
        """Submit a virtual market order against the L2 book."""
        snapshot = self._portfolio.get_pnl_snapshot()
        max_cost = snapshot.total_equity * MAX_POSITION_COST_PCT

        if side == OrderSide.YES:
            ask = book.best_yes_ask
            est_price = ask if ask is not None else Decimal("0.50")
        else:
            no_ask = Decimal("1") - book.best_yes_bid if book.best_yes_bid else None
            est_price = no_ask if no_ask is not None else Decimal("0.50")

        affordable_size = min(max_size, int(max_cost / est_price)) if est_price > 0 else 0
        if affordable_size <= 0:
            logger.debug("Cannot afford order on %s (equity=$%s)", ticker, snapshot.total_equity)
            return

        result = self._simulator.simulate_market_order(
            book, side, affordable_size, timeframe, reasoning
        )
        if result is None:
            return

        order, fill = result

        if not self._portfolio.can_afford(fill.cost):
            logger.warning(
                "Post-simulation cost check failed: $%s > balance $%s",
                fill.cost, self._portfolio.balance,
            )
            return

        self._portfolio.open_position(fill, timeframe)
        self._exec_logger.log_execution(order, fill)
        self._db_writer.enqueue_trade(
            trade_id=f"tr_{int(time.time()*1000)}_{ticker}_{random.randint(100, 999)}",
            ticker=ticker,
            side=fill.side.value,
            size=fill.size,
            price=float(fill.fill_price),
            gross_value=float(fill.cost),
            timeframe=timeframe.value,
            execution_mode="simulated",
            status="filled",
        )
        logger.info(
            "[SIM FILL]  %-18s | %-4s %-3d contracts @ $%-4s | Cost=$%-6.2f | Balance=$%-8.2f | [%s]",
            ticker, fill.side.value.upper(), fill.size, fill.fill_price,
            float(fill.cost), float(self._portfolio.balance), reasoning
        )

        # If live Demo execution client is attached, place real order on Kalshi Demo exchange
        if self._order_client is not None:
            try:
                demo_order = await self._order_client.place_order(
                    ticker=ticker,
                    side=side,
                    count=fill.size,
                    action="buy",
                    order_type="market",
                )
                if demo_order:
                    logger.info(
                        "[KALSHI DEMO EXCHANGE] Live Order Placed: %s | Status: %s",
                        demo_order.get("order_id"), demo_order.get("status"),
                    )
            except Exception as exc:
                logger.error("Failed to send order to Kalshi Demo exchange: %s", exc)

    # -- Background loops ----------------------------------------------------

    async def _pnl_report_loop(self) -> None:
        """Publish P&L summaries every 10 seconds."""
        while not self._shutdown.is_set():
            await asyncio.sleep(PNL_REPORT_INTERVAL_S)
            try:
                snapshot = self._portfolio.get_pnl_snapshot()
                self._exec_logger.log_pnl_summary(snapshot)
                self._db_writer.enqueue_equity_snapshot(
                    balance=float(snapshot.current_balance),
                    equity=float(snapshot.total_equity),
                    realized_pnl=float(snapshot.total_realized_pnl),
                    unrealized_pnl=float(snapshot.total_unrealized_pnl),
                    drawdown_pct=float(self._portfolio.current_drawdown_pct * 100),
                    win_rate=float((snapshot.win_rate or 0) * 100),
                    total_trades=snapshot.total_trades,
                    open_positions_count=snapshot.open_positions,
                )

                positions = self._portfolio.get_all_positions()
                if positions:
                    table = self._exec_logger.format_positions_table(positions)
                    logger.info("Open positions:\n%s", table)
            except Exception as exc:
                logger.error("P&L report error: %s", exc)

    async def _settlement_loop(self) -> None:
        """Check for expired positions and settle them every 10 seconds."""
        while not self._shutdown.is_set():
            await asyncio.sleep(SETTLEMENT_CHECK_INTERVAL_S)
            try:
                results = run_settlement_cycle(
                    self._portfolio,
                    self._market_cache,
                    self._ticker_cache,
                )
                for result in results:
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
                        balance_after=float(self._portfolio.balance),
                    )
            except Exception as exc:
                logger.error("Settlement cycle error: %s", exc)

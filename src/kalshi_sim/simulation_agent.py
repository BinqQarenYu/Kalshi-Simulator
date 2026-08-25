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
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from kalshi_sim.execution_logger import ExecutionLogger
from kalshi_sim.ml.onnx_engine import KalshiONNXEngine
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
SCALP_IMBALANCE_THRESHOLD = Decimal("0.65")
SCALP_MAX_POSITION_SIZE = 20
MOMENTUM_CONSECUTIVE_TICKS = 3
MOMENTUM_MAX_POSITION_SIZE = 50
SWING_DEPTH_RATIO_THRESHOLD = Decimal("2.0")
SWING_MAX_POSITION_SIZE = 100

PNL_REPORT_INTERVAL_S = 60.0
SETTLEMENT_CHECK_INTERVAL_S = 30.0
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
    ) -> None:
        self._orderbook = orderbook_manager
        self._timeframes = timeframes

        # Components
        self._portfolio = Portfolio(starting_balance=starting_capital)
        self._simulator = OrderSimulator()
        self._exec_logger = ExecutionLogger(data_dir=data_dir)
        self._onnx_engine = KalshiONNXEngine(model_path=model_path)

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

    async def start(self) -> None:
        """Start background tasks (P&L reporting, settlement checks)."""
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

        timeframe = self._ticker_timeframe_map.get(ticker)
        if timeframe is None:
            return

        # Position limits
        if len(self._portfolio.open_positions) >= MAX_CONCURRENT_POSITIONS:
            return

        if self._portfolio.get_position(ticker) is not None:
            return

        # 1. Run ONNX Model Inference
        trades = self._recent_trades.get(ticker, [])
        onnx_res = self._onnx_engine.process_orderbook_tick(book, latest_trades=trades)

        # 2. Check VPIN Adverse Selection Override
        if onnx_res.get("vpin_veto"):
            logger.debug(
                "[%s] VPIN Risk Override Active: score=%.3f — suppressing trades.",
                ticker, onnx_res.get("vpin_score", 0.0)
            )
            return

        # 3. ONNX Directional Execution Signal
        onnx_signal = onnx_res.get("signal", "WAIT")
        onnx_conf = onnx_res.get("confidence", 0.0)
        vpin_score = onnx_res.get("vpin_score", 0.0)

        if onnx_signal == "LONG":
            await self._place_virtual_order(
                book,
                ticker,
                OrderSide.YES,
                self._get_max_size_for_tf(timeframe),
                timeframe,
                f"ONNX Model LONG ({onnx_conf:.1%} conf) | VPIN: {vpin_score:.2f}",
            )
            return
        elif onnx_signal == "SHORT":
            await self._place_virtual_order(
                book,
                ticker,
                OrderSide.NO,
                self._get_max_size_for_tf(timeframe),
                timeframe,
                f"ONNX Model SHORT ({onnx_conf:.1%} conf) | VPIN: {vpin_score:.2f}",
            )
            return

        # 4. Fallback Microstructure Heuristics when ONNX is in WAIT state
        if timeframe in (Timeframe.FIVE_MIN, Timeframe.FIFTEEN_MIN) and Timeframe.FIVE_MIN in self._timeframes:
            await self._evaluate_scalp(book, ticker, Timeframe.FIVE_MIN)

        if timeframe == Timeframe.FIFTEEN_MIN and Timeframe.FIFTEEN_MIN in self._timeframes:
            await self._evaluate_momentum(book, ticker, timeframe)

        if timeframe == Timeframe.ONE_HOUR and Timeframe.ONE_HOUR in self._timeframes:
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

    # -- Background loops ----------------------------------------------------

    async def _pnl_report_loop(self) -> None:
        """Publish P&L summaries every 60 seconds."""
        while not self._shutdown.is_set():
            await asyncio.sleep(PNL_REPORT_INTERVAL_S)
            try:
                snapshot = self._portfolio.get_pnl_snapshot()
                self._exec_logger.log_pnl_summary(snapshot)

                positions = self._portfolio.get_all_positions()
                if positions:
                    table = self._exec_logger.format_positions_table(positions)
                    logger.info("Open positions:\n%s", table)
            except Exception as exc:
                logger.error("P&L report error: %s", exc)

    async def _settlement_loop(self) -> None:
        """Check for expired positions and settle them every 30 seconds."""
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
            except Exception as exc:
                logger.error("Settlement cycle error: %s", exc)

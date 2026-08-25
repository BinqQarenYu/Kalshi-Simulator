"""Simulation Execution Agent — strategy coordinator.

Evaluates entry/exit signals per timeframe mode, submits virtual orders
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
from typing import Any

from kalshi_sim.execution_logger import ExecutionLogger
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
)
from kalshi_sim.settlement import run_settlement_cycle

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Strategy parameters per mode
# ---------------------------------------------------------------------------

# Mode A (5m): Scalp — high-frequency imbalance
SCALP_IMBALANCE_THRESHOLD = Decimal("0.65")  # 65% order flow imbalance
SCALP_MAX_POSITION_SIZE = 20  # contracts per trade

# Mode B (15m): Momentum — consecutive directional moves
MOMENTUM_CONSECUTIVE_TICKS = 3  # ticks in same direction to trigger
MOMENTUM_MAX_POSITION_SIZE = 50

# Mode C (1h): Swing — book depth asymmetry
SWING_DEPTH_RATIO_THRESHOLD = Decimal("2.0")  # bid/ask volume ratio
SWING_MAX_POSITION_SIZE = 100

# General
PNL_REPORT_INTERVAL_S = 60.0
SETTLEMENT_CHECK_INTERVAL_S = 30.0
MAX_CONCURRENT_POSITIONS = 5
MAX_POSITION_COST_PCT = Decimal("0.10")  # max 10% of equity per position


class SimulationAgent:
    """Coordinates strategy evaluation, virtual order execution, and P&L tracking.

    Receives order book updates from the Data Ingestion Agent and evaluates
    timeframe-specific entry/exit conditions.
    """

    def __init__(
        self,
        orderbook_manager: OrderBookManager,
        timeframes: list[Timeframe],
        starting_capital: Decimal = Decimal("10000"),
        data_dir: Path = Path("data"),
    ) -> None:
        self._orderbook = orderbook_manager
        self._timeframes = timeframes

        # Components
        self._portfolio = Portfolio(starting_balance=starting_capital)
        self._simulator = OrderSimulator()
        self._exec_logger = ExecutionLogger(data_dir=data_dir)

        # Market metadata cache (populated by ingestion agent)
        self._market_cache: dict[str, MarketInfo] = {}
        self._ticker_cache: dict[str, TickerUpdate] = {}

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
            "Simulation Agent started | Capital: $%s | Timeframes: %s",
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
        """Evaluate strategy signals after an order book update.

        Called by the ingestion agent after every snapshot or delta.
        """
        book = self._orderbook.get_book(ticker)
        if book is None or book.is_stale:
            return

        timeframe = self._ticker_timeframe_map.get(ticker)
        if timeframe is None:
            return

        # Don't exceed max concurrent positions
        if len(self._portfolio.open_positions) >= MAX_CONCURRENT_POSITIONS:
            return

        # Already have a position in this ticker
        if self._portfolio.get_position(ticker) is not None:
            return

        # Evaluate based on timeframe mode
        if timeframe in (Timeframe.FIVE_MIN, Timeframe.FIFTEEN_MIN) and \
                Timeframe.FIVE_MIN in self._timeframes:
            await self._evaluate_scalp(book, ticker, Timeframe.FIVE_MIN)

        if timeframe == Timeframe.FIFTEEN_MIN and \
                Timeframe.FIFTEEN_MIN in self._timeframes:
            await self._evaluate_momentum(book, ticker, timeframe)

        if timeframe == Timeframe.ONE_HOUR and \
                Timeframe.ONE_HOUR in self._timeframes:
            await self._evaluate_swing(book, ticker, timeframe)

    async def on_ticker_update(self, update: TickerUpdate) -> None:
        """Process a ticker update — update caches and mark-to-market."""
        self._ticker_cache[update.market_ticker] = update

        # Track mid-price history for momentum detection
        if update.yes_bid is not None and update.yes_ask is not None:
            mid = (update.yes_bid + update.yes_ask) / 2
            history = self._mid_price_history.setdefault(
                update.market_ticker, []
            )
            history.append(mid)
            # Keep last 20 ticks
            if len(history) > 20:
                history.pop(0)

        # Mark-to-market open positions
        if update.yes_bid is not None:
            self._portfolio.mark_to_market(
                update.market_ticker, update.yes_bid
            )

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
            # Strong bid imbalance → buy Yes
            await self._place_virtual_order(
                book, ticker, OrderSide.YES, SCALP_MAX_POSITION_SIZE,
                timeframe,
                f"Scalp: bid imbalance {bid_pct:.1%} > {SCALP_IMBALANCE_THRESHOLD}",
            )
        elif (1 - bid_pct) > SCALP_IMBALANCE_THRESHOLD:
            # Strong ask imbalance → buy No
            await self._place_virtual_order(
                book, ticker, OrderSide.NO, SCALP_MAX_POSITION_SIZE,
                timeframe,
                f"Scalp: ask imbalance {1 - bid_pct:.1%} > {SCALP_IMBALANCE_THRESHOLD}",
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
                f"Swing: bid/ask depth ratio {ratio:.1f}:1 > {SWING_DEPTH_RATIO_THRESHOLD}",
            )
        elif (Decimal("1") / ratio) > SWING_DEPTH_RATIO_THRESHOLD:
            await self._place_virtual_order(
                book, ticker, OrderSide.NO, SWING_MAX_POSITION_SIZE,
                timeframe,
                f"Swing: ask/bid depth ratio {Decimal('1') / ratio:.1f}:1 > {SWING_DEPTH_RATIO_THRESHOLD}",
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
        # Risk check: max cost = 10% of equity
        snapshot = self._portfolio.get_pnl_snapshot()
        max_cost = snapshot.total_equity * MAX_POSITION_COST_PCT

        # Estimate cost: worst case = size × $1.00
        # Better estimate: size × current ask
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

        # Simulate the fill
        result = self._simulator.simulate_market_order(
            book, side, affordable_size, timeframe, reasoning
        )
        if result is None:
            return

        order, fill = result

        # Check if portfolio can afford the actual cost
        if not self._portfolio.can_afford(fill.cost):
            logger.warning(
                "Post-simulation cost check failed: $%s > balance $%s",
                fill.cost, self._portfolio.balance,
            )
            return

        # Execute the virtual trade
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

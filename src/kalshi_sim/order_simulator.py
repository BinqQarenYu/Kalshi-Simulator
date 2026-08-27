"""Order simulator — simulates fills against L2 order book state.

Walks the order book depth to compute realistic VWAP fill prices with
timeframe-specific slippage multipliers. No live orders are ever placed.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from kalshi_sim.schemas import (
    L2BookState,
    OrderSide,
    OrderType,
    SimulatedFill,
    SimulatedOrder,
    Timeframe,
)

logger = logging.getLogger(__name__)

# Timeframe-specific slippage multipliers
SLIPPAGE_MULTIPLIER: dict[Timeframe, Decimal] = {
    Timeframe.FIVE_MIN: Decimal("1.5"),    # thin books, fast markets
    Timeframe.FIFTEEN_MIN: Decimal("1.0"),  # baseline
    Timeframe.ONE_HOUR: Decimal("0.75"),    # deeper liquidity
    Timeframe.DAILY: Decimal("0.5"),        # deepest liquidity
}


class OrderSimulator:
    """Simulates order execution against the live L2 order book.

    No real orders are placed — fills are computed locally from book state.
    """

    def __init__(self) -> None:
        self._resting_orders: dict[str, list[SimulatedOrder]] = {}

    def place_resting_limit_order(
        self,
        book: L2BookState,
        side: OrderSide,
        size: int,
        limit_price: Decimal,
        timeframe: Timeframe,
        reasoning: str = "",
    ) -> SimulatedOrder:
        """Place a resting limit order on the book queue."""
        order_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)

        order = SimulatedOrder(
            order_id=order_id,
            ticker=book.market_ticker,
            side=side,
            order_type=OrderType.LIMIT,
            size=size,
            limit_price=limit_price,
            timeframe=timeframe,
            reasoning=reasoning,
            created_at=now,
            status="resting",
        )

        if book.market_ticker not in self._resting_orders:
            self._resting_orders[book.market_ticker] = []
        self._resting_orders[book.market_ticker].append(order)

        logger.info(
            "RESTING ORDER PLACED: %s %s %d @ $%s on %s (ID: %s)",
            side.value.upper(), "LIMIT", size, limit_price, book.market_ticker, order_id,
        )
        return order

    def cancel_resting_order(self, order_id: str) -> bool:
        """Cancel a resting limit order by ID."""
        for ticker, orders in self._resting_orders.items():
            for i, ord in enumerate(orders):
                if ord.order_id == order_id:
                    orders.pop(i)
                    logger.info("CANCELLED RESTING ORDER: %s on %s", order_id, ticker)
                    return True
        return False

    def get_all_resting_orders(self) -> list[SimulatedOrder]:
        """Return all currently active resting limit orders."""
        all_orders = []
        for orders in self._resting_orders.values():
            all_orders.extend(orders)
        return all_orders

    def process_resting_orders(
        self,
        book: L2BookState,
    ) -> list[tuple[SimulatedOrder, SimulatedFill]]:
        """Evaluate and match resting orders against new book state."""
        orders = self._resting_orders.get(book.market_ticker, [])
        if not orders:
            return []

        filled: list[tuple[SimulatedOrder, SimulatedFill]] = []
        remaining: list[SimulatedOrder] = []
        now = datetime.now(timezone.utc)

        for ord in orders:
            is_filled = False
            fill_price = ord.limit_price or Decimal("0.50")

            if ord.side == OrderSide.YES:
                best_ask = book.best_yes_ask
                if best_ask is not None and ord.limit_price is not None and ord.limit_price >= best_ask:
                    is_filled = True
                    fill_price = min(ord.limit_price, best_ask)
            else:
                best_no_bid = book.best_no_bid
                if best_no_bid is not None:
                    best_no_ask = Decimal("1") - book.best_yes_bid if book.best_yes_bid else None
                    if best_no_ask is not None and ord.limit_price is not None and ord.limit_price >= best_no_ask:
                        is_filled = True
                        fill_price = min(ord.limit_price, best_no_ask)

            if is_filled:
                cost = fill_price * ord.size
                ord.status = "filled"
                fill = SimulatedFill(
                    order_id=ord.order_id,
                    ticker=ord.ticker,
                    side=ord.side,
                    size=ord.size,
                    fill_price=fill_price,
                    slippage=Decimal("0"),
                    cost=cost,
                    timestamp=now,
                )
                filled.append((ord, fill))
                logger.info(
                    "RESTING ORDER MATCHED & FILLED: %s %s %d @ $%s (cost=$%s) [ID: %s]",
                    ord.side.value.upper(), ord.ticker, ord.size, fill_price, cost, ord.order_id,
                )
            else:
                remaining.append(ord)

        self._resting_orders[book.market_ticker] = remaining
        return filled

    def simulate_market_order(
        self,
        book: L2BookState,
        side: OrderSide,
        size: int,
        timeframe: Timeframe,
        reasoning: str = "",
    ) -> tuple[SimulatedOrder, SimulatedFill] | None:
        """Simulate a market order by walking the order book depth.

        For a Yes buy: we consume No side liquidity (buying yes = selling no).
        The fill price is the VWAP across consumed levels.

        Args:
            book: Current L2 order book state.
            side: ``OrderSide.YES`` or ``OrderSide.NO``.
            size: Number of contracts to fill.
            timeframe: Determines slippage multiplier.
            reasoning: Strategy rationale for the trade log.

        Returns:
            Tuple of (SimulatedOrder, SimulatedFill), or None if book
            has insufficient liquidity.
        """
        order_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)

        # Determine which side of the book to consume
        if side == OrderSide.YES:
            # Buying Yes: we hit the ask side, which is derived from No bids
            # Best yes ask = 1 - best_no_bid. Walk No book from highest to lowest.
            consume_book = book.no_book
            price_transform = lambda no_price: Decimal("1") - no_price
        else:
            # Buying No: we hit the Yes book directly
            consume_book = book.yes_book
            price_transform = lambda yes_price: Decimal("1") - yes_price

        if not consume_book:
            logger.warning(
                "Cannot simulate %s market order on %s: empty book",
                side.value, book.market_ticker,
            )
            return None

        # Walk the book to compute VWAP
        vwap_price, total_filled, slippage = self._walk_book(
            consume_book, size, side, timeframe
        )

        if total_filled == 0:
            logger.warning(
                "Insufficient liquidity for %s %s %d on %s",
                side.value, "market", size, book.market_ticker,
            )
            return None

        # Compute cost: price per contract × number of contracts
        cost = vwap_price * total_filled

        order = SimulatedOrder(
            order_id=order_id,
            ticker=book.market_ticker,
            side=side,
            order_type=OrderType.MARKET,
            size=total_filled,
            timeframe=timeframe,
            reasoning=reasoning,
            created_at=now,
            status="filled",
        )

        fill = SimulatedFill(
            order_id=order_id,
            ticker=book.market_ticker,
            side=side,
            size=total_filled,
            fill_price=vwap_price,
            slippage=slippage,
            cost=cost,
            timestamp=now,
        )

        logger.info(
            "SIM FILL: %s %s %d @ $%s (slippage=$%s, cost=$%s) [%s]",
            side.value.upper(), book.market_ticker, total_filled,
            vwap_price, slippage, cost, reasoning[:60],
        )

        return order, fill

    def simulate_limit_order(
        self,
        book: L2BookState,
        side: OrderSide,
        size: int,
        limit_price: Decimal,
        timeframe: Timeframe,
        reasoning: str = "",
    ) -> tuple[SimulatedOrder, SimulatedFill] | None:
        """Simulate a limit order — only fills if immediately marketable.

        If the limit price crosses the current spread, fills at the limit price.
        Non-marketable limits (that would rest on the book) return None in v1.

        Args:
            book: Current L2 order book state.
            side: Order side.
            size: Number of contracts.
            limit_price: Maximum price willing to pay.
            timeframe: Timeframe mode.
            reasoning: Strategy rationale.

        Returns:
            Tuple of (order, fill) if marketable, None otherwise.
        """
        order_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)

        # Check if limit is marketable
        is_marketable = False

        if side == OrderSide.YES:
            best_ask = book.best_yes_ask
            if best_ask is not None and limit_price >= best_ask:
                is_marketable = True
        else:
            best_no_bid = book.best_no_bid
            if best_no_bid is not None:
                best_no_ask = Decimal("1") - book.best_yes_bid if book.best_yes_bid else None
                if best_no_ask is not None and limit_price >= best_no_ask:
                    is_marketable = True

        if not is_marketable:
            logger.debug(
                "Limit order not marketable: %s %s %d @ $%s on %s",
                side.value, "limit", size, limit_price, book.market_ticker,
            )
            return None

        # Fill at the limit price (no slippage beyond limit)
        cost = limit_price * size

        order = SimulatedOrder(
            order_id=order_id,
            ticker=book.market_ticker,
            side=side,
            order_type=OrderType.LIMIT,
            size=size,
            limit_price=limit_price,
            timeframe=timeframe,
            reasoning=reasoning,
            created_at=now,
            status="filled",
        )

        fill = SimulatedFill(
            order_id=order_id,
            ticker=book.market_ticker,
            side=side,
            size=size,
            fill_price=limit_price,
            slippage=Decimal("0"),
            cost=cost,
            timestamp=now,
        )

        logger.info(
            "SIM LIMIT FILL: %s %s %d @ $%s (cost=$%s) [%s]",
            side.value.upper(), book.market_ticker, size,
            limit_price, cost, reasoning[:60],
        )

        return order, fill

    def _walk_book(
        self,
        book_side: dict[Decimal, Decimal],
        size: int,
        order_side: OrderSide,
        timeframe: Timeframe,
    ) -> tuple[Decimal, int, Decimal]:
        """Walk the order book to compute fill price with slippage.

        For Yes buys: we consume the No book. The best price for a Yes buyer
        is the *highest* No bid (cheapest Yes ask = 1 - highest_no_bid).

        For No buys: we consume the Yes book similarly.

        Args:
            book_side: The side of the book to consume (price → quantity).
            size: Contracts to fill.
            order_side: Which side we're buying.
            timeframe: For slippage multiplier.

        Returns:
            Tuple of (vwap_price, total_filled, total_slippage).
        """
        # Sort levels: for consuming, we want best price first
        if order_side == OrderSide.YES:
            # Consuming No book: highest No bid first (= cheapest Yes ask)
            sorted_levels = sorted(book_side.items(), key=lambda x: x[0], reverse=True)
        else:
            # Consuming Yes book: highest Yes bid first (= cheapest No ask)
            sorted_levels = sorted(book_side.items(), key=lambda x: x[0], reverse=True)

        remaining = size
        total_cost = Decimal("0")
        total_filled = 0
        first_price: Decimal | None = None

        for raw_price, qty in sorted_levels:
            if remaining <= 0:
                break

            # Convert to the buyer's price
            if order_side == OrderSide.YES:
                fill_price = Decimal("1") - raw_price  # yes price = 1 - no_bid
            else:
                fill_price = Decimal("1") - raw_price  # no price = 1 - yes_bid

            if first_price is None:
                first_price = fill_price

            fill_qty = min(remaining, int(qty))
            total_cost += fill_price * fill_qty
            total_filled += fill_qty
            remaining -= fill_qty

        if total_filled == 0:
            return Decimal("0"), 0, Decimal("0")

        # Compute VWAP
        vwap = (total_cost / total_filled).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

        # Apply timeframe-specific slippage
        multiplier = SLIPPAGE_MULTIPLIER.get(timeframe, Decimal("1.0"))
        raw_slippage = abs(vwap - first_price) if first_price else Decimal("0")
        adjusted_slippage = (raw_slippage * multiplier).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

        # Adjust VWAP by slippage
        final_vwap = (vwap + adjusted_slippage).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

        # Cap at $1.00 (binary option max)
        final_vwap = min(final_vwap, Decimal("1.00"))

        return final_vwap, total_filled, adjusted_slippage

    @staticmethod
    def compute_slippage(entry_price: Decimal, fair_mid: Decimal) -> Decimal:
        """Compute raw slippage between entry and fair mid price.

        Args:
            entry_price: Actual fill price.
            fair_mid: Theoretical fair/mid price.

        Returns:
            Absolute slippage in dollars.
        """
        return abs(entry_price - fair_mid)

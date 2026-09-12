"""Order simulator — simulates fills against L2 order book state.

Walks the order book depth to compute realistic VWAP fill prices with
timeframe-specific slippage multipliers. No live orders are ever placed.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, ROUND_UP

from kalshi_sim.schemas import (
    L2BookState,
    OrderSide,
    OrderStatus,
    OrderType,
    SimulatedFill,
    SimulatedOrder,
    Timeframe,
    TradeEvent,
)

logger = logging.getLogger(__name__)

# Timeframe-specific slippage multipliers
SLIPPAGE_MULTIPLIER: dict[Timeframe, Decimal] = {
    Timeframe.FIVE_MIN: Decimal("1.5"),    # thin books, fast markets
    Timeframe.FIFTEEN_MIN: Decimal("1.0"),  # baseline
    Timeframe.ONE_HOUR: Decimal("0.75"),    # deeper liquidity
    Timeframe.DAILY: Decimal("0.5"),        # deepest liquidity
}

# Multi-Asset Spot Velocity Adverse Selection Thresholds
SPOT_VELOCITY_ADVERSE_THRESHOLDS: dict[str, float] = {
    "BTC": 15.0,
    "ETH": 2.0,
    "SOL": 0.20,
    "GOLD": 0.50,
    "DOGE": 0.001,
}


class OrderSimulator:
    """Simulates order execution against the live L2 order book.

    No real orders are placed — fills are computed locally from book state.
    """

    def __init__(self, fee_per_contract: Decimal = Decimal("0.01")) -> None:
        self.fee_per_contract = fee_per_contract
        self._resting_orders: dict[str, list[SimulatedOrder]] = {}

    @staticmethod
    def calculate_kalshi_taker_fee(price: Decimal, contracts: int) -> Decimal:
        """Calculate realistic Kalshi member taker transaction fee.

        Kalshi taker fee formula:
            fee_cents = ceil(0.07 * contracts * P * (1 - P) * 100)
        Subject to:
            min: $0.01 per contract (1 cent floor)
            max: $0.02 per contract (2 cents cap)
        """
        if contracts <= 0:
            return Decimal("0.00")
        c_dec = Decimal(str(contracts))
        p = max(Decimal("0.01"), min(Decimal("0.99"), price))
        raw_cents = Decimal("7.0") * c_dec * p * (Decimal("1.00") - p)
        fee_cents = raw_cents.quantize(Decimal("1"), rounding=ROUND_UP)
        fee = fee_cents / Decimal("100")
        min_fee = Decimal("0.01") * c_dec
        max_fee = Decimal("0.02") * c_dec
        return max(min_fee, min(max_fee, fee))


    def place_resting_limit_order(
        self,
        book: L2BookState,
        side: OrderSide,
        size: int,
        limit_price: Decimal,
        timeframe: Timeframe,
        reasoning: str = "",
    ) -> SimulatedOrder:
        """Place a resting limit order on the book queue, tracking queue depth ahead."""
        order_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)

        # Track institutional FIFO queue depth ahead at this price level
        initial_queue = 0
        if side == OrderSide.YES and limit_price in book.yes_book:
            initial_queue = int(book.yes_book[limit_price])
        elif side == OrderSide.NO and limit_price in book.no_book:
            initial_queue = int(book.no_book[limit_price])

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
            status=OrderStatus.RESTING,
            queue_ahead=initial_queue,
            filled_size=0,
        )

        if book.market_ticker not in self._resting_orders:
            self._resting_orders[book.market_ticker] = []
        self._resting_orders[book.market_ticker].append(order)

        logger.info(
            "RESTING ORDER PLACED: %s %s %d @ $%s on %s (ID: %s, Queue Ahead: %d)",
            side.value.upper(), "LIMIT", size, limit_price, book.market_ticker, order_id, initial_queue,
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

    def cancel_resting_orders_for_ticker(self, ticker: str) -> int:
        """Cancel all resting limit orders for a given ticker."""
        orders = self._resting_orders.pop(ticker, [])
        if orders:
            logger.info("CANCELLED ALL %d RESTING ORDERS for %s", len(orders), ticker)
        return len(orders)

    def cancel_expired_orders(
        self,
        time_remaining_s: int,
        cutoff_s: int = 270,
        ticker: str | None = None,
    ) -> list[SimulatedOrder]:
        """Cancel resting limit orders when cycle entry window closes (T_rem <= cutoff_s)."""
        if time_remaining_s > cutoff_s:
            return []

        expired: list[SimulatedOrder] = []
        tickers_to_check = [ticker] if ticker else list(self._resting_orders.keys())

        for tkr in tickers_to_check:
            orders = self._resting_orders.get(tkr, [])
            remaining: list[SimulatedOrder] = []
            for ord in orders:
                ord.status = OrderStatus.EXPIRED
                expired.append(ord)
                logger.info(
                    "⏰ [RESTING ORDER EXPIRED UNFILLED] %s %s %d @ $%s on %s (T_rem: %ds <= %ds)",
                    ord.side.value.upper(),
                    ord.order_type.value.upper(),
                    ord.size,
                    ord.limit_price,
                    ord.ticker,
                    time_remaining_s,
                    cutoff_s,
                )
            self._resting_orders[tkr] = remaining

        return expired

    def get_all_resting_orders(self) -> list[SimulatedOrder]:
        """Return all currently active resting limit orders."""
        all_orders = []
        for orders in self._resting_orders.values():
            all_orders.extend(orders)
        return all_orders

    def process_resting_orders(
        self,
        book: L2BookState,
        latest_trades: list[TradeEvent] | None = None,
    ) -> list[tuple[SimulatedOrder, SimulatedFill]]:
        """Evaluate and match resting orders against new book state and public trade tape using FIFO queue priority."""
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
                # 1. Price touch / cross (market crossed limit)
                if best_ask is not None and ord.limit_price is not None and ord.limit_price >= best_ask:
                    is_filled = True
                    fill_price = min(ord.limit_price, best_ask)
                # 2. Passive queue execution: trade occurred on the public tape
                elif latest_trades and ord.limit_price is not None:
                    for tr in latest_trades:
                        if tr.market_ticker == ord.ticker and tr.yes_price is not None:
                            if tr.yes_price < ord.limit_price:
                                # Market swept below our bid level: instant full fill
                                is_filled = True
                                fill_price = ord.limit_price
                                break
                            elif tr.yes_price == ord.limit_price:
                                trade_count = int(getattr(tr, "count", 1) or 1)
                                if ord.queue_ahead > 0:
                                    if trade_count <= ord.queue_ahead:
                                        ord.queue_ahead -= trade_count
                                    else:
                                        excess = trade_count - ord.queue_ahead
                                        ord.queue_ahead = 0
                                        ord.filled_size += min(ord.size - ord.filled_size, excess)
                                        if ord.filled_size >= ord.size:
                                            is_filled = True
                                            fill_price = ord.limit_price
                                            break
                                else:
                                    ord.filled_size += min(ord.size - ord.filled_size, trade_count)
                                    if ord.filled_size >= ord.size:
                                        is_filled = True
                                        fill_price = ord.limit_price
                                        break
            else:
                best_no_ask = Decimal("1") - book.best_yes_bid if book.best_yes_bid else None
                if best_no_ask is not None and ord.limit_price is not None and ord.limit_price >= best_no_ask:
                    is_filled = True
                    fill_price = min(ord.limit_price, best_no_ask)
                elif latest_trades and ord.limit_price is not None:
                    for tr in latest_trades:
                        if tr.market_ticker == ord.ticker and tr.no_price is not None:
                            if tr.no_price < ord.limit_price:
                                is_filled = True
                                fill_price = ord.limit_price
                                break
                            elif tr.no_price == ord.limit_price:
                                trade_count = int(getattr(tr, "count", 1) or 1)
                                if ord.queue_ahead > 0:
                                    if trade_count <= ord.queue_ahead:
                                        ord.queue_ahead -= trade_count
                                    else:
                                        excess = trade_count - ord.queue_ahead
                                        ord.queue_ahead = 0
                                        ord.filled_size += min(ord.size - ord.filled_size, excess)
                                        if ord.filled_size >= ord.size:
                                            is_filled = True
                                            fill_price = ord.limit_price
                                            break
                                else:
                                    ord.filled_size += min(ord.size - ord.filled_size, trade_count)
                                    if ord.filled_size >= ord.size:
                                        is_filled = True
                                        fill_price = ord.limit_price
                                        break

            if is_filled:
                cost = fill_price * ord.size
                # Resting maker orders provide liquidity — Kalshi charges $0.00 maker fees
                fee = Decimal("0.00")
                ord.status = OrderStatus.FILLED
                fill = SimulatedFill(
                    order_id=ord.order_id,
                    ticker=ord.ticker,
                    side=ord.side,
                    size=ord.size,
                    fill_price=fill_price,
                    slippage=Decimal("0"),
                    fee=fee,
                    cost=cost,
                    timestamp=now,
                )
                filled.append((ord, fill))
                logger.info(
                    "RESTING MAKER ORDER MATCHED & FILLED: %s %s %d @ $%s (maker_fee=$0.00, cost=$%s) [ID: %s]",
                    ord.side.value.upper(), ord.ticker, ord.size, fill_price, cost, ord.order_id,
                )
            else:
                remaining.append(ord)

        self._resting_orders[book.market_ticker] = remaining
        return filled

    @staticmethod
    def get_adverse_velocity_threshold(asset_or_ticker: str) -> float:
        """Get spot velocity adverse threshold for specific asset."""
        key = asset_or_ticker.upper()
        for ast, thresh in SPOT_VELOCITY_ADVERSE_THRESHOLDS.items():
            if ast in key:
                return thresh
        return 15.0

    def simulate_market_order(
        self,
        book: L2BookState,
        side: OrderSide,
        size: int,
        timeframe: Timeframe,
        reasoning: str = "",
        spot_velocity: float = 0.0,
        asset: str | None = None,
    ) -> tuple[SimulatedOrder, SimulatedFill] | None:
        """Simulate a market order by walking the order book depth.

        For a Yes buy: we consume No side liquidity (buying yes = selling no).
        The fill price is the VWAP across consumed levels with realistic adverse selection.

        Args:
            book: Current L2 order book state.
            side: ``OrderSide.YES`` or ``OrderSide.NO``.
            size: Number of contracts to fill.
            timeframe: Determines slippage multiplier.
            reasoning: Strategy rationale for the trade log.
            spot_velocity: Rolling 10s spot price change in dollars (for adverse selection).
            asset: Optional asset identifier ('BTC', 'GOLD', etc.).

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

        # Walk the book to compute VWAP with depth exhaustion and asset-specific adverse drift
        vwap_price, total_filled, slippage = self._walk_book(
            consume_book,
            size,
            side,
            timeframe,
            spot_velocity=spot_velocity,
            asset_or_ticker=asset or book.market_ticker,
        )

        if total_filled == 0:
            logger.warning(
                "Insufficient liquidity for %s %s %d on %s",
                side.value, "market", size, book.market_ticker,
            )
            return None

        if total_filled < size:
            logger.info(
                "[PARTIAL IOC FILL] Requested %d contracts, only %d available in L2 book on %s",
                size, total_filled, book.market_ticker,
            )

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
            status=OrderStatus.FILLED,
        )

        # Exact Kalshi Taker Fee Schedule
        fee = self.calculate_kalshi_taker_fee(vwap_price, total_filled)

        fill = SimulatedFill(
            order_id=order_id,
            ticker=book.market_ticker,
            side=side,
            size=total_filled,
            fill_price=vwap_price,
            slippage=slippage,
            fee=fee,
            cost=cost,
            timestamp=now,
        )

        logger.info(
            "SIM FILL: %s %s %d @ $%s (fee=$%s, slippage=$%s, cost=$%s) [%s]",
            side.value.upper(), book.market_ticker, total_filled,
            vwap_price, fee, slippage, cost, reasoning[:60],
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
        spot_velocity: float = 0.0,
        asset: str | None = None,
    ) -> tuple[SimulatedOrder, SimulatedFill] | None:
        """Simulate a limit order — only fills if immediately marketable.

        If the limit price crosses the current spread, fills at the limit price (with
        latency/adverse drift check).

        Args:
            book: Current L2 order book state.
            side: Order side.
            size: Number of contracts.
            limit_price: Maximum price willing to pay.
            timeframe: Timeframe mode.
            reasoning: Strategy rationale.
            spot_velocity: Rolling spot velocity in dollars.
            asset: Optional asset key for adverse drift threshold.

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

        # Fill at limit price, accounting for in-flight fast-market drift
        fill_price = limit_price
        vel_thresh = self.get_adverse_velocity_threshold(asset or book.market_ticker)
        if (side == OrderSide.YES and spot_velocity > vel_thresh) or (
            side == OrderSide.NO and spot_velocity < -vel_thresh
        ):
            fill_price = min(Decimal("0.99"), limit_price + Decimal("0.01"))

        cost = fill_price * size

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
            status=OrderStatus.FILLED,
        )

        # Marketable limit orders cross the spread and pay taker fees
        fee = self.calculate_kalshi_taker_fee(fill_price, size)

        fill = SimulatedFill(
            order_id=order_id,
            ticker=book.market_ticker,
            side=side,
            size=size,
            fill_price=fill_price,
            slippage=Decimal("0"),
            fee=fee,
            cost=cost,
            timestamp=now,
        )

        logger.info(
            "SIM LIMIT FILL: %s %s %d @ $%s (fee=$%s, cost=$%s) [%s]",
            side.value.upper(), book.market_ticker, size,
            fill_price, fee, cost, reasoning[:60],
        )

        return order, fill

    def _walk_book(
        self,
        book_side: dict[Decimal, Decimal],
        size: int,
        order_side: OrderSide,
        timeframe: Timeframe,
        spot_velocity: float = 0.0,
        asset_or_ticker: str = "",
    ) -> tuple[Decimal, int, Decimal]:
        """Walk the order book to compute fill price with realistic depth and slippage.

        For Yes buys: we consume the No book. The best price for a Yes buyer
        is the *highest* No bid (cheapest Yes ask = 1 - highest_no_bid).

        For No buys: we consume the Yes book similarly.

        Args:
            book_side: The side of the book to consume (price → quantity).
            size: Contracts to fill.
            order_side: Which side we're buying.
            timeframe: For slippage multiplier.
            spot_velocity: Rolling spot velocity in dollars (adverse selection drift).
            asset_or_ticker: Asset key or ticker string for threshold calibration.

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
            if fill_qty <= 0:
                continue
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

        # Realistic adverse selection / latency price drift:
        # If market momentum is running strongly in trade direction,
        # by the time the order arrives (75-150ms), price has drifted adversely
        vel_threshold = self.get_adverse_velocity_threshold(asset_or_ticker)
        adverse_penalty = Decimal("0.0")
        if order_side == OrderSide.YES and spot_velocity > vel_threshold:
            adverse_penalty = Decimal("0.01")
        elif order_side == OrderSide.NO and spot_velocity < -vel_threshold:
            adverse_penalty = Decimal("0.01")

        final_vwap = (vwap + adjusted_slippage + adverse_penalty).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

        # Bound strictly between $0.01 and $0.99 for binary options
        final_vwap = max(Decimal("0.01"), min(Decimal("0.99"), final_vwap))
        total_slippage = abs(final_vwap - (first_price or final_vwap))

        return final_vwap, total_filled, total_slippage

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

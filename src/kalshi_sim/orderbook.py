"""L2 order book manager for Kalshi binary markets.

Maintains in-memory order book state per market ticker, applying
full snapshots and incremental deltas received over the WebSocket.
Detects sequence gaps and marks books as stale when re-synchronization
is required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import logging

from kalshi_sim.schemas import (
    L2BookState,
    OrderBookDelta,
    OrderBookLevel,
    OrderBookSnapshot,
)

logger = logging.getLogger(__name__)


import time

class OrderBookManager:
    """Manages reconstructed L2 order books across multiple Kalshi markets."""

    def __init__(self, enforce_consecutive_seq: bool = True) -> None:
        """Initialize the order book manager with an empty books registry.

        Args:
            enforce_consecutive_seq: If True, delta.seq must equal last_seq + 1 (single-market stream).
                If False, delta.seq is monotonically increasing across a shared multi-market session.
        """
        self._books: dict[str, L2BookState] = {}
        self._last_gap_warning: dict[str, float] = {}
        self._enforce_consecutive_seq = enforce_consecutive_seq
        self._logger = logging.getLogger(__name__)

    def apply_snapshot(self, snapshot: OrderBookSnapshot) -> L2BookState:
        """Create or reset the L2 book state from a full snapshot message.

        Args:
            snapshot: The initial full-depth order book snapshot.

        Returns:
            L2BookState: The updated in-memory book state.
        """
        book = L2BookState(snapshot.market_ticker)
        book.yes_book = {
            level.price: level.quantity for level in snapshot.yes_levels
        }
        book.no_book = {
            level.price: level.quantity for level in snapshot.no_levels
        }
        book.last_seq = snapshot.seq
        book._stale = False
        book.last_update = snapshot.timestamp
        self._books[snapshot.market_ticker] = book
        self._logger.debug(
            "Applied snapshot for %s at seq %d (yes_levels=%d, no_levels=%d)",
            snapshot.market_ticker,
            snapshot.seq,
            len(book.yes_book),
            len(book.no_book),
        )
        return book

    def apply_delta(self, delta: OrderBookDelta) -> L2BookState | None:
        """Apply an incremental price-level update to an existing order book.

        Validates sequence numbers to ensure no messages were dropped. If a sequence
        gap is detected, the book is marked as stale and None is returned to signal
        that re-subscription / snapshot recovery is required.

        Args:
            delta: Incremental L2 order book delta.

        Returns:
            L2BookState | None: The updated book state, or None if the book does not
                exist or a sequence gap was detected.
        """
        book = self._books.get(delta.market_ticker)
        if book is None:
            book = L2BookState(delta.market_ticker)
            book.last_seq = delta.seq
            book._stale = False
            self._books[delta.market_ticker] = book

        if book.last_seq == -1:
            book.last_seq = delta.seq
        elif self._enforce_consecutive_seq:
            expected_seq = book.last_seq + 1
            if delta.seq != expected_seq:
                now = time.monotonic()
                if now - self._last_gap_warning.get(delta.market_ticker, 0.0) > 10.0:
                    self._logger.debug(
                        "Sequence gap detected for %s: expected seq %d, received seq %d (resyncing)",
                        delta.market_ticker,
                        expected_seq,
                        delta.seq,
                    )
                    self._last_gap_warning[delta.market_ticker] = now
                book._stale = True
                book.last_seq = delta.seq
                return None
        else:
            if book.last_seq != -1 and delta.seq < book.last_seq:
                # Discard out-of-order delta older than current book state
                return book
            book._stale = False

        # Apply delta to the appropriate side book
        side_book = book.yes_book if delta.side == "yes" else book.no_book
        current_qty = side_book.get(delta.price, Decimal("0"))
        new_qty = current_qty + delta.delta

        if new_qty <= Decimal("0"):
            side_book.pop(delta.price, None)
        else:
            side_book[delta.price] = new_qty

        book.last_seq = delta.seq
        book.last_update = delta.timestamp
        return book

    def get_book(self, ticker: str) -> L2BookState | None:
        """Retrieve the order book state for a market ticker.

        Args:
            ticker: The market ticker symbol.

        Returns:
            L2BookState | None: The book state if tracked, otherwise None.
        """
        return self._books.get(ticker)

    def set_book(self, ticker: str, book: L2BookState) -> None:
        """Set or update the order book state for a market ticker.

        Args:
            ticker: The market ticker symbol.
            book: The L2BookState instance.
        """
        self._books[ticker] = book

    def get_top_of_book(
        self, ticker: str
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        """Get best yes bid, best yes ask, and spread for a market ticker.

        Args:
            ticker: The market ticker symbol.

        Returns:
            tuple[Decimal | None, Decimal | None, Decimal | None]: Tuple of
                `(best_bid, best_ask, spread)`. Returns `(None, None, None)`
                if the market is not tracked.
        """
        book = self.get_book(ticker)
        if book is None:
            return None, None, None
        return book.best_yes_bid, book.best_yes_ask, book.spread

    def get_depth_levels(
        self, ticker: str, n: int = 15
    ) -> tuple[list[OrderBookLevel], list[OrderBookLevel]]:
        """Get the top *n* bid and ask levels for a market ticker.

        Args:
            ticker: The market ticker symbol.
            n: Number of depth levels to return on each side (default 15).

        Returns:
            tuple[list[OrderBookLevel], list[OrderBookLevel]]: Tuple of
                `(bids, asks)` sorted best-first. Returns `([], [])` if
                the market is not tracked.
        """
        book = self.get_book(ticker)
        if book is None:
            return [], []
        return book.get_depth(n)

    def get_stale_tickers(self) -> list[str]:
        """Return a list of tickers whose order books are currently marked stale.

        Returns:
            list[str]: List of stale market ticker strings.
        """
        return [ticker for ticker, book in self._books.items() if book.is_stale]

    def remove_book(self, ticker: str) -> None:
        """Remove an order book from the manager.

        Args:
            ticker: The market ticker symbol to remove.
        """
        self._books.pop(ticker, None)

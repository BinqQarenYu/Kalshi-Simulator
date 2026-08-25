"""Pydantic v2 schemas for Kalshi WebSocket messages and internal state.

All monetary values use ``Decimal`` for exact binary-option pricing.
Timestamps are parsed into timezone-aware ``datetime`` objects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Timeframe(str, Enum):
    """Supported simulation timeframes."""
    FIVE_MIN = "5m"
    FIFTEEN_MIN = "15m"
    ONE_HOUR = "1h"
    DAILY = "daily"


class MarketStatus(str, Enum):
    OPEN = "open"
    UNOPENED = "unopened"
    CLOSED = "closed"
    SETTLED = "settled"


# ---------------------------------------------------------------------------
# REST — Market Discovery
# ---------------------------------------------------------------------------

class MarketInfo(BaseModel):
    """Parsed market metadata from ``GET /trade-api/v2/markets``."""
    ticker: str
    event_ticker: str
    series_ticker: str
    title: str = ""
    subtitle: str = ""
    status: MarketStatus
    open_time: datetime | None = None
    close_time: datetime | None = None
    latest_expiration_time: datetime | None = None
    yes_bid: Decimal | None = None
    yes_ask: Decimal | None = None
    no_bid: Decimal | None = None
    no_ask: Decimal | None = None
    last_price: Decimal | None = None
    volume: Decimal | None = None
    volume_24h: Decimal | None = None
    open_interest: Decimal | None = None
    floor_strike: Decimal | None = None
    cap_strike: Decimal | None = None
    strike_type: str | None = None

    model_config = {"extra": "ignore"}


# ---------------------------------------------------------------------------
# WebSocket — Order Book
# ---------------------------------------------------------------------------

class OrderBookLevel(BaseModel):
    """Single price level in the L2 book."""
    price: Decimal
    quantity: Decimal


class OrderBookSnapshot(BaseModel):
    """Initial full-depth snapshot from ``orderbook_snapshot`` message."""
    market_ticker: str
    market_id: str = ""
    seq: int
    yes_levels: list[OrderBookLevel] = Field(default_factory=list)
    no_levels: list[OrderBookLevel] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_ws(cls, msg: dict, seq: int) -> OrderBookSnapshot:
        """Parse from raw WebSocket ``msg`` payload."""
        yes_raw = msg.get("yes_dollars_fp", [])
        no_raw = msg.get("no_dollars_fp", [])
        return cls(
            market_ticker=msg["market_ticker"],
            market_id=msg.get("market_id", ""),
            seq=seq,
            yes_levels=[
                OrderBookLevel(price=Decimal(p), quantity=Decimal(q))
                for p, q in yes_raw
            ],
            no_levels=[
                OrderBookLevel(price=Decimal(p), quantity=Decimal(q))
                for p, q in no_raw
            ],
        )


class OrderBookDelta(BaseModel):
    """Incremental L2 update from ``orderbook_delta`` message."""
    market_ticker: str
    market_id: str = ""
    seq: int
    side: Literal["yes", "no"]
    price: Decimal
    delta: Decimal
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_ws(cls, msg: dict, seq: int) -> OrderBookDelta:
        """Parse from raw WebSocket ``msg`` payload."""
        ts = msg.get("ts_ms")
        if ts is not None:
            parsed_ts = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
        else:
            parsed_ts = datetime.now(timezone.utc)
        return cls(
            market_ticker=msg["market_ticker"],
            market_id=msg.get("market_id", ""),
            seq=seq,
            side=msg["side"],
            price=Decimal(msg["price_dollars"]),
            delta=Decimal(msg["delta_fp"]),
            timestamp=parsed_ts,
        )


# ---------------------------------------------------------------------------
# WebSocket — Ticker
# ---------------------------------------------------------------------------

class TickerUpdate(BaseModel):
    """Top-of-book + volume snapshot from ``ticker`` channel."""
    market_ticker: str
    yes_bid: Decimal | None = None
    yes_ask: Decimal | None = None
    yes_bid_size: Decimal | None = None
    yes_ask_size: Decimal | None = None
    last_price: Decimal | None = None
    volume: Decimal | None = None
    open_interest: Decimal | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_ws(cls, msg: dict) -> TickerUpdate:
        ts = msg.get("ts_ms")
        if ts is not None:
            parsed_ts = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
        else:
            parsed_ts = datetime.now(timezone.utc)

        def _dec(key: str) -> Decimal | None:
            v = msg.get(key)
            return Decimal(v) if v is not None else None

        return cls(
            market_ticker=msg["market_ticker"],
            yes_bid=_dec("yes_bid_dollars"),
            yes_ask=_dec("yes_ask_dollars"),
            yes_bid_size=_dec("yes_bid_size_fp"),
            yes_ask_size=_dec("yes_ask_size_fp"),
            last_price=_dec("price_dollars"),
            volume=_dec("volume_fp"),
            open_interest=_dec("open_interest_fp"),
            timestamp=parsed_ts,
        )


# ---------------------------------------------------------------------------
# WebSocket — Trade
# ---------------------------------------------------------------------------

class TradeEvent(BaseModel):
    """Public fill from ``trade`` channel."""
    trade_id: str
    market_ticker: str
    yes_price: Decimal
    no_price: Decimal
    count: Decimal
    taker_side: Literal["yes", "no"]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_ws(cls, msg: dict) -> TradeEvent:
        ts = msg.get("ts_ms")
        if ts is not None:
            parsed_ts = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
        else:
            parsed_ts = datetime.now(timezone.utc)
        return cls(
            trade_id=msg["trade_id"],
            market_ticker=msg["market_ticker"],
            yes_price=Decimal(msg["yes_price_dollars"]),
            no_price=Decimal(msg["no_price_dollars"]),
            count=Decimal(msg["count_fp"]),
            taker_side=msg["taker_side"],
            timestamp=parsed_ts,
        )


# ---------------------------------------------------------------------------
# Internal — Reconstructed L2 Book State
# ---------------------------------------------------------------------------

class L2BookState:
    """In-memory reconstructed L2 order book for a single market.

    Not a Pydantic model — mutable state optimised for fast updates.
    """

    __slots__ = (
        "market_ticker",
        "last_seq",
        "yes_book",
        "no_book",
        "last_update",
        "_stale",
    )

    def __init__(self, market_ticker: str) -> None:
        self.market_ticker = market_ticker
        self.last_seq: int = -1
        self.yes_book: dict[Decimal, Decimal] = {}  # price → qty
        self.no_book: dict[Decimal, Decimal] = {}
        self.last_update: datetime = datetime.now(timezone.utc)
        self._stale: bool = True

    # -- Properties ----------------------------------------------------------

    @property
    def best_yes_bid(self) -> Decimal | None:
        if not self.yes_book:
            return None
        return max(self.yes_book.keys())

    @property
    def best_no_bid(self) -> Decimal | None:
        if not self.no_book:
            return None
        return max(self.no_book.keys())

    @property
    def best_yes_ask(self) -> Decimal | None:
        """In a binary market, yes ask = 1 - best_no_bid."""
        nb = self.best_no_bid
        if nb is None:
            return None
        return Decimal("1") - nb

    @property
    def spread(self) -> Decimal | None:
        bid = self.best_yes_bid
        ask = self.best_yes_ask
        if bid is None or ask is None:
            return None
        return ask - bid

    @property
    def mid_price(self) -> Decimal | None:
        bid = self.best_yes_bid
        ask = self.best_yes_ask
        if bid is None or ask is None:
            return None
        return (bid + ask) / 2

    @property
    def is_stale(self) -> bool:
        return self._stale

    # -- Depth ---------------------------------------------------------------

    def get_depth(self, n: int = 15) -> tuple[list[OrderBookLevel], list[OrderBookLevel]]:
        """Return top *n* bid and ask levels, sorted best-first."""
        bids = sorted(
            (OrderBookLevel(price=p, quantity=q) for p, q in self.yes_book.items()),
            key=lambda lv: lv.price,
            reverse=True,
        )[:n]
        asks = sorted(
            (OrderBookLevel(price=p, quantity=q) for p, q in self.no_book.items()),
            key=lambda lv: lv.price,
            reverse=True,
        )[:n]
        return bids, asks


# ---------------------------------------------------------------------------
# Simulation — Enums
# ---------------------------------------------------------------------------

class OrderSide(str, Enum):
    """Side of a binary-option order."""
    YES = "yes"
    NO = "no"


class OrderType(str, Enum):
    """Virtual order type."""
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    """Lifecycle state of a simulated order."""
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Simulation — Orders & Fills
# ---------------------------------------------------------------------------

class SimulatedOrder(BaseModel):
    """A virtual order submitted by the simulation engine."""
    order_id: str
    ticker: str
    side: OrderSide
    order_type: OrderType
    size: int
    limit_price: Decimal | None = None
    timeframe: Timeframe
    reasoning: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: OrderStatus = OrderStatus.PENDING


class SimulatedFill(BaseModel):
    """Execution report for a simulated fill."""
    order_id: str
    ticker: str
    side: OrderSide
    size: int
    fill_price: Decimal
    slippage: Decimal = Decimal("0")
    cost: Decimal
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Simulation — Positions & P&L
# ---------------------------------------------------------------------------

class Position(BaseModel):
    """An open virtual position in a single market."""
    ticker: str
    side: OrderSide
    size: int
    avg_entry_price: Decimal
    current_price: Decimal | None = None
    unrealized_pnl: Decimal = Decimal("0")
    timeframe: Timeframe

    model_config = {"extra": "ignore"}


class SettlementResult(BaseModel):
    """Outcome of a settled binary-option position."""
    ticker: str
    side: OrderSide
    size: int
    entry_price: Decimal
    settlement_price: Decimal
    outcome: Literal["win", "loss"]
    pnl: Decimal
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PnLSnapshot(BaseModel):
    """Point-in-time portfolio performance summary."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    starting_balance: Decimal = Decimal("10000")
    current_balance: Decimal = Decimal("10000")
    total_realized_pnl: Decimal = Decimal("0")
    total_unrealized_pnl: Decimal = Decimal("0")
    total_equity: Decimal = Decimal("10000")
    open_positions: int = 0
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: Decimal | None = None

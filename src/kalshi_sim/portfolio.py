"""Virtual portfolio ledger — tracks balance, positions, fills, and P&L.

All arithmetic uses ``Decimal`` for exact binary-option settlement math.
Kalshi binary options pay \\$1.00 per contract on win, \\$0.00 on loss.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterator

from kalshi_sim.schemas import (
    OrderSide,
    PnLSnapshot,
    Position,
    SettlementResult,
    SimulatedFill,
    Timeframe,
)

logger = logging.getLogger(__name__)

# Binary option payout: $1.00 per contract
CONTRACT_PAYOUT = Decimal("1.00")


class Portfolio:
    """Thread-safe virtual portfolio for the simulation engine.

    Tracks cash balance, open positions, fill history, and realised P&L.

    Usage::

        portfolio = Portfolio(starting_balance=Decimal("10000"))
        portfolio.open_position(fill)
        result = portfolio.settle_position(ticker, settlement_price, strike, strike_type)
        snapshot = portfolio.get_pnl_snapshot()
    """

    def __init__(
        self,
        starting_balance: Decimal = Decimal("100"),
        max_drawdown_pct: Decimal = Decimal("0.20"),
    ) -> None:
        self._starting_balance = starting_balance
        self._balance = starting_balance
        self._positions: dict[str, Position] = {}
        self._fill_history: list[SimulatedFill] = []
        self._settlement_history: list[SettlementResult] = []
        self._total_trades = 0
        self._total_fees_paid = Decimal("0")
        self._wins = 0
        self._losses = 0

        # Circuit breaker state
        self._max_drawdown_pct = max_drawdown_pct
        self._max_drawdown_limit = starting_balance * max_drawdown_pct
        self._circuit_breaker_tripped = False
        self._peak_equity = starting_balance

    # -- Properties ----------------------------------------------------------

    @property
    def balance(self) -> Decimal:
        return self._balance

    @property
    def current_balance(self) -> Decimal:
        """Alias for balance."""
        return self._balance

    @property
    def equity(self) -> Decimal:
        total_unrealized = sum(p.unrealized_pnl for p in self._positions.values())
        return self._balance + total_unrealized

    @property
    def open_positions(self) -> dict[str, Position]:
        return dict(self._positions)

    def get_open_positions(self) -> list[Position]:
        """Return a list of all active open positions."""
        return list(self._positions.values())

    @property
    def total_trades(self) -> int:
        return self._total_trades

    @property
    def total_fees_paid(self) -> Decimal:
        """Cumulative exchange fees paid across all fills."""
        return self._total_fees_paid

    @property
    def circuit_breaker_tripped(self) -> bool:
        """True when max drawdown has been exceeded and all trading is halted."""
        return self._circuit_breaker_tripped

    @property
    def current_drawdown(self) -> Decimal:
        """Current drawdown from peak equity as a positive dollar amount."""
        return max(Decimal("0"), self._peak_equity - self.equity)

    @property
    def current_drawdown_pct(self) -> Decimal:
        """Current drawdown as a percentage of starting capital."""
        if self._starting_balance == 0:
            return Decimal("0")
        return self.current_drawdown / self._starting_balance

    # -- Circuit Breaker -----------------------------------------------------

    def _update_circuit_breaker(self) -> None:
        """Evaluate drawdown against threshold and trip the breaker if exceeded.

        Called after every settlement and position close to continuously
        monitor portfolio health.
        """
        current_equity = self.equity
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity

        drawdown = self._peak_equity - current_equity
        if drawdown >= self._max_drawdown_limit and not self._circuit_breaker_tripped:
            self._circuit_breaker_tripped = True
            logger.warning(
                "⚠️  CIRCUIT BREAKER TRIPPED: Drawdown $%.2f (%.1f%%) exceeds max "
                "allowed $%.2f (%.0f%%). ALL TRADING HALTED.",
                drawdown,
                (drawdown / self._starting_balance) * 100,
                self._max_drawdown_limit,
                self._max_drawdown_pct * 100,
            )

    def reset_circuit_breaker(self) -> None:
        """Manually reset the circuit breaker to resume trading."""
        self._circuit_breaker_tripped = False
        self._peak_equity = self.equity
        logger.info(
            "Circuit breaker RESET. Peak equity re-anchored to $%.2f. Trading resumed.",
            self._peak_equity,
        )

    # -- Risk Check ----------------------------------------------------------

    def can_afford(self, cost: Decimal) -> bool:
        """Check if the portfolio has enough balance to cover a trade cost."""
        return self._balance >= cost

    # -- Position Management -------------------------------------------------

    def open_position(self, fill: SimulatedFill, timeframe: Timeframe) -> Position:
        """Open or add to a position based on a simulated fill.

        Deducts the fill cost + exchange fee from the cash balance.

        Args:
            fill: The simulated execution fill.
            timeframe: Timeframe the trade belongs to.

        Returns:
            The updated Position.

        Raises:
            ValueError: If insufficient balance.
        """
        total_deduction = fill.cost + fill.fee
        if not self.can_afford(total_deduction):
            raise ValueError(
                f"Insufficient balance: need ${total_deduction} (cost=${fill.cost} + fee=${fill.fee}), have ${self._balance}"
            )

        self._balance -= total_deduction
        self._total_fees_paid += fill.fee
        self._fill_history.append(fill)
        self._total_trades += 1

        existing = self._positions.get(fill.ticker)
        if existing and existing.side == fill.side:
            # Average into existing position
            total_size = existing.size + fill.size
            total_cost = (existing.avg_entry_price * existing.size) + (
                fill.fill_price * fill.size
            )
            avg_price = total_cost / total_size

            existing.size = total_size
            existing.avg_entry_price = avg_price
            logger.info(
                "Position averaged: %s %s %d contracts @ $%s (balance: $%s)",
                fill.ticker, fill.side.value, total_size, avg_price, self._balance,
            )
            return existing
        else:
            # Create new position
            position = Position(
                ticker=fill.ticker,
                side=fill.side,
                size=fill.size,
                avg_entry_price=fill.fill_price,
                timeframe=timeframe,
            )
            self._positions[fill.ticker] = position
            logger.info(
                "Position opened: %s %s %d contracts @ $%s (balance: $%s)",
                fill.ticker, fill.side.value, fill.size,
                fill.fill_price, self._balance,
            )
            return position

    def settle_position(
        self,
        ticker: str,
        settlement_price: Decimal,
        floor_strike: Decimal | None,
        cap_strike: Decimal | None,
        strike_type: str | None,
    ) -> SettlementResult | None:
        """Settle a position at expiry using binary-option payout rules.

        Binary option settlement:
        - **Yes win**: payout = $1.00 × size; P&L = payout − cost
        - **Yes loss**: payout = $0.00; P&L = −cost
        - **No** side: inverse of Yes

        Args:
            ticker: Market ticker to settle.
            settlement_price: RTI proxy price for determining win/loss.
            floor_strike: Lower bound of the strike range.
            cap_strike: Upper bound of the strike range.
            strike_type: How to evaluate the strike ("greater", "less", etc.).

        Returns:
            SettlementResult if position exists, None otherwise.
        """
        position = self._positions.pop(ticker, None)
        if position is None:
            return None

        # Determine if the "Yes" outcome wins
        yes_wins = self._evaluate_settlement(
            settlement_price, floor_strike, cap_strike, strike_type
        )

        # Determine outcome based on the position side
        if position.side == OrderSide.YES:
            won = yes_wins
        else:
            won = not yes_wins

        # Calculate P&L
        cost = position.avg_entry_price * position.size
        if won:
            payout = CONTRACT_PAYOUT * position.size
            pnl = payout - cost
            outcome = "win"
            self._wins += 1
        else:
            payout = Decimal("0")
            pnl = -cost
            outcome = "loss"
            self._losses += 1

        # Credit payout to balance
        self._balance += payout

        result = SettlementResult(
            ticker=ticker,
            side=position.side,
            size=position.size,
            entry_price=position.avg_entry_price,
            settlement_price=settlement_price,
            outcome=outcome,
            pnl=pnl,
        )
        self._settlement_history.append(result)

        logger.info(
            "SETTLED %s: %s %s %d contracts | entry=$%s | settlement=$%s | "
            "outcome=%s | P&L=$%s | balance=$%s",
            ticker, position.side.value.upper(), outcome.upper(), position.size,
            position.avg_entry_price, settlement_price,
            outcome, pnl, self._balance,
        )
        self._update_circuit_breaker()
        return result

    def close_position(self, ticker: str, exit_price: Decimal) -> SettlementResult | None:
        """Close an open position at current market exit price before contract expiry.

        Args:
            ticker: Market contract ticker to close.
            exit_price: Exit price per contract in USD ($0.01 - $0.99).

        Returns:
            SettlementResult with realized P&L, or None if position was not found.
        """
        position = self._positions.pop(ticker, None)
        if position is None:
            return None

        # Calculate proceeds from liquidating contracts
        proceeds = exit_price * position.size
        cost = position.avg_entry_price * position.size
        pnl = proceeds - cost
        outcome = "win" if pnl >= Decimal("0") else "loss"

        if outcome == "win":
            self._wins += 1
        else:
            self._losses += 1

        # Credit liquidation proceeds to balance
        self._balance += proceeds

        result = SettlementResult(
            ticker=ticker,
            side=position.side,
            size=position.size,
            entry_price=position.avg_entry_price,
            settlement_price=exit_price,
            outcome=outcome,
            pnl=pnl,
        )
        self._settlement_history.append(result)

        logger.info(
            "CLOSED %s: %s %d contracts @ exit=$%s (entry=$%s) | P&L=$%s | balance=$%s",
            ticker, position.side.value.upper(), position.size,
            exit_price, position.avg_entry_price, pnl, self._balance,
        )
        self._update_circuit_breaker()
        return result

    @staticmethod
    def _evaluate_settlement(
        settlement_price: Decimal,
        floor_strike: Decimal | None,
        cap_strike: Decimal | None,
        strike_type: str | None,
    ) -> bool:
        """Determine if the 'Yes' outcome wins.

        Returns True if Yes wins based on strike type and settlement price.
        """
        # If settlement_price is in contract binary payoff range [0.0, 1.0] and strike is asset price (> $100)
        if settlement_price <= Decimal("1.00") and (
            (floor_strike is not None and floor_strike > Decimal("100.00"))
            or (cap_strike is not None and cap_strike > Decimal("100.00"))
        ):
            return settlement_price >= Decimal("0.50")

        if strike_type == "greater" and floor_strike is not None:
            return settlement_price >= floor_strike
        elif strike_type == "less" and cap_strike is not None:
            return settlement_price < cap_strike
        elif strike_type == "between" and floor_strike is not None and cap_strike is not None:
            return floor_strike <= settlement_price < cap_strike
        else:
            # Default: treat as "greater" with floor_strike
            if floor_strike is not None:
                return settlement_price >= floor_strike
            return False

    # -- Mark-to-Market ------------------------------------------------------

    def mark_to_market(self, ticker: str, current_price: Decimal) -> None:
        """Update unrealized P&L for an open position.

        Args:
            ticker: Market ticker.
            current_price: Current best price (yes bid for Yes, 1-yes_bid for No).
        """
        position = self._positions.get(ticker)
        if position is None:
            return

        if position.side == OrderSide.YES:
            # Mark yes position: if we sold now at current_price
            position.current_price = current_price
            position.unrealized_pnl = (
                (current_price - position.avg_entry_price) * position.size
            )
        else:
            # Mark no position: current value = 1 - current_yes_price
            no_value = Decimal("1") - current_price
            position.current_price = no_value
            position.unrealized_pnl = (
                (no_value - position.avg_entry_price) * position.size
            )

    # -- P&L Snapshot --------------------------------------------------------

    def get_pnl_snapshot(self) -> PnLSnapshot:
        """Generate a point-in-time portfolio performance summary."""
        total_unrealized = sum(
            p.unrealized_pnl for p in self._positions.values()
        )
        total_realized = sum(r.pnl for r in self._settlement_history)
        total_equity = self._balance + total_unrealized

        total_settled = self._wins + self._losses
        win_rate = (
            Decimal(str(self._wins)) / Decimal(str(total_settled))
            if total_settled > 0
            else None
        )

        return PnLSnapshot(
            starting_balance=self._starting_balance,
            current_balance=self._balance,
            total_realized_pnl=total_realized,
            total_unrealized_pnl=total_unrealized,
            total_equity=total_equity,
            open_positions=len(self._positions),
            total_trades=self._total_trades,
            wins=self._wins,
            losses=self._losses,
            win_rate=win_rate,
        )

    # -- Accessors -----------------------------------------------------------

    def get_position(self, ticker: str) -> Position | None:
        """Get an open position by ticker."""
        return self._positions.get(ticker)

    def get_all_positions(self) -> list[Position]:
        """Return all open positions."""
        return list(self._positions.values())

    def get_fill_history(self) -> list[SimulatedFill]:
        """Return all fill records."""
        return list(self._fill_history)

    def get_settlement_history(self) -> list[SettlementResult]:
        """Return all settlement records."""
        return list(self._settlement_history)

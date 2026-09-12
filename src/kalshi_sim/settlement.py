"""CF Benchmarks RTI settlement mock for expired Kalshi BTC contracts.

Evaluates open positions against market expiration times and determines
binary-option win/loss payouts based on proxy index prices.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from kalshi_sim.portfolio import Portfolio
from kalshi_sim.schemas import MarketInfo, OrderSide, Position, SettlementResult, TickerUpdate

logger = logging.getLogger(__name__)


def check_expirations(
    positions: dict[str, Position],
    markets: dict[str, MarketInfo],
    current_time: datetime,
) -> list[str]:
    """Check open positions for expired markets.

    Iterates over all open positions, looks up corresponding market metadata,
    and identifies markets whose close time or latest expiration time has passed.

    Args:
        positions: Dictionary mapping market tickers to open Positions.
        markets: Dictionary mapping market tickers to MarketInfo metadata.
        current_time: Reference datetime to compare expiration timestamps against.

    Returns:
        Deduplicated list of expired market tickers.
    """
    expired: list[str] = []
    seen: set[str] = set()

    for ticker in positions:
        market = markets.get(ticker)
        if market is None:
            # Fallback: check if the ticker timestamp itself indicates it has expired
            try:
                parts = ticker.split("-")
                if len(parts) >= 2:
                    ts_part = parts[1][:11]  # e.g., 26SEP091745
                    dt = datetime.strptime(ts_part, "%y%b%d%H%M").replace(tzinfo=timezone.utc)
                    if current_time >= dt:
                        if ticker not in seen:
                            seen.add(ticker)
                            expired.append(ticker)
            except Exception:
                pass
            continue

        is_expired = False
        if market.close_time is not None and current_time >= market.close_time:
            is_expired = True
        elif (
            market.latest_expiration_time is not None
            and current_time >= market.latest_expiration_time
        ):
            is_expired = True
        elif (
            hasattr(market, "expiration_time")
            and market.expiration_time is not None
            and current_time >= market.expiration_time
        ):
            is_expired = True

        if is_expired and ticker not in seen:
            seen.add(ticker)
            expired.append(ticker)

    return expired


def settle_position(
    portfolio: Portfolio,
    ticker: str,
    market_info: MarketInfo,
    last_ticker_update: TickerUpdate | None,
    btc_settle_price: Decimal | None = None,
) -> SettlementResult | None:
    """Settle an individual position using CF Benchmarks RTI proxy price or live Spot index.

    Args:
        portfolio: Virtual portfolio managing open positions and balance.
        ticker: Market ticker to settle.
        market_info: Market metadata containing strike thresholds and type.
        last_ticker_update: Most recent TickerUpdate for the market, or None.
        btc_settle_price: Optional real-time BTC Spot index price at settlement.

    Returns:
        SettlementResult if settlement succeeded, or None if price data was missing
        or position could not be settled.
    """
    if btc_settle_price is not None and btc_settle_price > Decimal("100.00"):
        settlement_price = btc_settle_price
    elif (
        last_ticker_update is not None
        and last_ticker_update.last_price is not None
        and last_ticker_update.last_price > Decimal("100.00")
    ):
        settlement_price = last_ticker_update.last_price
    else:
        logger.warning(
            "Cannot settle position %s: invalid or missing underlying Bitcoin Spot index price (got %s)",
            ticker,
            btc_settle_price or (last_ticker_update.last_price if last_ticker_update else None),
        )
        return None

    floor_strike = market_info.floor_strike if market_info.floor_strike is not None else market_info.target_strike
    result = portfolio.settle_position(
        ticker=ticker,
        settlement_price=settlement_price,
        floor_strike=floor_strike,
        cap_strike=market_info.cap_strike,
        strike_type=market_info.strike_type or "greater",
    )
    return result


def run_settlement_cycle(
    portfolio: Portfolio,
    market_cache: dict[str, MarketInfo],
    ticker_cache: dict[str, TickerUpdate],
) -> list[SettlementResult]:
    """Execute a full settlement cycle over all open positions.

    Identifies expired positions relative to current UTC time, settles each
    using cached market info and ticker prices, and logs a cycle summary.

    Args:
        portfolio: Virtual portfolio ledger.
        market_cache: Dictionary mapping tickers to MarketInfo.
        ticker_cache: Dictionary mapping tickers to latest TickerUpdate.

    Returns:
        List of SettlementResult objects for all positions settled in this cycle.
    """
    now = datetime.now(timezone.utc)
    expired_tickers = check_expirations(portfolio.open_positions, market_cache, now)

    results: list[SettlementResult] = []
    for ticker in expired_tickers:
        market_info = market_cache.get(ticker)
        if market_info is None:
            logger.warning(
                "Expired ticker %s not found in market cache", ticker
            )
            continue

        last_ticker_update = ticker_cache.get(ticker)
        res = settle_position(portfolio, ticker, market_info, last_ticker_update)
        if res is not None:
            results.append(res)

    logger.info("Settled %d positions in cycle", len(results))
    return results


def evaluate_twap_settlement(
    target_strike: Decimal,
    twap_60s: Decimal,
    strike_type: str = "greater",
) -> bool:
    """Evaluate whether YES won based on official 60s TWAP settlement parity.

    Args:
        target_strike: Contract strike price.
        twap_60s: CME CF Benchmarks 60-second trailing TWAP index price.
        strike_type: 'greater' (default) or 'less'.

    Returns:
        True if YES outcome won, False if NO won.
    """
    if strike_type == "less":
        return twap_60s <= target_strike
    return twap_60s >= target_strike


def calculate_twap_pnl(
    side: OrderSide | str,
    entry_price: Decimal,
    contracts: int,
    target_strike: Decimal,
    twap_60s: Decimal,
    fee: Decimal = Decimal("0.00"),
    strike_type: str = "greater",
) -> tuple[str, Decimal, Decimal]:
    """Calculate exact settlement outcome, gross PnL, and net PnL using 60s TWAP parity.

    All math is evaluated in strict Decimal arithmetic (zero IEEE 754 float drift).

    Args:
        side: Position side ('YES' or 'NO').
        entry_price: Average entry fill price ($0.01 - $0.99).
        contracts: Number of contracts (positive int).
        target_strike: Contract strike to beat.
        twap_60s: Trailing 60s settlement TWAP.
        fee: Total transaction fee paid on entry.
        strike_type: 'greater' or 'less'.

    Returns:
        Tuple of (outcome ("WIN" | "LOSS"), gross_pnl, net_pnl).
    """
    yes_won = evaluate_twap_settlement(target_strike, twap_60s, strike_type)
    side_str = side.value.upper() if isinstance(side, OrderSide) else str(side).upper()
    is_win = (side_str == "YES" and yes_won) or (side_str == "NO" and not yes_won)

    c_dec = Decimal(str(contracts))
    if is_win:
        gross_pnl = (Decimal("1.00") - entry_price) * c_dec
        net_pnl = gross_pnl - fee
        return "WIN", gross_pnl, net_pnl
    else:
        gross_pnl = -entry_price * c_dec
        net_pnl = gross_pnl
        return "LOSS", gross_pnl, net_pnl

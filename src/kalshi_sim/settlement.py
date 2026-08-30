"""CF Benchmarks RTI settlement mock for expired Kalshi BTC contracts.

Evaluates open positions against market expiration times and determines
binary-option win/loss payouts based on proxy index prices.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from kalshi_sim.portfolio import Portfolio
from kalshi_sim.schemas import MarketInfo, Position, SettlementResult, TickerUpdate

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
            continue

        is_expired = False
        if market.close_time is not None and current_time >= market.close_time:
            is_expired = True
        elif (
            market.latest_expiration_time is not None
            and current_time >= market.latest_expiration_time
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
    if btc_settle_price is not None:
        settlement_price = btc_settle_price
    elif last_ticker_update is not None and last_ticker_update.last_price is not None:
        settlement_price = last_ticker_update.last_price
    else:
        logger.warning(
            "Cannot settle position %s: missing ticker update, price or spot index",
            ticker,
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

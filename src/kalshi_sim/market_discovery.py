"""Market discovery module for discovering active BTC markets on Kalshi Demo REST API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import aiohttp

import os
from kalshi_sim.auth import DEMO_REST_BASE, PROD_REST_BASE, get_auth_headers
from kalshi_sim.schemas import MarketInfo, MarketStatus, Timeframe

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

logger = logging.getLogger(__name__)

# Module-level constant mapping timeframes to series tickers
TIMEFRAME_SERIES: dict[Timeframe, list[str]] = {
    Timeframe.FIVE_MIN: ["KXBTC15M"],  # no native 5m; use 15m + local windowing
    Timeframe.FIFTEEN_MIN: ["KXBTC15M"],
    Timeframe.ONE_HOUR: ["KXBTCH"],
    Timeframe.DAILY: ["KXBTCD"],
}


async def discover_btc_markets(
    session: aiohttp.ClientSession,
    api_key_id: str,
    private_key: RSAPrivateKey,
    timeframes: list[Timeframe],
    rest_base: str | None = None,
) -> dict[Timeframe, list[MarketInfo]]:
    """Discover open BTC markets across the specified timeframes via Kalshi REST API."""
    if rest_base is None:
        env = os.getenv("KALSHI_ENV", "live").lower()
        rest_base = PROD_REST_BASE if env in ("prod", "live") else DEMO_REST_BASE

    discovered: dict[Timeframe, list[MarketInfo]] = {tf: [] for tf in timeframes}
    endpoint_path = "/trade-api/v2/markets"
    url = f"{rest_base}/markets"

    for tf in timeframes:
        series_tickers = TIMEFRAME_SERIES.get(tf, [])
        tf_markets: list[MarketInfo] = []
        seen_tickers: set[str] = set()

        for series in series_tickers:
            cursor: str | None = None
            logger.info("Discovering markets for timeframe %s, series %s", tf.value, series)

            while True:
                params: dict[str, Any] = {
                    "series_ticker": series,
                    "status": MarketStatus.OPEN.value,
                    "limit": 100,
                }
                if cursor:
                    params["cursor"] = cursor

                try:
                    headers = get_auth_headers(
                        api_key_id=api_key_id,
                        private_key=private_key,
                        method="GET",
                        path=endpoint_path,
                    )
                    async with session.get(
                        url,
                        params=params,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=4.0),
                    ) as resp:

                        if resp.status != 200:
                            text = await resp.text()
                            logger.error(
                                "HTTP error querying markets for series %s (status %d): %s",
                                series,
                                resp.status,
                                text,
                            )
                            break

                        data = await resp.json()
                except Exception as exc:
                    logger.error(
                        "Network or parsing error querying markets for series %s: %s",
                        series,
                        exc,
                        exc_info=True,
                    )
                    break

                if not isinstance(data, dict):
                    logger.warning("Unexpected response format from %s: %s", url, type(data))
                    break

                raw_markets = data.get("markets", [])
                for raw_market in raw_markets:
                    try:
                        if isinstance(raw_market, dict) and not raw_market.get("series_ticker"):
                            raw_market["series_ticker"] = series
                        market_info = MarketInfo.model_validate(raw_market)
                        if market_info.ticker not in seen_tickers:
                            seen_tickers.add(market_info.ticker)
                            tf_markets.append(market_info)
                    except Exception as exc:
                        logger.warning(
                            "Failed to parse MarketInfo object: %s (error: %s)",
                            raw_market,
                            exc,
                        )

                cursor = data.get("cursor")
                if not cursor:
                    break

        discovered[tf] = tf_markets
        logger.info("Discovered %d markets for timeframe %s", len(tf_markets), tf.value)

    return discovered


def get_all_tickers(
    markets: dict[Timeframe, list[MarketInfo]],
    max_total: int = 35,
) -> list[str]:
    """Flatten discovered markets into a prioritized list of active tickers.

    Prioritizes high-frequency 15M, 5M, and 1H contracts, plus nearest ATM strikes,
    preventing massive snapshot floods and WebSocket sequence congestion on connect.

    Args:
        markets: Dictionary mapping timeframes to lists of MarketInfo instances.
        max_total: Maximum number of active markets to return (default 35).

    Returns:
        list[str]: Prioritized, deduplicated list of market ticker strings.
    """
    seen: set[str] = set()
    tickers: list[str] = []

    # 1. First pass: prioritize 15M, 5M, 1H contracts
    for tf in (Timeframe.FIFTEEN_MIN, Timeframe.FIVE_MIN, Timeframe.ONE_HOUR):
        market_list = markets.get(tf, [])
        for m in market_list:
            if m.ticker not in seen:
                seen.add(m.ticker)
                tickers.append(m.ticker)

    # 2. Second pass: remaining daily/other markets up to max_total
    for tf, market_list in markets.items():
        if tf in (Timeframe.FIFTEEN_MIN, Timeframe.FIVE_MIN, Timeframe.ONE_HOUR):
            continue
        for m in market_list:
            if len(tickers) >= max_total:
                break
            if m.ticker not in seen:
                seen.add(m.ticker)
                tickers.append(m.ticker)

    return tickers


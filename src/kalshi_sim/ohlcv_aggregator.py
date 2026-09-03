"""Rolling Multi-Timeframe OHLCV Candlestick Aggregator.

Processes live price ticks and trade events into standardized candlestick bars
(1m, 5m, 15m, 1h) for spot BTC and Kalshi binary contract mid-prices.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from decimal import Decimal
from typing import Deque, Dict, List, Optional, Union

from kalshi_sim.schemas import CandleInterval, OHLCVCandle

logger = logging.getLogger(__name__)

# Interval durations in seconds
INTERVAL_SECONDS: dict[CandleInterval, int] = {
    CandleInterval.ONE_MIN: 60,
    CandleInterval.FIVE_MIN: 300,
    CandleInterval.FIFTEEN_MIN: 900,
    CandleInterval.ONE_HOUR: 3600,
}


class OHLCVAggregator:
    """In-memory rolling multi-timeframe OHLCV bar aggregator.

    Usage::

        aggregator = OHLCVAggregator(max_bars=500)
        aggregator.add_tick("BTC", Decimal("78500.50"), volume=Decimal("1.5"))
        bars = aggregator.get_candles("BTC", interval=CandleInterval.ONE_MIN, limit=50)
    """

    def __init__(self, max_bars: int = 500) -> None:
        """Initialize the OHLCV Aggregator.

        Args:
            max_bars: Maximum rolling bars to retain per (symbol, interval) series.
        """
        self.max_bars = max_bars
        # Storage: candles[symbol][interval] -> Deque[OHLCVCandle]
        self._series: dict[str, dict[CandleInterval, Deque[OHLCVCandle]]] = defaultdict(
            lambda: {
                interval: deque(maxlen=max_bars)
                for interval in CandleInterval
            }
        )

    def add_tick(
        self,
        symbol: str,
        price: Union[Decimal, float, int],
        volume: Union[Decimal, float, int] = Decimal("0"),
        timestamp: Optional[Union[datetime, int, float]] = None,
    ) -> None:
        """Ingest a price tick and update all timeframe candlestick series for the symbol.

        Args:
            symbol: Identifier (e.g. "BTC" or Kalshi market ticker).
            price: Current price level.
            volume: Traded volume or contract quantity.
            timestamp: Event time as datetime or UNIX epoch seconds. Defaults to now UTC.
        """
        if price is None:
            return

        # Performance Optimization: Avoid string conversion when price or volume is already Decimal
        price_dec = price if isinstance(price, Decimal) else Decimal(str(price))
        if isinstance(volume, Decimal):
            vol_dec = volume
        elif volume is None:
            vol_dec = Decimal("0")
        else:
            vol_dec = Decimal(str(volume))

        # Determine UNIX epoch seconds
        if timestamp is None:
            ts_sec = int(time.time())
        elif isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            ts_sec = int(timestamp.timestamp())
        else:
            ts_sec = int(timestamp)

        symbol_series = self._series[symbol]

        for interval, dur_sec in INTERVAL_SECONDS.items():
            bucket_ts = (ts_sec // dur_sec) * dur_sec
            series_deque = symbol_series[interval]

            if not series_deque or series_deque[-1].timestamp < bucket_ts:
                # Open a new candlestick bar
                new_candle = OHLCVCandle(
                    timestamp=bucket_ts,
                    open=price_dec,
                    high=price_dec,
                    low=price_dec,
                    close=price_dec,
                    volume=vol_dec,
                    trades_count=1,
                )
                series_deque.append(new_candle)
            elif series_deque[-1].timestamp == bucket_ts:
                # Update existing active candlestick bar
                active = series_deque[-1]
                active.high = max(active.high, price_dec)
                active.low = min(active.low, price_dec)
                active.close = price_dec
                active.volume += vol_dec
                active.trades_count += 1
            else:
                # Out-of-order historical backfill update
                for candle in reversed(series_deque):
                    if candle.timestamp == bucket_ts:
                        candle.high = max(candle.high, price_dec)
                        candle.low = min(candle.low, price_dec)
                        candle.close = price_dec
                        candle.volume += vol_dec
                        candle.trades_count += 1
                        break

    def get_candles(
        self,
        symbol: str,
        interval: Union[CandleInterval, str] = CandleInterval.ONE_MIN,
        limit: int = 100,
    ) -> List[OHLCVCandle]:
        """Retrieve the most recent historical candlestick bars for a symbol and interval.

        Args:
            symbol: Target market or asset symbol.
            interval: Candlestick resolution (1m, 5m, 15m, 1h).
            limit: Maximum count of recent bars to return.

        Returns:
            List of OHLCVCandle sorted in chronological order (oldest to newest).
        """
        if isinstance(interval, str):
            try:
                interval = CandleInterval(interval.lower())
            except ValueError:
                interval = CandleInterval.ONE_MIN

        series_deque = self._series.get(symbol, {}).get(interval)
        if not series_deque:
            return []

        limit = max(1, min(limit, self.max_bars))
        # Return slice of the newest `limit` candles in chronological order
        bars = list(series_deque)
        return bars[-limit:]

    def seed_synthetic_history(
        self,
        symbol: str,
        start_price: Decimal,
        bars_count: int = 60,
        volatility: float = 15.0,
    ) -> None:
        """Seed initial historical candles for immediate chart rendering on cold start.

        Args:
            symbol: Symbol to seed.
            start_price: Baseline starting price.
            bars_count: Number of 1-minute historical bars to generate.
            volatility: Random walk step standard deviation.
        """
        import random

        now = int(time.time())
        current = float(start_price)

        for i in range(bars_count, 0, -1):
            bar_time = now - (i * 60)
            # Create 4 synthetic ticks within the minute bar
            for step in range(4):
                current += random.gauss(0, volatility / 2.0)
                tick_time = bar_time + (step * 15)
                self.add_tick(
                    symbol=symbol,
                    price=round(current, 2),
                    volume=random.randint(1, 10),
                    timestamp=tick_time,
                )

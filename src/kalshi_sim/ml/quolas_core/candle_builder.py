"""Real-Time Candle Builder for QuoLas Microstructure & HMM Macro Regime Analysis.

Converts sub-millisecond raw Binance aggTrade ticks into OHLCV candles in real time.
Maintains rolling bounded windows of closed candles per symbol for instant feature extraction
without hitting external REST APIs.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    """A single OHLCV candle representing an aggregated time bucket."""

    timestamp: int  # Candle open time (epoch ms)
    open: float
    high: float
    low: float
    close: float
    volume: float  # Base asset volume (BTC)
    volume_usd: float  # Quote (USD) volume
    trade_count: int
    is_closed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert candle to dictionary format expected by HMMBrain."""
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "volume_usd": self.volume_usd,
            "trade_count": self.trade_count,
            "funding_rate": 0.0,
        }


class CandleBuilder:
    """Aggregates raw trade ticks into OHLCV candles in real-time.

    Usage:
        builder = CandleBuilder(interval_seconds=300, max_candles=500)  # 5-minute candles
        closed_candle = builder.process_tick("BTCUSDT", price=97500.0, quantity=0.5, timestamp_ms=...)
        candles = builder.get_candles("BTCUSDT", count=288)
    """

    def __init__(self, interval_seconds: int = 300, max_candles: int = 500) -> None:
        """Initialize CandleBuilder.

        Args:
            interval_seconds: Candle duration in seconds (60=1m, 300=5m).
            max_candles: Maximum closed candles retained per symbol.
        """
        self.interval_ms = int(interval_seconds * 1000)
        self.max_candles = max_candles

        # symbol -> list of closed candles
        self._candles: Dict[str, List[Candle]] = defaultdict(list)

        # symbol -> current (open) candle being built
        self._current: Dict[str, Candle] = {}

    def process_tick(
        self,
        symbol: str,
        price: float,
        quantity: float,
        timestamp_ms: int,
    ) -> Optional[Candle]:
        """Feed a raw trade tick into the builder.

        Returns:
            The completed Candle if this tick crossed a boundary and closed the prior candle, else None.
        """
        if self.interval_ms <= 0:
            return None

        # Determine which candle bucket this tick belongs to
        candle_open_time = (timestamp_ms // self.interval_ms) * self.interval_ms
        current = self._current.get(symbol)

        # If no current candle or tick belongs to a new candle period
        if current is None or candle_open_time > current.timestamp:
            closed = None
            if current is not None:
                current.is_closed = True
                self._candles[symbol].append(current)
                closed = current

                # Trim ring buffer to max_candles
                if len(self._candles[symbol]) > self.max_candles:
                    self._candles[symbol] = self._candles[symbol][-self.max_candles:]

            # Start new candle bucket
            self._current[symbol] = Candle(
                timestamp=candle_open_time,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=quantity,
                volume_usd=price * quantity,
                trade_count=1,
            )
            return closed

        # Update current running candle in-place
        current.high = max(current.high, price)
        current.low = min(current.low, price)
        current.close = price
        current.volume += quantity
        current.volume_usd += price * quantity
        current.trade_count += 1
        return None

    def get_candles(self, symbol: str, count: int = 288, include_current: bool = True) -> List[Dict[str, Any]]:
        """Retrieve the last N candles for a symbol as dictionaries for HMM feature extraction.

        Args:
            symbol: Ticker symbol (e.g. 'BTCUSDT' or 'BTC-USDT').
            count: Number of closed candles to retrieve.
            include_current: Whether to append the current active (unclosed) candle.
        """
        candles = self._candles.get(symbol, [])
        result = [c.to_dict() for c in candles[-count:]]

        if include_current:
            current = self._current.get(symbol)
            if current is not None:
                result.append(current.to_dict())

        return result

    def process_trade(
        self,
        symbol: str,
        price: float,
        quantity: float,
        timestamp_ms: int,
    ) -> Optional[Candle]:
        """Alias for process_tick for trade feed ingestion compatibility."""
        return self.process_tick(symbol, price, quantity, timestamp_ms)

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get the latest close price for a symbol."""
        current = self._current.get(symbol)
        if current is not None:
            return current.close
        candles = self._candles.get(symbol, [])
        if candles:
            return candles[-1].close
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Return candle builder status for monitoring."""
        return {
            "interval_ms": self.interval_ms,
            "max_candles": self.max_candles,
            "symbols_tracked": list(self._current.keys()),
            "candle_counts": {sym: len(c_list) for sym, c_list in self._candles.items()},
        }

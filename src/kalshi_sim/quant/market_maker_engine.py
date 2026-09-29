"""Bot 6 Market Maker Engine.

Adapts the Polymarket enhanced market making strategy to Kalshi:
- Inventory tracking & skew-adjusted quotes
- Dynamic volatility-based spread widening
- Adverse selection protection (skip after spikes)
- Mean-reversion fade for inventory management
"""

import math
from typing import Dict, List, Optional
from decimal import Decimal
import logging
import time

from kalshi_sim.schemas import OrderSide

logger = logging.getLogger("MarketMakerEngine")

class MarketMakerEngine:
    """Quantitative Market Maker that generates skewed Bid/Ask quotes based on inventory."""

    STRATEGY_ID = "bot6_market_maker"
    STRATEGY_NAME = "Bot 6 MM (BTC + DOGE Market Maker)"

    def __init__(self) -> None:
        self.inventory: Dict[str, int] = {}  # net YES contracts
        self.price_history: Dict[str, List[float]] = {}
        self.last_eval_time: Dict[str, float] = {}

    def _update_history(self, ticker: str, yes_price: float) -> None:
        if ticker not in self.price_history:
            self.price_history[ticker] = []
        self.price_history[ticker].append(yes_price)
        if len(self.price_history[ticker]) > 5:
            self.price_history[ticker].pop(0)

    def _compute_volatility(self, ticker: str) -> float:
        hist = self.price_history.get(ticker, [])
        if len(hist) < 5:
            return 0.01
        returns = []
        for i in range(1, len(hist)):
            returns.append((hist[i] - hist[i-1]) / max(0.001, hist[i-1]))
        if not returns:
            return 0.01
        mean = sum(returns) / len(returns)
        variance = sum((r - mean)**2 for r in returns) / len(returns)
        return math.sqrt(variance)

    def _has_recent_spike(self, ticker: str, threshold: float = 0.03) -> bool:
        hist = self.price_history.get(ticker, [])
        if len(hist) < 5:
            return False
        oldest = hist[0]
        newest = hist[-1]
        change = abs(newest - oldest) / max(0.001, oldest)
        return change > threshold

    def notify_fill(self, ticker: str, side: OrderSide, size: int) -> None:
        """Update inventory immediately upon local or live fill."""
        current_inv = self.inventory.get(ticker, 0)
        if side == OrderSide.BUY:
            self.inventory[ticker] = current_inv + size
        else:
            self.inventory[ticker] = current_inv - size

    def evaluate(
        self,
        ticker: str,
        yes_bid: float,
        yes_ask: float,
        min_spread_cents: int = 2,
        inventory_skew_cents: int = 1,
        volatility_multiplier: float = 2.0,
        adverse_move_threshold: float = 0.03,
        max_inventory: int = 1,
    ) -> List[dict]:
        """Returns a list of order intents (raw dicts) representing optimal quotes."""
        now = time.monotonic()
        if now - self.last_eval_time.get(ticker, 0.0) < 1.0:
            return []  # Only quote once per second max per ticker
        self.last_eval_time[ticker] = now

        # Update history with mid price
        mid_price = (yes_bid + yes_ask) / 2.0
        self._update_history(ticker, mid_price)

        spread = yes_ask - yes_bid
        min_spread_usd = min_spread_cents / 100.0

        if spread < min_spread_usd:
            return []

        if yes_bid < 0.05 or yes_ask > 0.95:
            return []

        if self._has_recent_spike(ticker, adverse_move_threshold):
            return []

        vol = self._compute_volatility(ticker)
        dynamic_min_spread = max(min_spread_usd, vol * volatility_multiplier)
        
        if spread < dynamic_min_spread:
            return []

        net_inventory = self.inventory.get(ticker, 0)
        skew = (net_inventory * inventory_skew_cents) / 100.0
        
        half_spread = spread / 2.0
        buy_edge = (half_spread * 0.6) - skew
        sell_edge = (half_spread * 0.6) + skew

        intents = []
        
        # Quote Bid (BUY YES)
        if net_inventory < max_inventory and buy_edge > 0.001:
            bid_price = yes_bid + max(0.01, spread * 0.3) - skew
            bid_price = max(0.01, min(0.99, bid_price))
            intents.append({
                "side": OrderSide.BUY,
                "price": Decimal(f"{bid_price:.2f}"),
                "reasoning": f"MM Bid (Spread: ${spread:.2f}, Skew: ${skew:.2f})",
            })

        # Quote Ask (SELL YES / BUY NO)
        if net_inventory > -max_inventory and sell_edge > 0.001:
            ask_price = yes_ask - max(0.01, spread * 0.3) - skew
            ask_price = max(0.01, min(0.99, ask_price))
            intents.append({
                "side": OrderSide.SELL,
                "price": Decimal(f"{ask_price:.2f}"),
                "reasoning": f"MM Ask (Spread: ${spread:.2f}, Skew: ${skew:.2f})",
            })

        return intents

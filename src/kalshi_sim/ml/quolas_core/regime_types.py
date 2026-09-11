"""Regime Type Definitions for QuoLas HMM Brain in Kalshi Simulator.

The HMM detects three mutually exclusive market states:
- STABLE_RANGE: Low vol, mean-reverting (bias towards Contradiction Arbitrage)
- VOL_EXPANSION: High vol, directional momentum (bias towards Momentum Scalp)
- RISK_OFF: Extreme stress, cascade or low liquidity (Veto trades)
"""

from __future__ import annotations

from enum import IntEnum


class MarketRegime(IntEnum):
    """Hidden Markov Model states mapped to trading behavior."""

    STABLE_RANGE = 0    # Low vol, mean-reverting — scalp / contradiction mode
    VOL_EXPANSION = 1   # High vol, trending — momentum mode
    RISK_OFF = 2        # Extreme stress — NO TRADING

    @property
    def is_tradeable(self) -> bool:
        """Only STABLE_RANGE and VOL_EXPANSION allow trade entries."""
        return self != MarketRegime.RISK_OFF

    @property
    def description(self) -> str:
        descriptions = {
            MarketRegime.STABLE_RANGE: "Low volatility, mean-reverting conditions",
            MarketRegime.VOL_EXPANSION: "High volatility, trending/breakout conditions",
            MarketRegime.RISK_OFF: "Extreme stress, liquidation cascades — NO TRADING",
        }
        return descriptions.get(self, "Unknown regime")

    @property
    def emoji(self) -> str:
        emojis = {
            MarketRegime.STABLE_RANGE: "🟢",
            MarketRegime.VOL_EXPANSION: "🟡",
            MarketRegime.RISK_OFF: "🔴",
        }
        return emojis.get(self, "⚪")

"""Institutional Base Strategy Engine Architecture.

Standardizes strategy bot lifecycle, tick evaluation, cycle settlement hooks,
and telemetry contracts across all quantitative trading engines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional

from shared.schemas import L2BookState, MarketInfo, OrderSide, OrderType, Timeframe

logger = logging.getLogger("BaseEngine")


@dataclass
class TradeIntent:
    """Standardized trade decision emitted by an autonomous strategy engine."""

    ticker: str
    side: OrderSide
    order_type: OrderType = OrderType.LIMIT
    count: int = 1
    price: Optional[Decimal] = None
    reasoning: str = ""
    vpin: float = 0.15
    ai_prob: float = 0.50
    timeframe: Timeframe = Timeframe.FIFTEEN_MIN
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseStrategyEngine(ABC):
    """Abstract base class for all pluggable algorithmic trading engines."""

    def __init__(
        self,
        bot_id: str,
        bot_name: str,
        version: str = "1.0.0",
        is_live_authorized: bool = False,
    ) -> None:
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.version = version
        self.is_live_authorized = is_live_authorized
        self.total_evaluations: int = 0
        self.total_intents_emitted: int = 0
        self.last_eval_time: float = 0.0

    @abstractmethod
    def evaluate_tick(
        self,
        book: L2BookState,
        market_info: Optional[MarketInfo] = None,
        spot_price: Optional[Decimal] = None,
        twap_60s: Optional[Decimal] = None,
        time_to_expiry_s: float = 600.0,
        **kwargs: Any,
    ) -> Optional[TradeIntent]:
        """Evaluate incoming market state and return an actionable TradeIntent or None."""
        raise NotImplementedError

    @abstractmethod
    def on_cycle_settled(
        self,
        cycle_id: str,
        outcome: str,
        final_twap: Decimal,
        target_strike: Decimal,
    ) -> None:
        """Lifecycle hook triggered upon settlement of a 15M/5M contract cycle."""
        raise NotImplementedError

    @abstractmethod
    def get_telemetry(self) -> Dict[str, Any]:
        """Return real-time diagnostic indicators for terminal telemetry."""
        raise NotImplementedError

    def get_info(self) -> Dict[str, Any]:
        """Return standardized bot metadata."""
        return {
            "bot_id": self.bot_id,
            "bot_name": self.bot_name,
            "version": self.version,
            "is_live_authorized": self.is_live_authorized,
            "total_evaluations": self.total_evaluations,
            "total_intents_emitted": self.total_intents_emitted,
        }

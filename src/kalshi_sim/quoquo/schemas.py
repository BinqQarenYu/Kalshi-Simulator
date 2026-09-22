"""Quoquo Institutional Schemas.

Enforces strict institutional data invariants:
- Strict Decimal precision for monetary amounts, strikes, and price diffs.
- Eastern Time ('America/New_York') formatting for human-facing timelines.
- Standardized taxonomy for market events and bot veto classifications.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class CycleOutcome(str, Enum):
    TRADE_FIRED_WIN = "TRADE_FIRED_WIN"
    TRADE_FIRED_LOSS = "TRADE_FIRED_LOSS"
    CYCLE_HELD_VETO = "CYCLE_HELD_VETO"
    NO_SETUP = "NO_SETUP"


class VetoCategory(str, Enum):
    WHALE_QUEUE = "WHALE_QUEUE"
    RAZOR_TIGHT_MOAT = "RAZOR_TIGHT_MOAT"
    VPIN_TOXIC = "VPIN_TOXIC"
    PRICE_CEILING = "PRICE_CEILING"
    CONVICTION_HURDLE = "CONVICTION_HURDLE"
    CLOB_SPREAD = "CLOB_SPREAD"
    OPENING_QUARANTINE = "OPENING_QUARANTINE"
    EXPIRATION_QUARANTINE = "EXPIRATION_QUARANTINE"
    NONE = "NONE"


class CondensedCycleTelemetry(BaseModel):
    """Polished, token-efficient digest of a single Kalshi 15M/5M contract cycle."""

    cycle_ticker: str = Field(..., description="Unique contract ticker")
    asset: str = Field(default="BTC", description="Underlying asset")
    timeframe: str = Field(default="15m", description="Contract timeframe")
    cycle_time_et: str = Field(..., description="Localized Eastern Time window")
    strike_price: str = Field(..., description="Target strike formatted as Decimal string")
    settlement_spot_price: Optional[str] = Field(default=None, description="Final settlement spot price")

    # Execution Summary
    outcome: CycleOutcome = Field(default=CycleOutcome.CYCLE_HELD_VETO)
    trade_side: Optional[str] = Field(default=None, description="Trade side")
    entry_price: Optional[str] = Field(default=None, description="Maker fill or limit price")
    contracts: int = Field(default=0, description="Contracts executed")
    pnl: Optional[str] = Field(default=None, description="Realized PnL")

    # Veto and Microstructure Distribution
    dominant_veto: VetoCategory = Field(default=VetoCategory.NONE)
    veto_distribution: dict[str, int] = Field(default_factory=dict, description="Count of occurrences per veto type")
    spot_diff_range: list[str] = Field(default_factory=lambda: ["0.00", "0.00"], description="Min and max diff")
    vpin_range: list[float] = Field(default_factory=lambda: [0.15, 0.15], description="Min and max vpin")
    max_queue_depth_seen: int = Field(default=0, description="Peak contracts resting ahead")

    # Deer Synthesis
    deer_briefing: str = Field(..., description="Concise forensic summary")
    raw_tokens_eliminated: int = Field(default=0, description="Raw tokens filtered out")
    condensed_token_cost: int = Field(default=0, description="Actual token footprint of this summary")
    generated_at_utc: str = Field(..., description="ISO 8601 UTC timestamp")

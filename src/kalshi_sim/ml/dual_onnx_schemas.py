"""Schemas and Data Types for Dual-ONNX Contradiction Arbitrage System.

Defines the quantitative regimes, trading decisions, and telemetry structures
for cross-market orderflow arbitrage between QuoLas (Spot) and Kalshi (Binary).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional


class DualONNXRegime(str, Enum):
    """Execution regime determined by the Dual-ONNX Contradiction Matrix."""

    MOMENTUM_SCALP = "MOMENTUM_SCALP"
    CONTRADICTION_ARBITRAGE = "CONTRADICTION_ARBITRAGE"
    CHOP_WAIT = "CHOP_WAIT"
    TOXIC_VETO = "TOXIC_VETO"
    TEMPORAL_DESYNC = "TEMPORAL_DESYNC"


@dataclass(frozen=True)
class DualONNXDecision:
    """Immutable quantitative decision emitted by DualONNXArbitrageBot."""

    action: str  # "BUY_YES" | "BUY_NO" | "HOLD"
    regime: DualONNXRegime
    side: Optional[str]  # "yes" | "no" | None
    quolas_signal: str  # "LONG" / "UP", "SHORT" / "DOWN", "WAIT"
    quolas_confidence: float
    kalshi_signal: str  # "LONG" / "UP", "SHORT" / "DOWN", "WAIT"
    kalshi_confidence: float
    recommended_limit_price: Decimal
    expected_value: Decimal
    recommended_contracts: int = 1
    cancel_resting_orders: bool = False
    rationale: str = ""

    @property
    def is_trade(self) -> bool:
        """Return True if decision is an actionable trade."""
        return self.action in ("BUY_YES", "BUY_NO") and self.recommended_contracts > 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize decision for telemetry and logging."""
        return {
            "action": self.action,
            "regime": self.regime.value if isinstance(self.regime, DualONNXRegime) else str(self.regime),
            "side": self.side,
            "quolas_signal": self.quolas_signal,
            "quolas_confidence": round(self.quolas_confidence, 4),
            "kalshi_signal": self.kalshi_signal,
            "kalshi_confidence": round(self.kalshi_confidence, 4),
            "recommended_limit_price": str(self.recommended_limit_price),
            "expected_value": str(self.expected_value),
            "recommended_contracts": self.recommended_contracts,
            "cancel_resting_orders": self.cancel_resting_orders,
            "is_trade": self.is_trade,
            "rationale": self.rationale,
        }

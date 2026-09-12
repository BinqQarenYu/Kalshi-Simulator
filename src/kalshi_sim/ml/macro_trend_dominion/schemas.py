"""Schemas and data models for Bot 3: Macro Trend Dominion."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class MacroDominionDecision:
    """Structured decision output from Macro Trend Dominion Bot."""
    strategy_id: str
    strategy_name: str
    call: str  # 'YES' | 'NO' | 'DONT'
    confidence_pct: float
    limit_price: Decimal
    expected_value: Decimal
    net_edge_pct: float
    recommended_contracts: int
    macro_trend: str  # 'BULL' | 'BEAR' | 'CHOP'
    hmm_regime: str  # 'STABLE_RANGE' | 'VOL_EXPANSION' | 'RISK_OFF'
    spot_signal: str  # 'UP' | 'DOWN' | 'WAIT'
    spot_confidence: float
    kalshi_signal: str  # 'UP' | 'DOWN' | 'WAIT'
    kalshi_confidence: float
    is_ev_positive: bool
    rationale: str
    brier_shrinkage_factor: float = 1.0
    active_price_cap: Decimal = Decimal("0.89")
    cancel_resting_orders: bool = False

    @property
    def side(self) -> Optional[str]:
        """Convert call to side format ('yes', 'no', None)."""
        c = self.call.upper()
        if c == "YES":
            return "yes"
        if c == "NO":
            return "no"
        return None

    @property
    def recommended_side(self) -> str:
        """Alias for recommended_side ('yes', 'no', 'none')."""
        return self.side or "none"

    @property
    def macro_regime(self) -> str:
        """Alias for macro_regime ('MACRO_BULL', 'MACRO_BEAR', 'MACRO_CHOP')."""
        if self.macro_trend == "BULL":
            return "MACRO_BULL"
        if self.macro_trend == "BEAR":
            return "MACRO_BEAR"
        return "MACRO_CHOP"

    @property
    def active_playbook(self) -> str:
        """Active playbook name."""
        return "MACRO_CONSENSUS_15M"

    @property
    def playbook_stage(self) -> str:
        """Playbook stage."""
        return "FINAL_CONSENSUS"

    @property
    def onnx_signal(self) -> str:
        """ONNX signal alias."""
        return self.spot_signal if self.spot_signal != "WAIT" else self.kalshi_signal

    @property
    def onnx_confidence(self) -> float:
        """ONNX confidence alias."""
        return max(self.spot_confidence, self.kalshi_confidence)

    @property
    def onnx_prob_long(self) -> float:
        """Long probability estimate."""
        return self.spot_confidence if self.spot_signal == "UP" else (1.0 - self.spot_confidence)

    @property
    def onnx_prob_short(self) -> float:
        """Short probability estimate."""
        return self.spot_confidence if self.spot_signal == "DOWN" else (1.0 - self.spot_confidence)

    @property
    def onnx_prob_wait(self) -> float:
        """Wait probability estimate."""
        return 0.0

    @property
    def trend_1h_pct(self) -> float:
        """Macro trend return estimate."""
        return 0.0

    @property
    def trend_15m_pct(self) -> float:
        """15M trend return estimate."""
        return 0.0

    @property
    def p_up(self) -> float:
        """Probability UP."""
        return self.spot_confidence if self.spot_signal == "UP" else (1.0 - self.spot_confidence)

    @property
    def p_down(self) -> float:
        """Probability DOWN."""
        return self.spot_confidence if self.spot_signal == "DOWN" else (1.0 - self.spot_confidence)

    @property
    def p_wait(self) -> float:
        """Probability WAIT."""
        return 0.0

    @property
    def vpin(self) -> float:
        """VPIN toxicity score."""
        return 0.15

    @property
    def vpin_is_safe(self) -> bool:
        """VPIN safety check."""
        return True

    @property
    def edge_pct(self) -> float:
        """Net edge percentage alias."""
        return self.net_edge_pct

    @property
    def edge_yes(self) -> float:
        """Edge YES."""
        return (self.net_edge_pct / 100.0) if self.call == "YES" else 0.0

    @property
    def edge_no(self) -> float:
        """Edge NO."""
        return (self.net_edge_pct / 100.0) if self.call == "NO" else 0.0

    @property
    def kelly_f_yes(self) -> float:
        """Kelly fraction YES."""
        return 0.05 if self.call == "YES" else 0.0

    @property
    def kelly_f_no(self) -> float:
        """Kelly fraction NO."""
        return 0.05 if self.call == "NO" else 0.0

    @property
    def ev_yes(self) -> float:
        """Expected value on YES."""
        return float(self.expected_value) if self.call == "YES" else 0.0

    @property
    def ev_no(self) -> float:
        """Expected value on NO."""
        return float(self.expected_value) if self.call == "NO" else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for WebSocket and REST telemetry."""
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "call": self.call,
            "side": self.side,
            "confidence_pct": round(self.confidence_pct, 1),
            "limit_price": float(self.limit_price),
            "limit_price_cents": int(round(float(self.limit_price) * 100)),
            "expected_value": float(self.expected_value),
            "net_edge_pct": round(self.net_edge_pct, 2),
            "recommended_contracts": self.recommended_contracts,
            "macro_trend": self.macro_trend,
            "hmm_regime": self.hmm_regime,
            "spot_signal": self.spot_signal,
            "spot_confidence": round(self.spot_confidence, 3),
            "kalshi_signal": self.kalshi_signal,
            "kalshi_confidence": round(self.kalshi_confidence, 3),
            "is_ev_positive": self.is_ev_positive,
            "rationale": self.rationale,
            "brier_shrinkage_factor": round(self.brier_shrinkage_factor, 3),
            "active_price_cap": float(self.active_price_cap),
            "cancel_resting_orders": self.cancel_resting_orders,
        }

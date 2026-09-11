"""The Mistake Learning Diagnostic & Adaptive Recalibration Engine for Bot 3."""

from __future__ import annotations

from collections import deque
from decimal import Decimal
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("kalshi_sim.macro_trend_dominion.learning")


class MacroDominionLearningEngine:
    """Tracks trade predictions vs empirical outcomes to dynamically eliminate systematic trading mistakes.
    
    Operates 3 concrete mathematical tiers:
    1. Tier 1: Dynamic Brier Calibration & Shrinkage (damps overconfidence when model errs).
    2. Tier 2: Price Decile Pruning (dynamically caps allowable entry price if expensive fills lose).
    3. Tier 3: Mistake Classification (diagnoses exact failure mode: false breakout, cascade, or pin noise).
    """

    def __init__(
        self,
        rolling_window_size: int = 50,
        min_samples_for_adaptation: int = 5,
        default_price_cap: Decimal = Decimal("0.89"),
        adaptation_rate: float = 0.20,
    ) -> None:
        self.rolling_window_size = rolling_window_size
        self.min_samples = min_samples_for_adaptation
        self.default_price_cap = default_price_cap
        self.adaptation_rate = max(0.0, min(0.5, float(adaptation_rate)))

        # Rolling history of settled trade tickets
        self.trade_history: deque[Dict[str, Any]] = deque(maxlen=rolling_window_size)
        
        # Mistake frequency diagnostics
        self.mistake_counts: Dict[str, int] = {
            "FALSE_BREAKOUT": 0,
            "CASCADE_ADVERSE_SELECTION": 0,
            "PIN_CHOP_NOISE": 0,
            "NEGATIVE_EV_HIGH_PRICE": 0,
            "OTHER_LOSS": 0,
        }

        # Dynamic state
        self.current_shrinkage_factor: float = 1.0
        self.active_price_cap: Decimal = self.default_price_cap
        self.last_diagnostic_summary: str = "Learning Engine Initialized. Accumulating cycle samples."

    def calibrate_probability(self, raw_prob: float) -> Tuple[float, float]:
        """Calibrate model probability using empirical Brier shrinkage factor.
        
        Returns:
            Tuple of (calibrated_prob, shrinkage_factor)
        """
        p = max(0.01, min(0.99, float(raw_prob)))
        if len(self.trade_history) < self.min_samples or self.adaptation_rate <= 0.0:
            return p, 1.0

        # Calibrate relative to neutral 0.50
        scaled_diff = (p - 0.50) * self.current_shrinkage_factor
        calibrated = max(0.05, min(0.95, 0.50 + scaled_diff))
        return calibrated, self.current_shrinkage_factor

    def get_effective_price_cap(self, user_limit_cents: int) -> Decimal:
        """Return the effective price ceiling, respecting both user dials and empirical decile pruning."""
        user_dec = Decimal(str(max(1, min(89, user_limit_cents)))) / Decimal("100")
        return min(user_dec, self.active_price_cap)

    def record_cycle_result(
        self,
        cycle_id: str,
        ticker: str,
        call: str,
        predicted_prob: float,
        fill_price: Decimal,
        outcome: str,  # 'win' | 'loss'
        pnl: Decimal,
        spot_diff_at_entry: float,
        spot_diff_at_settle: float,
        macro_trend: str,
        hmm_regime: str,
        execution_mode: str = "paper",
    ) -> Dict[str, Any]:
        """Record settled trade ticket, diagnose mistakes, and update adaptive calibrations."""
        is_win = str(outcome).strip().lower() == "win"
        entry_pr = float(fill_price)
        actual_val = 1.0 if is_win else 0.0
        brier_err = (predicted_prob - actual_val) ** 2

        mistake_tag: Optional[str] = None
        if not is_win:
            # Diagnose specific mistake
            if entry_pr >= 0.65:
                mistake_tag = "NEGATIVE_EV_HIGH_PRICE"
            elif abs(spot_diff_at_settle) <= 12.0:
                mistake_tag = "PIN_CHOP_NOISE"
            elif abs(spot_diff_at_settle - spot_diff_at_entry) >= 30.0:
                mistake_tag = "CASCADE_ADVERSE_SELECTION"
            elif macro_trend in ("BULL", "BEAR"):
                mistake_tag = "FALSE_BREAKOUT"
            else:
                mistake_tag = "OTHER_LOSS"
            
            self.mistake_counts[mistake_tag] = self.mistake_counts.get(mistake_tag, 0) + 1

        record = {
            "cycle_id": cycle_id,
            "ticker": ticker,
            "call": call,
            "predicted_prob": predicted_prob,
            "fill_price": float(fill_price),
            "outcome": "win" if is_win else "loss",
            "pnl": float(pnl),
            "brier_error": brier_err,
            "mistake_tag": mistake_tag,
            "spot_diff_entry": spot_diff_at_entry,
            "spot_diff_settle": spot_diff_at_settle,
            "macro_trend": macro_trend,
            "hmm_regime": hmm_regime,
            "execution_mode": execution_mode,
        }
        self.trade_history.append(record)

        # Trigger recalibration
        self._recalculate_calibrations()
        return record

    def _recalculate_calibrations(self) -> None:
        """Update Tier 1 Brier shrinkage and Tier 2 decile price cap."""
        if len(self.trade_history) < self.min_samples:
            return

        # 1. Tier 1: Brier Shrinkage
        wins = sum(1 for r in self.trade_history if r["outcome"] == "win")
        total = len(self.trade_history)
        empirical_win_rate = wins / total
        mean_pred = sum(r["predicted_prob"] for r in self.trade_history) / total

        if mean_pred > 0.50 and empirical_win_rate < mean_pred:
            overconfidence_ratio = empirical_win_rate / mean_pred
            # Damp shrinkage according to adaptation rate
            target_shrinkage = max(0.20, min(1.0, overconfidence_ratio))
            self.current_shrinkage_factor = (
                (1.0 - self.adaptation_rate) * 1.0 + self.adaptation_rate * target_shrinkage
            )
        else:
            self.current_shrinkage_factor = 1.0

        # 2. Tier 2: Price Decile Pruning
        # Evaluate performance for entries > 60c
        high_price_trades = [r for r in self.trade_history if r["fill_price"] >= 0.60]
        if len(high_price_trades) >= 3:
            high_pnl = sum(r["pnl"] for r in high_price_trades)
            if high_pnl < -0.50:
                # Expensive fills are losing money -> clamp active cap to $0.55
                self.active_price_cap = Decimal("0.55")
                self.last_diagnostic_summary = (
                    f"Mistake Alert: High-price entries (>=60c) show negative PnL (${high_pnl:.2f}). "
                    f"Price cap pruned to 55c. Brier shrinkage: {self.current_shrinkage_factor:.2f}."
                )
                logger.warning("[LEARNING ENGINE] %s", self.last_diagnostic_summary)
                return

        # If performance is healthy, restore default cap
        self.active_price_cap = self.default_price_cap
        self.last_diagnostic_summary = (
            f"Healthy Edge: Win rate {empirical_win_rate*100:.1f}% vs Pred {mean_pred*100:.1f}%. "
            f"Brier shrinkage: {self.current_shrinkage_factor:.2f}. Cap: ${float(self.active_price_cap):.2f}."
        )

    def get_diagnostics(self) -> Dict[str, Any]:
        """Return full diagnostic telemetry for API and frontend console."""
        total = len(self.trade_history)
        wins = sum(1 for r in self.trade_history if r["outcome"] == "win")
        losses = total - wins
        wr = (wins / total * 100.0) if total > 0 else 0.0
        avg_brier = (sum(r["brier_error"] for r in self.trade_history) / total) if total > 0 else 0.0

        return {
            "total_cycles_recorded": total,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(wr, 1),
            "average_brier_score": round(avg_brier, 4),
            "shrinkage_factor": round(self.current_shrinkage_factor, 3),
            "active_price_cap": float(self.active_price_cap),
            "active_price_cap_cents": int(round(float(self.active_price_cap) * 100)),
            "mistake_breakdown": self.mistake_counts.copy(),
            "summary": self.last_diagnostic_summary,
            "recent_tickets": list(self.trade_history)[-5:],
        }

"""Warrior 3: The Bleed Defender (Adverse Wave Armor & Capital Shield).

Specialized execution guardian for Region 3 (BLEED).
Enforces:
1. Double-Wick Meatgrinder Veto (Immediate stand-down when wicks sweep both sides).
2. False-Breakout Rejection Pin Veto (Blocks top-of-wick FOMO entries).
3. Ultra-Deep Discount Pricing ($0.28 - $0.35 maker bids for 2.33:1 payoff asymmetry).
4. Super-Moat Defense (Requires spot distance >= $85.00).
5. Post-Loss Cooldown Throttling (Breaks high-frequency alternating whipsaw loops).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional, Tuple

from kalshi_sim.ml.wave_classifier import MarketWavePhysics

logger = logging.getLogger("kalshi_sim.bleed_defender")


class BleedDefender:
    """Warrior 3: Defense-first execution engine active during hostile Bleed waves."""

    def __init__(
        self,
        bleed_discount_limit_price: Decimal = Decimal("0.30"),
        bleed_max_entry_price: Decimal = Decimal("0.35"),
        min_spot_diff_bleed: float = 85.0,
        min_ev_hurdle_dollars: Decimal = Decimal("0.05"),
        cooldown_cycles_after_loss: int = 1,
    ) -> None:
        self.bleed_discount_limit_price = bleed_discount_limit_price
        self.bleed_max_entry_price = bleed_max_entry_price
        self.min_spot_diff_bleed = min_spot_diff_bleed
        self.min_ev_hurdle_dollars = min_ev_hurdle_dollars
        self.cooldown_cycles_after_loss = cooldown_cycles_after_loss
        self._cycles_in_cooldown: int = 0

    def trigger_loss_cooldown(self) -> None:
        """Arms post-loss cooldown to suppress immediate subsequent cycle execution."""
        self._cycles_in_cooldown = self.cooldown_cycles_after_loss
        logger.warning(
            "🛡️ [BLEED DEFENDER] Loss recorded! Armed %d cycle cooldown to terminate whipsaw loop.",
            self.cooldown_cycles_after_loss,
        )

    def is_cooling_down(self) -> bool:
        """Checks if Warrior 3 is currently enforcing a protective stand-down cooldown."""
        return self._cycles_in_cooldown > 0

    def step_cycle(self) -> None:
        """Decrements cooldown counter upon cycle boundary completion."""
        if self._cycles_in_cooldown > 0:
            self._cycles_in_cooldown -= 1
            logger.info(
                "🛡️ [BLEED DEFENDER] Cooldown cycle decremented (%d cycles remaining).",
                self._cycles_in_cooldown,
            )

    def evaluate_bleed_defense(
        self,
        physics: MarketWavePhysics,
        spot_diff: float,
        model_win_prob: float,
        time_to_expiry_s: float,
    ) -> Tuple[bool, Optional[Decimal], str]:
        """Evaluates whether to veto the trade or allow an ultra-discount entry.

        Returns:
            (allow_trade, limit_price_decimal, decision_rationale)
        """
        # 1. Cooldown Check
        if self._cycles_in_cooldown > 0:
            return (
                False,
                None,
                f"Bleed Cooldown Active: Standing down for {self._cycles_in_cooldown} cycle to break alternating whipsaw.",
            )

        # 2. Meatgrinder Veto (Sweeping both Yes & No bids)
        if physics.is_double_wick_meatgrinder:
            return (
                False,
                None,
                f"Meatgrinder Veto (Hard Stand-Down): Upper (${physics.upper_wick_dollars:.0f}) and "
                f"lower (${physics.lower_wick_dollars:.0f}) wicks sweep both strikes. Absolute stand-down.",
            )

        # 3. False Breakout Rejection Pin Veto
        if physics.is_false_breakout:
            return (
                False,
                None,
                f"False Breakout Veto: Rejection wick (${max(physics.upper_wick_dollars, physics.lower_wick_dollars):.0f}) "
                f"exceeds 1.8x candle body. Refusing top-of-wick trap.",
            )

        # 4. Super-Moat Distance Check
        if abs(spot_diff) < self.min_spot_diff_bleed:
            return (
                False,
                None,
                f"Super-Moat Veto: Spot diff (${abs(spot_diff):.1f}) < ${self.min_spot_diff_bleed:.1f} "
                f"required in high-energy Bleed regime. Brownian noise buffer breached.",
            )

        # 5. Pricing: Ultra-Deep Discount Floor ($0.28 - $0.35)
        # Mathematical Payoff Asymmetry: Risky 30c to win 70c (2.33:1 payoff ratio)
        ev_hurdle = float(self.min_ev_hurdle_dollars)
        target_discount = model_win_prob - ev_hurdle
        min_p = float(self.bleed_discount_limit_price)
        max_p = float(self.bleed_max_entry_price)
        clamped_p = max(min_p, min(target_discount, max_p))
        limit_price = Decimal(str(round(clamped_p, 2)))

        return (
            True,
            limit_price,
            f"Bleed Defender Asymmetric Entry Approved: Price=${limit_price} (2.33:1 Payoff Asymmetry) | "
            f"Moat=${abs(spot_diff):.1f} >= ${self.min_spot_diff_bleed:.1f}",
        )

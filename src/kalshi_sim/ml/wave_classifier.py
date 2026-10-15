"""Market Wave Physics & 4-Region Regime Classifier Module.

Classifies market waves for the Bot 1 V4 multi-warrior fleet into 4 distinct regions:
1. CHOP (Warrior 2: Chop Harvester) - Compressed, mean-reverting ranges.
2. STORM (Warrior 1: Storm Vanguard) - High-velocity, directional expansion waves.
3. BLEED (Warrior 3: Bleed Defender) - Tsunami whipsaws, double-wick meatgrinders, false breakouts.
4. HEALING (Healing Protocol Gate) - Post-bleed probationary shadow/quarantine state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger("kalshi_sim.wave_classifier")


@dataclass(frozen=True)
class MarketWavePhysics:
    """Quantitative physics of an active 15-minute price wave."""
    range_dollars: float
    body_dollars: float
    upper_wick_dollars: float
    lower_wick_dollars: float
    is_tsunami: bool
    is_double_wick_meatgrinder: bool
    is_false_breakout: bool
    wave_summary: str


def compute_wave_physics(
    open_price: float,
    high_price: float,
    low_price: float,
    current_price: float,
    tsunami_threshold: Optional[float] = None,
    wick_meatgrinder_threshold: Optional[float] = None,
    wick_ratio_threshold: float = 1.80,
    false_breakout_rng_threshold: Optional[float] = None,
    directional_body_threshold: Optional[float] = None,
    asset: Optional[str] = None,
) -> MarketWavePhysics:
    """Computes exact geometric wave features from candlestick boundaries with asset-aware scale."""
    high = max(high_price, open_price, current_price)
    low = min(low_price, open_price, current_price)
    rng = max(0.0, high - low)
    body = abs(current_price - open_price)
    upper_wick = max(0.0, high - max(open_price, current_price))
    lower_wick = max(0.0, min(open_price, current_price) - low)

    # Scale calibration: if asset is ETH or price magnitude matches ETH (< $10,000)
    is_eth_scale = (asset and asset.upper() == "ETH") or (asset is None and 100.0 <= current_price < 10000.0)

    # Resolve asset-calibrated defaults if not explicitly specified
    if tsunami_threshold is None:
        tsunami_threshold = 15.0 if is_eth_scale else 250.0
    if wick_meatgrinder_threshold is None:
        wick_meatgrinder_threshold = 2.50 if is_eth_scale else 45.0
    if false_breakout_rng_threshold is None:
        false_breakout_rng_threshold = 5.0 if is_eth_scale else 100.0
    if directional_body_threshold is None:
        directional_body_threshold = 5.0 if is_eth_scale else 100.0

    is_tsunami = rng >= tsunami_threshold
    is_double_wick = (upper_wick >= wick_meatgrinder_threshold) and (lower_wick >= wick_meatgrinder_threshold)
    is_false_breakout = (
        rng >= false_breakout_rng_threshold
        and max(upper_wick, lower_wick) >= (wick_ratio_threshold * max(1.0, body))
    )

    if is_tsunami:
        summary = f"TSUNAMI EXPANSION (${rng:.1f} range)"
    elif is_double_wick:
        summary = f"DOUBLE-WICK MEATGRINDER (up=${upper_wick:.1f}, dn=${lower_wick:.1f})"
    elif is_false_breakout:
        summary = f"FALSE BREAKOUT WICK (wick=${max(upper_wick, lower_wick):.1f} vs body=${body:.1f})"
    elif body >= directional_body_threshold:
        summary = f"DIRECTIONAL EXPANSION (${body:.1f} body)"
    else:
        summary = f"BOUNDED CHOP (${rng:.1f} range)"

    return MarketWavePhysics(
        range_dollars=rng,
        body_dollars=body,
        upper_wick_dollars=upper_wick,
        lower_wick_dollars=lower_wick,
        is_tsunami=is_tsunami,
        is_double_wick_meatgrinder=is_double_wick,
        is_false_breakout=is_false_breakout,
        wave_summary=summary,
    )


class WaveRegimeClassifier:
    """Evaluates multi-cycle wave physics and enforces transitions across the 4 regions."""

    def __init__(
        self,
        chop_range_threshold: float = 165.0,
        chop_vol_threshold: float = 12.0,
        tsunami_threshold: float = 250.0,
        consecutive_losses_bleed_trigger: int = 2,
        healing_consecutive_wins_required: int = 2,
    ) -> None:
        self.chop_range_threshold = chop_range_threshold
        self.chop_vol_threshold = chop_vol_threshold
        self.tsunami_threshold = tsunami_threshold
        self.consecutive_losses_bleed_trigger = consecutive_losses_bleed_trigger
        self.healing_consecutive_wins_required = healing_consecutive_wins_required

        self.current_region: str = "CHOP"
        self.consecutive_losses: int = 0
        self.healing_consecutive_wins: int = 0
        self.last_transition_reason: str = "Initial startup state"

    def record_settled_cycle(self, won: bool) -> None:
        """Updates internal win/loss trackers to trigger Bleed or Healing transitions."""
        if won:
            self.consecutive_losses = 0
            if self.current_region == "HEALING":
                self.healing_consecutive_wins += 1
                logger.info(
                    "🌱 [HEALING GATE] Recorded winning cycle (%d/%d required for graduation).",
                    self.healing_consecutive_wins,
                    self.healing_consecutive_wins_required,
                )
                if self.healing_consecutive_wins >= self.healing_consecutive_wins_required:
                    self.current_region = "CHOP"
                    self.healing_consecutive_wins = 0
                    self.last_transition_reason = "Healing Protocol Completed: 2 consecutive winning cycles verified."
                    logger.info("✅ [HEALING GRADUATION] Boat restored to normal operations! Promoted to CHOP region.")
        else:
            self.consecutive_losses += 1
            self.healing_consecutive_wins = 0
            logger.warning(
                "⚠️ [WAVE CLASSIFIER] Recorded cycle loss (Streak: %d consecutive losses).",
                self.consecutive_losses,
            )
            if self.consecutive_losses >= self.consecutive_losses_bleed_trigger:
                self.current_region = "BLEED"
                self.last_transition_reason = (
                    f"Bleed Trigger: {self.consecutive_losses} consecutive cycle losses experienced."
                )

    def transition_to_healing(self, reason: str = "Initiating healing convalescence") -> None:
        """Transitions into Region 4 (HEALING) and arms probationary quarantine."""
        self.current_region = "HEALING"
        self.consecutive_losses = 0
        self.healing_consecutive_wins = 0
        self.last_transition_reason = reason
        logger.info("🌱 [WAVE CLASSIFIER] Transitioned to HEALING region: %s", reason)

    def classify_region(
        self,
        open_price: float,
        high_price: float,
        low_price: float,
        current_price: float,
        rolling_vol_1m: float,
        spot_velocity_3s: float = 0.0,
        onnx_signal: str = "WAIT",
        onnx_confidence: float = 0.0,
    ) -> Tuple[str, MarketWavePhysics, str]:
        """Determines active region (CHOP, STORM, BLEED, or HEALING) and wave physics.

        Returns:
            (region_name, wave_physics, decision_rationale)
        """
        physics = compute_wave_physics(
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            current_price=current_price,
            tsunami_threshold=self.tsunami_threshold,
        )

        effective_chop_range = max(self.chop_range_threshold, current_price * 0.0020)

        is_hostile_wave = (
            physics.is_tsunami
            or physics.is_double_wick_meatgrinder
            or physics.is_false_breakout
        )

        # 1. Healing Region Check (If in convalescence, stay in HEALING unless interrupted by rogue wave)
        if self.current_region == "HEALING":
            if is_hostile_wave:
                self.current_region = "BLEED"
                reason = f"Bleed Region Active: Rogue wave interrupted healing ({physics.wave_summary}) | Warrior 3 engaged."
                self.last_transition_reason = reason
                return "BLEED", physics, reason
            reason = (
                f"Healing Region Active: Convalescence ({self.healing_consecutive_wins}/"
                f"{self.healing_consecutive_wins_required} wins). Capital protected in probationary gate."
            )
            self.last_transition_reason = reason
            return "HEALING", physics, reason

        # 2. Bleed Region Check (Immediate trigger on hostile rogue wave or loss streak)
        if self.consecutive_losses >= self.consecutive_losses_bleed_trigger or is_hostile_wave:
            if self.current_region != "BLEED":
                self.current_region = "BLEED"
                self.healing_consecutive_wins = 0
            reason = (
                f"Bleed Region Active: {physics.wave_summary} | "
                f"Loss Streak: {self.consecutive_losses} | Warrior 3 (Bleed Defender) engaged."
            )
            self.last_transition_reason = reason
            return "BLEED", physics, reason

        # 3. Stormy Region Check (Fast-Path Volcano or Clean Directional Trend)
        is_volcano = (
            abs(spot_velocity_3s) >= 15.0
            or (onnx_signal in ("LONG", "SHORT") and onnx_confidence >= 0.75)
            or (
                (physics.range_dollars > effective_chop_range or abs(spot_velocity_3s) >= 12.0)
                and physics.body_dollars >= 80.0
                and not physics.is_false_breakout
                and (onnx_signal in ("LONG", "SHORT") and onnx_confidence >= 0.70)
            )
        )

        if is_volcano:
            self.current_region = "STORM"
            reason = (
                f"Volcano Breakout detected: vel={spot_velocity_3s:+.1f}$/s, "
                f"range=${physics.range_dollars:.0f}, ONNX={onnx_signal}({onnx_confidence:.0%}) | Warrior 1 engaged."
            )
            self.last_transition_reason = reason
            return "STORM", physics, reason

        # 4. Choppy Region (Default quiet waters)
        self.current_region = "CHOP"
        reason = (
            f"Chop Region Active: Compressed range (${physics.range_dollars:.1f} <= ${effective_chop_range:.1f}), "
            f"vol=${rolling_vol_1m:.1f} | Warrior 2 (Chop Harvester) engaged."
        )
        self.last_transition_reason = reason
        return "CHOP", physics, reason

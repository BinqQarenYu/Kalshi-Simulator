"""Region 4: The Healing Protocol Gate (Post-Drawdown Convalescence).

State machine governing recovery after a drawdown or Bleed episode.
Enforces:
1. Probationary Quarantine: Suppresses live capital exposure while market stabilizes.
2. Two-Green-Strike Gate: Demands 2 consecutive winning settlement verifications in paper shadow mode.
3. Automatic Re-Arming Handshake: Seamlessly restores live trading once statistical stability is proven.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger("kalshi_sim.healing_protocol")


class HealingProtocol:
    """Manages the convalescence state machine and gates re-entry into live capital trading."""

    def __init__(self, consecutive_wins_required: int = 2) -> None:
        self.consecutive_wins_required = consecutive_wins_required
        self.is_active: bool = False
        self.consecutive_wins: int = 0
        self.quarantine_reason: str = "System healthy"

    def arm_healing_quarantine(self, reason: str = "Drawdown / Bleed episode recovery initiated") -> None:
        """Transitions the boat into Region 4 (HEALING)."""
        self.is_active = True
        self.consecutive_wins = 0
        self.quarantine_reason = reason
        logger.warning(
            "🌱 [HEALING PROTOCOL] Arming probationary quarantine: %s. "
            "Live capital suppressed until %d consecutive verified wins are achieved.",
            reason,
            self.consecutive_wins_required,
        )

    def record_settled_cycle(self, won: bool) -> bool:
        """Records cycle settlement during healing.

        Returns:
            True if system graduated out of healing, False otherwise.
        """
        if not self.is_active:
            return False

        if won:
            self.consecutive_wins += 1
            logger.info(
                "🌱 [HEALING PROGRESS] Verified winning cycle (%d/%d required).",
                self.consecutive_wins,
                self.consecutive_wins_required,
            )
            if self.consecutive_wins >= self.consecutive_wins_required:
                self.is_active = False
                self.consecutive_wins = 0
                self.quarantine_reason = "Graduated: 2 consecutive winning cycles verified"
                logger.info("🎉 [HEALING GRADUATION] Convalescence gate cleared! Re-arming live fleet.")
                return True
        else:
            self.consecutive_wins = 0
            logger.warning(
                "⚠️ [HEALING RESET] Cycle loss during probation. Resetting win streak to 0/%d.",
                self.consecutive_wins_required,
            )
        return False

    def should_suppress_live_capital(self) -> bool:
        """True if boat is in probationary quarantine and must not risk live funds."""
        return self.is_active

    def get_status(self) -> Dict[str, Any]:
        """Provides status payload for telemetry endpoints and desktop HUD."""
        return {
            "is_active": self.is_active,
            "consecutive_wins": self.consecutive_wins,
            "wins_required": self.consecutive_wins_required,
            "quarantine_reason": self.quarantine_reason,
            "live_capital_suppressed": self.is_active,
        }

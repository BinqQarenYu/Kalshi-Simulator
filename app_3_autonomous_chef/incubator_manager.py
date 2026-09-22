"""Lane 2 Incubator Governance & Safety Interlock Manager.

Enforces execution segregation and live-trading locks for assets undergoing
shadow incubation (e.g. GOLD) until formal 4-pillar and Council certification criteria
are satisfied (e.g., >= 65% win rate over 30 cycles).
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from shared.schemas import CryptoAsset

logger = logging.getLogger("IncubatorManager")

DEFAULT_REGISTRY_PATH = Path("data") / "incubator_registry.json"

DEFAULT_INCUBATOR_CONFIG: Dict[str, Any] = {
    "GOLD": {
        "status": "INCUBATOR",
        "is_locked": True,
        "strategy": "GoldInversionBot",
        "target_cycles": 30,
        "target_win_rate": 0.65,
        "completed_cycles": 0,
        "wins": 0,
        "losses": 0,
        "current_win_rate": 0.0,
        "net_pnl": 0.0,
        "certified_at": None,
        "lock_reason": "Quarantined in Lane 2 Incubator under Council Testing (17.1% historical WR failure)",
        "quarantined_at": "2026-09-12T09:15:00Z",
    },
    "DOGE": {
        "status": "INCUBATOR",
        "is_locked": True,
        "strategy": "DogeInversionBot",
        "target_cycles": 30,
        "target_win_rate": 0.65,
        "completed_cycles": 0,
        "wins": 0,
        "losses": 0,
        "current_win_rate": 0.0,
        "net_pnl": 0.0,
        "certified_at": None,
        "lock_reason": "Quarantined in Lane 2 Incubator under Council Testing (14.3% historical WR failure, illiquid spread dump)",
        "quarantined_at": "2026-09-12T09:42:00Z",
    },
}


class IncubatorManager:
    """Thread-safe manager governing Lane 2 Incubator assets and live selection locks."""

    @classmethod
    def get_instance(cls, registry_path: Union[str, Path] = DEFAULT_REGISTRY_PATH) -> IncubatorManager:
        """Retrieve global thread-safe IncubatorManager singleton."""
        return get_incubator_manager(registry_path)

    def __init__(self, registry_path: Union[str, Path] = DEFAULT_REGISTRY_PATH) -> None:
        self.registry_path = Path(registry_path)
        self._lock = threading.RLock()
        self._state: Dict[str, Dict[str, Any]] = {}
        self._load_state()

    def _load_state(self) -> None:
        with self._lock:
            if self.registry_path.exists():
                try:
                    with open(self.registry_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            self._state = data.get("assets", {})
                            return
                except Exception as e:
                    logger.warning("Failed reading %s: %s. Rebuilding defaults.", self.registry_path, e)

            # Initialize with default configuration
            self._state = {k: dict(v) for k, v in DEFAULT_INCUBATOR_CONFIG.items()}
            self._save_state()

    def _save_state(self) -> None:
        with self._lock:
            try:
                self.registry_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "title": "Kalshi Desk Lane 2 Incubator Registry",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "assets": self._state,
                }
                with open(self.registry_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
            except Exception as e:
                logger.error("Failed saving incubator registry to %s: %s", self.registry_path, e)

    def is_locked(self, asset: Union[CryptoAsset, str]) -> bool:
        """Return True if asset is currently quarantined in Incubator and locked from Live trading."""
        key = asset.value if hasattr(asset, "value") else str(asset).upper().strip()
        with self._lock:
            asset_info = self._state.get(key)
            if not asset_info:
                return False
            return bool(asset_info.get("is_locked", False))

    def get_lock_reason(self, asset: Union[CryptoAsset, str]) -> str:
        """Return human-readable lock reason for the asset."""
        key = asset.value if hasattr(asset, "value") else str(asset).upper().strip()
        with self._lock:
            asset_info = self._state.get(key)
            if not asset_info or not asset_info.get("is_locked"):
                return ""
            return str(asset_info.get("lock_reason", "Quarantined in Lane 2 Incubator"))

    def get_status(self, asset: Optional[Union[CryptoAsset, str]] = None) -> Dict[str, Any]:
        """Return status dictionary for a specific asset or all tracked incubator assets."""
        with self._lock:
            if asset:
                key = asset.value if hasattr(asset, "value") else str(asset).upper().strip()
                return dict(self._state.get(key, {}))
            return {k: dict(v) for k, v in self._state.items()}

    def record_cycle_outcome(
        self,
        asset: Union[CryptoAsset, str],
        outcome: str,
        pnl: Union[float, Decimal] = 0.0,
    ) -> bool:
        """Record the outcome of a completed shadow test cycle.

        Automatically certifies and unlocks the asset once target_cycles and
        target_win_rate are met.
        Returns True if the asset was promoted/unlocked on this cycle.
        """
        key = asset.value if hasattr(asset, "value") else str(asset).upper().strip()
        outcome_clean = str(outcome).upper().strip()
        pnl_float = float(pnl)

        with self._lock:
            if key not in self._state:
                return False

            info = self._state[key]
            info["completed_cycles"] = int(info.get("completed_cycles", 0)) + 1
            if outcome_clean == "WIN":
                info["wins"] = int(info.get("wins", 0)) + 1
            elif outcome_clean == "LOSS":
                info["losses"] = int(info.get("losses", 0)) + 1

            info["net_pnl"] = round(float(info.get("net_pnl", 0.0)) + pnl_float, 4)

            total_settled = info["wins"] + info["losses"]
            if total_settled > 0:
                info["current_win_rate"] = round(info["wins"] / total_settled, 4)
            else:
                info["current_win_rate"] = 0.0

            # Check promotion criteria
            target_cycles = int(info.get("target_cycles", 30))
            target_wr = float(info.get("target_win_rate", 0.65))

            promoted = False
            if (
                info["is_locked"]
                and info["completed_cycles"] >= target_cycles
                and info["current_win_rate"] >= target_wr
            ):
                info["is_locked"] = False
                info["status"] = "CERTIFIED"
                info["certified_at"] = datetime.now(timezone.utc).isoformat()
                info["lock_reason"] = (
                    f"Certified by Council & Incubator ({info['completed_cycles']} cycles, "
                    f"{info['current_win_rate'] * 100:.1f}% WR >= {target_wr * 100:.1f}%)"
                )
                promoted = True
                logger.info(
                    "🎉 [INCUBATOR PROMOTION] Asset %s has satisfied certification criteria! Lock automatically released.",
                    key,
                )

            self._save_state()
            return promoted

    def configure_asset(
        self,
        asset: Union[CryptoAsset, str],
        target_cycles: Optional[int] = None,
        target_win_rate: Optional[float] = None,
        strategy: Optional[str] = None,
    ) -> None:
        """Update target thresholds or active strategy for an incubator asset."""
        key = asset.value if hasattr(asset, "value") else str(asset).upper().strip()
        with self._lock:
            if key not in self._state:
                self._state[key] = {
                    "status": "INCUBATOR",
                    "is_locked": True,
                    "strategy": strategy or "QuoLasGoldONNXBot",
                    "target_cycles": target_cycles or 30,
                    "target_win_rate": target_win_rate or 0.85,
                    "completed_cycles": 0,
                    "wins": 0,
                    "losses": 0,
                    "current_win_rate": 0.0,
                    "net_pnl": 0.0,
                    "certified_at": None,
                    "lock_reason": "Incubating in Lane 2",
                    "quarantined_at": datetime.now(timezone.utc).isoformat(),
                }
            else:
                info = self._state[key]
                if target_cycles is not None:
                    info["target_cycles"] = target_cycles
                if target_win_rate is not None:
                    info["target_win_rate"] = target_win_rate
                if strategy is not None:
                    info["strategy"] = strategy
            self._save_state()

    def reset_incubator(self, asset: Union[CryptoAsset, str]) -> None:
        """Reset incubator progress for specified asset."""
        key = asset.value if hasattr(asset, "value") else str(asset).upper().strip()
        with self._lock:
            if key in DEFAULT_INCUBATOR_CONFIG:
                self._state[key] = dict(DEFAULT_INCUBATOR_CONFIG[key])
                self._save_state()


# Module-level singleton
_instance: Optional[IncubatorManager] = None
_instance_lock = threading.Lock()


def get_incubator_manager(registry_path: Union[str, Path] = DEFAULT_REGISTRY_PATH) -> IncubatorManager:
    """Retrieve global thread-safe IncubatorManager singleton."""
    global _instance
    with _instance_lock:
        if _instance is None or _instance.registry_path != Path(registry_path):
            _instance = IncubatorManager(registry_path)
        return _instance

"""Degree-of-Freedom (DoF) Autonomous Patch Governor.

Continuously monitors live 6-trade evaluation batches. The moment a specific failure
code (e.g. ERR_DISPERSION_EXCURSION, ERR_TWAP_PIN_VICTIM, ERR_DOOMED_HOLD_TO_ZERO)
is empirically detected, it arms the corresponding DoF patch to protect subsequent cycles.
When the regime clears and 18 consecutive cycles pass with zero errors, it de-escalates
back to baseline freedom.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kalshi_sim.dof_governor")

_DEFAULT_PATCHES: Dict[str, Any] = {
    "dof_01_vol_moat": {
        "name": "Dynamic Volatility Moat",
        "active": False,
        "error_code": "ERR_DISPERSION_EXCURSION",
        "triggered_in_batch": None,
        "cycles_since_activation": 0,
        "params": {
            "k_vol_mult": 2.0,
            "early_cycle_mult": 2.0,
            "early_tau_threshold": 720.0,
        },
    },
    "dof_02_twap_guard": {
      "name": "60s Trailing TWAP Integral Guard",
      "active": False,
      "error_code": "ERR_TWAP_PIN_VICTIM",
      "triggered_in_batch": None,
      "cycles_since_activation": 0,
      "params": {
          "twap_window_s": 60.0,
          "late_tau_veto_s": 90.0,
      },
    },
    "dof_03_stepped_salvage": {
      "name": "Stepped Liquidity Salvage Floor",
      "active": False,
      "error_code": "ERR_DOOMED_HOLD_TO_ZERO",
      "triggered_in_batch": None,
      "cycles_since_activation": 0,
      "params": {
          "floor_price": "0.10",
          "ofi_urgency_threshold": -0.70,
          "min_tau_salvage_s": 45.0,
      },
    },
    "dof_04_salvage_persistence": {
      "name": "2-Tick Adverse Persistence Filter",
      "active": False,
      "error_code": "ERR_SALVAGE_WHIPSAW",
      "triggered_in_batch": None,
      "cycles_since_activation": 0,
      "params": {
          "persistence_seconds": 3.0,
          "mid_cycle_tau_s": 300.0,
      },
    },
    "dof_05_anti_exhaustion": {
      "name": "Anti-Retail Momentum Exhaustion Gate",
      "active": False,
      "error_code": "ERR_MOMENTUM_EXHAUSTION",
      "triggered_in_batch": None,
      "cycles_since_activation": 0,
      "params": {
          "rsi_ceiling": 80.0,
          "wick_ratio_ceiling": 2.5,
      },
    },
}


class DofPatchGovernor:
    """Manages Degree-of-Freedom patches per asset, auto-arming and de-escalating based on 6-trade batch audits."""

    def __init__(self, state_file: str | Path = "data/active_dof_patches.json") -> None:
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_or_initialize_state()

    def _load_or_initialize_state(self) -> Dict[str, Any]:
        """Load state from disk or initialize with baseline degrees of freedom."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "ETH" in data and "BTC" in data:
                    return data
            except Exception as exc:
                logger.debug("Failed reading DoF state: %s. Reinitializing.", exc)

        initial = {
            "version": "1.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "ETH": json.loads(json.dumps(_DEFAULT_PATCHES)),
            "BTC": json.loads(json.dumps(_DEFAULT_PATCHES)),
        }
        self._save_state(initial)
        return initial

    def _save_state(self, state_data: Optional[Dict[str, Any]] = None) -> None:
        """Persist state atomically to disk."""
        data_to_save = state_data or self.state
        data_to_save["last_updated"] = datetime.now(timezone.utc).isoformat()
        temp_file = self.state_file.with_suffix(".tmp")
        temp_file.write_text(json.dumps(data_to_save, indent=2), encoding="utf-8")
        temp_file.replace(self.state_file)

    def is_patch_active(self, asset: str, patch_id: str) -> bool:
        """Check if a specific DoF patch is currently armed for the given asset."""
        asset_norm = str(asset).upper()
        patches = self.state.get(asset_norm, {})
        patch = patches.get(patch_id, {})
        return bool(patch.get("active", False))

    def get_patch_params(self, asset: str, patch_id: str) -> Dict[str, Any]:
        """Retrieve the parameter configuration of an armed patch."""
        asset_norm = str(asset).upper()
        patches = self.state.get(asset_norm, {})
        patch = patches.get(patch_id, {})
        return patch.get("params", {})

    def get_active_summary(self, asset: str) -> List[str]:
        """Return names of all currently active patches for logging."""
        asset_norm = str(asset).upper()
        patches = self.state.get(asset_norm, {})
        return [f"{pid} ({p.get('name')})" for pid, p in patches.items() if p.get("active")]

    def evaluate_batch(
        self,
        asset: str,
        batch_num: int,
        recent_trades: List[Dict[str, Any]],
        win_rate: float,
    ) -> Dict[str, Any]:
        """Audit the 6-trade evaluation batch for failure codes and trigger DoF patches."""
        asset_norm = str(asset).upper()
        if asset_norm not in self.state:
            self.state[asset_norm] = json.loads(json.dumps(_DEFAULT_PATCHES))

        asset_patches = self.state[asset_norm]
        newly_armed: List[str] = []
        newly_deescalated: List[str] = []

        # Tally failure codes from recent batch
        batch_failure_codes: Dict[str, int] = {}
        for t in recent_trades:
            outcome = str(t.get("outcome", "")).upper()
            if outcome == "LOSS" or float(t.get("pnl", 0.0) or 0.0) < 0.0:
                f_code = t.get("failure_code") or t.get("why") or "UNKNOWN"
                batch_failure_codes[f_code] = batch_failure_codes.get(f_code, 0) + 1

        # Check each patch rule
        for patch_id, patch_data in asset_patches.items():
            target_err = patch_data.get("error_code")
            is_active = patch_data.get("active", False)
            err_count = batch_failure_codes.get(target_err, 0)

            if err_count >= 1:
                # Arm or reinforce patch
                if not is_active:
                    patch_data["active"] = True
                    patch_data["triggered_in_batch"] = batch_num
                    patch_data["cycles_since_activation"] = 0
                    newly_armed.append(patch_id)
                    logger.warning(
                        "🛡️ [DoF GOVERNOR ACTIVATION] Armed %s on %s! Reason: %s detected %d time(s) in Batch #%d.",
                        patch_id, asset_norm, target_err, err_count, batch_num
                    )
                else:
                    # Reset decay counter
                    patch_data["cycles_since_activation"] = 0
            else:
                # Error did not occur in this batch
                if is_active:
                    patch_data["cycles_since_activation"] = patch_data.get("cycles_since_activation", 0) + len(recent_trades)
                    # De-escalation condition: 18 consecutive cycles (3 batches) with zero errors + WR >= 67%
                    if patch_data["cycles_since_activation"] >= 18 and win_rate >= 66.6:
                        patch_data["active"] = False
                        patch_data["triggered_in_batch"] = None
                        patch_data["cycles_since_activation"] = 0
                        newly_deescalated.append(patch_id)
                        logger.info(
                            "🕊️ [DoF GOVERNOR DE-ESCALATION] Disarmed %s on %s. 18 cycles clean with %.1f%% win rate. Restored baseline freedom.",
                            patch_id, asset_norm, win_rate
                        )

        self._save_state()

        return {
            "asset": asset_norm,
            "batch_num": batch_num,
            "newly_armed": newly_armed,
            "newly_deescalated": newly_deescalated,
            "total_active": [pid for pid, p in asset_patches.items() if p.get("active")],
        }


# Global singleton instance
_GLOBAL_GOVERNOR: Optional[DofPatchGovernor] = None


def get_dof_governor() -> DofPatchGovernor:
    """Return the global DofPatchGovernor singleton."""
    global _GLOBAL_GOVERNOR
    if _GLOBAL_GOVERNOR is None:
        _GLOBAL_GOVERNOR = DofPatchGovernor()
    return _GLOBAL_GOVERNOR

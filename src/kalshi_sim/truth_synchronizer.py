"""truth_synchronizer.py — Dynamic Single Source of Truth Parameter Synchronizer

Eliminates the stale in-memory RAM cache bug permanently by ensuring strategy engines:
1. Continuously monitor `data/bot_parameters_domination.json` modification time (mtime).
2. Automatically hot-reload parameters into active strategy engine memory before tick evaluation.
3. Guarantee that user configuration changes are instantly live across disk, RAM, and API state.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("kalshi_sim.truth_synchronizer")

DEFAULT_TRUTH_PATH = Path("data/bot_parameters_domination.json")


class DynamicTruthSynchronizer:
    """Monitors disk parameter files and hot-reloads in-memory parameters dynamically."""

    def __init__(self, truth_path: Path = DEFAULT_TRUTH_PATH) -> None:
        self.truth_path = truth_path
        self._last_mtime: float = 0.0
        self._cached_truth: Dict[str, Any] = {}

    def get_truth_parameters(self, asset: str = "BTC") -> Dict[str, Any]:
        """Reads latest parameters from the Single Source of Truth on disk."""
        if not self.truth_path.exists():
            return {}

        try:
            mtime = os.path.getmtime(self.truth_path)
            if mtime != self._last_mtime or not self._cached_truth:
                data = json.loads(self.truth_path.read_text(encoding="utf-8"))
                self._cached_truth = data
                self._last_mtime = mtime
                logger.debug(f"[TRUTH SYNC] Hot-reloaded parameters from {self.truth_path} (mtime={mtime})")

            merged = dict(self._cached_truth)
            assets_dict = merged.get("assets", {})
            if isinstance(assets_dict, dict) and asset.upper() in assets_dict:
                asset_overrides = assets_dict[asset.upper()]
                if isinstance(asset_overrides, dict):
                    merged.update(asset_overrides)
            return merged
        except Exception as e:
            logger.warning(f"[TRUTH SYNC ERROR] Could not read {self.truth_path}: {e}")
            return self._cached_truth

    def sync_engine(self, engine: Any, asset: str = "BTC") -> bool:
        """Hot-reloads fresh parameters from disk into a target strategy engine instance."""
        if not hasattr(engine, "update_parameters"):
            return False

        truth_params = self.get_truth_parameters(asset=asset)
        if not truth_params:
            return False

        try:
            engine.update_parameters(**truth_params)
            return True
        except Exception as e:
            logger.warning(f"[TRUTH SYNC] Failed hot-reloading engine {engine}: {e}")
            return False


# Global singleton instance
truth_synchronizer = DynamicTruthSynchronizer()

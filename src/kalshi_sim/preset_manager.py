"""Institutional Bot Preset Vault & Configuration Lifecycle Management.

Enables zero-downtime saving, atomic loading/hot-swapping, unloading (reverting to baseline),
and importing/uploading of JSON trading presets with strict pre-flight invariant validation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("kalshi_sim.preset_manager")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PRESETS_DIR = DATA_DIR / "presets"
ACTIVE_PRESET_FILE = DATA_DIR / "active_preset.json"
PARAMS_FILE = DATA_DIR / "bot_parameters_domination.json"
BASELINE_PRESET_ID = "baseline_council_v3.2"


class PresetAuditor:
    """Pre-flight invariant validator for trading presets.
    
    Strictly enforces repository invariants:
    1. Micro-bankroll sizing armor: max_contracts must be <= 1 for all assets.
    2. Limit price ceiling: discount_limit_price must be <= $0.52 (positive expectancy).
    3. Dynamic spot velocity engine: enable_dynamic_spot_velocity must be True.
    """

    @staticmethod
    def validate_preset_dict(preset_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate a preset dictionary against all safety invariants.
        
        Returns (is_valid, list_of_violations).
        """
        violations: List[str] = []

        if not isinstance(preset_data, dict):
            return False, ["Preset must be a valid JSON object."]

        # 1. Check Global Overrides if present
        global_overrides = preset_data.get("global_overrides", {})
        if isinstance(global_overrides, dict):
            max_c = global_overrides.get("max_contracts")
            if max_c is not None and max_c > 1:
                violations.append(
                    f"INVARIANT VETO (Sizing Armor): global max_contracts must be <= 1 (found {max_c})"
                )

        # 2. Check Root Fallback Parameters
        root_max_c = preset_data.get("max_contracts")
        if root_max_c is not None and root_max_c > 1:
            violations.append(
                f"INVARIANT VETO (Sizing Armor): root max_contracts must be <= 1 (found {root_max_c})"
            )

        root_discount = preset_data.get("discount_limit_price")
        if root_discount is not None and root_discount > 0.52:
            violations.append(
                f"INVARIANT VETO (Positive EV): root discount_limit_price must be <= $0.52 (found ${root_discount})"
            )

        # 3. Check Per-Asset Dials
        assets = preset_data.get("assets", {})
        if isinstance(assets, dict):
            for asset_key, dials in assets.items():
                if not isinstance(dials, dict):
                    continue
                
                # Sizing cap
                a_max_c = dials.get("max_contracts")
                if a_max_c is not None and a_max_c > 1:
                    violations.append(
                        f"INVARIANT VETO (Sizing Armor): asset {asset_key} max_contracts must be <= 1 (found {a_max_c})"
                    )

                # Limit price cap
                a_disc = dials.get("discount_limit_price")
                if a_disc is not None and a_disc > 0.52:
                    violations.append(
                        f"INVARIANT VETO (Positive EV): asset {asset_key} discount_limit_price must be <= $0.52 (found ${a_disc})"
                    )

                # Dynamic spot velocity must not be explicitly disabled
                dyn_v = dials.get("enable_dynamic_spot_velocity")
                if dyn_v is False:
                    violations.append(
                        f"INVARIANT VETO (Dynamic Fading): asset {asset_key} enable_dynamic_spot_velocity cannot be disabled"
                    )

        is_valid = len(violations) == 0
        return is_valid, violations


class PresetManager:
    """Manages creation, loading, unloading, and synchronization of trading presets."""

    def __init__(self, presets_dir: Optional[Path] = None, data_dir: Optional[Path] = None) -> None:
        self.data_dir = data_dir or DATA_DIR
        self.presets_dir = presets_dir or (self.data_dir / "presets")
        self.active_preset_file = self.data_dir / "active_preset.json"
        self.params_file = self.data_dir / "bot_parameters_domination.json"
        
        self.presets_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_baseline_preset()
        self._ensure_active_preset_state()

    def _ensure_baseline_preset(self) -> None:
        """Seed the factory default baseline preset if it does not exist."""
        baseline_path = self.presets_dir / f"{BASELINE_PRESET_ID}.json"
        if not baseline_path.exists():
            current_params = self._read_current_params()
            baseline_data = {
                "preset_id": BASELINE_PRESET_ID,
                "preset_name": "Council Baseline v3.2 (Dynamic Fading)",
                "version": "3.2.0",
                "created_at": "2026-09-12T12:00:00Z",
                "author": "Council Certified Baseline",
                "description": "Factory default institutional preset with 4-regime Dynamic Spot Velocity Front-Run, Silas TWAP Gravity, and 51¢ discount cap.",
                "is_council_certified": True,
                "global_overrides": {
                    "asset_mode": current_params.get("asset_mode", "single"),
                    "active_asset": current_params.get("active_asset", "BTC"),
                    "is_armed": current_params.get("is_armed", True),
                    "max_contracts": 1,
                },
                "assets": current_params.get("assets", {}),
            }
            for k, v in current_params.items():
                if k not in ("assets", "global_overrides", "preset_id", "preset_name"):
                    baseline_data[k] = v

            baseline_data["checksum"] = self._compute_checksum(baseline_data)
            with open(baseline_path, "w", encoding="utf-8") as f:
                json.dump(baseline_data, f, indent=2)
            logger.info("Seeded canonical baseline preset to %s", baseline_path)

    def _ensure_active_preset_state(self) -> None:
        """Ensure active_preset.json exists and points to a valid preset."""
        if not self.active_preset_file.exists():
            state = {
                "active_preset_id": BASELINE_PRESET_ID,
                "active_preset_name": "Council Baseline v3.2 (Dynamic Fading)",
                "loaded_at": datetime.now(timezone.utc).isoformat(),
                "is_council_certified": True,
            }
            with open(self.active_preset_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)

    def _read_current_params(self) -> Dict[str, Any]:
        """Read current live parameters from bot_parameters_domination.json."""
        if self.params_file.exists():
            try:
                with open(self.params_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Failed reading %s: %s", self.params_file, e)
        return {}

    def _compute_checksum(self, data: Dict[str, Any]) -> str:
        """Generate a SHA256 checksum for preset configuration integrity."""
        c = copy.deepcopy(data)
        c.pop("checksum", None)
        c.pop("loaded_at", None)
        s = json.dumps(c, sort_keys=True)
        return f"sha256:{hashlib.sha256(s.encode('utf-8')).hexdigest()[:16]}"

    def list_presets(self) -> List[Dict[str, Any]]:
        """Return metadata for all available presets in the vault."""
        active_id = self.get_active_preset_id()
        presets: List[Dict[str, Any]] = []

        for p_file in self.presets_dir.glob("*.json"):
            try:
                with open(p_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                preset_id = data.get("preset_id", p_file.stem)
                presets.append({
                    "preset_id": preset_id,
                    "preset_name": data.get("preset_name", preset_id.replace("_", " ").title()),
                    "version": data.get("version", "1.0.0"),
                    "created_at": data.get("created_at", ""),
                    "author": data.get("author", "Unknown"),
                    "description": data.get("description", ""),
                    "is_council_certified": bool(data.get("is_council_certified", False)),
                    "is_active": (preset_id == active_id),
                    "file_path": str(p_file),
                    "checksum": data.get("checksum", ""),
                })
            except Exception as exc:
                logger.warning("Could not parse preset file %s: %s", p_file, exc)

        presets.sort(
            key=lambda x: (x["is_active"], x["is_council_certified"], x["created_at"]),
            reverse=True,
        )
        return presets

    def get_active_preset_id(self) -> str:
        """Return the currently loaded preset ID."""
        if self.active_preset_file.exists():
            try:
                with open(self.active_preset_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("active_preset_id", BASELINE_PRESET_ID)
            except Exception:
                pass
        return BASELINE_PRESET_ID

    def get_active_preset_metadata(self) -> Dict[str, Any]:
        """Return metadata for the currently loaded active preset."""
        active_id = self.get_active_preset_id()
        preset_file = self.presets_dir / f"{active_id}.json"
        if preset_file.exists():
            try:
                with open(preset_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    "preset_id": active_id,
                    "preset_name": data.get("preset_name", active_id),
                    "author": data.get("author", "Operator"),
                    "description": data.get("description", ""),
                    "is_council_certified": data.get("is_council_certified", False),
                    "checksum": data.get("checksum", ""),
                }
            except Exception:
                pass
        return {
            "preset_id": BASELINE_PRESET_ID,
            "preset_name": "Council Baseline v3.2 (Dynamic Fading)",
            "author": "Council Certified Baseline",
            "is_council_certified": True,
        }

    def save_preset(
        self,
        preset_name: str,
        description: str = "",
        author: str = "Operator",
        custom_params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Snapshot current live parameters into a new named preset."""
        if not preset_name or not preset_name.strip():
            return False, "Preset name cannot be empty.", {}

        clean_slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", preset_name.strip().lower())
        clean_slug = re.sub(r"_+", "_", clean_slug).strip("_")
        timestamp_suffix = datetime.now(timezone.utc).strftime("%y%m%d_%H%M")
        preset_id = f"{clean_slug}_{timestamp_suffix}"

        source_params = custom_params or self._read_current_params()
        if not source_params:
            return False, "No active parameters available to snapshot.", {}

        preset_data: Dict[str, Any] = {
            "preset_id": preset_id,
            "preset_name": preset_name.strip(),
            "version": "1.0.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "author": author.strip(),
            "description": description.strip(),
            "is_council_certified": False,
            "global_overrides": {
                "asset_mode": source_params.get("asset_mode", "single"),
                "active_asset": source_params.get("active_asset", "BTC"),
                "is_armed": source_params.get("is_armed", True),
                "max_contracts": 1,
            },
            "assets": source_params.get("assets", {}),
        }
        for k, v in source_params.items():
            if k not in ("assets", "global_overrides", "preset_id", "preset_name"):
                preset_data[k] = v

        is_valid, violations = PresetAuditor.validate_preset_dict(preset_data)
        if not is_valid:
            error_msg = f"Cannot save preset: {'; '.join(violations)}"
            logger.error(error_msg)
            return False, error_msg, {}

        preset_data["checksum"] = self._compute_checksum(preset_data)
        target_file = self.presets_dir / f"{preset_id}.json"

        try:
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(preset_data, f, indent=2)
            logger.info("Successfully saved preset '%s' to %s", preset_name, target_file)
            return True, f"Preset '{preset_name}' successfully saved.", preset_data
        except Exception as exc:
            logger.error("Failed to write preset file: %s", exc)
            return False, f"Failed writing preset file: {exc}", {}

    def load_preset(self, preset_id: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Atomically load and apply a saved preset into live configuration."""
        preset_file = self.presets_dir / f"{preset_id}.json"
        if not preset_file.exists():
            return False, f"Preset '{preset_id}' not found in vault.", {}

        try:
            with open(preset_file, "r", encoding="utf-8") as f:
                preset_data = json.load(f)
        except Exception as exc:
            return False, f"Error reading preset file: {exc}", {}

        # 1. Pre-flight invariant audit
        is_valid, violations = PresetAuditor.validate_preset_dict(preset_data)
        if not is_valid:
            error_msg = f"Preset failed Pre-Flight Invariant Audit: {'; '.join(violations)}"
            logger.error(error_msg)
            return False, error_msg, {}

        # 2. Extract and format parameters for bot_parameters_domination.json
        new_params = copy.deepcopy(preset_data)
        new_params.pop("preset_id", None)
        new_params.pop("preset_name", None)
        new_params.pop("version", None)
        new_params.pop("created_at", None)
        new_params.pop("author", None)
        new_params.pop("description", None)
        new_params.pop("is_council_certified", None)
        new_params.pop("checksum", None)
        new_params.pop("global_overrides", None)
        new_params["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Hard invariant clamp: micro bankroll sizing must never exceed 1
        new_params["max_contracts"] = 1
        if "assets" in new_params and isinstance(new_params["assets"], dict):
            for a_key in new_params["assets"]:
                new_params["assets"][a_key]["max_contracts"] = 1

        # 3. Write atomically to bot_parameters_domination.json
        tmp_file = self.params_file.with_suffix(".tmp")
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(new_params, f, indent=2)
            tmp_file.replace(self.params_file)
        except Exception as exc:
            return False, f"Failed updating live parameter file: {exc}", {}

        # 4. Update active preset pointer
        active_state = {
            "active_preset_id": preset_id,
            "active_preset_name": preset_data.get("preset_name", preset_id),
            "loaded_at": datetime.now(timezone.utc).isoformat(),
            "is_council_certified": preset_data.get("is_council_certified", False),
            "checksum": preset_data.get("checksum", ""),
        }
        with open(self.active_preset_file, "w", encoding="utf-8") as f:
            json.dump(active_state, f, indent=2)

        logger.info("⚡ [HOT-SWAP APPLIED] Loaded preset '%s' (%s)", preset_data.get("preset_name"), preset_id)
        return True, f"Preset '{preset_data.get('preset_name')}' loaded successfully.", preset_data

    def unload_preset(self) -> Tuple[bool, str, Dict[str, Any]]:
        """Unload current custom preset and revert to Council Baseline."""
        return self.load_preset(BASELINE_PRESET_ID)

    def import_preset_json(self, raw_json_str: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Validate and import an uploaded preset JSON string."""
        try:
            data = json.loads(raw_json_str)
        except Exception as exc:
            return False, f"Malformed JSON: {exc}", {}

        if not isinstance(data, dict):
            return False, "Uploaded file must be a JSON object.", {}

        # Pre-flight audit
        is_valid, violations = PresetAuditor.validate_preset_dict(data)
        if not is_valid:
            error_msg = f"Upload Rejected: {'; '.join(violations)}"
            logger.warning("Preset upload rejected: %s", error_msg)
            return False, error_msg, {}

        preset_name = data.get("preset_name") or data.get("preset_id") or "Imported Preset"
        clean_slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", preset_name.strip().lower())
        clean_slug = re.sub(r"_+", "_", clean_slug).strip("_")
        timestamp_suffix = datetime.now(timezone.utc).strftime("%y%m%d_%H%M")
        preset_id = f"import_{clean_slug}_{timestamp_suffix}"

        data["preset_id"] = preset_id
        data["preset_name"] = str(preset_name).strip()
        data["created_at"] = datetime.now(timezone.utc).isoformat()
        data["is_council_certified"] = False
        data["checksum"] = self._compute_checksum(data)

        data["max_contracts"] = 1
        if "assets" in data and isinstance(data["assets"], dict):
            for a_key in data["assets"]:
                data["assets"][a_key]["max_contracts"] = 1

        target_file = self.presets_dir / f"{preset_id}.json"
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info("Successfully imported preset '%s' as %s", preset_name, preset_id)
            return True, f"Preset '{preset_name}' successfully imported to vault.", data
        except Exception as exc:
            return False, f"Failed saving imported preset: {exc}", {}

    def export_preset(self, preset_id: str) -> Optional[Dict[str, Any]]:
        """Return the raw JSON dictionary of a preset for downloading/exporting."""
        preset_file = self.presets_dir / f"{preset_id}.json"
        if not preset_file.exists():
            return None
        try:
            with open(preset_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("Error exporting preset %s: %s", preset_id, exc)
            return None

    def delete_preset(self, preset_id: str) -> Tuple[bool, str]:
        """Delete a custom preset from the vault (cannot delete baseline)."""
        if preset_id == BASELINE_PRESET_ID:
            return False, "Cannot delete the Council Certified Baseline preset."

        if preset_id == self.get_active_preset_id():
            return False, "Cannot delete the currently active preset. Unload or switch presets first."

        target_file = self.presets_dir / f"{preset_id}.json"
        if not target_file.exists():
            return False, f"Preset '{preset_id}' does not exist."

        try:
            target_file.unlink()
            logger.info("Deleted preset file %s", target_file)
            return True, f"Preset '{preset_id}' deleted."
        except Exception as exc:
            return False, f"Failed deleting preset file: {exc}"


_preset_manager: Optional[PresetManager] = None


def get_preset_manager() -> PresetManager:
    """Return singleton instance of PresetManager."""
    global _preset_manager
    if _preset_manager is None:
        _preset_manager = PresetManager()
    return _preset_manager

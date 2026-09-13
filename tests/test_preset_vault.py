"""Tests for Bot Preset Vault & Configuration Lifecycle Management.

Verifies:
1. PresetAuditor rejects invariant violations (max_contracts > 1, discount_limit_price > 0.52, dynamic velocity disabled)
2. Baseline seeding (baseline_council_v3.2.json)
3. Preset saving, loading, unloading, importing, exporting, and deleting
4. Safe hot-swapping into bot parameters file
"""

import json
from pathlib import Path
import pytest

from kalshi_sim.preset_manager import (
    BASELINE_PRESET_ID,
    PresetAuditor,
    PresetManager,
)


@pytest.fixture
def temp_vault(tmp_path):
    """Fixture providing an isolated PresetManager in a temporary directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    presets_dir = data_dir / "presets"
    
    # Seed mock bot_parameters_domination.json
    params_file = data_dir / "bot_parameters_domination.json"
    mock_params = {
        "active_asset": "BTC",
        "asset_mode": "single",
        "is_armed": True,
        "max_contracts": 1,
        "discount_limit_price": 0.51,
        "enable_dynamic_spot_velocity": True,
        "velocity_z_score_threshold": 2.5,
        "assets": {
            "BTC": {
                "discount_limit_price": 0.51,
                "max_contracts": 1,
                "enable_dynamic_spot_velocity": True,
                "velocity_z_score_threshold": 2.5,
            }
        }
    }
    with open(params_file, "w", encoding="utf-8") as f:
        json.dump(mock_params, f, indent=2)

    manager = PresetManager(presets_dir=presets_dir, data_dir=data_dir)
    return manager


def test_baseline_preset_seeded(temp_vault):
    """Verify that baseline_council_v3.2 is automatically seeded upon initialization."""
    presets = temp_vault.list_presets()
    assert len(presets) >= 1
    baseline = next((p for p in presets if p["preset_id"] == BASELINE_PRESET_ID), None)
    assert baseline is not None
    assert baseline["is_council_certified"] is True
    assert baseline["is_active"] is True
    assert temp_vault.get_active_preset_id() == BASELINE_PRESET_ID


def test_auditor_rejects_sizing_armor_violation():
    """Verify that any preset attempting max_contracts > 1 is strictly rejected."""
    bad_preset = {
        "preset_name": "Rogue Whale Sizing",
        "max_contracts": 10,  # Rogue!
        "discount_limit_price": 0.50,
        "assets": {
            "BTC": {"max_contracts": 1, "discount_limit_price": 0.50}
        }
    }
    is_valid, violations = PresetAuditor.validate_preset_dict(bad_preset)
    assert not is_valid
    assert any("Sizing Armor" in v for v in violations)

    # In asset dict
    bad_asset_preset = {
        "preset_name": "Rogue Asset Sizing",
        "max_contracts": 1,
        "assets": {
            "BTC": {"max_contracts": 5, "discount_limit_price": 0.50}  # Rogue!
        }
    }
    is_valid2, violations2 = PresetAuditor.validate_preset_dict(bad_asset_preset)
    assert not is_valid2
    assert any("Sizing Armor" in v for v in violations2)


def test_auditor_rejects_limit_price_ceiling_violation():
    """Verify that any preset setting discount_limit_price > $0.52 is strictly rejected."""
    bad_price_preset = {
        "preset_name": "Negative EV Chaser",
        "max_contracts": 1,
        "discount_limit_price": 0.75,  # Rogue price > 52¢!
        "assets": {
            "BTC": {"max_contracts": 1, "discount_limit_price": 0.50}
        }
    }
    is_valid, violations = PresetAuditor.validate_preset_dict(bad_price_preset)
    assert not is_valid
    assert any("Positive EV" in v for v in violations)


def test_auditor_rejects_disabling_dynamic_spot_velocity():
    """Verify that explicitly disabling dynamic spot velocity is rejected."""
    bad_fading_preset = {
        "preset_name": "Static Noise Dumper",
        "max_contracts": 1,
        "discount_limit_price": 0.50,
        "assets": {
            "BTC": {
                "max_contracts": 1,
                "discount_limit_price": 0.50,
                "enable_dynamic_spot_velocity": False,  # Rogue!
            }
        }
    }
    is_valid, violations = PresetAuditor.validate_preset_dict(bad_fading_preset)
    assert not is_valid
    assert any("Dynamic Fading" in v for v in violations)


def test_save_and_load_custom_preset(temp_vault):
    """Verify creating a new preset snapshot and atomically loading it."""
    # 1. Save new snapshot
    success, msg, data = temp_vault.save_preset(
        preset_name="Aggressive Vol Momentum",
        description="Tuned for 3σ momentum expansions",
        author="Trader Alice",
    )
    assert success is True
    preset_id = data["preset_id"]
    assert "aggressive_vol_momentum" in preset_id

    # Verify preset appears in vault list
    presets = temp_vault.list_presets()
    saved = next((p for p in presets if p["preset_id"] == preset_id), None)
    assert saved is not None
    assert saved["author"] == "Trader Alice"

    # 2. Load the custom preset
    load_success, load_msg, load_data = temp_vault.load_preset(preset_id)
    assert load_success is True
    assert temp_vault.get_active_preset_id() == preset_id

    # 3. Unload back to baseline
    unload_success, unload_msg, _ = temp_vault.unload_preset()
    assert unload_success is True
    assert temp_vault.get_active_preset_id() == BASELINE_PRESET_ID


def test_import_uploaded_preset_json(temp_vault):
    """Verify uploading/importing a valid preset JSON string."""
    valid_json = json.dumps({
        "preset_name": "Desk Weekend Defensive",
        "description": "Tight spreads for illiquid weekend sessions",
        "max_contracts": 1,
        "discount_limit_price": 0.49,
        "enable_dynamic_spot_velocity": True,
        "assets": {
            "BTC": {
                "discount_limit_price": 0.49,
                "max_contracts": 1,
                "enable_dynamic_spot_velocity": True,
            }
        }
    })

    success, msg, data = temp_vault.import_preset_json(valid_json)
    assert success is True
    assert "desk_weekend_defensive" in data["preset_id"]

    # Loading the imported preset succeeds
    load_ok, _, _ = temp_vault.load_preset(data["preset_id"])
    assert load_ok is True
    assert temp_vault.get_active_preset_id() == data["preset_id"]


def test_import_invalid_or_malformed_json(temp_vault):
    """Verify that malformed or invariant-violating uploads are cleanly rejected."""
    # Malformed syntax
    bad_json = "{ invalid_json_syntax "
    ok, msg, _ = temp_vault.import_preset_json(bad_json)
    assert ok is False
    assert "Malformed JSON" in msg

    # Non-dict JSON
    array_json = json.dumps(["not", "an", "object"])
    ok2, msg2, _ = temp_vault.import_preset_json(array_json)
    assert ok2 is False
    assert "must be a JSON object" in msg2

    # Invariant violating JSON (max_contracts: 50)
    toxic_json = json.dumps({
        "preset_name": "Toxic Kamikaze Preset",
        "max_contracts": 50,
        "discount_limit_price": 0.50,
    })
    ok3, msg3, _ = temp_vault.import_preset_json(toxic_json)
    assert ok3 is False
    assert "Upload Rejected" in msg3


def test_delete_protection_for_baseline_and_active(temp_vault):
    """Verify that deleting the baseline or the active preset is strictly blocked."""
    # Cannot delete baseline
    del_baseline, msg_b = temp_vault.delete_preset(BASELINE_PRESET_ID)
    assert del_baseline is False
    assert "Cannot delete the Council Certified Baseline" in msg_b

    # Create a custom preset and load it
    _, _, custom = temp_vault.save_preset("Temporary Test Preset")
    temp_vault.load_preset(custom["preset_id"])
    assert temp_vault.get_active_preset_id() == custom["preset_id"]

    # Cannot delete active preset
    del_active, msg_a = temp_vault.delete_preset(custom["preset_id"])
    assert del_active is False
    assert "Cannot delete the currently active preset" in msg_a

    # Unload back to baseline, then deletion of custom preset succeeds
    temp_vault.unload_preset()
    del_ok, _ = temp_vault.delete_preset(custom["preset_id"])
    assert del_ok is True

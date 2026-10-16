"""Unit tests for Degree-of-Freedom (DoF) Autonomous Patch Governor.

Verifies:
1. Baseline degrees of freedom (all patches inactive).
2. Autonomous arming on 6-trade batch error fingerprint detection.
3. Patch persistence and parameters retrieval.
4. Autonomous de-escalation back to baseline freedom after 18 clean cycles with >=66.6% win rate.
"""

import json
from pathlib import Path
import pytest

from kalshi_sim.ml.dof_governor import DofPatchGovernor, get_dof_governor


@pytest.fixture
def temp_dof_governor(tmp_path: Path) -> DofPatchGovernor:
    """Provide an isolated DofPatchGovernor with a temporary state file."""
    state_file = tmp_path / "test_active_dof_patches.json"
    return DofPatchGovernor(state_file=state_file)


def test_baseline_state_all_inactive(temp_dof_governor: DofPatchGovernor) -> None:
    """Verify that initially all patches for both ETH and BTC are inactive (maximum freedom)."""
    for asset in ["ETH", "BTC"]:
        assert not temp_dof_governor.is_patch_active(asset, "dof_01_vol_moat")
        assert not temp_dof_governor.is_patch_active(asset, "dof_02_twap_guard")
        assert not temp_dof_governor.is_patch_active(asset, "dof_03_stepped_salvage")
        assert not temp_dof_governor.is_patch_active(asset, "dof_04_salvage_persistence")
        assert not temp_dof_governor.is_patch_active(asset, "dof_05_anti_exhaustion")
        assert temp_dof_governor.get_active_summary(asset) == []


def test_arm_dof_01_on_dispersion_excursion(temp_dof_governor: DofPatchGovernor) -> None:
    """Verify that ERR_DISPERSION_EXCURSION arms dof_01_vol_moat on ETH."""
    batch_trades = [
        {"outcome": "WIN", "pnl": 0.50},
        {"outcome": "WIN", "pnl": 0.50},
        {"outcome": "WIN", "pnl": 0.50},
        {"outcome": "WIN", "pnl": 0.50},
        {"outcome": "WIN", "pnl": 0.50},
        {"outcome": "LOSS", "pnl": -0.50, "failure_code": "ERR_DISPERSION_EXCURSION"},
    ]

    res = temp_dof_governor.evaluate_batch(
        asset="ETH",
        batch_num=1,
        recent_trades=batch_trades,
        win_rate=83.3,
    )

    assert "dof_01_vol_moat" in res["newly_armed"]
    assert temp_dof_governor.is_patch_active("ETH", "dof_01_vol_moat")
    assert not temp_dof_governor.is_patch_active("BTC", "dof_01_vol_moat")  # Isolated per asset

    # Params should be accessible
    params = temp_dof_governor.get_patch_params("ETH", "dof_01_vol_moat")
    assert params.get("k_vol_mult") == 2.0


def test_arm_all_error_codes(temp_dof_governor: DofPatchGovernor) -> None:
    """Verify all 5 error codes map to their respective DoF patches."""
    error_mapping = {
        "ERR_DISPERSION_EXCURSION": "dof_01_vol_moat",
        "ERR_TWAP_PIN_VICTIM": "dof_02_twap_guard",
        "ERR_DOOMED_HOLD_TO_ZERO": "dof_03_stepped_salvage",
        "ERR_SALVAGE_WHIPSAW": "dof_04_salvage_persistence",
        "ERR_MOMENTUM_EXHAUSTION": "dof_05_anti_exhaustion",
    }

    for err_code, expected_patch in error_mapping.items():
        batch = [
            {"outcome": "LOSS", "pnl": -0.40, "failure_code": err_code},
        ]
        res = temp_dof_governor.evaluate_batch(
            asset="BTC",
            batch_num=10,
            recent_trades=batch,
            win_rate=50.0,
        )
        assert expected_patch in res["newly_armed"]
        assert temp_dof_governor.is_patch_active("BTC", expected_patch)


def test_deescalation_after_18_cycles_clean(temp_dof_governor: DofPatchGovernor) -> None:
    """Verify that after 18 clean cycles with WR >= 66.6%, patch de-escalates to baseline freedom."""
    # Step 1: Arm dof_02_twap_guard on ETH
    arm_batch = [{"outcome": "LOSS", "pnl": -0.45, "failure_code": "ERR_TWAP_PIN_VICTIM"}]
    temp_dof_governor.evaluate_batch("ETH", 1, arm_batch, win_rate=50.0)
    assert temp_dof_governor.is_patch_active("ETH", "dof_02_twap_guard")

    clean_batch_6 = [
        {"outcome": "WIN", "pnl": 0.50},
        {"outcome": "WIN", "pnl": 0.50},
        {"outcome": "WIN", "pnl": 0.50},
        {"outcome": "WIN", "pnl": 0.50},
        {"outcome": "WIN", "pnl": 0.50},
        {"outcome": "LOSS", "pnl": -0.40, "failure_code": "OTHER_ERR"},
    ]

    # Batch 2: 6 cycles clean (total 6) -> Still active
    res2 = temp_dof_governor.evaluate_batch("ETH", 2, clean_batch_6, win_rate=83.3)
    assert temp_dof_governor.is_patch_active("ETH", "dof_02_twap_guard")
    assert "dof_02_twap_guard" not in res2["newly_deescalated"]

    # Batch 3: 6 cycles clean (total 12) -> Still active
    res3 = temp_dof_governor.evaluate_batch("ETH", 3, clean_batch_6, win_rate=83.3)
    assert temp_dof_governor.is_patch_active("ETH", "dof_02_twap_guard")
    assert "dof_02_twap_guard" not in res3["newly_deescalated"]

    # Batch 4: 6 cycles clean (total 18) -> De-escalates!
    res4 = temp_dof_governor.evaluate_batch("ETH", 4, clean_batch_6, win_rate=83.3)
    assert not temp_dof_governor.is_patch_active("ETH", "dof_02_twap_guard")
    assert "dof_02_twap_guard" in res4["newly_deescalated"]
    assert temp_dof_governor.get_active_summary("ETH") == []

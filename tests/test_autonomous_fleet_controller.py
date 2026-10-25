"""Unit tests for AutonomousFleetController."""

from decimal import Decimal
from pathlib import Path
import pytest

from kalshi_sim.autonomous_fleet_controller import AutonomousFleetController, FleetState


def test_autonomous_fleet_controller_initialization(tmp_path: Path) -> None:
    """Test AutonomousFleetController initializes with clean state and default fleet."""
    controller = AutonomousFleetController(root_dir=tmp_path)
    assert "BTC" in controller.states
    assert "ETH" in controller.states
    assert "BNB" in controller.states


def test_autonomous_fleet_controller_verdict_logic(tmp_path: Path) -> None:
    """Test health evaluation logic produces type-safe action verdicts."""
    controller = AutonomousFleetController(root_dir=tmp_path)
    verdict = controller.assess_asset_health("BTC")
    assert verdict.asset == "BTC"
    assert verdict.action in (FleetState.RUNNING, FleetState.PAUSED, FleetState.STOPPED, FleetState.ASSESSING)
    assert isinstance(verdict.pnl, Decimal)


def test_autonomous_fleet_sync(tmp_path: Path) -> None:
    """Verify sync_fleet_states correctly evaluates all assets in the fleet."""
    controller = AutonomousFleetController(root_dir=tmp_path)
    verdicts = controller.sync_fleet_states()
    assert len(verdicts) == 3
    assert set(verdicts.keys()) == {"BTC", "ETH", "BNB"}

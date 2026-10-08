"""Unit tests for Project Odin Watch-and-Learn Volatility Harvester (Lane 2 Shadow Fleet).

Verifies:
1. Zero Real Capital Risk (Jackal Invariant: hard isolation, zero live orders).
2. Zero Float Financial Math (Directive 1: Decimal precision on all prices, fees, PnLs).
3. Volatility Triggering (only fires on extreme VPIN >= 0.70 or large vetoed shocks).
4. Settlement & Causal Ground-Truth Logging to ContinuousExperienceBuffer.
5. Telemetry endpoint data validity.
"""

from decimal import Decimal
import pytest

from kalshi_sim.ml.experience_buffer import ContinuousExperienceBuffer
from kalshi_sim.ml.odin_shadow_harvester import (
    OdinObservation,
    OdinShadowHarvester,
    OdinShadowPosition,
)


def test_odin_jackal_invariant_zero_live_orders():
    """Verify Odin module has zero imports of live order client placement."""
    import inspect
    from kalshi_sim.ml import odin_shadow_harvester

    source = inspect.getsource(odin_shadow_harvester)
    assert "place_order" not in source
    assert "KalshiLiveOrderClient" not in source
    assert "order_client" not in source


def test_odin_zero_float_math():
    """Verify that all financial calculations in Odin use Decimal exclusively."""
    harvester = OdinShadowHarvester(vpin_harvest_threshold=0.70)

    pos = harvester.observe_and_harvest(
        ticker="KXBTC15M-26OCT08-T95000",
        cycle_id="cycle_vol_001",
        spot_price=Decimal("95060.00"),
        strike_price=Decimal("95000.00"),
        vpin=0.82,
        time_to_expiry_s=420.0,
        live_bot_vetoed=True,
        yes_ask=Decimal("0.58"),
        no_ask=Decimal("0.44"),
    )

    assert pos is not None
    assert isinstance(pos.entry_price, Decimal)
    assert isinstance(pos.taker_fee, Decimal)
    assert isinstance(pos.spot_diff, Decimal)
    assert pos.taker_fee > Decimal("0.00")


def test_odin_ignores_benign_markets():
    """Verify Odin remains dormant when volatility is low/normal (VPIN < 0.70)."""
    harvester = OdinShadowHarvester(vpin_harvest_threshold=0.70)

    # Benign tick: low VPIN, small spot diff
    pos = harvester.observe_and_harvest(
        ticker="KXBTC15M-26OCT08-T95000",
        cycle_id="cycle_calm_001",
        spot_price=Decimal("95005.00"),
        strike_price=Decimal("95000.00"),
        vpin=0.25,
        time_to_expiry_s=600.0,
        live_bot_vetoed=False,
    )
    assert pos is None
    assert harvester.total_shadow_trades == 0


def test_odin_harvests_extreme_volatility_and_settles_win(tmp_path):
    """Verify Odin triggers on extreme VPIN and settles a winning YES trade."""
    buffer = ContinuousExperienceBuffer(max_buffer_size=50, history_file=tmp_path / "empty.json")
    harvester = OdinShadowHarvester(experience_buffer=buffer, vpin_harvest_threshold=0.70)

    # Extreme volatility burst (spot exploded $45 above strike)
    pos = harvester.observe_and_harvest(
        ticker="KXBTC15M-26OCT08-T95000",
        cycle_id="cycle_extreme_001",
        spot_price=Decimal("95045.00"),
        strike_price=Decimal("95000.00"),
        vpin=0.88,
        time_to_expiry_s=300.0,
        live_bot_vetoed=True,
        yes_ask=Decimal("0.62"),
    )

    assert pos is not None
    assert pos.side == "yes"
    assert pos.strategy_mode == "volatility_breakout"

    # Settle at expiration above strike -> WIN
    settled_pos = harvester.record_settlement(
        cycle_id="cycle_extreme_001",
        settlement_spot=Decimal("95050.00"),
        strike_price=Decimal("95000.00"),
    )

    assert settled_pos is not None
    assert settled_pos.outcome == "win"
    assert settled_pos.net_pnl > Decimal("0.00")
    assert harvester.total_shadow_wins == 1
    assert harvester.total_shadow_losses == 0

    # Verify ground-truth logged to ContinuousExperienceBuffer
    assert len(buffer.experiences) == 1
    exp = buffer.experiences[0]
    assert exp.execution_mode == "shadow_odin"
    assert exp.outcome == "win"


def test_odin_harvests_extreme_volatility_and_logs_causal_loss(tmp_path):
    """Verify Odin correctly classifies causal loss (EXTREME_VOLATILITY_SWEEP) on failure."""
    buffer = ContinuousExperienceBuffer(max_buffer_size=50, history_file=tmp_path / "empty.json")
    harvester = OdinShadowHarvester(experience_buffer=buffer, vpin_harvest_threshold=0.70)

    # Volatility burst takes YES, but market reverses
    pos = harvester.observe_and_harvest(
        ticker="KXBTC15M-26OCT08-T95000",
        cycle_id="cycle_extreme_002",
        spot_price=Decimal("95040.00"),
        strike_price=Decimal("95000.00"),
        vpin=0.79,
        time_to_expiry_s=250.0,
        live_bot_vetoed=True,
        yes_ask=Decimal("0.60"),
    )

    assert pos is not None
    assert pos.side == "yes"

    # Settle below strike -> LOSS
    settled_pos = harvester.record_settlement(
        cycle_id="cycle_extreme_002",
        settlement_spot=Decimal("94980.00"),
        strike_price=Decimal("95000.00"),
    )

    assert settled_pos is not None
    assert settled_pos.outcome == "loss"
    assert settled_pos.net_pnl < Decimal("0.00")
    assert harvester.total_shadow_losses == 1

    # Verify experience buffer logged EXTREME_VOLATILITY_SWEEP
    assert len(buffer.experiences) == 1
    exp = buffer.experiences[0]
    assert exp.execution_mode == "shadow_odin"
    assert exp.outcome == "loss"
    assert exp.loss_cause == "EXTREME_VOLATILITY_SWEEP"


def test_odin_telemetry():
    """Verify telemetry dictionary structure for API and UI rendering."""
    harvester = OdinShadowHarvester(vpin_harvest_threshold=0.75)
    telemetry = harvester.get_telemetry()

    assert telemetry["name"] == "Project Odin Shadow Volatility Harvester"
    assert telemetry["lane"] == "Lane 2 Shadow (Simulation)"
    assert telemetry["harvest_vpin_threshold"] == 0.75
    assert "total_shadow_trades" in telemetry
    assert "total_shadow_pnl" in telemetry

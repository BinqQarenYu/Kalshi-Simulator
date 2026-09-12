"""Unit tests for LiveCoordinator anti-wash trading shield."""

import json
from pathlib import Path
import time
import pytest

from kalshi_sim.live_coordinator import LiveCoordinator


@pytest.fixture
def temp_coordinator(tmp_path: Path) -> LiveCoordinator:
    coord_file = tmp_path / "test_coordination.json"
    return LiveCoordinator(coord_path=coord_file)


def test_first_mover_permission(temp_coordinator: LiveCoordinator):
    is_ok, reason = temp_coordinator.check_trade_permission(
        ticker="KXBTC15M-TEST-1",
        proposed_side="yes",
        bot_id="dominion",
        requested_contracts=1,
        is_live=False,
    )
    assert is_ok is True
    assert "FIRST_MOVER" in reason


def test_anti_wash_trading_opposing_veto(temp_coordinator: LiveCoordinator):
    ticker = "KXBTC15M-TEST-2"
    # Dominion records YES
    temp_coordinator.record_trade(
        ticker=ticker,
        side="yes",
        contracts=1,
        price=0.48,
        bot_id="dominion",
    )

    # ONNX tries to trade NO on the same ticker -> MUST BE VETOED
    is_ok, reason = temp_coordinator.check_trade_permission(
        ticker=ticker,
        proposed_side="no",
        bot_id="the_onnx_strategy",
        requested_contracts=1,
        is_live=False,
    )
    assert is_ok is False
    assert "ANTI-WASH TRADING VETO" in reason
    assert "dominion" in reason


def test_same_direction_cooperative_allowance(temp_coordinator: LiveCoordinator):
    ticker = "KXBTC15M-TEST-3"
    # Dominion records YES (1 contract)
    temp_coordinator.record_trade(
        ticker=ticker,
        side="yes",
        contracts=1,
        price=0.48,
        bot_id="dominion",
    )

    # ONNX also wants YES (1 contract) -> Allowed (1 + 1 = 2 <= 2)
    is_ok, reason = temp_coordinator.check_trade_permission(
        ticker=ticker,
        proposed_side="yes",
        bot_id="the_onnx_strategy",
        requested_contracts=1,
        is_live=False,
    )
    assert is_ok is True
    assert "COOPERATIVE" in reason

    # Record ONNX's trade
    temp_coordinator.record_trade(
        ticker=ticker,
        side="yes",
        contracts=1,
        price=0.49,
        bot_id="the_onnx_strategy",
    )

    # 3rd contract proposed -> EXCEEDS CAP OF 2
    is_ok_3, reason_3 = temp_coordinator.check_trade_permission(
        ticker=ticker,
        proposed_side="yes",
        bot_id="third_bot",
        requested_contracts=1,
        is_live=False,
    )
    assert is_ok_3 is False
    assert "COMBINED EXPOSURE CAP VETO" in reason_3


def test_cycle_expiry_reset(temp_coordinator: LiveCoordinator):
    ticker = "KXBTC15M-TEST-4"
    past_ts = time.time() - 10.0
    temp_coordinator.record_trade(
        ticker=ticker,
        side="yes",
        contracts=1,
        price=0.48,
        bot_id="dominion",
        expiry_ts=past_ts,
    )

    # Since expiry_ts is in the past, NO should now be permitted because cycle expired
    is_ok, reason = temp_coordinator.check_trade_permission(
        ticker=ticker,
        proposed_side="no",
        bot_id="the_onnx_strategy",
        requested_contracts=1,
        is_live=False,
    )
    assert is_ok is True
    assert "EXPIRED" in reason

"""Unit tests for the unified KalshiWebEmulator engine."""

import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from kalshi_sim.schemas import Timeframe
from kalshi_sim.web_emulator import KalshiWebEmulator


def test_web_emulator_init_and_snapshot_structure():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        emulator = KalshiWebEmulator(
            starting_capital=Decimal("100.00"),
            mode="live",
            data_dir=tmp_dir,
            timeframe=Timeframe.FIFTEEN_MIN,
        )

        snap = emulator.get_web_snapshot()
        assert "timestamp" in snap
        assert "market" in snap
        assert "chart" in snap
        assert "trade_tape" in snap
        assert "orderbook_ladder" in snap
        assert "ai_signals" in snap
        assert "portfolio" in snap
        assert "memory_profile" in snap
        assert "settings" in snap

        assert snap["market"]["series"] == "KXBTC15M"
        assert snap["market"]["target_strike_str"] == "$77,453.12"
        assert snap["portfolio"]["balance"] == 100.0
        assert snap["settings"]["mode"] == "live"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_web_emulator_step_progression():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        emulator = KalshiWebEmulator(starting_capital=Decimal("100.00"), data_dir=tmp_dir)

        # Advance step with new spot BTC price
        new_price = Decimal("79200.50")
        snap = emulator.step(new_spot_price=new_price)

        assert snap["market"]["current_btc_price"] == 79200.50
        assert len(snap["chart"]) > 0
        assert snap["chart"][-1]["price"] == 79200.50
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_web_emulator_order_execution_and_tape():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        emulator = KalshiWebEmulator(starting_capital=Decimal("100.00"), data_dir=tmp_dir)

        # Place YES limit order for 5 contracts @ $0.48
        resp = emulator.execute_order(
            side="yes",
            size=5,
            limit_price=0.48,
            order_type="limit",
        )
        assert resp.success is True
        assert resp.count == 5

        snap = emulator.get_web_snapshot()
        assert len(snap["trade_tape"]) >= 1
        assert snap["trade_tape"][-1]["side"] == "yes"
        assert snap["trade_tape"][-1]["contracts"] == 5
        assert snap["portfolio"]["balance"] < 100.0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_web_emulator_reset_and_timeframe_switch():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        emulator = KalshiWebEmulator(starting_capital=Decimal("100.00"), data_dir=tmp_dir)
        emulator.execute_order(side="no", size=10, limit_price=0.50)

        # Reset capital
        emulator.reset_portfolio(Decimal("100.00"))
        snap = emulator.get_web_snapshot()
        assert snap["portfolio"]["balance"] == 100.0
        assert len(snap["trade_tape"]) == 0

        # Switch timeframe
        emulator.set_timeframe("5m")
        snap5m = emulator.get_web_snapshot()
        assert snap5m["settings"]["timeframe"] == "5m"
        assert snap5m["market"]["series"] == "KXBTC5M"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

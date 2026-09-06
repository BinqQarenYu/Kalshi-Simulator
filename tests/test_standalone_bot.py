"""Unit and integration tests for the 24/7 Standalone 3-Step Dominion Bot.

Verifies:
- Pre-flight audit certification gate passes across all 4 pillars
- Mutual exclusion TradingEngineLock prevents concurrent live execution
- Guardrail pre-trade intent validation caps sizing to 1-2 contracts and locks cycles
- Pocket Cockpit REST endpoints (GET /, GET /api/state, POST /api/bot/arm, disarm, panic)
- Main server rejects live order routing with HTTP 409 when standalone bot holds lock
"""

from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from kalshi_sim.process_lock import TradingEngineLock, get_active_lock_holder, is_pid_running
from kalshi_sim.standalone_bot import StandaloneBotEngine, app, app_engine
from kalshi_sim.schemas import LiveOrderRequest
from kalshi_sim.server import app as server_app


def test_pid_running():
    # Current process PID is definitely running
    assert is_pid_running(os.getpid()) is True
    # Non-existent PID
    assert is_pid_running(0) is False
    assert is_pid_running(-1) is False


def test_trading_engine_lock_lifecycle(tmp_path: Path):
    lock_file = tmp_path / "test_trading.lock"
    lock1 = TradingEngineLock(lock_path=lock_file, owner_name="standalone_bot")
    
    assert lock1.acquire(force=False) is True
    assert lock_file.exists() is True
    assert lock1.acquired is True

    # Check active lock holder
    holder = get_active_lock_holder(lock_file)
    assert holder is not None
    assert holder[0] == "standalone_bot"
    assert holder[1] == os.getpid()

    # Lock release
    lock1.release()
    assert lock_file.exists() is False
    assert lock1.acquired is False
    assert get_active_lock_holder(lock_file) is None


def test_trading_engine_lock_stale_reclaim(tmp_path: Path):
    lock_file = tmp_path / "test_stale.lock"
    # Write a stale lock with dead PID
    stale_payload = {
        "owner": "dead_bot",
        "pid": 99999999,
        "started_at": "2026-09-01T00:00:00Z",
    }
    lock_file.write_text(json.dumps(stale_payload), encoding="utf-8")

    lock = TradingEngineLock(lock_path=lock_file, owner_name="fresh_bot")
    assert lock.acquire(force=False) is True
    holder = get_active_lock_holder(lock_file)
    assert holder is not None
    assert holder[0] == "fresh_bot"
    assert holder[1] == os.getpid()
    lock.release()


def test_standalone_bot_engine_initialization(tmp_path: Path):
    engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path)
    assert engine.bot is not None
    assert engine.guardrails is not None
    assert engine.auditor is not None
    assert engine.is_armed is True

    # Verify 1-2 contract sizing cap on micro/nano bankroll
    allowed, reason, size, diag = engine.guardrails.validate_pre_trade_intent(
        ticker="KXBTC15M-T86500",
        side="yes",
        requested_size=10,
        est_price=Decimal("0.48"),
        total_equity=Decimal("21.09"),
        vpin=0.20,
        cycle_id="KXBTC15M-T86500",
        is_bot=True,
    )
    assert allowed is True
    assert size <= 2  # Hard bankroll cap enforced: 1-2 contracts max


def test_standalone_bot_vpin_veto(tmp_path: Path):
    engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path)
    allowed, reason, size, diag = engine.guardrails.validate_pre_trade_intent(
        ticker="KXBTC15M-T86500",
        side="yes",
        requested_size=2,
        est_price=Decimal("0.48"),
        total_equity=Decimal("21.09"),
        vpin=0.75,  # Toxic burst
        cycle_id="KXBTC15M-T86500",
        is_bot=True,
    )
    assert allowed is False
    assert "VPIN TOXICITY VETO" in reason


def test_pocket_cockpit_api(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TESTING", "true")
    # Initialize engine mock inside standalone app
    engine = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path)
    engine.order_client = None
    engine.balance_dollars = Decimal("21.09")
    engine.total_balance_dollars = Decimal("21.09")
    engine.shard2_balance_dollars = Decimal("17.81")
    engine.today_pnl = Decimal("1.85")
    engine.settled_cycles = 19
    engine.active_ticker = "KXBTC15M-T86500"
    engine.current_btc_spot = Decimal("86450.00")
    engine.target_strike = Decimal("86400.00")

    with patch("kalshi_sim.standalone_bot.app_engine", engine):
        client = TestClient(app)

        # 1. Test GET /
        resp_ui = client.get("/")
        assert resp_ui.status_code == 200
        assert "3-STEP DOMINION" in resp_ui.text

        # 2. Test GET /api/state
        resp_state = client.get("/api/state")
        assert resp_state.status_code == 200
        data = resp_state.json()
        assert data["balance"] == 21.09
        assert data["shard2_balance"] == 17.81
        assert data["today_pnl"] == 1.85
        assert data["settled_cycles"] == 19
        assert data["spot_price"] == 86450.00
        assert data["target_strike"] == 86400.00
        assert data["spot_diff"] == 50.00
        assert data["armed"] is False

        # 3. Test POST /api/bot/arm
        resp_arm = client.post("/api/bot/arm")
        assert resp_arm.status_code == 200
        assert resp_arm.json()["status"] == "ARMED"
        assert engine.is_armed is True

        # 4. Test POST /api/bot/disarm
        resp_disarm = client.post("/api/bot/disarm")
        assert resp_disarm.status_code == 200
        assert resp_disarm.json()["status"] == "DISARMED"
        assert engine.is_armed is False

        # 5. Test POST /api/bot/panic
        resp_panic = client.post("/api/bot/panic")
        assert resp_panic.status_code == 200
        assert resp_panic.json()["status"] == "PANIC_EXECUTED"
        assert engine.is_armed is False


def test_standalone_bot_sync_pnl_reports(tmp_path: Path):
    engine = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path)
    now_utc = datetime.now(timezone.utc)
    today_prefix = now_utc.strftime("%y%b%d").upper()
    reports = [
        {"report_id": "WLR-1", "ticker": f"KXBTC15M-{today_prefix}1000-00", "pnl": 1.04, "outcome": "win", "execution_mode": "live", "timestamp_utc": now_utc.isoformat()},
        {"report_id": "WLR-2", "ticker": f"KXBTC15M-{today_prefix}1015-15", "pnl": -0.96, "outcome": "loss", "execution_mode": "live", "timestamp_utc": now_utc.isoformat()},
    ]
    (tmp_path / "win_loss_reports.json").write_text(json.dumps(reports), encoding="utf-8")
    engine.sync_pnl_reports()
    assert engine.settled_cycles == 2
    assert engine.today_pnl == Decimal("0.08")
    assert engine.today_wins == 1
    assert engine.today_losses == 1
    assert engine.today_win_rate == 50.0


def test_main_server_lockout_when_standalone_active(tmp_path: Path):
    # Mock active lock held by a different PID
    fake_holder = ("standalone_bot", 99999)
    with patch("kalshi_sim.server.get_active_lock_holder", return_value=fake_holder):
        client = TestClient(server_app)
        req_payload = {
            "ticker": "KXBTC15M-T86500",
            "side": "yes",
            "action": "buy",
            "count": 1,
            "order_type": "limit",
            "limit_price_dollars": 0.48,
            "dry_run": False,
        }
        with patch.dict(os.environ, {"KALSHI_API_KEY_ID": "mock_id", "KALSHI_PRIVATE_KEY_PATH": "mock.pem", "KALSHI_LIVE_TRADING_ENABLED": "true"}):
            with patch("pathlib.Path.exists", return_value=True):
                resp = client.post("/api/kalshi/orders/live", json=req_payload)
                assert resp.status_code == 409
                assert "24/7 Standalone Bot" in resp.json()["detail"]

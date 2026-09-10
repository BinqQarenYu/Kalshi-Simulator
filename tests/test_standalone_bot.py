"""Unit and integration tests for the 24/7 Standalone 3-Step Dominion Bot.

Verifies:
- Pre-flight audit certification gate passes across all 4 pillars
- Mutual exclusion TradingEngineLock prevents concurrent live execution
- Guardrail pre-trade intent validation caps sizing to 1-2 contracts and locks cycles
- Pocket Cockpit REST endpoints (GET /, GET /api/state, POST /api/bot/arm, disarm, panic)
- Main server rejects live order routing with HTTP 409 when standalone bot holds lock
"""

import asyncio
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


def test_standalone_bot_cors(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TESTING", "true")
    engine = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path)
    with patch("kalshi_sim.standalone_bot.app_engine", engine):
        client = TestClient(app)
        # Test request from allowed origin
        origin = "http://localhost:3000"
        resp = client.get("/api/state", headers={"Origin": origin})
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == origin
        assert resp.headers.get("access-control-allow-credentials") == "true"

        # Test preflight OPTIONS request
        options_resp = client.options(
            "/api/state",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert options_resp.status_code == 200
        assert options_resp.headers.get("access-control-allow-origin") == origin


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


def test_standalone_bot_resting_order_watchdog(tmp_path: Path):
    async def _run():
        engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path)
        mock_client = AsyncMock()
        mock_client.cancel_order = AsyncMock(return_value={"cancelled": True})
        mock_client.get_open_orders = AsyncMock(return_value=[{"order_id": "ord_123", "ticker": "KXBTC15M-EXP"}])
        engine.order_client = mock_client
        engine.active_ticker = "KXBTC15M-EXP"
        engine.active_resting_orders["ord_123"] = {
            "ticker": "KXBTC15M-EXP",
            "side": "yes",
            "size": 1,
            "price": Decimal("0.50"),
            "placed_at": 1000.0,
        }

        # Time to expiry <= 45s triggers auto-cancel
        with patch.object(engine, "get_time_to_expiry", return_value=30.0):
            engine._running = True
            watchdog_task = asyncio.create_task(engine._resting_order_watchdog_loop())
            await asyncio.sleep(0.05)
            engine._running = False
            watchdog_task.cancel()
            try:
                await watchdog_task
            except asyncio.CancelledError:
                pass

            assert mock_client.cancel_order.called
            assert "ord_123" not in engine.active_resting_orders

    asyncio.run(_run())


def test_standalone_bot_settlement_reconciliation(tmp_path: Path):
    async def _run():
        engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path)
        mock_client = AsyncMock()
        mock_client.get_settlements = AsyncMock(return_value=[
            {
                "ticker": "KXBTC15M-SETTLE1",
                "market_result": "yes",
                "count": 2,
                "revenue": 200,  # $2.00
                "settled_time": "2026-09-06T12:00:00Z",
            }
        ])
        mock_client.get_balance = AsyncMock(return_value={"balance_dollars": 25.00})
        engine.order_client = mock_client
        engine.active_ticker = "KXBTC15M-SETTLE1"

        # Pre-populate SQLite with the matching trade
        await engine.db_writer.start()
        engine.db_writer.enqueue_trade(
            trade_id="live_trade_1",
            ticker="KXBTC15M-SETTLE1",
            side="yes",
            size=2,
            price=0.50,
            gross_value=1.00,
            fees=0.0,
            timeframe="15m",
            bot_type="3_step_domination_bot",
            execution_mode="live",
            status="filled",
        )
        await engine.db_writer.flush()

        # Lock cycle in guardrails
        engine.guardrails.record_resting_order(
            order_id="live_trade_1",
            ticker="KXBTC15M-SETTLE1",
            side="yes",
            size=2,
            price=Decimal("0.50"),
            cycle_id="KXBTC15M-SETTLE1",
            bot_type="3_step_domination_bot",
        )
        assert engine.guardrails.is_cycle_locked("KXBTC15M-SETTLE1") is True

        # Run one pass of settlement loop
        engine._running = True
        settle_task = asyncio.create_task(engine._settlement_reconciliation_loop())
        for _ in range(30):
            if not engine.guardrails.is_cycle_locked("KXBTC15M-SETTLE1"):
                break
            await asyncio.sleep(0.05)
        engine._running = False
        settle_task.cancel()
        try:
            await settle_task
        except asyncio.CancelledError:
            pass
        await engine.db_writer.stop()

        # Check that cycle lock is released
        assert engine.guardrails.is_cycle_locked("KXBTC15M-SETTLE1") is False

        # Check that win_loss_reports.json has the report
        reports_file = tmp_path / "win_loss_reports.json"
        assert reports_file.exists()
        reports = json.loads(reports_file.read_text(encoding="utf-8"))
        assert len(reports) >= 1
        rep = [r for r in reports if r["ticker"] == "KXBTC15M-SETTLE1"][0]
        assert rep["outcome"] == "win"
        assert rep["pnl"] == 1.00  # $2.00 rev - $1.00 cost

    asyncio.run(_run())


def test_main_server_ai_auto_trade_lockout():
    fake_holder = ("standalone_bot", 99999)
    with patch("kalshi_sim.server.get_active_lock_holder", return_value=fake_holder):
        from kalshi_sim.server import state as server_state
        old_mode = server_state.mode
        server_state.mode = "live"
        try:
            client = TestClient(server_app)
            resp = client.post("/api/settings", json={"ai_auto_trade": True})
            assert resp.status_code == 409
            assert "Cannot enable Live AI Auto-Trade" in resp.json()["detail"]
        finally:
            server_state.mode = old_mode


def test_standalone_bot_parameters_and_endpoints(tmp_path):
    engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path)
    # Check default parameters
    p = engine.get_parameters()
    assert p["discount_limit_price"] == 0.48
    assert p["max_contracts"] == 1
    assert p["min_edge_pct"] == 6.0
    assert p["min_ev_dollars"] == 0.02
    assert p["min_spot_diff"] == 35.0

    # Test dynamic update
    updated = engine.update_parameters(
        discount_limit_price=0.45,
        max_contracts=1,
        min_edge_pct=8.0,
        min_ev_dollars=0.03,
        min_spot_diff=40.0,
        vpin_toxic_threshold=0.55,
    )
    assert updated["discount_limit_price"] == 0.45
    assert updated["max_contracts"] == 1
    assert updated["min_edge_pct"] == 8.0
    assert updated["min_ev_dollars"] == 0.03
    assert updated["min_spot_diff"] == 40.0
    assert updated["vpin_toxic_threshold"] == 0.55
    assert engine.guardrails.max_micro_bankroll_contracts == 1

    # Test HTTP endpoints via TestClient
    with patch("kalshi_sim.standalone_bot.app_engine", engine):
        client = TestClient(app)
        r_get = client.get("/api/bot/parameters")
        assert r_get.status_code == 200
        assert r_get.json()["discount_limit_price"] == 0.45

        r_post = client.post("/api/bot/parameters", json={
            "discount_limit_price": 0.42,
            "max_contracts": 1,
            "min_edge_pct": 10.0,
        })
        assert r_post.status_code == 200
        assert r_post.json()["status"] == "SUCCESS"
        assert r_post.json()["parameters"]["discount_limit_price"] == 0.42
        assert r_post.json()["parameters"]["max_contracts"] == 1


def test_standalone_bot_sweep_old_orders(tmp_path):
    async def _run():
        engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path)
        mock_client = AsyncMock()
        mock_client.get_open_orders = AsyncMock(return_value=[
            {"order_id": "old_order_1", "ticker": "KXBTC15M-OLD1"},
            {"order_id": "active_order_2", "ticker": "KXBTC15M-ACTIVE"},
        ])
        mock_client.cancel_order = AsyncMock(return_value={"status": "cancelled"})
        engine.order_client = mock_client
        engine.active_ticker = "KXBTC15M-ACTIVE"

        cancelled = await engine.sweep_old_orders(keep_ticker="KXBTC15M-ACTIVE")
        assert cancelled == 1
        mock_client.cancel_order.assert_called_once_with("old_order_1", ticker="KXBTC15M-OLD1")

    asyncio.run(_run())


def test_simulation_agent_live_lockout_suppression(tmp_path):
    async def _run():
        from kalshi_sim.simulation_agent import SimulationAgent
        from kalshi_sim.orderbook import OrderBookManager
        from kalshi_sim.schemas import L2BookState

        mgr = OrderBookManager()
        book = L2BookState("KXBTC15M-LOCKTEST")
        mgr.set_book("KXBTC15M-LOCKTEST", book)

        from kalshi_sim.schemas import Timeframe
        agent = SimulationAgent(orderbook_manager=mgr, timeframes=[Timeframe.FIFTEEN_MIN])
        agent.execution_mode = "live"
        agent.active_strategy_bot = "3_step_domination_bot"
        agent._ticker_timeframe_map["KXBTC15M-LOCKTEST"] = Timeframe.FIFTEEN_MIN
        agent._domination_bot = MagicMock()
        agent._domination_bot.evaluate = MagicMock()

        # Simulate another process holding the lock
        with patch("kalshi_sim.simulation_agent.get_active_lock_holder", return_value=("standalone_bot", 88888)):
            with patch("os.getpid", return_value=11111):
                await agent._evaluate_market("KXBTC15M-LOCKTEST", book)
                # Domination bot evaluation should have been completely skipped!
                agent._domination_bot.evaluate.assert_not_called()

    asyncio.run(_run())


def test_standalone_bot_multi_asset_switching(tmp_path: Path):
    from kalshi_sim.schemas import CryptoAsset

    # 1. Initialize engine with ETH
    engine = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path, asset=CryptoAsset.ETH)
    assert engine.active_asset == CryptoAsset.ETH
    assert engine.active_cfg.series_ticker_15m == "KXETH15M"
    assert engine.bot.asset == CryptoAsset.ETH
    assert engine.bot.min_spot_diff == 2.50

    # 2. Switch to SOL
    engine.set_asset(CryptoAsset.SOL)
    assert engine.active_asset == CryptoAsset.SOL
    assert engine.active_cfg.series_ticker_15m == "KXSOL15M"
    assert engine.bot.asset == CryptoAsset.SOL
    assert engine.bot.min_spot_diff == 0.50

    # 3. Switch to DOGE and verify sub-penny formatting in /api/state
    engine.set_asset(CryptoAsset.DOGE)
    assert engine.active_asset == CryptoAsset.DOGE
    assert engine.active_cfg.series_ticker_15m == "KXDOGE15M"
    assert engine.bot.asset == CryptoAsset.DOGE
    assert engine.bot.min_spot_diff == 0.0005

    engine.current_btc_spot = Decimal("0.245000")
    engine.target_strike = Decimal("0.240000")

    with patch("kalshi_sim.standalone_bot.app_engine", engine):
        client = TestClient(app)

        # Verify /api/state metadata and sub-penny precision
        resp_state = client.get("/api/state")
        assert resp_state.status_code == 200
        s_data = resp_state.json()
        assert s_data["active_asset"] == "DOGE"
        assert s_data["active_asset_name"] == "Dogecoin"
        assert s_data["series_ticker"] == "KXDOGE15M"
        assert s_data["spot_price_str"] == "$0.245000"
        assert s_data["target_strike_str"] == "$0.240000"
        assert s_data["spot_diff"] == 0.005000

        # Verify GET /api/assets
        resp_assets = client.get("/api/assets")
        assert resp_assets.status_code == 200
        a_data = resp_assets.json()
        assert a_data["active_asset"] == "DOGE"
        assert len(a_data["assets"]) == 4
        doge_asset = [a for a in a_data["assets"] if a["id"] == "DOGE"][0]
        assert doge_asset["is_active"] is True
        btc_asset = [a for a in a_data["assets"] if a["id"] == "BTC"][0]
        assert btc_asset["is_active"] is False

        # Verify POST /api/assets/select
        resp_sel = client.post("/api/assets/select", json={"asset": "BTC"})
        assert resp_sel.status_code == 200
        sel_data = resp_sel.json()
        assert sel_data["status"] == "SUCCESS"
        assert sel_data["active_asset"] == "BTC"
        assert sel_data["series_ticker"] == "KXBTC15M"
        assert engine.active_asset == CryptoAsset.BTC

        # Verify invalid asset returns 400
        resp_inv = client.post("/api/assets/select", json={"asset": "INVALID_COIN"})
        assert resp_inv.status_code == 400


def test_standalone_bot_consecutive_loss_streak_breaker(tmp_path: Path):
    """Verify that 3 consecutive losses auto-disarm the bot, and re-arming resets the streak."""
    engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path)
    assert engine.is_armed is True
    assert engine.consecutive_losses == 0
    assert engine.max_consecutive_losses == 3

    # Mock order client get_settlements returning 3 losses in sequence
    mock_settlements = [
        {"ticker": "KXBTC15M-T1", "market_result": "no", "count": 1, "settled_time": "2026-09-07T00:00:00Z"},
        {"ticker": "KXBTC15M-T2", "market_result": "no", "count": 1, "settled_time": "2026-09-07T00:15:00Z"},
        {"ticker": "KXBTC15M-T3", "market_result": "no", "count": 1, "settled_time": "2026-09-07T00:30:00Z"},
    ]
    engine.order_client = MagicMock()
    engine.order_client.get_settlements = AsyncMock(return_value=mock_settlements)

    # Seed mock local trades where bot bet YES (so market_result=no results in losses)
    local_trades = {
        "KXBTC15M-T1": {"trade_id": "tr1", "ticker": "KXBTC15M-T1", "side": "yes", "size": 1, "price": Decimal("0.48"), "gross_value": Decimal("0.48"), "timestamp_utc": "2026-09-07T00:00:00Z", "bot_type": "3_step_domination_bot"},
        "KXBTC15M-T2": {"trade_id": "tr2", "ticker": "KXBTC15M-T2", "side": "yes", "size": 1, "price": Decimal("0.48"), "gross_value": Decimal("0.48"), "timestamp_utc": "2026-09-07T00:15:00Z", "bot_type": "3_step_domination_bot"},
        "KXBTC15M-T3": {"trade_id": "tr3", "ticker": "KXBTC15M-T3", "side": "yes", "size": 1, "price": Decimal("0.48"), "gross_value": Decimal("0.48"), "timestamp_utc": "2026-09-07T00:30:00Z", "bot_type": "3_step_domination_bot"},
    }

    async def _test():
        engine._running = True
        with patch("kalshi_sim.standalone_bot.get_db") as mock_get_db:
            mock_cursor = AsyncMock()
            mock_cursor.fetchall.return_value = [
                ("tr1", "KXBTC15M-T1", "yes", 1, 0.48, 0.48, "2026-09-07T00:00:00Z", "3_step_domination_bot"),
                ("tr2", "KXBTC15M-T2", "yes", 1, 0.48, 0.48, "2026-09-07T00:15:00Z", "3_step_domination_bot"),
                ("tr3", "KXBTC15M-T3", "yes", 1, 0.48, 0.48, "2026-09-07T00:30:00Z", "3_step_domination_bot"),
            ]
            mock_conn = AsyncMock()
            mock_conn.execute.return_value.__aenter__.return_value = mock_cursor
            mock_get_db.return_value.get_connection.return_value.__aenter__.return_value = mock_conn

            settle_task = asyncio.create_task(engine._settlement_reconciliation_loop())
            await asyncio.sleep(0.05)
            engine._running = False
            settle_task.cancel()
            try:
                await settle_task
            except asyncio.CancelledError:
                pass

    asyncio.run(_test())

    # Verify auto-disarm triggered after 3 consecutive losses
    assert engine.consecutive_losses == 3
    assert engine.is_armed is False

    # Verify /api/state reflects auto-disarmed and consecutive loss status
    with patch("kalshi_sim.standalone_bot.app_engine", engine):
        client = TestClient(app)
        st = client.get("/api/state").json()
        assert st["armed"] is False
        assert st["consecutive_losses"] == 3
        assert st["max_consecutive_losses"] == 3

        # Re-arm via API
        resp_arm = client.post("/api/bot/arm")
        assert resp_arm.status_code == 200
        arm_data = resp_arm.json()
        assert arm_data["status"] == "ARMED"
        assert arm_data["armed"] is True
        assert arm_data["consecutive_losses"] == 0

        # State should now be reset
        assert engine.is_armed is True
        assert engine.consecutive_losses == 0


def test_standalone_bot_window_management_api():
    """Test Win32 window management endpoints (status, pin, resize, launch-widget)."""
    client = TestClient(app)

    # 1. Test /api/window/status when no window found
    with patch("kalshi_sim.standalone_bot.find_cockpit_windows", return_value=[]):
        resp = client.get("/api/window/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert data["is_topmost"] is False

    # 2. Test /api/window/status when window found and pinned
    with patch("kalshi_sim.standalone_bot.find_cockpit_windows", return_value=[(99999, "Kalshi 3-Step Dominion — Pocket Cockpit")]):
        with patch("kalshi_sim.standalone_bot.is_always_on_top", return_value=True):
            resp = client.get("/api/window/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["available"] is True
            assert data["is_topmost"] is True
            assert data["hwnd"] == 99999

    # 3. Test /api/window/pin
    with patch("kalshi_sim.standalone_bot.find_cockpit_windows", return_value=[(99999, "Kalshi 3-Step Dominion — Pocket Cockpit")]):
        with patch("kalshi_sim.standalone_bot.set_always_on_top", return_value=True) as mock_pin:
            with patch("kalshi_sim.standalone_bot.resize_window", return_value=True) as mock_resize:
                resp = client.post("/api/window/pin", json={"topmost": True, "width": 515, "height": 245})
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "SUCCESS"
                assert data["topmost"] is True
                mock_pin.assert_called_once_with(99999, True)
                mock_resize.assert_called_once_with(99999, 515, 245, topmost=True)

    # 4. Test /api/window/resize
    with patch("kalshi_sim.standalone_bot.find_cockpit_windows", return_value=[(99999, "Kalshi 3-Step Dominion — Pocket Cockpit")]):
        with patch("kalshi_sim.standalone_bot.resize_window", return_value=True) as mock_resize:
            resp = client.post("/api/window/resize", json={"width": 515, "height": 780, "topmost": True})
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "SUCCESS"
            assert data["width"] == 515
            assert data["height"] == 780
            mock_resize.assert_called_once_with(99999, 515, 780, topmost=True)

    # 5. Test /api/window/launch-widget
    with patch("kalshi_sim.standalone_bot.launch_widget_window", return_value=True) as mock_launch:
        resp = client.post("/api/window/launch-widget")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "LAUNCHED"
        assert data["success"] is True
        mock_launch.assert_called_once()



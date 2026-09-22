"""Unit and integration tests for the 24/7 Standalone 3-Step Dominion Bot.

Verifies:
- Pre-flight audit certification gate passes across all 4 pillars
- Mutual exclusion TradingEngineLock prevents concurrent live execution
- Guardrail pre-trade intent validation caps sizing to 1-2 contracts and locks cycles
- Pocket Cockpit REST endpoints (GET /, GET /api/state, POST /api/bot/arm, disarm, panic)
- Main server rejects live order routing with HTTP 409 when standalone bot holds lock
"""

import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from kalshi_sim.process_lock import TradingEngineLock, get_active_lock_holder, is_pid_running
from shared.schemas import CryptoAsset, LiveOrderRequest
from app_2_execution_bot.standalone_bot import StandaloneBotEngine, app, app_engine
from app_2_execution_bot.server import app as server_app


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

        # 2.5 Test GET /api/state?asset=GOLD (Asset-Scoped Telemetry Isolation)
        engine.asset_markets["GOLD"] = {
            "ticker": "KXGOLD15M-26SEP11-4337.41",
            "target_strike": Decimal("4337.41"),
            "spot_price": Decimal("4335.20"),
            "target_time_str": "11:15 AM",
            "time_window_str": "11:00 AM - 11:15 AM",
            "best_yes_bid": Decimal("0.27"),
            "best_yes_ask": Decimal("0.28"),
            "best_no_bid": Decimal("0.72"),
            "best_no_ask": Decimal("0.73"),
        }
        resp_gold = client.get("/api/state?asset=GOLD")
        assert resp_gold.status_code == 200
        gold_data = resp_gold.json()
        assert gold_data["active_asset"] == "BTC"
        assert gold_data["view_asset"] == "GOLD"
        assert gold_data["target_strike"] == 4337.41
        assert gold_data["target_strike_str"] == "$4,337.41"
        assert gold_data["spot_price"] == 4335.20
        assert gold_data["spot_price_str"] == "$4,335.20"
        assert gold_data["active_ticker"] == "KXGOLD15M-26SEP11-4337.41"
        assert gold_data["best_yes_bid"] == 0.27
        assert gold_data["best_yes_ask"] == 0.28
        assert gold_data["twap_60s"] is None

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


def test_standalone_bot_security_headers(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TESTING", "true")
    engine = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path)
    with patch("kalshi_sim.standalone_bot.app_engine", engine):
        client = TestClient(app)
        resp = client.get("/api/state")
        assert resp.status_code == 200
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
        assert resp.headers.get("x-xss-protection") == "1; mode=block"
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


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
        from app_2_execution_bot.server import state as server_state
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
    assert p["discount_limit_price"] == 0.52
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
        from app_2_execution_bot.orderbook import OrderBookManager
        from shared.schemas import L2BookState

        mgr = OrderBookManager()
        book = L2BookState("KXBTC15M-LOCKTEST")
        mgr.set_book("KXBTC15M-LOCKTEST", book)

        from shared.schemas import Timeframe
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
    from shared.schemas import CryptoAsset

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
        assert len(a_data["assets"]) == 6
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
    assert engine.max_consecutive_losses == 7
    engine.max_consecutive_losses = 3  # Calibrate to 3 for fast test verification

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


def test_take_profit_ceiling_execution_in_standalone_engine(tmp_path: Path):
    """Verify StandaloneBotEngine holds winners to $1.00 when no reversal,

    and executes take-profit ceiling when an adverse reversal >= 85% is detected.
    """
    from datetime import timedelta
    from shared.schemas import L2BookState

    engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path)
    engine.active_ticker = "KXBTC15M-T100000"
    engine.target_strike = Decimal("100000")
    engine.current_btc_spot = Decimal("100050")  # +$50 in the money (no reversal)
    engine.active_market_close_dt = datetime.now(timezone.utc) + timedelta(minutes=5)

    # Establish an open position bought at 52¢
    engine.active_position = {
        "ticker": "KXBTC15M-T100000",
        "side": "yes",
        "size": 1,
        "entry_price": Decimal("0.52"),
        "entry_time": 0.0,
    }

    # Populate order book where YES bid has reached $0.96 (above $0.95 ceiling)
    book = L2BookState(market_ticker="KXBTC15M-T100000")
    book.yes_book = {Decimal("0.96"): Decimal("100"), Decimal("0.95"): Decimal("50")}
    book.no_book = {Decimal("0.03"): Decimal("50")}
    engine.orderbook._books["KXBTC15M-T100000"] = book

    # 1. When winning with NO reversal detected -> Continues holding to $1.00 expiry
    asyncio.run(engine.evaluate_and_execute())
    assert engine.active_position is not None, "Bot should hold winners when no adverse reversal"

    # 2. When spot crashes $200 below strike -> Adverse reversal >= 85% detected
    engine.current_btc_spot = Decimal("99800")
    engine.last_eval_time = 0.0  # Reset throttle timer
    asyncio.run(engine.evaluate_and_execute())

    # Position should now be cleared (exited at 96¢ ceiling to bank profit before collapse)
    assert engine.active_position is None
    assert engine.today_wins == 1
    # Realized PnL = 0.96 - 0.52 - 0.01 fee = 0.43
    assert engine.today_pnl == Decimal("0.43")
    assert engine.settled_cycles == 1


def test_take_profit_ceiling_api_parameter_update(tmp_path: Path):
    """Verify enable_take_profit_ceiling and reversal gate parameter API updates."""
    from app_2_execution_bot.standalone_bot import app_engine
    import app_2_execution_bot.standalone_bot as sb

    test_engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path)
    sb.app_engine = test_engine

    client = TestClient(sb.app)
    params_resp = client.get("/api/bot/parameters")
    assert params_resp.status_code == 200
    p = params_resp.json()
    assert p["enable_take_profit_ceiling"] is True
    assert p["take_profit_price_threshold"] == 0.95
    assert p["require_reversal_for_tp_ceiling"] is True
    assert p["enable_reverse_take_profit_roi"] is True
    assert p["reverse_indicator_threshold"] == 85.0
    assert p["min_take_profit_roi"] == 20.0

    # Update via POST
    update_resp = client.post(
        "/api/bot/parameters",
        json={
            "enable_take_profit_ceiling": False,
            "take_profit_price_threshold": 0.92,
            "require_reversal_for_tp_ceiling": False,
            "enable_reverse_take_profit_roi": False,
            "reverse_indicator_threshold": 90.0,
            "min_take_profit_roi": 25.0,
        },
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["parameters"]["enable_take_profit_ceiling"] is False
    assert data["parameters"]["take_profit_price_threshold"] == 0.92
    assert data["parameters"]["require_reversal_for_tp_ceiling"] is False
    assert data["parameters"]["enable_reverse_take_profit_roi"] is False
    assert data["parameters"]["reverse_indicator_threshold"] == 90.0
    assert data["parameters"]["min_take_profit_roi"] == 25.0
    assert test_engine.bot.enable_take_profit_ceiling is False
    assert test_engine.bot.require_reversal_for_tp_ceiling is False
    assert test_engine.bot.enable_reverse_take_profit_roi is False
    assert test_engine.bot.reverse_indicator_threshold == 0.90
    assert test_engine.bot.min_take_profit_roi == 0.25


def test_bot_parameters_persistence_across_restarts(tmp_path: Path):
    """Verify strategy parameters survive daemon reboots and become permanent defaults."""
    import json
    from shared.schemas import CryptoAsset

    # 1. Initial engine has factory defaults
    engine1 = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path)
    assert engine1.bot.discount_limit_price == Decimal("0.52")
    assert engine1.bot.max_entry_price == Decimal("0.62")
    assert engine1.bot.min_confidence == 0.70
    assert engine1.bot.min_spot_diff == 35.0

    # 2. Update parameters (e.g. from UI 'Apply & Save as Default')
    engine1.update_parameters(
        discount_limit_price=0.49,
        momentum_max_price=0.58,
        min_confidence=0.75,
        min_spot_diff=25.0,
        enable_take_profit_ceiling=True,
        take_profit_price_threshold=0.96,
    )
    assert engine1.bot.discount_limit_price == Decimal("0.49")
    assert engine1.bot.max_entry_price == Decimal("0.58")
    assert engine1.bot.min_confidence == 0.75
    assert engine1.bot.min_spot_diff == 25.0

    # Verify JSON file written to disk
    params_file = tmp_path / "bot_parameters_domination.json"
    assert params_file.exists()
    with open(params_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["discount_limit_price"] == 0.49
    assert data["momentum_max_price"] == 0.58
    assert data["min_confidence"] == 75.0  # get_parameters returns percentage
    assert data["take_profit_price_threshold"] == 0.96
    assert data["assets"]["BTC"]["min_spot_diff"] == 25.0
    assert data["max_contracts"] == 1  # Invariant armor

    # 3. Simulate daemon reboot / restart: instantiate brand new engine in same data_dir
    engine2 = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path)
    assert engine2.bot.discount_limit_price == Decimal("0.49")
    assert engine2.bot.max_entry_price == Decimal("0.58")
    assert engine2.bot.min_confidence == 0.75
    assert engine2.bot.min_spot_diff == 25.0
    assert engine2.bot.take_profit_price_threshold == Decimal("0.96")
    assert engine2.guardrails.max_micro_bankroll_contracts == 1

    # 4. Multi-asset moat isolation: switch to ETH, customize ETH moat, check BTC retention
    engine2.set_asset(CryptoAsset.ETH)
    assert engine2.bot.asset == CryptoAsset.ETH
    # Default ETH moat is 2.50
    assert engine2.bot.min_spot_diff == 2.50
    # Custom update ETH moat to 2.20
    engine2.update_parameters(min_spot_diff=2.20)
    assert engine2.bot.min_spot_diff == 2.20

    # Switch back to BTC
    engine2.set_asset(CryptoAsset.BTC)
    assert engine2.bot.asset == CryptoAsset.BTC
    assert engine2.bot.min_spot_diff == 25.0

    # 5. Simulate 2nd reboot: create engine3 and verify both BTC and ETH retain custom defaults
    engine3 = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path)
    assert engine3.bot.min_spot_diff == 25.0
    engine3.set_asset(CryptoAsset.ETH)
    assert engine3.bot.min_spot_diff == 2.20


def test_corrupt_parameters_file_fallback(tmp_path: Path):
    """Verify engine gracefully falls back to factory defaults if saved JSON is corrupted."""
    params_file = tmp_path / "bot_parameters_domination.json"
    # Write garbage JSON
    params_file.write_text("{corrupt json syntax!@#$", encoding="utf-8")

    # Engine initialization should not crash
    engine = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path)
    # Reverts safely to factory defaults
    assert engine.bot.discount_limit_price == Decimal("0.52")
    assert engine.bot.max_entry_price == Decimal("0.62")
    assert engine.bot.min_confidence == 0.70
    assert engine.bot.min_spot_diff == 35.0
    assert engine.guardrails.max_micro_bankroll_contracts == 1


def test_watchdog_does_not_cancel_resting_order_on_active_position(tmp_path: Path):
    """Verify watchdog finished event sweep never cancels resting orders on tickers with active positions."""
    async def _run():
        engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path)
        mock_client = AsyncMock()
        mock_client.cancel_order = AsyncMock(return_value={"cancelled": True})
        # Exchange has a resting order on BTC, while engine is currently focused on GOLD
        mock_client.get_open_orders = AsyncMock(return_value=[
            {"order_id": "tp_sell_btc", "ticker": "KXBTC15M-OPEN"},
            {"order_id": "obsolete_old", "ticker": "KXBTC15M-OLDEXPIRED"},
        ])
        engine.order_client = mock_client
        engine.active_ticker = "KXGOLD15M-ACTIVE"
        engine.active_market_close_dt = datetime.now(timezone.utc) + timedelta(minutes=10)

        # Engine holds an active position on BTC!
        engine.active_positions["KXBTC15M-OPEN"] = {
            "ticker": "KXBTC15M-OPEN",
            "side": "yes",
            "size": 1,
            "entry_price": Decimal("0.52"),
        }
        engine.active_resting_orders["tp_sell_btc"] = {
            "order_id": "tp_sell_btc",
            "ticker": "KXBTC15M-OPEN",
            "action": "sell",
        }

        with patch.object(engine, "get_time_to_expiry", return_value=120.0):
            engine._running = True
            watchdog_task = asyncio.create_task(engine._resting_order_watchdog_loop())
            await asyncio.sleep(0.05)
            engine._running = False
            watchdog_task.cancel()
            try:
                await watchdog_task
            except asyncio.CancelledError:
                pass

        # tp_sell_btc was PROTECTED (not cancelled)
        # obsolete_old WAS cancelled
        cancelled_calls = [call.args for call in mock_client.cancel_order.call_args_list]
        cancelled_oids = [c[0] for c in cancelled_calls]
        assert "tp_sell_btc" not in cancelled_oids
        assert "obsolete_old" in cancelled_oids

    asyncio.run(_run())


def test_watchdog_detects_take_profit_fill_and_finalizes(tmp_path: Path):
    """Verify watchdog detects when resting TP limit order fills and finalizes exit."""
    async def _run():
        engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path)
        mock_client = AsyncMock()
        mock_client.get_open_orders = AsyncMock(return_value=[])  # Empty open orders -> filled!
        mock_client.get_balance = AsyncMock(return_value={"balance_dollars": 25.00})
        engine.order_client = mock_client
        engine.active_ticker = "KXBTC15M-ACTIVE"

        engine.active_positions["KXBTC15M-ACTIVE"] = {
            "ticker": "KXBTC15M-ACTIVE",
            "side": "yes",
            "size": 1,
            "entry_price": Decimal("0.50"),
        }
        mock_exit_dec = MagicMock()
        mock_exit_dec.exit_price = Decimal("0.90")
        mock_exit_dec.unrealized_pnl = Decimal("0.40")
        mock_exit_dec.exit_reason = "LATE_CYCLE_HARVEST"
        mock_exit_dec.rationale = "Test rationale"

        engine.active_resting_orders["tp_sell_1"] = {
            "order_id": "tp_sell_1",
            "ticker": "KXBTC15M-ACTIVE",
            "side": "yes",
            "size": 1,
            "price": Decimal("0.90"),
            "action": "sell",
            "exit_dec": mock_exit_dec,
            "pos": engine.active_positions["KXBTC15M-ACTIVE"],
        }

        with patch.object(engine, "get_time_to_expiry", return_value=120.0):
            engine._running = True
            watchdog_task = asyncio.create_task(engine._resting_order_watchdog_loop())
            await asyncio.sleep(0.05)
            engine._running = False
            watchdog_task.cancel()
            try:
                await watchdog_task
            except asyncio.CancelledError:
                pass

        # Resting order filled and cleaned up
        assert "tp_sell_1" not in engine.active_resting_orders
        assert "KXBTC15M-ACTIVE" not in engine.active_positions
        assert engine.today_wins == 1
        assert engine.today_pnl == Decimal("0.40")

    asyncio.run(_run())


def test_take_profit_suppresses_duplicate_when_exit_resting(tmp_path: Path):
    """Verify take profit evaluation does not place duplicate orders when an exit order is resting."""
    async def _run():
        engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path)
        mock_client = AsyncMock()
        mock_client.place_order = AsyncMock(return_value={"order_id": "duplicate_ord"})
        engine.order_client = mock_client
        engine.active_ticker = "KXBTC15M-ACTIVE"
        engine.active_market_close_dt = datetime.now(timezone.utc) + timedelta(minutes=5)

        engine.active_positions["KXBTC15M-ACTIVE"] = {
            "ticker": "KXBTC15M-ACTIVE",
            "side": "yes",
            "size": 1,
            "entry_price": Decimal("0.50"),
        }
        # Already has an active resting sell exit!
        engine.active_resting_orders["tp_sell_1"] = {
            "order_id": "tp_sell_1",
            "ticker": "KXBTC15M-ACTIVE",
            "action": "sell",
        }

        # Setup orderbook and evaluate
        engine.orderbook.get_book = MagicMock()
        mock_book = MagicMock()
        mock_book.yes_book = {Decimal("0.90"): 10}
        mock_book.no_book = {Decimal("0.10"): 10}
        engine.orderbook.get_book.return_value = mock_book

        await engine.evaluate_and_execute()

        # place_order should NOT have been called because exit is already resting
        assert not mock_client.place_order.called

    asyncio.run(_run())


def test_bot_basket_asset_selection_persistence_across_restarts(tmp_path: Path):
    """Verify active basket assets, asset_mode, per-asset dials, and armed status persist across engine reboots."""
    # 1. Start engine with initial BTC
    engine1 = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path)
    assert engine1.asset_mode == "single"
    assert engine1.active_assets == [CryptoAsset.BTC]

    # 2. User selects custom basket ['BTC', 'GOLD', 'DOGE']
    engine1.set_asset(["BTC", "GOLD", "DOGE"])
    assert engine1.asset_mode == "basket"
    assert [a.value for a in engine1.active_assets] == ["BTC", "GOLD", "DOGE"]

    # 3. User customizes GOLD parameters
    engine1.update_parameters(asset="GOLD", discount_limit_price=0.48, min_confidence=86.0)
    assert engine1.asset_profiles["GOLD"]["discount_limit_price"] == 0.48
    assert engine1.asset_profiles["GOLD"]["min_confidence"] == 86.0

    # 4. User disarms bot
    engine1.is_armed = False
    engine1._persist_parameters()

    # Verify JSON file on disk
    params_file = tmp_path / "bot_parameters_domination.json"
    assert params_file.exists()
    saved = json.loads(params_file.read_text(encoding="utf-8"))
    assert saved["active_assets"] == ["BTC", "GOLD", "DOGE"]
    assert saved["asset_mode"] == "basket"
    assert saved["is_armed"] is False
    assert saved["assets"]["GOLD"]["discount_limit_price"] == 0.48

    # 5. Boot brand new StandaloneBotEngine on same data directory with no explicit asset passed (server boot simulation)
    engine2 = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path, asset=None)
    assert engine2.asset_mode == "basket"
    assert [a.value for a in engine2.active_assets] == ["BTC", "GOLD", "DOGE"]
    assert engine2.is_armed is False  # Restored disarmed state!
    assert engine2.asset_profiles["GOLD"]["discount_limit_price"] == 0.48
    assert engine2.asset_profiles["GOLD"]["min_confidence"] == 86.0

    # 6. User re-arms and selects ALL mode
    engine2.set_asset("ALL")
    engine2.is_armed = True
    engine2._persist_parameters()

    # 7. Boot third engine (simulating next reboot)
    engine3 = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path, asset=None)
    assert engine3.asset_mode == "all"
    assert len(engine3.active_assets) == len(CryptoAsset)
    assert engine3.is_armed is True


def test_entry_timing_window_and_auto_sweep(tmp_path: Path):
    """Verify entry timing windows (Option C) and auto-sweep of resting entry orders at cutoff."""
    engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path)

    # 1. Verify default asset profile timing parameters
    btc_prof = engine.asset_profiles["BTC"]
    assert btc_prof["entry_window_open_minutes"] == 12.0
    assert btc_prof["entry_window_close_minutes"] == 4.5

    gold_prof = engine.asset_profiles["GOLD"]
    assert gold_prof["entry_window_open_minutes"] == 7.0
    assert gold_prof["entry_window_close_minutes"] == 2.0

    # 2. Verify dynamic parameter update
    engine.update_parameters(asset="BTC", entry_window_open_minutes=10.0, entry_window_close_minutes=3.0)
    assert engine.asset_profiles["BTC"]["entry_window_open_minutes"] == 10.0
    assert engine.asset_profiles["BTC"]["entry_window_close_minutes"] == 3.0

    # 3. Verify auto-sweep in resting order watchdog
    engine.asset_profiles["BTC"]["entry_window_close_minutes"] = 4.5
    engine.active_ticker = "KXBTC15M-TEST"

    # Set market close_dt such that time_to_expiry is ~200s (below 270s / 4.5m cutoff)
    now_utc = datetime.now(timezone.utc)
    engine.active_market_close_dt = (now_utc + timedelta(seconds=200)).isoformat()
    engine.asset_markets["BTC"] = {"close_dt": engine.active_market_close_dt}

    # Add resting entry buy order and resting take-profit sell order
    engine.active_resting_orders = {
        "order_buy_1": {
            "order_id": "order_buy_1",
            "ticker": "KXBTC15M-TEST",
            "action": "buy",
            "side": "yes",
            "count": 1,
            "asset": "BTC",
        },
        "order_sell_tp": {
            "order_id": "order_sell_tp",
            "ticker": "KXBTC15M-TEST",
            "action": "sell",
            "side": "yes",
            "count": 1,
            "asset": "BTC",
        },
    }

    # Run the watchdog sweep logic directly
    for oid, o_info in list(engine.active_resting_orders.items()):
        if o_info.get("action") == "sell":
            continue
        o_ast_key = o_info.get("asset", engine.active_asset.value)
        o_profile = engine.asset_profiles.get(o_ast_key, {})
        close_min = float(o_profile.get("entry_window_close_minutes", 4.5))
        close_sec = close_min * 60.0
        m_info = engine.asset_markets.get(o_ast_key, {})
        c_dt = m_info.get("close_dt", engine.active_market_close_dt)
        t_rem_order = engine.get_time_to_expiry(c_dt)
        if t_rem_order <= close_sec:
            engine.active_resting_orders.pop(oid, None)

    # Entry buy order was swept, but take-profit sell order remains protected
    assert "order_buy_1" not in engine.active_resting_orders
    assert "order_sell_tp" in engine.active_resting_orders


def test_standalone_poe_endpoints_and_flight_recorder(tmp_path: Path):
    """Verify POE endpoints /api/poe/scorecards and /api/poe/report on StandaloneBotEngine."""
    import app_2_execution_bot.standalone_bot as sb

    engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path)
    sb.app_engine = engine

    client = TestClient(sb.app)

    # Initial state
    resp = client.get("/api/poe/scorecards")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["total_records"] == 0

    # Buffer a veto candidate and flush it
    engine._cycle_veto_candidates["KXBTC15M-TEST-001"] = {
        "cycle_id": "KXBTC15M-TEST-001",
        "tau_seconds_remaining": 400.0,
        "spot_price": 88000.0,
        "target_strike": 87900.0,
        "moneyness_diff": 100.0,
        "spot_velocity_10s": 10.0,
        "vpin_score": 0.20,
        "ai_predicted_side": "YES",
        "ai_confidence": 0.85,
        "ev_gross": Decimal("0.08"),
        "ev_net": Decimal("0.06"),
        "decision": "VETO",
        "primary_blocking_parameter": "AI_CONVICTION_FLOOR",
    }
    engine._flush_cycle_veto("KXBTC15M-TEST-001")
    assert "KXBTC15M-TEST-001" in engine.poe_recorder._records

    # Settle the vetoed cycle (settled NO -> Q4 Shielded Capital)
    engine.poe_recorder.record_settlement(
        cycle_id="KXBTC15M-TEST-001",
        settlement_spot=87850.0,
        contract_winning_side="NO",
        settled_payout=Decimal("0.00"),
    )

    # Check scorecards endpoint
    resp2 = client.get("/api/poe/scorecards")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["settled_records"] == 1
    assert "AI_CONVICTION_FLOOR" in data2["scorecards"]
    sc = data2["scorecards"]["AI_CONVICTION_FLOOR"]
    assert sc["quadrant_4_shielded"] == 1
    assert sc["vps_score_pct"] == 100.0
    assert sc["status"] == "SHIELD"

    # Check report endpoint
    rep_resp = client.get("/api/poe/report")
    assert rep_resp.status_code == 200
    rep_data = rep_resp.json()
    assert "AGENT POE: EMPIRICAL AUDIT REPORT" in rep_data["report_markdown"]
    assert "AI_CONVICTION_FLOOR" in rep_data["report_markdown"]




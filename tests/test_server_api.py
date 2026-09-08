"""Unit tests for FastAPI REST API and WebSocket state serialization."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from kalshi_sim.server import app, _build_full_state_payload


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_get_state_endpoint(client: TestClient) -> None:
    response = client.get("/api/state")
    assert response.status_code == 200
    data = response.json()
    assert "market" in data
    assert "orderbook_ladder" in data
    assert "ai_signals" in data
    assert "portfolio" in data
    assert data["market"]["ticker"].startswith(("KXBTC", "KXETH", "KXSOL", "KXDOGE"))


def test_update_settings_endpoint(client: TestClient) -> None:
    response = client.post("/api/settings", json={"ai_auto_trade": False})
    assert response.status_code == 200
    data = response.json()
    assert data["ai_auto_trade"] is False


def test_switch_timeframe_endpoint(client: TestClient) -> None:
    # 1. Switch to 5m
    resp5m = client.post("/api/settings", json={"active_timeframe": "5m"})
    assert resp5m.status_code == 200
    data5m = resp5m.json()
    assert data5m["active_timeframe"] == "5m"
    assert data5m["active_ticker"] == "KXBTC5M-T78600"
    assert data5m["target_strike"] == 78600.0

    # 2. Switch to 1h
    resp1h = client.post("/api/settings", json={"active_timeframe": "1h"})
    assert resp1h.status_code == 200
    data1h = resp1h.json()
    assert data1h["active_timeframe"] == "1h"
    assert data1h["active_ticker"] == "KXBTCH-T78500"

    # 3. Switch back to 15m
    resp15m = client.post("/api/settings", json={"active_timeframe": "15m"})
    assert resp15m.status_code == 200
    data15m = resp15m.json()
    assert data15m["active_timeframe"] == "15m"


def test_toggle_feed_mode_endpoint(client: TestClient) -> None:
    from unittest.mock import patch
    from kalshi_sim.server import state
    # Switch to mock
    resp_mock = client.post("/api/settings", json={"mode": "mock"})
    assert resp_mock.status_code == 200
    assert resp_mock.json()["mode"] == "mock"

    # Switch to live (mocked to prevent outbound network handshake during testing)
    async def fake_start_live() -> bool:
        state.mode = "live"
        return True

    with patch("kalshi_sim.server.start_live_feed", side_effect=fake_start_live):
        resp_live = client.post("/api/settings", json={"mode": "live"})
        assert resp_live.status_code == 200
        assert resp_live.json()["mode"] == "live"

    # Restore to mock mode
    client.post("/api/settings", json={"mode": "mock"})






def test_reset_portfolio_endpoint(client: TestClient) -> None:
    response = client.post("/api/reset", json={"capital": 15000.0})
    assert response.status_code == 200
    data = response.json()
    assert data["capital"] == 15000.0


def test_place_and_close_order_endpoint(client: TestClient) -> None:
    with client:
        # Place order
        order_res = client.post("/api/orders", json={"side": "yes", "size": 10, "order_type": "market"})
        assert order_res.status_code == 200
        order_data = order_res.json()
        assert order_data["success"] is True

        # Close position
        close_res = client.post("/api/positions/close", json={"ticker": "KXBTC15M-T78650"})
        assert close_res.status_code == 200
        close_data = close_res.json()
        assert close_data["success"] is True
        assert close_data["size"] >= 10
        assert "pnl" in close_data


def test_close_nonexistent_position(client: TestClient) -> None:
    with client:
        response = client.post("/api/positions/close", json={"ticker": "NONEXISTENT-T99999"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "already_cleared"


def test_resting_limit_order_lifecycle(client: TestClient) -> None:
    with client:
        # Place resting limit order
        resp = client.post(
            "/api/orders",
            json={
                "ticker": "KXBTC15M-T78650",
                "side": "yes",
                "size": 15,
                "order_type": "limit",
                "limit_price": 0.02,
                "resting_only": True,
            },
        )
        assert resp.status_code == 200
        order_data = resp.json()
        assert order_data["success"] is True
        assert order_data["status"] == "resting"
        order_id = order_data["order_id"]

        # Fetch open orders list
        open_res = client.get("/api/orders/open")
        assert open_res.status_code == 200
        open_orders = open_res.json()
        assert any(o["order_id"] == order_id for o in open_orders)

        # Cancel resting order
        cancel_res = client.delete(f"/api/orders/{order_id}")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"

        # Verify no longer in open orders list
        open_res_after = client.get("/api/orders/open")
        assert not any(o["order_id"] == order_id for o in open_res_after.json())


def test_circuit_breaker_reset_endpoint(client: TestClient) -> None:
    with client:
        resp = client.post("/api/circuit-breaker/reset")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


def test_ohlcv_history_endpoint(client: TestClient) -> None:
    with client:
        resp = client.get("/api/history/ohlcv?symbol=BTC&interval=1m&limit=20")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "BTC"
        assert data["interval"] == "1m"
        assert "candles" in data
        assert len(data["candles"]) > 0
        candle = data["candles"][0]
        assert "open" in candle
        assert "high" in candle
        assert "low" in candle
        assert "close" in candle
        assert "volume" in candle
        assert "trades_count" in candle


def test_export_trades_csv_and_jsonl(client: TestClient) -> None:
    with client:
        # CSV format
        resp_csv = client.get("/api/export/trades?format=csv")
        assert resp_csv.status_code == 200
        assert "text/csv" in resp_csv.headers["content-type"]
        assert "order_id,ticker,side" in resp_csv.text

        # JSONL format
        resp_jsonl = client.get("/api/export/trades?format=jsonl")
        assert resp_jsonl.status_code == 200
        assert "application/x-ndjson" in resp_jsonl.headers["content-type"]


def test_export_settlements_csv_and_jsonl(client: TestClient) -> None:
    with client:
        # CSV format
        resp_csv = client.get("/api/export/settlements?format=csv")
        assert resp_csv.status_code == 200
        assert "text/csv" in resp_csv.headers["content-type"]
        assert "ticker,side,size" in resp_csv.text

        # JSONL format
        resp_jsonl = client.get("/api/export/settlements?format=jsonl")
        assert resp_jsonl.status_code == 200
        assert "application/x-ndjson" in resp_jsonl.headers["content-type"]


def test_export_pnl_csv_and_json(client: TestClient) -> None:
    with client:
        # CSV format
        resp_csv = client.get("/api/export/pnl?format=csv")
        assert resp_csv.status_code == 200
        assert "text/csv" in resp_csv.headers["content-type"]
        assert "starting_balance,current_balance" in resp_csv.text

        # JSON format
        resp_json = client.get("/api/export/pnl?format=json")
        assert resp_json.status_code == 200
        assert "application/json" in resp_json.headers["content-type"]
        data = resp_json.json()
        assert "starting_balance" in data
        assert "current_balance" in data


def test_gdrive_status_endpoint(client: TestClient) -> None:
    with client:
        resp = client.get("/api/gdrive/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "rclone_available" in data
        assert "gdrive_configured" in data
        assert "last_sync_status" in data
        assert "sync_count" in data


def test_gdrive_sync_trigger_endpoint(client: TestClient) -> None:
    from unittest.mock import AsyncMock, patch
    with client:
        with patch("kalshi_sim.gdrive_sync.async_backup_data_to_gdrive", new_callable=AsyncMock) as mock_backup:
            mock_backup.return_value = True
            resp = client.post("/api/gdrive/sync")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "status" in data


def test_state_payload_structure() -> None:
    payload = _build_full_state_payload()
    assert "timestamp" in payload
    assert "market" in payload
    assert "target_strike" in payload["market"]
    assert "current_btc_price" in payload["market"]
    assert "ai_signals" in payload
    assert "p_up" in payload["ai_signals"]
    assert "vpin" in payload["ai_signals"]
    assert "win_loss_reports" in payload
    assert "open_orders" in payload["portfolio"]
    assert "circuit_breaker_tripped" in payload["portfolio"]
    assert "current_drawdown_pct" in payload["portfolio"]


def test_bot_test_trade_endpoint(client: TestClient) -> None:
    with client:
        resp = client.post("/api/bot/test-trade")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "ai_signal" in data
        assert "report" in data
        report = data["report"]
        assert "report_id" in report
        assert "outcome" in report
        assert report["outcome"] in ("win", "loss", "breakeven")
        assert "pnl" in report
        assert "roi_pct" in report
        assert "ai_confidence" in report


def test_win_loss_reports_endpoint(client: TestClient) -> None:
    with client:
        resp = client.get("/api/reports/win-loss")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "reports" in data
        assert "win_rate_pct" in data["summary"]
        assert "total_pnl" in data["summary"]
        assert "profit_factor" in data["summary"]
        assert "today_summary" in data
        assert "dominion2_summary" in data
        assert "total_today_reports" in data
        assert len(data["reports"]) > 0

        # Query by date=today
        resp_today = client.get("/api/reports/win-loss?date=today")
        assert resp_today.status_code == 200
        data_today = resp_today.json()
        assert data_today["filter_date"] == "today"

        # Query by bot_type
        resp_bot = client.get("/api/reports/win-loss?bot_type=3_step_dom")
        assert resp_bot.status_code == 200
        data_bot = resp_bot.json()
        assert data_bot["filter_bot_type"] == "3_step_dom"


def test_win_loss_export_endpoints(client: TestClient) -> None:
    with client:
        # CSV export
        resp_csv = client.get("/api/reports/win-loss/export.csv")
        assert resp_csv.status_code == 200
        assert "text/csv" in resp_csv.headers["content-type"]
        assert "report_id" in resp_csv.text and "bot_type" in resp_csv.text and "ticker" in resp_csv.text

        # CSV export with date=today
        resp_csv_today = client.get("/api/reports/win-loss/export.csv?date=today")
        assert resp_csv_today.status_code == 200
        assert "today_" in resp_csv_today.headers["content-disposition"]

        # JSON export
        resp_json = client.get("/api/reports/win-loss/export.json")
        assert resp_json.status_code == 200
        assert "application/json" in resp_json.headers["content-type"]
        reports_list = resp_json.json()
        assert isinstance(reports_list, list)

        # JSON export with date=today and bot_type
        resp_json_today = client.get("/api/reports/win-loss/export.json?date=today&bot_type=3_step_dom")
        assert resp_json_today.status_code == 200
        assert "today_" in resp_json_today.headers["content-disposition"]


def test_cors_middleware_headers(client: TestClient) -> None:
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_middleware_disallows_unauthorized_origin(client: TestClient) -> None:
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://evil-attacker.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") != "http://evil-attacker.com"


def test_domination_config_endpoints(client: TestClient) -> None:
    with client:
        # GET config
        resp = client.get("/api/bot/domination/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "discount_limit_price" in data
        assert data["order_type"] == "limit"
        assert data["fee_per_contract"] == 0.00
        assert data["mode"] == "maker_sniper"

        # POST update discount price
        update_resp = client.post("/api/bot/domination/config", json={"discount_limit_price": 0.35})
        assert update_resp.status_code == 200
        up_data = update_resp.json()
        assert up_data["success"] is True
        assert up_data["discount_limit_price"] == 0.35

        # Verify state broadcast payload includes domination_discount_price
        state_resp = client.get("/api/state")
        assert state_resp.status_code == 200
        assert state_resp.json()["settings"]["domination_discount_price"] == 0.35

        # Also test update via /api/settings
        set_resp = client.post("/api/settings", json={"domination_discount_price": 0.40})
        assert set_resp.status_code == 200
        assert set_resp.json()["domination_discount_price"] == 0.40


def test_supported_assets_endpoint(client: TestClient) -> None:
    resp = client.get("/api/assets")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_asset" in data
    assert "assets" in data
    assert len(data["assets"]) == 4
    asset_ids = [a["id"] for a in data["assets"]]
    assert set(asset_ids) == {"BTC", "ETH", "SOL", "DOGE"}

    # Verify BTC asset config values
    btc_item = next(a for a in data["assets"] if a["id"] == "BTC")
    assert btc_item["name"] == "Bitcoin"
    assert btc_item["series_15m"] == "KXBTC15M"
    assert btc_item["cf_index_id"] == "BRTI"
    assert btc_item["strike_step"] == 25.0
    assert btc_item["min_spot_diff"] == 35.0


def test_select_active_asset_endpoint(client: TestClient) -> None:
    # 1. Select ETH
    resp_eth = client.post("/api/assets/select", json={"asset": "ETH"})
    assert resp_eth.status_code == 200
    data_eth = resp_eth.json()
    assert data_eth["status"] == "SUCCESS"
    assert data_eth["active_asset"] == "ETH"
    assert data_eth["series_ticker"] == "KXETH15M"

    # Verify state reflection
    state_resp = client.get("/api/state")
    assert state_resp.status_code == 200
    assert state_resp.json()["market"]["active_asset"] == "ETH"

    # 2. Select SOL
    resp_sol = client.post("/api/assets/select", json={"asset": "SOL"})
    assert resp_sol.status_code == 200
    assert resp_sol.json()["active_asset"] == "SOL"

    # 3. Select DOGE
    resp_doge = client.post("/api/assets/select", json={"asset": "DOGE"})
    assert resp_doge.status_code == 200
    assert resp_doge.json()["active_asset"] == "DOGE"

    # 4. Invalid asset rejected with 400
    resp_bad = client.post("/api/assets/select", json={"asset": "INVALID_COIN"})
    assert resp_bad.status_code == 400

    # 5. Restore back to BTC to preserve default environment
    resp_btc = client.post("/api/assets/select", json={"asset": "BTC"})
    assert resp_btc.status_code == 200
    assert resp_btc.json()["active_asset"] == "BTC"


def test_bot_arm_disarm_panic_endpoints(client: TestClient) -> None:
    # 1. Arm
    resp_arm = client.post("/api/bot/arm")
    assert resp_arm.status_code == 200
    assert resp_arm.json()["status"] == "ARMED"
    assert resp_arm.json()["armed"] is True

    # 2. Disarm
    resp_disarm = client.post("/api/bot/disarm")
    assert resp_disarm.status_code == 200
    assert resp_disarm.json()["status"] == "DISARMED"
    assert resp_disarm.json()["armed"] is False

    # 3. Panic
    resp_panic = client.post("/api/bot/panic")
    assert resp_panic.status_code == 200
    assert resp_panic.json()["status"] == "PANIC_EXECUTED"
    assert resp_panic.json()["armed"] is False


def test_mother_standalone_single_source_of_truth_sync(client: TestClient) -> None:
    """Verify that Mother server synchronizes 100% of its market, timer, and balance state from Standalone Bot."""
    import time
    from unittest.mock import patch
    from kalshi_sim.server import state, _build_full_state_payload

    # Simulate Standalone Bot running with active lock
    with patch("kalshi_sim.server.get_active_lock_holder", return_value=("standalone_bot", 99999)):
        # Inject mock standalone telemetry into state
        state._standalone_data = {
            "active_ticker": "KXETH15M-TRUTH-15",
            "active_asset": "ETH",
            "active_asset_name": "Ethereum",
            "target_strike": 2150.00,
            "target_strike_str": "$2,150.00",
            "spot_price": 2162.50,
            "spot_price_str": "$2,162.50",
            "spot_diff": 12.50,
            "spot_diff_pct": 0.581,
            "moneyness_diff_str": "+$12.50 (+0.581%)",
            "expiry_countdown_seconds": 385,
            "time_remaining_str": "06:25",
            "target_time_str": "09:00am ET",
            "time_window_str": "September 07, 08:45 - 09:00 AM ET",
            "balance": 24.6462,
            "today_pnl": 3.56,
            "settled_cycles": 10,
            "today_wins": 5,
            "today_losses": 5,
            "today_win_rate": 50.0,
            "best_yes_ask": 0.58,
            "best_yes_bid": 0.57,
            "best_no_ask": 0.43,
            "best_no_bid": 0.42,
            "armed": True,
            "playbook": "Playbook 2: OFI Drift",
            "edge_pct": 14.5,
            "ev": 0.04,
            "vpin": 0.18,
            "vpin_is_safe": True,
            "rationale": "High conviction drift detected",
            "orderbook_ladder": [
                {"side": "yes", "price_cents": "57.0¢", "price_raw": 0.57, "contracts": 10, "total": "$6", "depth_pct": 80}
            ],
        }
        state._last_standalone_sync = time.monotonic()

        payload = _build_full_state_payload()
        m = payload["market"]
        p = payload["portfolio"]
        s = payload["settings"]
        ai = payload["ai_signals"]

        # 1. Market parity
        assert m["ticker"] == "KXETH15M-TRUTH-15"
        assert m["target_strike"] == 2150.00
        assert m["target_strike_str"] == "$2,150.00"
        assert m["current_btc_price"] == 2162.50
        assert m["current_btc_price_str"] == "$2,162.50"
        assert m["diff"] == 12.50
        assert m["expiry_countdown_seconds"] == 385
        assert m["expiry_countdown_str"] == "06:25"
        assert m["target_time_str"] == "09:00am ET"

        # 2. Portfolio & PnL parity
        assert p["balance"] == 24.6462
        assert p["realized_pnl"] == 3.56
        assert p["total_trades"] == 10
        assert p["wins"] == 5
        assert p["losses"] == 5
        assert p["win_rate"] == 50.0

        # 3. AI signal parity
        assert ai["active_playbook"] == "Playbook 2: OFI Drift"
        assert ai["statistical_edge"] == 14.5
        assert ai["expected_value"] == 0.04
        assert ai["p_up"] == 0.50

        # 4. Settings & lock indicator
        assert s["standalone_lock_active"] is True
        assert s["standalone_sync_active"] is True
        assert s["lock_holder"] == "standalone_bot"

        # Clean up
        state._standalone_data = None
        state._last_standalone_sync = 0.0


def test_sweep_orders_endpoint(client: TestClient) -> None:
    """Verify POST /api/bot/sweep-orders returns SWEEP_COMPLETE and cleans resting orders."""
    from unittest.mock import patch
    with patch("kalshi_sim.server.get_active_lock_holder", return_value=None):
        # Test sweep when idle
        resp = client.post("/api/bot/sweep-orders")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SWEEP_COMPLETE"
        assert "cancelled_orders" in data
        assert "time_to_expiry_s" in data

        # Test sweep with simulated resting orders
        from kalshi_sim.server import state
        if state.sim_agent is not None:
            state.sim_agent.active_resting_orders = {
                "order-old-1": {"ticker": "KXBTC15M-OLD-TICKER", "price": 0.45},
                "order-active-1": {"ticker": state.active_ticker or "KXBTC15M-ACTIVE", "price": 0.48},
            }
            resp2 = client.post("/api/bot/sweep-orders?force=true")
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert data2["status"] == "SWEEP_COMPLETE"
            # Force true should sweep all resting orders
            assert len(state.sim_agent.active_resting_orders) == 0


def test_export_ticks_security_sanitization(client: TestClient) -> None:
    with client:
        # Invalid / path traversal / glob injection timeframe inputs must return 400 Bad Request
        invalid_inputs = [
            "../etc/passwd",
            "..",
            "mock/../",
            "*",
            "mock*",
            "timeframe;drop",
            "mock.jsonl",
            "../../../",
        ]
        for invalid_tf in invalid_inputs:
            resp = client.get(f"/api/export/ticks?timeframe={invalid_tf}")
            assert resp.status_code == 400, f"Expected 400 for timeframe '{invalid_tf}', got {resp.status_code}"
            assert resp.json()["detail"] == "Invalid timeframe parameter"

        # Valid timeframe parameters must not trigger 400 validation error
        valid_resp = client.get("/api/export/ticks?timeframe=mock")
        # Should be either 200 (if tick files exist) or 404 (if no tick files found), but NOT 400
        assert valid_resp.status_code in (200, 404)

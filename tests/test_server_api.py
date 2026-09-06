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
    assert data["market"]["ticker"].startswith("KXBTC")


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
        assert len(data["reports"]) > 0


def test_win_loss_export_endpoints(client: TestClient) -> None:
    with client:
        # CSV export
        resp_csv = client.get("/api/reports/win-loss/export.csv")
        assert resp_csv.status_code == 200
        assert "text/csv" in resp_csv.headers["content-type"]
        assert "report_id" in resp_csv.text and "bot_type" in resp_csv.text and "ticker" in resp_csv.text

        # JSON export
        resp_json = client.get("/api/reports/win-loss/export.json")
        assert resp_json.status_code == 200
        assert "application/json" in resp_json.headers["content-type"]
        reports_list = resp_json.json()
        assert isinstance(reports_list, list)


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

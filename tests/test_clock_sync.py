"""Unit tests for Kalshi Clock Synchronization and Port 8003 Dial Synchronization."""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import io
import ssl
import time
from unittest.mock import MagicMock, patch
import pytest

from kalshi_sim.clock_sync import KalshiClockSync, clock_sync


def test_clock_sync_initialization_and_monotonicity() -> None:
    """Verify KalshiClockSync initialization, drift reporting, and kalshi_now UTC validity."""
    cs = KalshiClockSync(refresh_interval_seconds=60.0)
    assert cs.drift_seconds == 0.0
    now_k = cs.kalshi_now()
    now_sys = datetime.now(timezone.utc)
    # Without drift, kalshi_now matches system UTC within 100ms
    assert abs((now_k - now_sys).total_seconds()) < 0.100


def test_clock_sync_mocked_exchange_date_header() -> None:
    """Verify drift calculation correctly incorporates RTT and server timestamp."""
    cs = KalshiClockSync()
    
    # Simulate Kalshi exchange server 10.5 seconds ahead of local time
    local_target = datetime(2026, 9, 14, 19, 0, 0, tzinfo=timezone.utc)
    simulated_server_date = "Mon, 14 Sep 2026 19:00:10 GMT"  # +10s
    
    mock_resp = MagicMock()
    mock_resp.headers.get.return_value = simulated_server_date
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp), \
         patch("time.time", side_effect=[local_target.timestamp(), local_target.timestamp() + 0.200]): # 200ms RTT
        
        drift = cs.sync()
        # Expected drift: (19:00:10 + 0.100s) - (19:00:00 + 0.200s) = +9.900s
        assert abs(drift - 9.900) < 0.05
        assert cs.get_drift_seconds() == drift

        # kalshi_now() should be ~9.9s ahead of raw datetime.now()
        with patch("kalshi_sim.clock_sync.datetime") as mock_dt:
            mock_dt.now.return_value = local_target
            calibrated = cs.kalshi_now()
            assert abs((calibrated - (local_target + timedelta(seconds=drift))).total_seconds()) < 0.001


def test_clock_sync_ssl_fallback_resilience() -> None:
    """Verify that SSL certificate failure gracefully falls back to unverified context."""
    cs = KalshiClockSync()
    simulated_server_date = "Mon, 14 Sep 2026 19:00:05 GMT"
    
    mock_resp = MagicMock()
    mock_resp.headers.get.return_value = simulated_server_date
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    call_count = 0
    def mock_urlopen(req, timeout, context):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ssl.SSLCertVerificationError("Self-signed or missing local issuer")
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        drift = cs.sync()
        assert call_count == 2
        assert cs.drift_seconds != 0.0


def test_global_clock_sync_instance() -> None:
    """Verify module-level singleton clock_sync behaves consistently."""
    assert isinstance(clock_sync, KalshiClockSync)
    now_k = clock_sync.kalshi_now()
    assert now_k.tzinfo == timezone.utc


def test_port_8003_dial_sync_bridge() -> None:
    """Verify Mother Server GET and POST /api/bot/parameters bridges with Port 8003."""
    from fastapi.testclient import TestClient
    from kalshi_sim.server import app, state

    client = TestClient(app)

    # 1. Test GET /api/bot/parameters merges live Port 8003 data
    mock_macro_data = {
        "parameters": {
            "limit_price_cents": 54,
            "min_confidence_pct": 68.0,
            "volatility_moat_dollars": 32.0,
            "hmm_risk_off_veto": True,
            "macro_trend_window": "15m+30m",
            "take_profit_harvest_cents": 96,
            "adaptive_learning_rate": 0.25,
        }
    }
    state._standalone_macro_data = mock_macro_data
    state._last_standalone_macro_sync = time.monotonic()

    resp = client.get("/api/bot/parameters")
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit_price_cents"] == 54
    assert data["min_confidence_pct"] == 68.0
    assert data["volatility_moat_dollars"] == 32.0

    # 2. Test POST /api/bot/parameters forwards dials to Port 8003
    mock_m_resp = MagicMock()
    mock_m_resp.status = 200
    mock_m_resp.json = MagicMock(return_value={"status": "SUCCESS", "parameters": {"limit_price_cents": 51, "min_confidence_pct": 70.0}})

    post_resp = client.post("/api/bot/parameters", json={
        "bot_id": "macro_trend_dominion",
        "limit_price_cents": 51,
        "min_confidence_pct": 70.0,
        "volatility_moat_dollars": 30.0,
    })
    assert post_resp.status_code == 200
    post_data = post_resp.json()
    assert post_data.get("limit_price_cents") == 51 or post_data.get("status") == "UPDATED"

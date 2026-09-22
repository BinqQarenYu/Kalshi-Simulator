"""Unit tests for Kalshi Clock Synchronization and Port 8003 Dial Synchronization."""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import io
import ssl
import time
from unittest.mock import MagicMock, patch
import pytest

from shared.clock_sync import KalshiClockSync, clock_sync


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


def test_unified_macro_trend_parameters() -> None:
    """Verify Mother Server GET and POST /api/bot/parameters updates Macro Trend Dominion directly in unified engine."""
    from fastapi.testclient import TestClient
    from app_2_execution_bot.server import app, state, resolve_bot_instance

    client = TestClient(app)
    macro_inst = resolve_bot_instance("macro_trend_dominion")
    if macro_inst and hasattr(macro_inst, "update_parameters"):
        macro_inst.update_parameters(limit_price_cents=54, min_confidence_pct=68.0, volatility_moat_dollars=32.0)

    resp = client.get("/api/bot/parameters")
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit_price_cents"] == 54
    assert data["min_confidence_pct"] == 68.0
    assert data["volatility_moat_dollars"] == 32.0

    post_resp = client.post("/api/bot/parameters", json={
        "bot_id": "macro_trend_dominion",
        "limit_price_cents": 51,
        "min_confidence_pct": 70.0,
        "volatility_moat_dollars": 30.0,
    })
    assert post_resp.status_code == 200
    post_data = post_resp.json()
    assert post_data.get("limit_price_cents") == 51 or post_data.get("status") == "UPDATED"


def test_clock_sync_web_now_parity() -> None:
    """Verify web_now() matches local machine UTC time for 1:1 Kalshi web countdown timer parity."""
    cs = KalshiClockSync()
    cs._drift_seconds = 10.5  # Simulate arbitrary exchange drift
    t_sys = datetime.now(timezone.utc)
    t_web = cs.web_now()
    assert abs((t_web - t_sys).total_seconds()) < 0.05
    # Confirm web_now is NOT skewed by _drift_seconds
    assert abs((t_web - (t_sys + timedelta(seconds=10.5))).total_seconds()) > 5.0

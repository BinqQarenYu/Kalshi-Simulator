import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from kalshi_sim.live_coordinator import LiveCoordinator
from kalshi_sim.order_client import KalshiLiveOrderClient
from kalshi_sim.exchange_router import KalshiExchangeAdapter


@pytest.fixture
def temp_maint_file(tmp_path):
    maint_file = tmp_path / "kalshi_maintenance.json"
    return maint_file


@pytest.mark.asyncio
async def test_maintenance_detection_and_veto(temp_maint_file):
    mock_key = MagicMock()
    mock_key.sign.return_value = b"dummy_signature_bytes"
    with patch("kalshi_sim.order_client.load_private_key", return_value=mock_key):
        client = KalshiLiveOrderClient(api_key_id="test_key", private_key_path="dummy.pem")
        client._maintenance_file = temp_maint_file

        # Initially online
        assert client.is_in_maintenance is False
        assert client.maintenance_reason == "Online"

        # Activate maintenance
        client.set_maintenance_state(True, reason="Scheduled CFTC Maintenance")
        assert client.is_in_maintenance is True
        assert client.maintenance_reason == "Scheduled CFTC Maintenance"
        assert temp_maint_file.exists()

        maint_data = json.loads(temp_maint_file.read_text())
        assert maint_data["active"] is True
        assert maint_data["reason"] == "Scheduled CFTC Maintenance"

        # Verify place_order is blocked during maintenance
        res = await client.place_order(ticker="KXBTC15M-TEST", side="yes", count=1)
        assert res is None

        # Verify LiveCoordinator vetoes live orders during maintenance
        coord = LiveCoordinator()
        with patch.object(coord, "check_kalshi_maintenance", return_value=(True, "Scheduled CFTC Maintenance")):
            is_ok, msg = coord.check_trade_permission(
                ticker="KXBTC15M-TEST",
                proposed_side="yes",
                bot_id="3_step_domination_bot",
                is_live=True,
            )
            assert is_ok is False
            assert "KALSHI MAINTENANCE VETO" in msg

        # Deactivate maintenance (Exchange back online)
        client.set_maintenance_state(False, reason="Online")
        assert client.is_in_maintenance is False
        maint_data_after = json.loads(temp_maint_file.read_text())
        assert maint_data_after["active"] is False


@pytest.mark.asyncio
async def test_http_503_triggers_maintenance():
    mock_key = MagicMock()
    mock_key.sign.return_value = b"dummy_signature_bytes"
    with patch("kalshi_sim.order_client.load_private_key", return_value=mock_key):
        client = KalshiLiveOrderClient(api_key_id="test_key", private_key_path="dummy.pem")
        client._maintenance_file = Path("data") / "kalshi_maintenance.json"

        # Mock aiohttp session returning 503 Service Unavailable
        mock_resp = AsyncMock()
        mock_resp.status = 503
        mock_resp.text.return_value = "503 Service Unavailable: Kalshi in maintenance mode"

        mock_session = MagicMock()
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)
        client._get_session = AsyncMock(return_value=mock_session)

        res = await client.place_order(ticker="KXBTC15M-TEST", side="yes", count=1)
        assert res is None
        assert client.is_in_maintenance is True
        assert "HTTP 503" in client.maintenance_reason

        # Cleanup test maintenance file state
        client.set_maintenance_state(False, reason="Online")


@pytest.mark.asyncio
async def test_exchange_adapter_maintenance_healthcheck():
    mock_key = MagicMock()
    mock_key.sign.return_value = b"dummy_signature_bytes"
    with patch("kalshi_sim.order_client.load_private_key", return_value=mock_key):
        client = KalshiLiveOrderClient(api_key_id="test_key", private_key_path="dummy.pem")
        adapter = KalshiExchangeAdapter(inner_client=client, is_live=True)

        client.set_maintenance_state(True, reason="Daily 3-5 AM Maintenance")
        is_ok, lat, msg = await adapter.check_health()
        assert is_ok is False
        assert "KALSHI_MAINTENANCE_PAUSED" in msg

        client.set_maintenance_state(False, reason="Online")

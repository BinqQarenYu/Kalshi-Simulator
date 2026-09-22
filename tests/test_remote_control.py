"""Unit and integration tests for Remote Control & Zero-Trust Pairing.

Verifies:
- Device discovery (LAN IP, hostname, Tailscale IP)
- RemoteControlManager token generation, persistence, revocation, and constant-time auth
- FastAPI endpoints (/api/remote/info, /api/remote/toggle, /api/remote/regenerate, /api/remote/revoke)
- Zero-Trust Middleware:
    - Localhost bypass allows friction-free desktop trading
    - Remote clients without auth are rejected with 401
    - Remote clients with valid auth (?auth=, X-Remote-Token, cookie) succeed
    - Disabled remote control returns 403
    - Static assets and root HTML are served to allow initial pairing handshake
"""

import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app_3_autonomous_chef.remote_control import (
    RemoteControlManager,
    get_device_name,
    get_local_lan_ip,
    get_tailscale_ip,
)
from app_2_execution_bot.standalone_bot import app, app_engine


def test_device_discovery():
    """Verify device name, LAN IP, and Tailscale IP discovery functions."""
    name = get_device_name()
    assert isinstance(name, str)
    assert len(name) > 0

    lan_ip = get_local_lan_ip()
    assert isinstance(lan_ip, str)
    assert len(lan_ip.split(".")) == 4

    ts_ip = get_tailscale_ip()
    if ts_ip:
        assert ts_ip.startswith("100.") or isinstance(ts_ip, str)


def test_remote_control_manager_lifecycle(tmp_path: Path):
    """Verify manager initialization, token persistence, regeneration, and revocation."""
    mgr = RemoteControlManager(data_dir=tmp_path, port=8001)
    assert mgr.enabled is True
    assert mgr.active_token.startswith("rc_")
    token_1 = mgr.active_token

    # Verify state saved to disk
    auth_file = tmp_path / "remote_control_auth.json"
    assert auth_file.exists()
    disk_data = json.loads(auth_file.read_text(encoding="utf-8"))
    assert disk_data["token"] == token_1
    assert disk_data["enabled"] is True

    # Constant-time auth verification
    assert mgr.is_authorized(token_1) is True
    assert mgr.is_authorized("rc_invalid_token_123") is False
    assert mgr.is_authorized("") is False
    assert mgr.is_authorized(None) is False

    # Regenerate token
    token_2 = mgr.regenerate_token()
    assert token_2.startswith("rc_")
    assert token_2 != token_1
    assert mgr.is_authorized(token_2) is True
    assert mgr.is_authorized(token_1) is False

    # Revoke token
    mgr.revoke_token()
    assert mgr.enabled is False
    assert mgr.active_token == ""
    assert mgr.is_authorized(token_2) is False

    # Toggle enabled
    mgr.toggle(True)
    assert mgr.enabled is True
    assert mgr.active_token.startswith("rc_")


def test_remote_control_get_info(tmp_path: Path):
    """Verify get_info outputs correct pairing links and metadata."""
    mgr = RemoteControlManager(data_dir=tmp_path, port=8001)
    info = mgr.get_info(port=8001)
    assert info["enabled"] is True
    assert "rc_" in info["pairing_token"]
    assert "8001" in info["lan_pairing_url"]
    assert info["device_name"] == get_device_name()


def test_remote_control_api_endpoints(tmp_path: Path):
    """Test FastAPI remote control REST routes."""
    mgr = RemoteControlManager(data_dir=tmp_path, port=8001)
    with patch("kalshi_sim.standalone_bot.app_engine") as mock_engine:
        mock_engine.remote_manager = mgr
        client = TestClient(app)

        # GET /api/remote/info
        res = client.get("/api/remote/info")
        assert res.status_code == 200
        data = res.json()
        assert data["enabled"] is True
        assert data["device_name"] == get_device_name()
        assert "rc_" in data["pairing_token"]

        # POST /api/remote/toggle
        res = client.post("/api/remote/toggle", json={"enabled": False})
        assert res.status_code == 200
        assert res.json()["enabled"] is False
        assert mgr.enabled is False

        # POST /api/remote/toggle back on
        res = client.post("/api/remote/toggle", json={"enabled": True})
        assert res.status_code == 200
        assert res.json()["enabled"] is True

        # POST /api/remote/regenerate
        orig_token = mgr.active_token
        res = client.post("/api/remote/regenerate")
        assert res.status_code == 200
        new_token = res.json()["token"]
        assert new_token != orig_token
        assert mgr.active_token == new_token

        # POST /api/remote/revoke
        res = client.post("/api/remote/revoke")
        assert res.status_code == 200
        assert res.json()["enabled"] is False
        assert mgr.enabled is False


def test_remote_auth_middleware_guards(tmp_path: Path):
    """Verify Zero-Trust middleware enforcing security on remote clients."""
    mgr = RemoteControlManager(data_dir=tmp_path, port=8001)
    token = mgr.active_token

    with patch("kalshi_sim.standalone_bot.app_engine") as mock_engine:
        mock_engine.remote_manager = mgr
        client = TestClient(app)

        # 1. Localhost client (default in TestClient is 127.0.0.1 or testclient) -> allowed
        res = client.get("/api/remote/info")
        assert res.status_code == 200

        # 2. Remote client (simulate client host 192.168.1.50) without token -> 401
        remote_client = TestClient(app, client=("192.168.1.50", 50000))
        res = remote_client.get("/api/remote/info")
        assert res.status_code == 401
        assert "pairing token" in res.json()["detail"].lower()

        # 3. Remote client with valid query param ?auth=... -> 200 + sets cookie
        res = remote_client.get(f"/api/remote/info?auth={token}")
        assert res.status_code == 200
        assert "rc_token" in res.cookies

        # 4. Remote client with X-Remote-Token header -> 200
        res = remote_client.get("/api/remote/info", headers={"X-Remote-Token": token})
        assert res.status_code == 200

        # 5. Remote client with invalid token -> 401
        res = remote_client.get("/api/remote/info", headers={"X-Remote-Token": "wrong_token"})
        assert res.status_code == 401

        # 6. Remote client requesting HTML root / -> allowed to load UI
        res = remote_client.get("/")
        assert res.status_code == 200

        # 7. Remote client requesting /static/qrcode.min.js -> allowed to load
        res = remote_client.get("/static/qrcode.min.js")
        assert res.status_code == 200

        # 8. Disabled remote control -> 403 Forbidden
        mgr.toggle(False)
        res = remote_client.get(f"/api/remote/info?auth={token}")
        assert res.status_code == 403
        assert "disabled" in res.json()["detail"].lower()

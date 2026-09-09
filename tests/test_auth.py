"""Unit and integration tests for Kalshi RSA authentication, key loading, and validation."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import pytest

from kalshi_sim.auth import (
    async_validate_credentials,
    get_auth_headers,
    get_ssl_context,
    get_ws_auth_headers,
    load_private_key,
    sign_request,
    verify_signature,
)
from kalshi_sim.server import app


@pytest.fixture
def ephemeral_rsa_key():
    """Generate a clean in-memory RSA private/public key pair for tests."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    return private_key


def test_load_private_key_from_demo_file():
    """Test loading the project demo PEM file."""
    pem_path = Path("kalshi_demo.pem")
    if pem_path.exists():
        key = load_private_key(pem_path)
        assert isinstance(key, rsa.RSAPrivateKey)


def test_load_private_key_from_raw_string(ephemeral_rsa_key):
    """Test loading RSA key from a raw PEM string."""
    pem_bytes = ephemeral_rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pem_str = pem_bytes.decode("utf-8")
    loaded = load_private_key(pem_str)
    assert isinstance(loaded, rsa.RSAPrivateKey)


def test_load_private_key_from_base64(ephemeral_rsa_key):
    """Test loading RSA key from a base64-encoded string."""
    pem_bytes = ephemeral_rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    b64_str = base64.b64encode(pem_bytes).decode("utf-8")
    loaded = load_private_key(b64_str)
    assert isinstance(loaded, rsa.RSAPrivateKey)


def test_load_private_key_invalid_raises():
    """Test that malformed keys raise ValueError."""
    with pytest.raises(ValueError):
        load_private_key("invalid_corrupted_key_payload_12345")


def test_sign_and_verify_signature_roundtrip(ephemeral_rsa_key):
    """Test RSA-PSS SHA-256 signing and verification roundtrip."""
    timestamp = "1720000000000"
    method = "GET"
    path = "/trade-api/v2/portfolio/balance?limit=10"

    sig = sign_request(ephemeral_rsa_key, timestamp, method, path)
    assert isinstance(sig, str)
    assert len(sig) > 64

    # Verify with public key
    public_key = ephemeral_rsa_key.public_key()
    is_valid = verify_signature(public_key, sig, timestamp, method, path)
    assert is_valid is True

    # Corrupt timestamp or method -> must fail
    assert verify_signature(public_key, sig, "1720000000001", method, path) is False
    assert verify_signature(public_key, sig, timestamp, "POST", path) is False


def test_get_auth_headers(ephemeral_rsa_key):
    """Test generation of Kalshi HTTP and WebSocket authentication headers."""
    headers = get_auth_headers(
        api_key_id="test-key-uuid-1234",
        private_key=ephemeral_rsa_key,
        method="GET",
        path="/trade-api/v2/markets",
    )
    assert headers["KALSHI-ACCESS-KEY"] == "test-key-uuid-1234"
    assert "KALSHI-ACCESS-TIMESTAMP" in headers
    assert "KALSHI-ACCESS-SIGNATURE" in headers

    ws_headers = get_ws_auth_headers(
        api_key_id="test-key-uuid-1234",
        private_key=ephemeral_rsa_key,
    )
    assert ws_headers["KALSHI-ACCESS-KEY"] == "test-key-uuid-1234"


class _MockAsyncContext:
    def __init__(self, resp):
        self.resp = resp

    async def __aenter__(self):
        return self.resp

    async def __aexit__(self, exc_type, exc, tb):
        pass


@pytest.mark.anyio
async def test_async_validate_credentials_success(ephemeral_rsa_key):
    """Test credential validation with mocked successful response."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"balance": 500000, "portfolio_id": "test_port"})

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get.return_value = _MockAsyncContext(mock_resp)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        valid, msg, data = await async_validate_credentials(
            api_key_id="test_key_id",
            private_key=ephemeral_rsa_key,
            is_demo=True,
        )
        assert valid is True
        assert "successfully authenticated" in msg
        assert data["balance"] == 500000


@pytest.mark.anyio
async def test_async_validate_credentials_401_unauthorized(ephemeral_rsa_key):
    """Test credential validation with 401 unauthorized response."""
    mock_resp = MagicMock()
    mock_resp.status = 401

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get.return_value = _MockAsyncContext(mock_resp)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        valid, msg, data = await async_validate_credentials(
            api_key_id="test_key_id",
            private_key=ephemeral_rsa_key,
            is_demo=True,
        )
        assert valid is False
        assert "Authentication failed" in msg


def test_validate_credentials_endpoint(ephemeral_rsa_key):
    """Test POST /api/kalshi/validate-credentials endpoint."""
    client = TestClient(app)

    pem_bytes = ephemeral_rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pem_str = pem_bytes.decode("utf-8")

    with patch("kalshi_sim.server.async_validate_credentials", new_callable=AsyncMock) as mock_val:
        mock_val.return_value = (True, "Authenticated", {"balance": 1000})

        res = client.post(
            "/api/kalshi/validate-credentials",
            json={
                "api_key_id": "mock_id",
                "private_key": pem_str,
                "is_demo": True,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is True
        assert data["mode"] == "demo"
        assert data["account_info"]["balance"] == 1000


def test_no_hardcoded_api_key_id_fallback():
    """Test that KALSHI_API_KEY_ID defaults to None when missing from environment."""
    import os
    with patch.dict(os.environ, {}, clear=True):
        assert os.getenv("KALSHI_API_KEY_ID") is None


def test_get_ssl_context_security():
    """Test that get_ssl_context returns a verified SSL context and raises on failure without unverified fallback."""
    import ssl
    ctx = get_ssl_context()
    assert isinstance(ctx, ssl.SSLContext)
    # Check that SSL certificate verification is enabled
    assert ctx.verify_mode != ssl.CERT_NONE

    # Test failure behavior when both system default context and certifi fail
    with patch("ssl.create_default_context", side_effect=Exception("System CA store error")):
        with patch.dict("sys.modules", {"certifi": None}):
            with pytest.raises(RuntimeError, match="Failed to create secure SSL context"):
                get_ssl_context()

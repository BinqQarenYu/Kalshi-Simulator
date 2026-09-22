"""Unit and integration tests for live order dispatching, rate limiting, and dry-run safety."""

from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pytest

from app_2_execution_bot.rate_limiter import AsyncTokenBucket
from app_2_execution_bot.server import app


@pytest.mark.anyio
async def test_token_bucket_rate_limiter_burst_and_refill():
    """Test AsyncTokenBucket capacity, burst consumption, and refill."""
    bucket = AsyncTokenBucket(rate=10.0, capacity=5.0)

    # 1. Burst 5 tokens immediately
    for _ in range(5):
        acquired = await bucket.acquire(1.0, timeout=0.1)
        assert acquired is True

    # 2. 6th token should need wait/fail with 0.01s timeout
    t0 = time.monotonic()
    acquired = await bucket.acquire(1.0, timeout=0.02)
    assert acquired is False

    # 3. Wait for refill (0.15s should refill ~1.5 tokens)
    await asyncio.sleep(0.15)
    acquired = await bucket.acquire(1.0, timeout=0.5)
    assert acquired is True


def test_live_order_dry_run_safety_mode():
    """Test that live order endpoint defaults to safety dry-run without routing funds."""
    with TestClient(app) as client:
        res = client.post(
            "/api/kalshi/orders/live",
            json={
                "ticker": "KXBTC15M-T78650",
                "side": "yes",
                "count": 25,
                "action": "buy",
                "order_type": "market",
                "dry_run": True,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["is_dry_run"] is True
        assert data["status"] == "dry_run"
        assert data["count"] == 25
        assert data["ticker"] == "KXBTC15M-T78650"


def test_live_order_execution_mocked_success():
    """Test live order execution when enabled and mocked exchange succeeds."""
    with TestClient(app) as client:
        with patch.dict("os.environ", {"KALSHI_API_KEY_ID": "test_id", "KALSHI_PRIVATE_KEY_PATH": "test_key.pem", "KALSHI_LIVE_TRADING_ENABLED": "true"}):
            with patch("kalshi_sim.server.get_active_lock_holder", return_value=None):
                with patch("kalshi_sim.server.KalshiLiveOrderClient") as mock_cls:
                    mock_client = AsyncMock()
                    mock_client.place_order.return_value = {
                        "order_id": "order_uuid_12345",
                        "status": "executed",
                        "yes_price_dollars": "0.48",
                    }
                    mock_cls.return_value = mock_client

                    res = client.post(
                        "/api/kalshi/orders/live",
                        json={
                            "ticker": "KXBTC15M-T78650",
                            "side": "yes",
                            "count": 10,
                            "action": "buy",
                            "order_type": "limit",
                            "limit_price_dollars": "0.48",
                            "dry_run": False,
                        },
                    )
                    assert res.status_code == 200
                    data = res.json()
                    assert data["success"] is True
                    assert data["order_id"] == "order_uuid_12345"
                    assert data["status"] == "executed"
                    assert data["fill_price"] == "0.48"
                    assert data["is_dry_run"] is False


def test_live_order_cancellation_endpoint():
    """Test cancelling live order on exchange."""
    with TestClient(app) as client:
        with patch.dict("os.environ", {"KALSHI_API_KEY_ID": "test_id", "KALSHI_PRIVATE_KEY_PATH": "test_key.pem"}):
            with patch("kalshi_sim.server.KalshiLiveOrderClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.cancel_order.return_value = True
                mock_cls.return_value = mock_client

                res = client.delete("/api/kalshi/orders/live/order_uuid_999")
                assert res.status_code == 200
                data = res.json()
                assert data["success"] is True
                assert data["order_id"] == "order_uuid_999"


def test_live_open_orders_endpoint():
    """Test fetching open orders from live exchange."""
    with TestClient(app) as client:
        with patch.dict("os.environ", {"KALSHI_API_KEY_ID": "test_id", "KALSHI_PRIVATE_KEY_PATH": "test_key.pem"}):
            with patch("kalshi_sim.server.KalshiLiveOrderClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.get_open_orders.return_value = [
                    {"order_id": "resting_1", "ticker": "KXBTC15M-T78650", "status": "resting"}
                ]
                mock_cls.return_value = mock_client

                res = client.get("/api/kalshi/orders/live/open")
                assert res.status_code == 200
                data = res.json()
                assert len(data) == 1
                assert data[0]["order_id"] == "resting_1"

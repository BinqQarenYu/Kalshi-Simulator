"""Unit tests for BTC spot sync REST fallback exception logging."""

import asyncio
import logging
from unittest.mock import patch
import pytest

import aiohttp


@pytest.mark.asyncio
async def test_live_btc_spot_sync_loop_exception_logging(caplog):
    """Verify live_btc_spot_sync_loop logs exceptions for both Coinbase and Binance REST failures."""
    caplog.set_level(logging.DEBUG)

    class DummyContextManager:
        async def __aenter__(self):
            raise Exception("Simulated REST Error")

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class DummySession:
        def get(self, url, **kwargs):
            return DummyContextManager()

    class DummySessionContextManager:
        async def __aenter__(self):
            return DummySession()

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    # Import locally or dynamically to isolate test execution
    from kalshi_sim.server import live_btc_spot_sync_loop

    with patch("kalshi_sim.server.create_aiohttp_connector"):
        with patch("aiohttp.ClientSession", return_value=DummySessionContextManager()):
            with patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError()]):
                with pytest.raises(asyncio.CancelledError):
                    await live_btc_spot_sync_loop()

    assert "[SPOT SYNC] Coinbase REST sync error: Simulated REST Error" in caplog.text
    assert "[SPOT SYNC] Binance REST fallback sync error: Simulated REST Error" in caplog.text

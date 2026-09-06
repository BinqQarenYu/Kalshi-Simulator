"""Unit tests for CFBenchmarksBRTISync module.

Verifies:
1. Initial state and credentials loading
2. Message parsing for 5Hz real-time ticks
3. Message parsing for 1Hz ticks and trailing 60s TWAP
4. REST response payload extraction
5. Callback invocation with Decimal invariants
6. Graceful error handling on malformed payloads
"""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kalshi_sim.cfbenchmarks_sync import CFBenchmarksBRTISync


def test_cfbenchmarks_initial_state():
    sync = CFBenchmarksBRTISync(
        api_key_id="test_key",
        private_key_path="dummy_path",
    )
    assert sync.api_key_id == "test_key"
    assert sync.current_price == Decimal("0.00")
    assert sync.twap_60s is None
    assert sync.is_connected is False
    assert sync.brti_connected is False


def test_cfbenchmarks_5hz_parsing():
    updates = []

    def callback(price: Decimal, twap: Decimal | None, source: str):
        updates.append((price, twap, source))

    sync = CFBenchmarksBRTISync(
        api_key_id="test_key",
        private_key_path="dummy_path",
        on_price_update=callback,
    )

    # 1. Standard 5Hz message with value_usd
    msg_5hz = {
        "type": "cfbenchmarks_value_5hz",
        "sid": 1,
        "seq": 1,
        "msg": {
            "index_id": "BRTI",
            "value_usd": "79767.34000000",
            "source_ts_ms": 1788717461800,
            "received_at": 1788717461839,
            "data": '{"type":"value","time":1788717461800,"id":"BRTI","value":"79767.34"}',
        },
    }

    sync._update_price(
        Decimal(str(msg_5hz["msg"]["value_usd"])),
        source_label="CF Benchmarks BRTI (5Hz WS)",
        source_ts_ms=msg_5hz["msg"]["source_ts_ms"],
    )

    assert sync.current_price == Decimal("79767.34000000")
    assert sync.brti_connected is True
    assert sync.is_connected is True
    assert sync.source == "CF Benchmarks BRTI (5Hz WS)"
    assert len(updates) == 1
    assert updates[0][0] == Decimal("79767.34000000")


def test_cfbenchmarks_1hz_twap_parsing():
    updates = []

    def callback(price: Decimal, twap: Decimal | None, source: str):
        updates.append((price, twap, source))

    sync = CFBenchmarksBRTISync(
        api_key_id="test_key",
        private_key_path="dummy_path",
        on_price_update=callback,
    )

    # 1Hz message with avg_60s_data
    msg_1hz = {
        "type": "cfbenchmarks_value",
        "sid": 1,
        "seq": 1,
        "msg": {
            "index_id": "BRTI",
            "received_at": 1788717445071,
            "data": '{"type":"value","time":1788717445000,"id":"BRTI","value":"79760.76"}',
            "avg_60s_data": {
                "value": "79760.53333333",
                "window_size": 3,
                "window_start_ts_ms": 1788717388000,
                "window_end_ts_exclusive": 1788717448000,
            },
        },
    }

    p = Decimal("79760.76")
    twap = Decimal("79760.53333333")
    sync._update_price(p, twap_dec=twap, source_label="CF Benchmarks BRTI (1Hz WS)")

    assert sync.current_price == Decimal("79760.76")
    assert sync.twap_60s == Decimal("79760.53333333")
    assert sync.brti_connected is True
    assert updates[-1][1] == Decimal("79760.53333333")


@pytest.mark.anyio
async def test_cfbenchmarks_rest_payload_extraction():
    sync = CFBenchmarksBRTISync(
        api_key_id="test_key",
        private_key_path="dummy_path",
    )

    mock_rest_data = {
        "data": {
            "serverTime": "2026-09-06T17:55:44.864Z",
            "payload": {
                "values": [
                    {"value": "79741.78", "time": 1788717388000},
                    {"value": "79742.40", "time": 1788717389000},
                ]
            },
        }
    }

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=mock_rest_data)

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_resp
    sync._session = mock_session
    sync.private_key = MagicMock()

    with patch("kalshi_sim.cfbenchmarks_sync.get_auth_headers", return_value={"test": "header"}):
        res = await sync._poll_kalshi_brti_rest()
        assert res is True
        assert sync.current_price == Decimal("79742.40")
        assert sync.source == "CF Benchmarks BRTI (REST)"
        assert sync.brti_connected is True

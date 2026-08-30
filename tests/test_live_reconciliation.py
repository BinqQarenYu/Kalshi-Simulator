"""Unit and integration tests for live Kalshi portfolio sync and ledger reconciliation."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import pytest

from kalshi_sim.order_client import KalshiLiveOrderClient
from kalshi_sim.portfolio import Portfolio
from kalshi_sim.schemas import OrderSide, Timeframe
from kalshi_sim.server import app, state


@pytest.fixture
def ephemeral_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.mark.anyio
async def test_get_live_portfolio_state_parsing(ephemeral_key):
    """Test parsing of raw exchange balance and position dictionaries."""
    client = KalshiLiveOrderClient(
        api_key_id="test-key",
        private_key_path=ephemeral_key,
    )

    client.get_balance = AsyncMock(return_value={
        "balance": 150000,  # 150,000 cents = $1,500.00
        "available_balance": 120000,  # $1,200.00
        "payout": 30000,  # $300.00
    })

    client.get_positions = AsyncMock(return_value=[
        {
            "ticker": "KXBTC15M-T78650",
            "position": 50,
            "fees_paid": 250,  # $2.50
            "realized_pnl": 500,  # $5.00
            "resting_orders_count": 1,
        }
    ])

    live_state = await client.get_live_portfolio_state()
    assert live_state.balance_dollars == Decimal("1500.00")
    assert live_state.available_margin == Decimal("1200.00")
    assert live_state.payout_pending == Decimal("300.00")
    assert len(live_state.positions) == 1

    pos = live_state.positions[0]
    assert pos.ticker == "KXBTC15M-T78650"
    assert pos.position == 50
    assert pos.side == OrderSide.YES
    assert pos.fees_paid == Decimal("2.50")
    assert pos.realized_pnl == Decimal("5.00")
    assert pos.resting_orders_count == 1


@pytest.mark.anyio
async def test_reconcile_with_simulated_synchronized(ephemeral_key):
    """Test reconciliation when simulated and exchange balances match."""
    client = KalshiLiveOrderClient(
        api_key_id="test-key",
        private_key_path=ephemeral_key,
    )

    client.get_balance = AsyncMock(return_value={"balance": 1000000})  # $10,000.00
    client.get_positions = AsyncMock(return_value=[])

    sim_portfolio = Portfolio(starting_balance=Decimal("10000.00"))

    report = await client.reconcile_with_simulated(sim_portfolio)
    assert report.is_synchronized is True
    assert report.cash_discrepancy == Decimal("0.00")
    assert report.simulated_positions_count == 0
    assert report.exchange_positions_count == 0
    assert len(report.alerts) == 0


@pytest.mark.anyio
async def test_reconcile_with_simulated_discrepancy(ephemeral_key):
    """Test reconciliation reporting divergence in cash and positions."""
    client = KalshiLiveOrderClient(
        api_key_id="test-key",
        private_key_path=ephemeral_key,
    )

    client.get_balance = AsyncMock(return_value={"balance": 950000})  # $9,500.00
    client.get_positions = AsyncMock(return_value=[
        {"ticker": "KXBTC15M-T78650", "position": 10, "fees_paid": 0, "realized_pnl": 0}
    ])

    sim_portfolio = Portfolio(starting_balance=Decimal("10000.00"))

    report = await client.reconcile_with_simulated(sim_portfolio)
    assert report.is_synchronized is False
    assert report.cash_discrepancy == Decimal("-500.00")
    assert report.exchange_positions_count == 1
    assert report.simulated_positions_count == 0
    assert len(report.alerts) >= 2


def test_server_portfolio_sync_endpoint():
    """Test GET /api/kalshi/portfolio/sync endpoint."""
    with TestClient(app) as test_client:
        res = test_client.get("/api/kalshi/portfolio/sync")
        assert res.status_code == 200
        data = res.json()
        assert "authenticated" in data
        assert "reconciliation" in data


def test_server_live_balance_endpoint():
    """Test GET /api/kalshi/balance endpoint."""
    with TestClient(app) as test_client:
        res = test_client.get("/api/kalshi/balance")
        assert res.status_code == 200
        data = res.json()
        assert "balance_dollars" in data
        assert "available_margin" in data
        assert "positions" in data
        assert "is_authenticated" in data



"""Unit and integration tests for Agent_integrity_check suite."""

from __future__ import annotations

from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from kalshi_sim.integrity_agent import AgentIntegrityCheck, get_integrity_agent
from kalshi_sim.portfolio import Portfolio
from kalshi_sim.schemas import OrderSide, SettlementResult
from kalshi_sim.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_integrity_mathematical_invariants() -> None:
    agent = AgentIntegrityCheck()
    portfolio = Portfolio(starting_balance=Decimal("100.00"))

    items = agent.audit_mathematical_invariants(portfolio)
    assert len(items) >= 3

    # 1. Decimal type check
    dec_check = next(i for i in items if i.name == "Decimal Type Strictness")
    assert dec_check.status == "PASS"

    # 2. Equity invariant
    equity_check = next(i for i in items if i.name == "Equity Reconciliation Invariant")
    assert equity_check.status == "PASS"

    # 3. Payoff bounds
    payoff_check = next(i for i in items if i.name == "Binary Option Payoff Boundaries")
    assert payoff_check.status == "PASS"


def test_integrity_payoff_violation_detection() -> None:
    agent = AgentIntegrityCheck()
    portfolio = Portfolio(starting_balance=Decimal("100.00"))

    # Inject an illegal settlement payout (e.g. $2.00 on win instead of $1.00)
    bad_settlement = SettlementResult(
        ticker="KXBTC-TEST",
        side=OrderSide.YES,
        size=10,
        entry_price=Decimal("0.50"),
        settlement_price=Decimal("1.00"),
        outcome="win",
        pnl=Decimal("15.00"),  # Illegal: should be (1.00 - 0.50) * 10 = $5.00
    )
    portfolio._settlement_history.append(bad_settlement)

    items = agent.audit_mathematical_invariants(portfolio)
    payoff_check = next(i for i in items if i.name == "Binary Option Payoff Boundaries")
    assert payoff_check.status == "FAIL"


def test_integrity_orderbook_uncrossed_invariant() -> None:
    agent = AgentIntegrityCheck()

    class MockBook:
        best_yes_bid = Decimal("0.45")
        best_no_bid = Decimal("0.50")

    class MockOBManager:
        def get_book(self, ticker: str):
            return MockBook()

    items = agent.audit_microstructure(MockOBManager(), "KXBTC-TEST")
    uncrossed_check = next(i for i in items if i.name == "Uncrossed Book Invariant")
    assert uncrossed_check.status == "PASS"

    # Now simulate a crossed book anomaly (YES Bid: $0.60 + NO Bid: $0.55 = $1.15 > $1.00)
    MockBook.best_yes_bid = Decimal("0.60")
    MockBook.best_no_bid = Decimal("0.55")

    items_crossed = agent.audit_microstructure(MockOBManager(), "KXBTC-TEST")
    crossed_check = next(i for i in items_crossed if i.name == "Uncrossed Book Invariant")
    assert crossed_check.status == "WARN"


def test_integrity_latency_sampling() -> None:
    agent = AgentIntegrityCheck()
    for latency in [1.2, 2.5, 3.1, 4.0, 5.5, 6.2]:
        agent.record_latency(latency)

    items = agent.audit_latency()
    lat_check = next(i for i in items if i.name == "WebSocket Processing Latency")
    assert lat_check.status == "PASS"


def test_integrity_ground_truth_and_connection() -> None:
    agent = AgentIntegrityCheck()

    # Normal case
    items = agent.audit_ground_truth_and_connection(
        mode="live",
        btc_price=Decimal("77500.00"),
        ws_connected=True,
    )
    assert all(i.status == "PASS" for i in items)

    # Anomaly case: Corrupted spot price
    items_anom = agent.audit_ground_truth_and_connection(
        mode="live",
        btc_price=Decimal("12.50"),  # Corrupted BTC price
        ws_connected=True,
    )
    spot_check = next(i for i in items_anom if i.name == "Bitcoin Spot Index Plausibility")
    assert spot_check.status == "FAIL"


def test_integrity_full_scan_report() -> None:
    agent = AgentIntegrityCheck()
    portfolio = Portfolio(starting_balance=Decimal("100.00"))

    report = agent.run_full_audit(
        portfolio=portfolio,
        orderbook=None,
        active_ticker="KXBTC15M-TEST",
        mode="mock",
        btc_price=Decimal("77500.00"),
        ws_connected=True,
    )

    assert "score" in report
    assert "status" in report
    assert "checks" in report
    assert report["score"] >= 80.0
    assert report["status"] in ("HEALTHY", "WARNING")


def test_integrity_rest_endpoints(client: TestClient) -> None:
    with client:
        # 1. GET status
        resp = client.get("/api/integrity/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "score" in data
        assert "status" in data
        assert "checks" in data

        # 2. POST audit-now
        resp_audit = client.post("/api/integrity/audit-now")
        assert resp_audit.status_code == 200
        audit_data = resp_audit.json()
        assert audit_data["score"] >= 0.0
        assert audit_data["status"] in ("HEALTHY", "WARNING", "CRITICAL")
        assert len(audit_data["checks"]) > 0

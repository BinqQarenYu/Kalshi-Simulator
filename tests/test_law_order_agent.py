"""Comprehensive Unit & Invariant Tests for AgentLawOrder (CFTC, Legal & API Compliance Guardian)."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from kalshi_sim.law_order_agent import AgentLawOrder, ComplianceCheckItem
from shared.schemas import OrderSide, OrderType, OrderStatus, SimulatedOrder, Timeframe


@pytest.fixture
def law_agent():
    return AgentLawOrder(
        max_contracts_per_market=250,
        max_notional_exposure=Decimal("25000.00"),
        rate_limit_rps=30.0,
        burst_capacity=40,
    )


def test_initial_compliance_status(law_agent):
    status = law_agent.get_compliance_status()
    assert status["status"] == "COMPLIANT"
    assert status["score"] == 100.0
    assert status["total_checks"] == 9
    assert status["passed"] == 9
    assert status["failed"] == 0
    assert status["warnings"] == 0
    assert len(status["checks"]) == 9
    assert status["recent_violations_count"] == 0


def test_get_dos_and_donts(law_agent):
    handbook = law_agent.get_dos_and_donts()
    assert "dos" in handbook
    assert "donts" in handbook
    assert len(handbook["dos"]) >= 5
    assert len(handbook["donts"]) >= 5

    # Verify key CFTC rules are present
    dont_titles = [item["title"] for item in handbook["donts"]]
    assert any("Wash Trading" in t for t in dont_titles)
    assert any("Spoofing" in t for t in dont_titles)
    assert any("Secret Key" in t for t in dont_titles)

    do_titles = [item["title"] for item in handbook["dos"]]
    assert any("Pre-Trade Wash Trade" in t for t in do_titles)
    assert any("Rate Limits" in t for t in do_titles)
    assert any("Audit Trail" in t for t in do_titles)


def test_wash_trade_prevention(law_agent):
    # Setup resting YES order at $0.55
    resting_order = SimulatedOrder(
        order_id="rest_yes_01",
        ticker="KXBTC15M-T78000",
        side=OrderSide.YES,
        order_type=OrderType.LIMIT,
        size=10,
        limit_price=Decimal("0.55"),
        timeframe=Timeframe.FIFTEEN_MIN,
        created_at=datetime.now(timezone.utc),
        status=OrderStatus.PENDING,
        reasoning="Test resting order",
    )

    # 1. Inbound NO order at $0.50 -> Sum = 0.55 + 0.50 = 1.05 >= 1.00 -> WASH TRADE!
    is_ok, msg = law_agent.validate_pre_trade_order(
        ticker="KXBTC15M-T78000",
        side="no",
        size=5,
        price=Decimal("0.50"),
        open_orders=[resting_order],
        current_positions={},
        current_balance=Decimal("1000.00"),
    )
    assert is_ok is False
    assert "Wash Trade" in msg or "wash" in msg.lower()

    # Verify compliance score downgraded and violation logged
    status = law_agent.get_compliance_status()
    assert status["score"] < 100.0
    assert status["recent_violations_count"] > 0


def test_wash_trade_non_crossing_allowed(law_agent):
    # Setup resting YES order at $0.40
    resting_order = SimulatedOrder(
        order_id="rest_yes_02",
        ticker="KXBTC15M-T78000",
        side=OrderSide.YES,
        order_type=OrderType.LIMIT,
        size=10,
        limit_price=Decimal("0.40"),
        timeframe=Timeframe.FIFTEEN_MIN,
        created_at=datetime.now(timezone.utc),
        status=OrderStatus.PENDING,
        reasoning="Test resting order",
    )

    # Inbound NO order at $0.45 -> Sum = 0.40 + 0.45 = 0.85 < 1.00 -> Valid uncrossed market
    is_ok, msg = law_agent.validate_pre_trade_order(
        ticker="KXBTC15M-T78000",
        side="no",
        size=5,
        price=Decimal("0.45"),
        open_orders=[resting_order],
        current_positions={},
        current_balance=Decimal("1000.00"),
    )
    assert is_ok is True
    assert "compliance approved" in msg.lower()


def test_position_limit_rejection(law_agent):
    # Max contracts is 250
    # Try placing order of size 300
    is_ok, msg = law_agent.validate_pre_trade_order(
        ticker="KXBTC15M-T78000",
        side="yes",
        size=300,
        price=Decimal("0.50"),
        open_orders=[],
        current_positions={},
        current_balance=Decimal("10000.00"),
    )
    assert is_ok is False
    assert "Position limit exceeded" in msg
    assert "250 contracts" in msg


def test_rate_limiter_governor(law_agent):
    # Burst capacity is 40. Consume 40 immediately
    for _ in range(40):
        ok, _ = law_agent.check_rate_limit(cost=1.0)
        assert ok is True

    # 41st request should be rejected by rate limiter
    ok, msg = law_agent.check_rate_limit(cost=1.0)
    assert ok is False
    assert "Rate limit quota exceeded" in msg

    # Check status reflects rate warning/failure
    status = law_agent.get_compliance_status()
    rate_check = next((c for c in status["checks"] if c["category"] == "rate_limits"), None)
    assert rate_check is not None
    assert rate_check["status"] in ("FAIL", "WARN")


def test_cancellation_tracking_and_otr(law_agent):
    # Record 5 orders and 5 cancellations
    for i in range(5):
        law_agent.record_order_cancellation(f"ord_{i}", "KXBTC15M-T78000")

    status = law_agent.get_compliance_status()
    spoof_check = next((c for c in status["checks"] if "Anti-Spoofing" in c["name"]), None)
    assert spoof_check is not None
    assert spoof_check["status"] in ("PASS", "WARN")


def test_credential_leak_audit(law_agent):
    # Safe payload
    safe_item = law_agent.audit_credential_security({"ticker": "KXBTC15M", "price": 0.50})
    assert safe_item.status == "PASS"

    # Unsafe payload with private key leaked
    unsafe_item = law_agent.audit_credential_security({
        "ticker": "KXBTC15M",
        "secret": "-----BEGIN RSA PRIVATE KEY-----MIIE..."
    })
    assert unsafe_item.status == "FAIL"
    assert "CRITICAL SECURITY LEAK" in unsafe_item.message

    # Unsafe payload with api_secret key
    unsafe_secret_item = law_agent.audit_credential_security({
        "ticker": "KXBTC15M",
        "api_secret": "super_secret_key"
    })
    assert unsafe_secret_item.status == "FAIL"
    assert "CRITICAL SECURITY LEAK" in unsafe_secret_item.message

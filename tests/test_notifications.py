"""Unit tests for TelemetryAlertDispatcher (Phase 3.3)."""

from decimal import Decimal
import pytest
from unittest.mock import AsyncMock, patch

from kalshi_sim.notifications import TelemetryAlertDispatcher


@pytest.mark.anyio
async def test_telemetry_dispatcher_logging():
    dispatcher = TelemetryAlertDispatcher()
    
    # Test send_order_alert
    await dispatcher.send_order_alert(
        ticker="KXBTC15M-TEST",
        side="yes",
        contracts=5,
        price=Decimal("0.48"),
        cost=Decimal("2.40"),
        fee=Decimal("0.05"),
        ai_prob=0.72,
        vpin=0.18,
        execution_mode="paper",
    )

    # Test send_settlement_alert
    await dispatcher.send_settlement_alert(
        ticker="KXBTC15M-TEST",
        side="yes",
        contracts=5,
        pnl=Decimal("2.60"),
        roi_pct=108.3,
        outcome="win",
        balance_after=Decimal("102.60"),
        strike_price=78000.0,
        settlement_btc_price=78050.0,
    )

    # Test send_circuit_breaker_alert
    await dispatcher.send_circuit_breaker_alert(
        reason="Exceeded daily drawdown threshold",
        current_drawdown_pct=21.5,
        daily_loss_dollars=-15.0,
    )

    await dispatcher.close()


@pytest.mark.anyio
async def test_telemetry_webhook_dispatch():
    dispatcher = TelemetryAlertDispatcher(
        discord_webhook_url="https://discord.com/api/webhooks/mock",
        telegram_bot_token="123456:ABC-DEF",
        telegram_chat_id="987654",
    )

    mock_resp = AsyncMock()
    mock_resp.status = 200

    mock_session = AsyncMock()
    mock_session.closed = False
    mock_session.post.return_value.__aenter__.return_value = mock_resp
    dispatcher._session = mock_session

    await dispatcher.send_order_alert(
        ticker="KXBTC15M-TEST",
        side="no",
        contracts=2,
        price=Decimal("0.55"),
        cost=Decimal("1.10"),
        fee=Decimal("0.02"),
        ai_prob=0.65,
        vpin=0.20,
    )

    assert mock_session.post.call_count == 2
    await dispatcher.close()

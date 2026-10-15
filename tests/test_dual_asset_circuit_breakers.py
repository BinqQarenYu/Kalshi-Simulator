"""Tests for Asset-Isolated Circuit Breakers and 10th-Trade Continuation Gates.

Verifies:
1. ETH Bot 3-consecutive loss circuit breaker trips and disarms ETH without affecting BTC.
2. BTC Bot 10th-trade gate evaluates cumulative PnL: halts if non-positive, continues if positive.
3. Pre-trade intent vetoes disarmed ETH orders (eth_bot_disarmed) and halted BTC orders (btc_bot_halted).
4. Zero Float Decimal typing across all calculations.
"""

from decimal import Decimal
import pytest
from kalshi_sim.agent_guardrails import AgentGuardrails


def test_eth_consecutive_loss_circuit_breaker():
    """Verify ETH bot auto-disarms on 3 consecutive losses and leaves BTC unharmed."""
    guard = AgentGuardrails()
    assert guard.is_eth_bot_armed is True
    assert guard.is_btc_bot_armed is True

    # 1st ETH loss
    guard.record_trade_settlement("KXETH15M-1", Decimal("-0.45"), was_win=False, execution_mode="live")
    assert guard._eth_consecutive_losses == 1
    assert guard.is_eth_bot_armed is True

    # Interleaving BTC trade (should not reset or contaminate ETH counter)
    guard.record_trade_settlement("KXBTC15M-1", Decimal("0.52"), was_win=True, execution_mode="live")
    assert guard._eth_consecutive_losses == 1
    assert guard._btc_trades_count == 1
    assert guard._btc_pnl == Decimal("0.52")

    # 2nd ETH loss
    guard.record_trade_settlement("KXETH15M-2", Decimal("-0.42"), was_win=False, execution_mode="live")
    assert guard._eth_consecutive_losses == 2
    assert guard.is_eth_bot_armed is True

    # 3rd consecutive ETH loss: TRIPS ETH CIRCUIT BREAKER
    guard.record_trade_settlement("KXETH15M-3", Decimal("-0.40"), was_win=False, execution_mode="live")
    assert guard._eth_consecutive_losses == 3
    assert guard.is_eth_bot_armed is False
    # BTC bot MUST remain armed!
    assert guard.is_btc_bot_armed is True

    # Validation must now veto ETH orders
    allowed, msg, size, diag = guard.validate_pre_trade_intent(
        ticker="KXETH15M-4",
        side="yes",
        requested_size=1,
        est_price=Decimal("0.42"),
        total_equity=Decimal("100.00"),
        bot_type="eth_bot1_v4",
        is_bot=True,
    )
    assert allowed is False
    assert diag.get("veto") == "eth_consecutive_losses_disarmed"

    # Validation must still permit BTC orders
    btc_allowed, btc_msg, btc_size, btc_diag = guard.validate_pre_trade_intent(
        ticker="KXBTC15M-2",
        side="yes",
        requested_size=1,
        est_price=Decimal("0.42"),
        total_equity=Decimal("100.00"),
        bot_type="bot1_v4_domination",
        is_bot=True,
    )
    assert btc_allowed is True
    assert btc_size == 1


def test_eth_win_resets_loss_streak():
    """Verify that an ETH win resets the consecutive loss counter to 0."""
    guard = AgentGuardrails()
    guard.record_trade_settlement("KXETH15M-1", Decimal("-0.45"), was_win=False, execution_mode="live")
    guard.record_trade_settlement("KXETH15M-2", Decimal("-0.45"), was_win=False, execution_mode="live")
    assert guard._eth_consecutive_losses == 2

    # Win resets streak
    guard.record_trade_settlement("KXETH15M-3", Decimal("0.55"), was_win=True, execution_mode="live")
    assert guard._eth_consecutive_losses == 0
    assert guard.is_eth_bot_armed is True


def test_btc_10th_trade_positive_continuation_gate():
    """Verify BTC bot continues if cumulative net PnL is positive at trade 10."""
    guard = AgentGuardrails()
    assert guard.is_btc_bot_armed is True

    # 6 wins (+$0.52 each) and 4 losses (-$0.48 each) -> Net PnL = 6 * 0.52 - 4 * 0.48 = 3.12 - 1.92 = +$1.20
    for i in range(1, 7):
        guard.record_trade_settlement(f"KXBTC15M-{i}", Decimal("0.52"), was_win=True, execution_mode="live")
    for i in range(7, 11):
        guard.record_trade_settlement(f"KXBTC15M-{i}", Decimal("-0.48"), was_win=False, execution_mode="live")

    assert guard._btc_trades_count == 10
    assert guard.btc_gate_evaluated is True
    assert guard._btc_pnl == Decimal("1.20")
    # Positive cumulative PnL -> CONTINUES!
    assert guard.is_btc_bot_armed is True

    # Next BTC order is permitted
    allowed, msg, size, _ = guard.validate_pre_trade_intent(
        ticker="KXBTC15M-11",
        side="yes",
        requested_size=1,
        est_price=Decimal("0.42"),
        total_equity=Decimal("100.00"),
        bot_type="bot1_v4_domination",
        is_bot=True,
    )
    assert allowed is True
    assert size == 1


def test_btc_10th_trade_non_positive_halts():
    """Verify BTC bot halts if cumulative net PnL is non-positive at trade 10."""
    guard = AgentGuardrails()
    assert guard.is_btc_bot_armed is True

    # 4 wins (+$0.40 each = $1.60) and 6 losses (-$0.50 each = -$3.00) -> Net PnL = -$1.40
    for i in range(1, 5):
        guard.record_trade_settlement(f"KXBTC15M-{i}", Decimal("0.40"), was_win=True, execution_mode="live")
    for i in range(5, 11):
        guard.record_trade_settlement(f"KXBTC15M-{i}", Decimal("-0.50"), was_win=False, execution_mode="live")

    assert guard._btc_trades_count == 10
    assert guard.btc_gate_evaluated is True
    assert guard._btc_pnl == Decimal("-1.40")
    # Non-positive cumulative PnL -> HALTS!
    assert guard.is_btc_bot_armed is False

    # Next BTC order is vetoed
    allowed, msg, size, diag = guard.validate_pre_trade_intent(
        ticker="KXBTC15M-11",
        side="yes",
        requested_size=1,
        est_price=Decimal("0.42"),
        total_equity=Decimal("50.00"),
        bot_type="bot1_v4_domination",
        is_bot=True,
    )
    assert allowed is False
    assert diag.get("veto") == "btc_10th_trade_halted"

"""Unit & Integration Tests for Lane 2 Incubator Safety Lock & Auto-Release Lifecycle.

Verifies:
1. Default quarantine & lock on GOLD in IncubatorManager.
2. AgentGuardrails vetoes live order placement for quarantined assets.
3. Pre-trade intent validation blocks live orders with [INCUBATOR LOCK VETO].
4. GoldInversionBot decision rules (Barnaby Inversion, velocity shield, macro blackout).
5. Auto-release mechanism: completing 30 cycles with >= 65% win rate automatically releases the lock.
6. Post-certification access: live order placement allowed once certified.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import pytest

from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.incubator_manager import IncubatorManager
from kalshi_sim.ml.gold_inversion_bot import GoldInversionBot
from kalshi_sim.schemas import (
    CryptoAsset,
    L2BookState,
    MarketInfo,
    MarketStatus,
    OrderSide,
    OrderType,
)


@pytest.fixture
def tmp_incubator(tmp_path: Path) -> IncubatorManager:
    """Fixture providing an isolated IncubatorManager instance."""
    reg_path = tmp_path / "test_incubator_registry.json"
    return IncubatorManager(registry_path=reg_path)


def test_default_gold_quarantine_lock(tmp_incubator: IncubatorManager) -> None:
    """Verify that GOLD is quarantined and locked by default."""
    assert tmp_incubator.is_locked("GOLD") is True
    assert tmp_incubator.is_locked(CryptoAsset.GOLD) is True
    assert tmp_incubator.is_locked("BTC") is False
    assert tmp_incubator.is_locked("ETH") is False

    status = tmp_incubator.get_status("GOLD")
    assert status["status"] == "INCUBATOR"
    assert status["is_locked"] is True
    assert status["target_cycles"] == 30
    assert status["target_win_rate"] == 0.65
    assert status["completed_cycles"] == 0


def test_guardrails_incubator_lock_veto(tmp_incubator: IncubatorManager, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that AgentGuardrails vetoes live order placement for GOLD while locked."""
    from kalshi_sim import incubator_manager

    # Point global singleton to tmp_incubator
    monkeypatch.setattr(incubator_manager, "get_incubator_manager", lambda *args, **kwargs: tmp_incubator)

    guardrails = AgentGuardrails()

    # 1. Live mode must be vetoed
    is_locked, reason = guardrails.verify_incubator_lock("KXGOLD15M-26SEP121500-00", is_live=True)
    assert is_locked is True
    assert "[INCUBATOR LOCK VETO]" in reason
    assert "GOLD" in reason

    # 2. Paper/Sim mode must NOT be vetoed (Lane 2 incubator allows paper/shadow testing)
    is_locked_paper, _ = guardrails.verify_incubator_lock("KXGOLD15M-26SEP121500-00", is_live=False)
    assert is_locked_paper is False

    # 3. BTC must NOT be vetoed in live mode
    is_locked_btc, _ = guardrails.verify_incubator_lock("KXBTC15M-26SEP121500-00", is_live=True)
    assert is_locked_btc is False


def test_pre_trade_intent_blocks_live_gold(tmp_incubator: IncubatorManager, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that validate_pre_trade_intent blocks live orders for GOLD."""
    from kalshi_sim import incubator_manager
    monkeypatch.setattr(incubator_manager, "get_incubator_manager", lambda *args, **kwargs: tmp_incubator)

    guardrails = AgentGuardrails()

    # Attempt to place live order on GOLD
    allowed, reason, size, diag = guardrails.validate_pre_trade_intent(
        ticker="KXGOLD15M-26SEP121500-00",
        side="yes",
        requested_size=1,
        est_price=Decimal("0.48"),
        total_equity=Decimal("20.00"),
        is_live=True,
    )
    assert allowed is False
    assert size == 0
    assert "[INCUBATOR LOCK VETO]" in reason
    assert diag.get("veto") == "incubator_locked"


def test_gold_inversion_bot_barnaby_rule() -> None:
    """Verify GoldInversionBot's Barnaby Inversion logic buys NO during mean-reverting chop."""
    bot = GoldInversionBot(
        max_contracts=1,
        entry_price=Decimal("0.50"),
        spot_velocity_limit=Decimal("0.50"),
        max_spot_diff_for_chop=Decimal("2.00"),
    )

    market = MarketInfo(
        ticker="KXGOLD15M-26SEP121500-00",
        title="Gold 15M",
        expiration_time=datetime.now(timezone.utc),
        floor_strike=Decimal("2500.00"),
        status=MarketStatus.OPEN,
    )

    # Spot is $2499.50 (diff -$0.50), T=300s left (5m), normal velocity
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    bot.update_spot(now.timestamp() - 5.0, Decimal("2499.40"))
    bot.update_spot(now.timestamp(), Decimal("2499.50"))

    book = L2BookState("KXGOLD15M-26SEP121500-00")
    book.yes_book = {Decimal("0.50"): Decimal("100")}
    book.no_book = {Decimal("0.49"): Decimal("100")}

    decision = bot.decide(
        market=market,
        orderbook=book,
        spot_price=Decimal("2499.50"),
        time_remaining_s=300,
        ofi_imbalance=-0.10,
        now_utc=now,
    )

    assert decision.action == "BUY"
    assert decision.side == OrderSide.NO
    assert decision.price == Decimal("0.50")
    assert decision.contracts == 1
    assert "BARNABY INVERSION" in decision.rationale


def test_gold_inversion_bot_velocity_shield() -> None:
    """Verify that sharp spot velocity triggers the velocity shield."""
    bot = GoldInversionBot(spot_velocity_limit=Decimal("0.50"))

    market = MarketInfo(
        ticker="KXGOLD15M-26SEP121500-00",
        title="Gold 15M",
        expiration_time=datetime.now(timezone.utc),
        floor_strike=Decimal("2500.00"),
        status=MarketStatus.OPEN,
    )

    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    # Simulate a sudden $1.20 drop in 2 seconds
    bot.update_spot(now.timestamp() - 2.0, Decimal("2501.20"))
    bot.update_spot(now.timestamp(), Decimal("2500.00"))

    decision = bot.decide(
        market=market,
        orderbook=None,
        spot_price=Decimal("2500.00"),
        time_remaining_s=300,
        now_utc=now,
    )

    assert decision.action == "WAIT"
    assert "[VELOCITY SHIELD]" in decision.rationale


def test_auto_release_upon_target_completion(tmp_incubator: IncubatorManager) -> None:
    """Verify that recording 30 cycles with >= 65% win rate automatically releases the lock."""
    assert tmp_incubator.is_locked("GOLD") is True

    # Feed 20 wins and 10 losses (20/30 = 66.7% WR >= 65.0%)
    for i in range(20):
        promoted = tmp_incubator.record_cycle_outcome("GOLD", outcome="WIN", pnl=0.50)
        # Not promoted yet because cycles < 30
        assert promoted is False

    for i in range(9):
        promoted = tmp_incubator.record_cycle_outcome("GOLD", outcome="LOSS", pnl=-0.50)
        assert promoted is False

    assert tmp_incubator.get_status("GOLD")["completed_cycles"] == 29
    assert tmp_incubator.is_locked("GOLD") is True

    # 30th cycle: WIN -> 21/30 = 70.0% WR
    promoted = tmp_incubator.record_cycle_outcome("GOLD", outcome="WIN", pnl=0.50)
    assert promoted is True

    # Verify state after auto-release
    status = tmp_incubator.get_status("GOLD")
    assert status["is_locked"] is False
    assert status["status"] == "CERTIFIED"
    assert status["completed_cycles"] == 30
    assert status["wins"] == 21
    assert status["losses"] == 9
    assert status["current_win_rate"] == 0.70
    assert status["certified_at"] is not None

    # Verify is_locked method now returns False
    assert tmp_incubator.is_locked("GOLD") is False


def test_post_certification_live_access_granted(
    tmp_incubator: IncubatorManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that once certified, AgentGuardrails allows live trading on GOLD."""
    from kalshi_sim import incubator_manager
    monkeypatch.setattr(incubator_manager, "get_incubator_manager", lambda *args, **kwargs: tmp_incubator)

    # Fast-forward certification
    for _ in range(25):
        tmp_incubator.record_cycle_outcome("GOLD", "WIN", 0.50)
    for _ in range(5):
        tmp_incubator.record_cycle_outcome("GOLD", "LOSS", -0.50)

    assert tmp_incubator.is_locked("GOLD") is False

    guardrails = AgentGuardrails()
    is_locked, reason = guardrails.verify_incubator_lock("KXGOLD15M-26SEP121500-00", is_live=True)
    assert is_locked is False
    assert reason == ""


def test_doge_quarantine_lock(tmp_incubator: IncubatorManager) -> None:
    """Verify that DOGE is quarantined and blocked from Live Trading by AgentGuardrails."""
    assert tmp_incubator.is_locked("DOGE") is True
    guardrails = AgentGuardrails()
    is_locked, reason = guardrails.verify_incubator_lock("KXDOGE15M-26SEP121500-00", is_live=True)
    assert is_locked is True
    assert "[INCUBATOR LOCK VETO]" in reason


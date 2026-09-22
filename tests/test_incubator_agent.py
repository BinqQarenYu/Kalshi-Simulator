"""Unit and integration tests for IncubatorAgent (Lane 2 Shadow Supervisor & Pre-Flight Certification Engine)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app_3_autonomous_chef.incubator_agent import (
    IncubatorAgent,
    ShadowTradeRecord,
    CyclePostMortem,
    BotScorecard,
    calc_taker_fee,
)
from app_2_execution_bot.server import app


@pytest.fixture
def tmp_incubator(tmp_path: Path) -> IncubatorAgent:
    """Fixture creating an isolated IncubatorAgent with temporary disk storage."""
    state_file = tmp_path / "test_incubator_state.json"
    return IncubatorAgent(state_path=state_file)


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(app)


def test_calc_taker_fee_strict_decimal() -> None:
    """Verify official Kalshi taker fee formula with strict Decimal arithmetic."""
    # Price = 0.50, Count = 1
    # 0.07 * 1 * 0.50 * 0.50 = 0.0175 -> ceil to 0.02
    fee = calc_taker_fee(1, Decimal("0.50"))
    assert isinstance(fee, Decimal)
    assert fee == Decimal("0.02")

    # Price = 0.90, Count = 1
    # 0.07 * 1 * 0.90 * 0.10 = 0.0063 -> ceil to 0.01 (floor)
    fee_floor = calc_taker_fee(1, Decimal("0.90"))
    assert fee_floor == Decimal("0.01")


def test_shadow_trade_settlement_yes_win(tmp_incubator: IncubatorAgent) -> None:
    """Verify shadow trade settlement for a winning YES position."""
    trade = tmp_incubator.record_shadow_order(
        trade_id="SHADOW-01",
        bot_id="dominion_2_bot",
        bot_name="Dominion 2 Bot",
        ticker="KXBTC15M-T78650",
        side="yes",
        count=1,
        entry_price=Decimal("0.48"),
        target_strike=Decimal("78650.00"),
        entry_spot=Decimal("78655.00"),
        vpin_at_entry=0.15,
        cycle_id="CYCLE-78650-1",
    )

    # Spot settles above strike -> YES wins
    final_twap = Decimal("78660.00")
    pnl = trade.settle(final_twap, Decimal("78650.00"))

    assert trade.settled is True
    assert trade.won is True
    assert trade.outcome == "YES_WIN"
    # PnL = 1 * (1.00 - 0.48) - 0.02 (fee) = 0.50
    assert pnl == Decimal("0.50")
    assert trade.adverse_drift is False


def test_shadow_trade_settlement_no_loss_with_adverse_drift(tmp_incubator: IncubatorAgent) -> None:
    """Verify shadow trade settlement for a losing NO position with adverse price drift."""
    trade = tmp_incubator.record_shadow_order(
        trade_id="SHADOW-02",
        bot_id="the_onnx_strategy",
        bot_name="The ONNX Strategy",
        ticker="KXBTC15M-T78650",
        side="no",
        count=1,
        entry_price=Decimal("0.52"),
        target_strike=Decimal("78650.00"),
        entry_spot=Decimal("78640.00"),
        vpin_at_entry=0.72,  # Toxic flow
        cycle_id="CYCLE-78650-2",
    )

    # Final TWAP surges to 78680 (+40$ against NO trade) -> NO loses with adverse drift
    final_twap = Decimal("78680.00")
    pnl = trade.settle(final_twap, Decimal("78650.00"))

    assert trade.settled is True
    assert trade.won is False
    assert trade.outcome == "YES_WIN"
    # PnL = -(1 * 0.52) - 0.02 (fee) = -0.54
    assert pnl == Decimal("-0.54")
    assert trade.adverse_drift is True


def test_on_cycle_settled_post_mortem(tmp_incubator: IncubatorAgent) -> None:
    """Verify autonomous warm-path cycle post-mortem creation and diagnostic synthesis."""
    tmp_incubator.record_shadow_order(
        trade_id="SHADOW-03",
        bot_id="macro_trend_dominion",
        bot_name="Macro Trend Dominion",
        ticker="KXBTC15M-T78700",
        side="yes",
        count=1,
        entry_price=Decimal("0.46"),
        target_strike=Decimal("78700.00"),
        entry_spot=Decimal("78705.00"),
        vpin_at_entry=0.20,
        cycle_id="CYCLE-78700",
    )

    pm = tmp_incubator.on_cycle_settled(
        ticker="KXBTC15M-T78700",
        final_twap=Decimal("78712.50"),
        target_strike=Decimal("78700.00"),
        cycle_id="CYCLE-78700",
    )

    assert pm.outcome == "YES_WIN"
    assert pm.total_pnl == Decimal("0.52")
    assert "Macro Trend Dominion" in pm.diagnosis
    assert len(pm.trades) == 1

    recent = tmp_incubator.get_recent_post_mortems()
    assert len(recent) == 1
    assert recent[0]["cycle_id"] == "CYCLE-78700"


def test_bot_scorecard_metrics(tmp_incubator: IncubatorAgent) -> None:
    """Verify quantitative scorecard metrics (Win Rate, Profit Factor, Drawdown, Readiness)."""
    # Record 5 winning trades and 1 losing trade
    for i in range(5):
        t = tmp_incubator.record_shadow_order(
            trade_id=f"WIN-{i}",
            bot_id="bot_alpha",
            bot_name="Bot Alpha",
            ticker=f"KXBTC15M-T{78000+i}",
            side="yes",
            count=1,
            entry_price=Decimal("0.48"),
            target_strike=Decimal("78000.00"),
            entry_spot=Decimal("78005.00"),
        )
        t.settle(Decimal("78020.00"), Decimal("78000.00"))

    loss_trade = tmp_incubator.record_shadow_order(
        trade_id="LOSS-1",
        bot_id="bot_alpha",
        bot_name="Bot Alpha",
        ticker="KXBTC15M-T78999",
        side="yes",
        count=1,
        entry_price=Decimal("0.48"),
        target_strike=Decimal("78000.00"),
        entry_spot=Decimal("78005.00"),
    )
    loss_trade.settle(Decimal("77980.00"), Decimal("78000.00"))

    scorecard = tmp_incubator.get_bot_scorecard("bot_alpha")
    assert scorecard.total_trades == 6
    assert scorecard.wins == 5
    assert scorecard.losses == 1
    # 5/6 = 83.33%
    assert scorecard.win_rate_pct == Decimal("83.33")
    # Gross gains: 5 * 0.50 = 2.50. Gross loss: 0.50. Profit Factor = 2.50 / 0.50 = 5.00
    assert scorecard.profit_factor == Decimal("5.00")
    assert scorecard.total_pnl == Decimal("2.00")


def test_audit_for_promotion_gate(tmp_incubator: IncubatorAgent) -> None:
    """Verify 4-Pillar pre-flight promotion gate enforcement."""
    # Under-sampled bot (< 20 trades) must FAIL performance gate
    for i in range(5):
        t = tmp_incubator.record_shadow_order(
            trade_id=f"SAMPLE-{i}",
            bot_id="candidate_bot",
            bot_name="Candidate Bot",
            ticker=f"KXBTC15M-T{78000+i}",
            side="yes",
            count=1,
            entry_price=Decimal("0.48"),
            target_strike=Decimal("78000.00"),
            entry_spot=Decimal("78005.00"),
        )
        t.settle(Decimal("78020.00"), Decimal("78000.00"))

    audit_res = tmp_incubator.audit_for_promotion("candidate_bot")
    assert audit_res["is_eligible_for_live_promotion"] is False
    assert audit_res["performance_gate"]["status"] == "FAIL"
    assert any("Insufficient shadow sample size" in f for f in audit_res["performance_gate"]["failures"])


def test_generate_mobile_digest(tmp_incubator: IncubatorAgent) -> None:
    """Verify mobile digest output formatting."""
    tmp_incubator.record_shadow_order(
        trade_id="DIGEST-1",
        bot_id="3_step_domination_bot",
        bot_name="3-Step Domination",
        ticker="KXBTC15M-T78500",
        side="yes",
        count=1,
        entry_price=Decimal("0.48"),
        target_strike=Decimal("78500.00"),
        entry_spot=Decimal("78502.00"),
    )
    tmp_incubator.on_cycle_settled("KXBTC15M-T78500", Decimal("78510.00"), Decimal("78500.00"))

    digest = tmp_incubator.generate_mobile_digest()
    assert "INCUBATOR AGENT: SHADOW TELEMETRY" in digest
    assert "3-Step Domination" in digest
    assert "Win Rate:" in digest
    assert "Latest Cycle Post-Mortem:" in digest


# ---------------------------------------------------------------------------
# Integration Tests with FastAPI Server
# ---------------------------------------------------------------------------

def test_api_incubator_endpoints(api_client: TestClient) -> None:
    """Verify FastAPI REST API endpoints for Incubator Agent."""
    # 1. Record shadow trade
    trade_payload = {
        "trade_id": "API-TEST-SHADOW-1",
        "bot_id": "dominion_2_bot",
        "bot_name": "Dominion 2 Bot",
        "ticker": "KXBTC15M-API-TEST",
        "side": "yes",
        "count": 1,
        "entry_price": 0.48,
        "target_strike": 78600.0,
        "entry_spot": 78605.0,
        "vpin_at_entry": 0.12,
        "cycle_id": "CYCLE-API-1",
    }
    resp_trade = api_client.post("/api/incubator/record-trade", json=trade_payload)
    assert resp_trade.status_code == 200
    assert resp_trade.json()["success"] is True

    # 2. Settle cycle
    settle_payload = {
        "ticker": "KXBTC15M-API-TEST",
        "final_twap": 78620.0,
        "target_strike": 78600.0,
        "cycle_id": "CYCLE-API-1",
    }
    resp_settle = api_client.post("/api/incubator/settle-cycle", json=settle_payload)
    assert resp_settle.status_code == 200
    assert resp_settle.json()["post_mortem"]["outcome"] == "YES_WIN"

    # 3. Fetch scorecards
    resp_sc = api_client.get("/api/incubator/scorecards")
    assert resp_sc.status_code == 200
    scorecards = resp_sc.json()
    assert isinstance(scorecards, list)
    assert any(s["bot_id"] == "dominion_2_bot" for s in scorecards)

    # 4. Fetch post-mortems
    resp_pm = api_client.get("/api/incubator/post-mortems?limit=5")
    assert resp_pm.status_code == 200
    post_mortems = resp_pm.json()
    assert isinstance(post_mortems, list)
    assert len(post_mortems) >= 1

    # 5. Fetch mobile summary
    resp_mob = api_client.get("/api/incubator/mobile-summary")
    assert resp_mob.status_code == 200
    assert "summary" in resp_mob.json()
    assert "INCUBATOR AGENT" in resp_mob.json()["summary"]

    # 6. Audit promotion
    resp_audit = api_client.post("/api/incubator/audit-promotion", json={"bot_id": "dominion_2_bot"})
    assert resp_audit.status_code == 200
    audit_data = resp_audit.json()
    assert "is_eligible_for_live_promotion" in audit_data
    assert "performance_gate" in audit_data
    assert "four_pillar_audit" in audit_data

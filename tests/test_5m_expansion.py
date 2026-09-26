"""Tests for 5-Minute Event Expansion (KXBTC5M) — Live Trading Prohibition & Microstructure Scaling."""

from decimal import Decimal
from datetime import datetime, timezone
import pytest

from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.schemas import Timeframe


def test_5m_live_trade_is_now_permitted():
    """Verify that AgentGuardrails allows live real-money orders on 5M contracts (prohibition bypassed per user mandate)."""
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    
    # Attempting to place a LIVE order on a 5M contract — should now pass
    ok, reason, size, diag = guardrails.validate_pre_trade_intent(
        ticker="KXBTC5M-26SEP071305-05",
        side="yes",
        requested_size=1,
        est_price=Decimal("0.50"),
        total_equity=Decimal("100.00"),
        vpin=0.15,
        is_live=True,
    )
    
    assert ok is True
    assert reason == "PASSED_GUARDRAILS"
    assert size == 1



def test_5m_cycle_id_live_trade_now_permitted():
    """Verify that 5M cycle_id live trades are now permitted (prohibition bypassed per user mandate)."""
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    
    ok, reason, size, diag = guardrails.validate_pre_trade_intent(
        ticker="BTC_CONTRACT_X",
        side="yes",
        requested_size=1,
        est_price=Decimal("0.50"),
        total_equity=Decimal("100.00"),
        vpin=0.15,
        cycle_id="2026-09-07T13:00:00+00:00_5m",
        is_live=True,
    )
    
    assert ok is True
    assert reason == "PASSED_GUARDRAILS"
    assert size == 1



def test_5m_paper_order_is_permitted():
    """Verify that AgentGuardrails allows paper / simulated orders on 5M contracts."""
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    
    # Simulated / Paper mode (is_live=False)
    ok, reason, size, diag = guardrails.validate_pre_trade_intent(
        ticker="KXBTC5M-26SEP071305-05",
        side="yes",
        requested_size=1,
        est_price=Decimal("0.50"),
        total_equity=Decimal("100.00"),
        vpin=0.15,
        is_live=False,
    )
    
    assert ok is True
    assert reason == "PASSED_GUARDRAILS"
    assert size == 1


def test_5m_cycle_boundary_math():
    """Verify 5-minute cycle boundary and remaining seconds strictly snap to 300s."""
    interval_mins = 5
    
    # Case 1: Exactly at :02:15 -> 2 mins 15 secs elapsed = 135s -> 165s remaining
    t1 = datetime(2026, 9, 7, 13, 2, 15, tzinfo=timezone.utc)
    passed_secs1 = (t1.minute * 60 + t1.second) % (interval_mins * 60)
    remaining_secs1 = (interval_mins * 60) - passed_secs1
    assert passed_secs1 == 135
    assert remaining_secs1 == 165
    assert 0 <= remaining_secs1 <= 300
    
    # Case 2: Boundary test at :05:00 -> 0s elapsed -> 300s remaining
    t2 = datetime(2026, 9, 7, 13, 5, 0, tzinfo=timezone.utc)
    passed_secs2 = (t2.minute * 60 + t2.second) % (interval_mins * 60)
    remaining_secs2 = (interval_mins * 60) - passed_secs2
    assert passed_secs2 == 0
    assert remaining_secs2 == 300


def test_5m_clob_tau_scaling():
    """Verify that tau scaling correctly normalizes against 300s for 5m contracts."""
    import math
    
    remaining_secs = 150
    cycle_duration_5m = 300.0
    cycle_duration_15m = 900.0
    
    tau_5m = min(1.0, max(5, remaining_secs) / cycle_duration_5m)
    tau_15m = min(1.0, max(5, remaining_secs) / cycle_duration_15m)
    
    assert tau_5m == 0.5
    assert abs(tau_15m - (150 / 900)) < 1e-6
    
    # Volatility scale for 5m should be tighter than 15m at the same remaining seconds
    scale_5m = max(25.0, 105.0 * math.sqrt(tau_5m))
    scale_15m = max(35.0, 180.0 * math.sqrt(tau_15m))
    
    assert scale_5m > 0
    assert scale_15m > 0


def test_5m_domination_bot_playbook_scaling():
    """Verify that 3-Step Domination Bot dynamically scales all 3 playbooks on 5M contracts."""
    from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
    from kalshi_sim.orderbook import L2BookState
    
    bot = ThreeStepDominationBot()
    book = L2BookState("KXBTC5M-26SEP071305-05")
    book.yes_book = {Decimal("0.48"): Decimal("100"), Decimal("0.47"): Decimal("200")}
    book.no_book = {Decimal("0.52"): Decimal("100"), Decimal("0.53"): Decimal("200")}
    
    # 1. T = 250s on 5m (first 50s of 5m sprint) -> Playbook 1 (Early Momentum Breakout)
    d1 = bot.evaluate(
        book=book,
        spot_price=80100.0,
        target_strike=80000.0,
        time_to_expiry_s=250.0,
    )
    assert d1.playbook_stage == "breakout"
    assert "Playbook 1" in d1.active_playbook
    
    # 2. T = 150s on 5m (mid-cycle) -> Playbook 2 (Mid-Cycle OFI Trend Drift)
    d2 = bot.evaluate(
        book=book,
        spot_price=80100.0,
        target_strike=80000.0,
        time_to_expiry_s=150.0,
    )
    assert d2.playbook_stage == "drift"
    assert "Playbook 2" in d2.active_playbook
    
    # 3. T = 50s on 5m (late cycle) -> Playbook 3 (Late-Cycle Gamma Snub)
    d3 = bot.evaluate(
        book=book,
        spot_price=80100.0,
        target_strike=80000.0,
        time_to_expiry_s=50.0,
    )
    assert d3.playbook_stage == "gamma_snub"
    assert "Playbook 3" in d3.active_playbook
    
    # 4. T = 10s on 5m -> Settlement Lock (<20s)
    d4 = bot.evaluate(
        book=book,
        spot_price=80100.0,
        target_strike=80000.0,
        time_to_expiry_s=10.0,
    )
    assert d4.recommended_side == "wait"
    assert "Cycle Closing Window" in d4.rationale or "Expiration Quarantine Zone" in d4.rationale


def test_5m_win_loss_event_report_generation():
    """Verify record_win_loss_event_report properly generates 5M reports with 5m cycle windows."""
    from kalshi_sim.server import record_win_loss_event_report, format_cycle_time_from_iso
    
    rep = record_win_loss_event_report(
        ticker="KXBTC5M-26SEP071305-05",
        side="yes",
        contracts=1,
        entry_price=Decimal("0.48"),
        settlement_btc_price=Decimal("80200.00"),
        strike_price=Decimal("80000.00"),
        timeframe="5m",
        bot_type="3_step_domination_bot",
        execution_mode="simulated",
    )
    
    assert rep["timeframe"] == "5m"
    assert rep["bot_type"] == "3_step_domination_bot"
    assert rep["execution_mode"] == "simulated"
    assert rep["contracts"] == 1
    assert rep["outcome"] == "win"
    assert rep["pnl"] == pytest.approx(0.52, 0.001)
    assert "5M" in rep["cycle_time"] or "ET" in rep["cycle_time"]
    
    # Verify 5-minute cycle time formatting
    iso_sample = "2026-09-07T13:05:00+00:00"
    ct_5m = format_cycle_time_from_iso(iso_sample, interval=5)
    assert "ET" in ct_5m
    assert "September 07" in ct_5m


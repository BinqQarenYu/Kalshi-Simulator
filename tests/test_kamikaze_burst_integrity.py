"""Comprehensive Stress Tests for Anti-Kamikaze Sizing, Burst/Spam Protection, and Systemic Integrity.

Covers:
1. Anti-Kamikaze: Micro-bankroll protection, lottery ticket veto, overpay ceiling, drawdown taper, 1-ct cap.
2. Burst & Spam: Evaluation cooldown throttling, 1-trade-per-cycle locks, token-bucket burst limit, toxic VPIN veto, spoofing cancels.
3. Integrity: Decimal arithmetic strictness, equity reconciliation, binary payoffs {0, 1}, ET clock parity, live auditor status.
"""

from decimal import Decimal
import time
import urllib.request
import json
import pytest

from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.law_order_agent import AgentLawOrder
from kalshi_sim.integrity_agent import AgentIntegrityCheck
from kalshi_sim.ml.macro_trend_dominion_bot import MacroTrendDominionBot
from kalshi_sim.portfolio import Portfolio
from kalshi_sim.schemas import L2BookState, OrderSide


# =============================================================================
# SUITE 1: ANTI-KAMIKAZE RISK & SIZING DEFENSE
# =============================================================================

def test_kamikaze_nano_bankroll_clamp() -> None:
    """Anti-Kamikaze: Nano bankroll ($25) requesting massive 100 contracts is clamped to nano cap (<= 2)."""
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    
    ok, reason, size, diag = guardrails.validate_pre_trade_intent(
        ticker="KXBTC15M-T78000",
        side="yes",
        requested_size=100,  # Kamikaze request
        est_price=Decimal("0.50"),
        total_equity=Decimal("25.00"),
        vpin=0.10,
    )
    assert ok is True
    assert size <= 2, f"Expected nano bankroll cap <= 2, got {size}"
    assert diag["approved_size"] == size


def test_kamikaze_price_corridor_lottery_veto() -> None:
    """Anti-Kamikaze: Cheap lottery tickets ($0.03 <= $0.06) are strictly vetoed."""
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    
    ok, reason, size, _ = guardrails.validate_pre_trade_intent(
        ticker="KXBTC15M-T78000",
        side="yes",
        requested_size=1,
        est_price=Decimal("0.04"),  # Negative-EV lottery ticket
        total_equity=Decimal("25.00"),
        vpin=0.10,
    )
    assert ok is False
    assert "PRICE CORRIDOR VETO" in reason
    assert size == 0


def test_kamikaze_drawdown_loss_streak_taper() -> None:
    """Anti-Kamikaze: Consecutive loss streaks taper approved sizing to 1 contract flat."""
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0, consecutive_loss_taper_threshold=2)
    guardrails.validate_pre_trade_intent("T0", "yes", 1, Decimal("0.50"), total_equity=Decimal("100.00"))
    
    # 2 consecutive losses
    guardrails.record_cycle_settlement("T1", outcome="loss", pnl=Decimal("-1.00"), balance_after=Decimal("99.00"))
    guardrails.record_cycle_settlement("T2", outcome="loss", pnl=Decimal("-1.00"), balance_after=Decimal("98.00"))
    
    ok, reason, size, diag = guardrails.validate_pre_trade_intent(
        ticker="KXBTC15M-T3",
        side="yes",
        requested_size=10,
        est_price=Decimal("0.50"),
        total_equity=Decimal("98.00"),
        vpin=0.10,
    )
    assert ok is True
    assert diag["is_tapered"] is True
    assert size == 1, "Loss streak must force maximum size down to 1 contract"


def test_macro_trend_dominion_anti_kamikaze_flat_sizing() -> None:
    """MacroTrendDominionBot: Sizing engine strictly returns 1 contract when bankroll is micro (< $50)."""
    bot = MacroTrendDominionBot()
    # Feed bullish spot prices (up +$300)
    now = time.time()
    bot.record_spot_tick(now - 3600, 85000.0)
    bot.record_spot_tick(now, 85300.0)
    
    book = L2BookState("KXBTC-TEST")
    book.yes_book = {Decimal("0.50"): Decimal("100")}
    book.no_book = {Decimal("0.50"): Decimal("100")}
    
    decision = bot.evaluate(
        book=book,
        spot_price=85300.0,
        target_strike=85200.0,
        time_to_expiry_s=600.0,
        total_equity=Decimal("27.50"),  # Micro bankroll
    )
    assert decision.recommended_side == "yes"
    assert decision.recommended_contracts == 1, f"Expected 1 contract flat sizing, got {decision.recommended_contracts}"
    assert decision.macro_regime == "MACRO_BULL"


def test_macro_trend_dominion_cut_loss_salvage() -> None:
    """Anti-Kamikaze: In deep adverse moves near expiry (T <= 90s), salvage capital instead of $0.00."""
    bot = MacroTrendDominionBot()
    book = L2BookState("KXBTC-TEST")
    book.yes_book = {Decimal("0.12"): Decimal("50")}
    book.no_book = {Decimal("0.88"): Decimal("50")}
    
    # We hold YES entered at $0.50, but spot collapsed $70 below target strike with 60s remaining
    exit_decision = bot.evaluate_exit(
        side="yes",
        entry_price=Decimal("0.50"),
        size=1,
        book=book,
        time_to_expiry_s=60,
        spot_price=Decimal("84930.00"),
        target_strike=Decimal("85000.00"),  # Spot is $70 OTM
    )
    assert exit_decision.should_exit is True
    assert exit_decision.exit_reason == "CUT_LOSS_SALVAGE"
    assert exit_decision.exit_price >= Decimal("0.08")


# =============================================================================
# SUITE 2: BURST, SPAM & TOXIC FLOW DEFENSE
# =============================================================================

def test_burst_1_trade_per_cycle_lockout() -> None:
    """Burst Defense: 10 rapid-fire orders on the same cycle produce exactly 1 approval and 9 lockouts."""
    guardrails = AgentGuardrails(min_order_interval_seconds=0.0)
    ticker = "KXBTC15M-BURST-CYCLE"
    
    # First attempt: Approved
    ok1, _, size1, _ = guardrails.validate_pre_trade_intent(
        ticker=ticker,
        side="yes",
        requested_size=1,
        est_price=Decimal("0.50"),
        total_equity=Decimal("25.00"),
        vpin=0.10,
    )
    assert ok1 is True
    assert size1 == 1
    
    # Record inception to seal the cycle lock
    guardrails.record_trade_inception(
        trade_id="tr_burst_1",
        ticker=ticker,
        side="yes",
        size=size1,
        price=Decimal("0.50"),
        cost=Decimal("0.50"),
        fee=Decimal("0.01"),
        bot_type="macro_trend_dominion",
        execution_mode="live",
        rationale="Trend Breakout",
        vpin=0.10,
        ai_prob=0.85,
    )
    
    # Subsequent 9 burst orders in the same cycle must all be REJECTED
    rejections = 0
    for i in range(9):
        ok, reason, size, _ = guardrails.validate_pre_trade_intent(
            ticker=ticker,
            side="yes",
            requested_size=1,
            est_price=Decimal("0.50"),
            total_equity=Decimal("25.00"),
            vpin=0.10,
        )
        if not ok and "1-TRADE-PER-CYCLE LOCKOUT" in reason:
            rejections += 1
            
    assert rejections == 9, f"Expected 9 rejections, got {rejections}"


def test_burst_token_bucket_rate_limiter() -> None:
    """Burst Defense: AgentLawOrder absorbs exactly 40 burst calls and throttles the 41st."""
    agent = AgentLawOrder(rate_limit_rps=30.0, burst_capacity=40)
    
    # 40 immediate burst requests should all succeed
    successes = 0
    for _ in range(40):
        ok, _ = agent.check_rate_limit(cost=1.0)
        if ok:
            successes += 1
    assert successes == 40
    
    # 41st immediate call must be rate-limited
    ok41, msg = agent.check_rate_limit(cost=1.0)
    assert ok41 is False
    assert "Rate limit quota exceeded" in msg


def test_burst_toxic_orderflow_vpin_veto() -> None:
    """Burst Defense: Toxic orderflow burst (VPIN > 0.45) strictly vetoes trade execution."""
    guardrails = AgentGuardrails(vpin_toxic_threshold=0.45)
    
    ok, reason, size, _ = guardrails.validate_pre_trade_intent(
        ticker="KXBTC15M-TOXIC",
        side="yes",
        requested_size=1,
        est_price=Decimal("0.50"),
        total_equity=Decimal("50.00"),
        vpin=0.62,  # Severe toxicity burst
    )
    assert ok is False
    assert "VPIN TOXICITY VETO" in reason
    assert size == 0


def test_burst_spoofing_cancellation_detection() -> None:
    """Burst Defense: Rapid burst of cancellations triggers CFTC anti-spoofing warning."""
    agent = AgentLawOrder(rate_limit_rps=30.0, burst_capacity=40)
    
    # Submit 5 orders then cancel 26 in quick succession within 10s
    for i in range(26):
        agent.record_order_cancellation(f"ord_{i}", "KXBTC-BURST")
        
    assert any("Anti-Spoofing" in v["rule_name"] for v in agent._violations), "High cancellation burst must record spoofing violation"
    status = agent.get_compliance_status()
    spoof_check = next(c for c in status["checks"] if "Spoofing" in c["name"])
    assert spoof_check["status"] in ("PASS", "WARN")


# =============================================================================
# SUITE 3: SYSTEMIC INTEGRITY & LIVE DAEMON AUDIT
# =============================================================================

def test_integrity_decimal_strictness() -> None:
    """Integrity: Decimal strictness is 100% enforced across portfolio math."""
    agent = AgentIntegrityCheck()
    portfolio = Portfolio(starting_balance=Decimal("25.00"))
    
    items = agent.audit_mathematical_invariants(portfolio)
    dec_check = next(i for i in items if i.name == "Decimal Type Strictness")
    assert dec_check.status == "PASS"


def test_integrity_equity_and_payoff_invariants() -> None:
    """Integrity: Equity = Cash + Unrealized PnL, and Payoffs in {0.00, 1.00}."""
    agent = AgentIntegrityCheck()
    portfolio = Portfolio(starting_balance=Decimal("50.00"))
    
    items = agent.audit_mathematical_invariants(portfolio)
    equity_check = next(i for i in items if i.name == "Equity Reconciliation Invariant")
    payoff_check = next(i for i in items if i.name == "Binary Option Payoff Boundaries")
    assert equity_check.status == "PASS"
    assert payoff_check.status == "PASS"


def test_integrity_live_daemon_status() -> None:
    """Integrity: Live running server responds with active bot and healthy checks."""
    try:
        req = urllib.request.urlopen("http://127.0.0.1:8000/api/integrity/status", timeout=1.0)
        data = json.loads(req.read().decode())
        req_strat = urllib.request.urlopen("http://127.0.0.1:8000/api/bot/strategies", timeout=1.0)
        strat_data = json.loads(req_strat.read().decode())
    except Exception:
        # Fallback to in-process TestClient if live daemon is not running on port 8000
        from fastapi.testclient import TestClient
        from kalshi_sim.server import app
        client = TestClient(app)
        res_integrity = client.post("/api/integrity/audit-now")
        assert res_integrity.status_code == 200
        data = res_integrity.json()
        res_strat = client.get("/api/bot/strategies")
        assert res_strat.status_code == 200
        strat_data = res_strat.json()

    checks = {c["name"]: c["status"] for c in data.get("checks", [])}

    # Verify key institutional invariants on the daemon
    assert checks.get("Decimal Type Strictness") == "PASS"
    assert checks.get("Equity Reconciliation Invariant") == "PASS"
    assert checks.get("Binary Option Payoff Boundaries") == "PASS"
    assert checks.get("Solvency & Collateral Safety") == "PASS"
    assert checks.get("L2 Delta Sequence Monotonicity") == "PASS"
    assert checks.get("Zero-Mock Isolation") == "PASS"
    assert checks.get("Kalshi ET Clock Alignment") == "PASS"
    assert checks.get("Kalshi Spot Price Precision") == "PASS"

    # Verify active strategy is valid institutional bot (3-Step Domination, The ONNX Strategy, or Macro Trend Dominion)
    assert strat_data.get("active_strategy") in (
        "3_step_domination_bot",
        "macro_trend_dominion",
        "macro_onnx",
        "dual_onnx",
        "the_onnx_strategy",
        "onnx_macro_v2",
    )


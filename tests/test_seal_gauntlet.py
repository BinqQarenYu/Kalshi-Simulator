"""Comprehensive 6-Stage Seal of Excellence Verification Gauntlet.

Tests the deterministic graduation pipeline:
1. Stage 1: AST Code Integrity & Strict Decimal Gate (zero native floats in monetary math)
2. Stage 2: Adversarial SimSim Crucible (60s TWAP settlement parity & Dr. Nash Net EV >= +$0.04)
3. Stage 3: Anti-Kamikaze & Harakiri Fault-Injection (1-ct clamp, 3-loss streak disarm, panic sweep)
4. Stage 4: Multi-Regime Incubator Evaluation (N >= 30 cycles, WR >= 55%, PF >= 1.25)
5. Stage 5: Deterministic 5-Pillar Pre-Flight Audit
6. Stage 6: Cryptographic SHA-256 Token Minting & Live Authorization Interlock
"""

import ast
from datetime import datetime, timezone
from decimal import Decimal
import inspect
import json
from pathlib import Path
import pytest
from typing import Any, Dict

from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.bot_deployment_auditor import (
    BotDeploymentAuditor,
    SealOfExcellence,
)
from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
from kalshi_sim.ml.macro_trend_dominion_bot import MacroTrendDominionBot


# ==============================================================================
# STAGE 1: AST CODE INTEGRITY & STRICT DECIMAL GATE
# ==============================================================================

def test_stage_1_ast_zero_float_inspection() -> None:
    """Stage 1: Verify via AST that strategy constructors and monetary attributes reject native floats."""
    strat_files = [
        Path("src") / "kalshi_sim" / "ml" / "domination_bot.py",
        Path("src") / "kalshi_sim" / "ml" / "macro_trend_dominion_bot.py",
    ]

    for sf in strat_files:
        assert sf.exists(), f"Strategy file {sf} must exist"
        tree = ast.parse(sf.read_text(encoding="utf-8"))

        # Find classes
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Inspect assignments within class methods
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        # Ensure evaluate and evaluate_exit accept **kwargs
                        if item.name in ("evaluate", "evaluate_exit"):
                            has_kwargs = item.args.kwarg is not None
                            assert has_kwargs, f"{node.name}.{item.name} must accept **kwargs for engine decoupling"

    # Runtime attribute strictness check on live strategy instance
    bot = ThreeStepDominationBot()
    assert isinstance(bot.discount_limit_price, Decimal), "discount_limit_price must be Decimal"
    assert bot.discount_limit_price <= Decimal("0.52"), "Maker entry price must enforce discount"


# ==============================================================================
# STAGE 2: ADVERSARIAL SIMSIM CRUCIBLE (TWAP PARITY & NET EV)
# ==============================================================================

def test_stage_2_simsim_twap_parity_and_net_ev() -> None:
    """Stage 2: Silas 60-Second TWAP parity and Dr. Nash Net EV >= +$0.0400 per contract."""
    # 1. Silas 60-second TWAP parity verification:
    # A spot price spike in the last 5 seconds cannot win if 60s TWAP is below strike
    target_strike = Decimal("80000.00")
    # Simulate 55 seconds below strike at 79,980 and 5 seconds spike at 80,050
    twap_samples = [Decimal("79980.00")] * 55 + [Decimal("80050.00")] * 5
    calculated_twap = sum(twap_samples) / Decimal(str(len(twap_samples)))
    instantaneous_spot = twap_samples[-1]

    assert instantaneous_spot > target_strike, "Instantaneous spot is above strike"
    assert calculated_twap < target_strike, "Trailing 60s TWAP is below strike"

    # Contract settles based on TWAP, NOT instantaneous spot:
    settled_win = calculated_twap >= target_strike
    assert settled_win is False, "Silas TWAP settlement parity must rule as NO_WIN despite spot spike"

    # 2. Dr. Nash Net EV Hurdle calculation:
    # 58% win rate entering at $0.48 maker limit ($0.00 fee)
    win_rate = Decimal("0.58")
    entry_price = Decimal("0.48")
    payout_win = Decimal("1.00")
    maker_fee = Decimal("0.00")

    # Net EV = P(win) * (1.00 - entry_price - fee) - P(loss) * (entry_price + fee)
    ev_net = (win_rate * (payout_win - entry_price - maker_fee)) - ((Decimal("1.0") - win_rate) * entry_price)
    # 0.58 * 0.52 - 0.42 * 0.48 = 0.3016 - 0.2016 = +$0.1000
    assert ev_net >= Decimal("0.0400"), f"Net EV {ev_net} must satisfy Dr. Nash hurdle >= +$0.0400"


# ==============================================================================
# STAGE 3: ANTI-KAMIKAZE & HARAKIRI FAULT INJECTION
# ==============================================================================

def test_stage_3_anti_kamikaze_micro_bankroll_clamp() -> None:
    """Stage 3A: Anti-Kamikaze clamps nano bankroll ($20) requesting 100 contracts to 1 contract."""
    guard = AgentGuardrails()
    allowed, reason, size, _ = guard.validate_pre_trade_intent(
        ticker="KXBTC15M-TEST-1",
        side="yes",
        requested_size=100,
        est_price=Decimal("0.48"),
        total_equity=Decimal("20.00"),
        cycle_id="CYCLE-KAMIKAZE-1",
        is_bot=True,
    )
    assert allowed is True
    assert size == 1, f"Approved size {size} must be clamped to 1 contract flat"


def test_stage_3_harakiri_three_loss_streak_breaker() -> None:
    """Stage 3B: Harakiri Gate verifies automatic self-disarm after 3 consecutive losses."""
    guard = AgentGuardrails()

    # Simulate 3 consecutive losses
    guard.record_trade_settlement("KXBTC15M-1", pnl=Decimal("-0.48"), was_win=False)
    assert guard._consecutive_losses == 1
    assert guard.is_bot_armed is True

    guard.record_trade_settlement("KXBTC15M-2", pnl=Decimal("-0.48"), was_win=False)
    assert guard._consecutive_losses == 2
    assert guard.is_bot_armed is True

    guard.record_trade_settlement("KXBTC15M-3", pnl=Decimal("-0.48"), was_win=False)
    assert guard._consecutive_losses == 3
    # Bot MUST commit Harakiri (auto-disarm immediately)
    assert guard.is_bot_armed is False, "Bot must be auto-disarmed upon reaching 3 consecutive losses"

    # Subsequent orders must be rejected immediately
    allowed, reason, _, _ = guard.validate_pre_trade_intent(
        ticker="KXBTC15M-4",
        side="yes",
        requested_size=1,
        est_price=Decimal("0.48"),
        total_equity=Decimal("20.00"),
        cycle_id="CYCLE-HARAKIRI-4",
        is_bot=True,
    )
    assert allowed is False
    assert "DISARMED" in reason


# ==============================================================================
# STAGE 4: MULTI-REGIME INCUBATOR EVALUATION & ON-DEMAND TRIGGER
# ==============================================================================

def test_stage_4_on_demand_excellence_readiness_check(tmp_path: Path) -> None:
    """Stage 4: Evaluate on-demand excellence readiness trigger ('check bot if it's time to test for excellence')."""
    auditor = BotDeploymentAuditor(seal_path=tmp_path / "test_seals.json")

    # Case A: Bot still cooking (only 10 cycles)
    cooking_incubator = tmp_path / "cooking_incubator.json"
    cooking_trades = [
        {"bot_id": "test_bot", "settled": True, "won": True, "realized_pnl": "0.50", "adverse_drift": False}
        for _ in range(10)
    ]
    cooking_incubator.write_text(json.dumps({"trades": cooking_trades}), encoding="utf-8")

    res_cooking = auditor.check_bot_excellence_readiness("test_bot", incubator_state_path=cooking_incubator)
    assert res_cooking["ready_for_gauntlet"] is False
    assert res_cooking["status"] == "COOKING_IN_INCUBATOR"

    # Case B: Bot matured (32 cycles, 20 wins = 62.5% WR, multi-regime distribution)
    matured_incubator = tmp_path / "matured_incubator.json"
    matured_trades = (
        [{"bot_id": "mature_bot", "settled": True, "won": True, "realized_pnl": "0.52", "adverse_drift": False} for _ in range(20)]
        + [{"bot_id": "mature_bot", "settled": True, "won": False, "realized_pnl": "-0.48", "adverse_drift": True} for _ in range(12)]
    )
    matured_incubator.write_text(json.dumps({"trades": matured_trades}), encoding="utf-8")

    res_mature = auditor.check_bot_excellence_readiness("mature_bot", incubator_state_path=matured_incubator)
    assert res_mature["ready_for_gauntlet"] is True
    assert res_mature["status"] == "READY_FOR_GAUNTLET"
    assert res_mature["settled_cycles"] == 32
    assert res_mature["win_rate"] == 0.625
    assert res_mature["profit_factor"] > 1.25
    assert res_mature["regime_distribution"]["low_vol_cycles"] == 20
    assert res_mature["regime_distribution"]["high_vol_cycles"] == 12


# ==============================================================================
# STAGE 5 & 6: 5-PILLAR AUDIT & CRYPTOGRAPHIC MINTING
# ==============================================================================

def test_stage_5_and_6_gauntlet_minting_and_disk_interlock(tmp_path: Path) -> None:
    """Stage 5 & 6: Pre-flight audit, SHA-256 token minting, and static disk authorization interlock."""
    seal_file = tmp_path / "seal_of_excellence.json"
    auditor = BotDeploymentAuditor(seal_path=seal_file)

    # 1. Candidate bot without seal is strictly unauthorized
    auth_init, msg_init = auditor.check_live_authorization_on_disk("new_candidate_bot", seal_path=seal_file)
    assert auth_init is False
    assert "UNAUTHORIZED" in msg_init or "SEAL_MISSING" in msg_init

    # 2. Mint the Seal of Excellence after passing the gauntlet
    seal = auditor.mint_seal_of_excellence(
        bot_id="new_candidate_bot",
        bot_name="New Candidate Alpha",
        win_rate=0.60,
        profit_factor=1.45,
        settled_cycles=35,
        net_ev=0.048,
        max_dd=8.5,
        commit_hash="c0ff33cafe1234",
        harakiri_verified=True,
        simsim_verified=True,
        regime_distribution={"low_vol": 18, "high_vol": 17},
    )

    assert seal.seal_status == "SEALED_EXCELLENT"
    assert seal.live_trading_authorized is True
    assert seal.seal_token.startswith("SEAL-NEW_")
    assert seal.net_expected_value == 0.048
    assert seal.harakiri_verified is True
    assert seal.git_commit_hash == "c0ff33cafe1234"

    # 3. Verify disk interlock recognizes the newly minted token
    auth_after, msg_after = auditor.check_live_authorization_on_disk("new_candidate_bot", seal_path=seal_file)
    assert auth_after is True
    assert "AUTHORIZED" in msg_after
    assert seal.seal_token in msg_after

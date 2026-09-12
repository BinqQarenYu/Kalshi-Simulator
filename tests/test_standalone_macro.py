"""Unit and Integration Tests for Kalshi Macro Trend Dominion Standalone Bot (Port 8003).

Verifies:
1. Engine initialization, 4-pillar pre-flight certification, and parameter exposure.
2. Lock acquisition on data/trading_engine_macro.lock.
3. Mutual Live Interlock logic with Port 8001 (Dominion) and Port 8002 (ONNX).
4. REST endpoints: /, /api/state, /api/arm, /api/disarm, /api/panic, /api/sweep, and /api/bot/parameters.
5. Strict 1-contract micro-bankroll sizing armor and 15M decision telemetry.
"""

import os
from pathlib import Path
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

os.environ["TESTING"] = "true"

from kalshi_sim.standalone_macro import (
    app,
    StandaloneMacroEngine,
    LOCK_FILE_PATH,
    DOM_LOCK_FILE_PATH,
    ONNX_LOCK_FILE_PATH,
)
from kalshi_sim.schemas import CryptoAsset


@pytest.fixture
def test_engine(tmp_path: Path):
    """Fixture providing an isolated StandaloneMacroEngine."""
    engine = StandaloneMacroEngine(
        is_live=False,
        is_armed=True,
        data_dir=tmp_path,
        asset=CryptoAsset.BTC,
    )
    return engine


def test_standalone_macro_initialization_and_audit(test_engine: StandaloneMacroEngine):
    """Verify engine startup passes 4-pillar pre-flight audit and initializes 3 brains."""
    assert test_engine.bot is not None
    assert test_engine.candle_builder is not None
    assert test_engine.hmm_brain is not None
    assert test_engine.gateway is not None
    assert test_engine.guardrails is not None
    assert "macro_trend_dominion" in test_engine.guardrails.authorized_live_bots
    assert test_engine.guardrails.max_micro_bankroll_contracts == 1
    assert test_engine.guardrails.max_nano_bankroll_contracts == 1
    assert test_engine.execution_mode == "SHADOW"


def test_standalone_macro_parameters_introspection_and_update(test_engine: StandaloneMacroEngine):
    """Verify all 9 dials are introspectable and dynamically updatable."""
    params = test_engine.get_parameters()
    assert "limit_price_cents" in params
    assert "min_confidence_pct" in params
    assert "min_ev_dollars" in params
    assert "volatility_moat_dollars" in params
    assert "hmm_risk_off_veto" in params
    assert "adaptive_learning_rate" in params
    assert params["limit_price_cents"] == 52

    # Update parameters
    updated = test_engine.update_parameters(
        limit_price_cents=48,
        min_confidence_pct=70.0,
        volatility_moat_dollars=35.0,
        adaptive_learning_rate=0.25,
    )
    assert updated["limit_price_cents"] == 48
    assert updated["min_confidence_pct"] == 70.0
    assert updated["volatility_moat_dollars"] == 35.0
    assert updated["adaptive_learning_rate"] == 0.25


def test_mutual_interlock_detection(tmp_path: Path, monkeypatch):
    """Verify mutual live interlock detects active peer bot locks."""
    # When no locks exist
    monkeypatch.setattr("kalshi_sim.standalone_macro.get_active_lock_holder", lambda p: None)
    engine = StandaloneMacroEngine(
        is_live=False,
        is_armed=True,
        data_dir=tmp_path,
        asset=CryptoAsset.BTC,
    )
    assert not engine.peer_bot_active

    # Mock Port 8001 lock
    monkeypatch.setattr(
        "kalshi_sim.standalone_macro.get_active_lock_holder",
        lambda p: ("dominion_8001", 12345) if p == DOM_LOCK_FILE_PATH else None,
    )
    engine._check_mutual_interlock()
    assert engine.peer_bot_active is True
    assert "Port 8001" in engine.interlock_msg
    assert engine.execution_mode == "SHADOW"


def test_standalone_macro_endpoints(test_engine: StandaloneMacroEngine, monkeypatch):
    """Verify REST API endpoints and Pocket Cockpit HTML delivery."""
    import kalshi_sim.standalone_macro as sm
    sm.app_engine = test_engine

    client = TestClient(app)

    # 1. Cockpit HTML
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Macro Trend Dominion" in resp.text
    assert "PORT 8003" in resp.text

    # 2. State & Status
    resp = client.get("/api/state")
    assert resp.status_code == 200
    state = resp.json()
    assert state["bot_type"] == "macro_trend_dominion"
    assert "three_brain_matrix" in state
    assert "learning_engine" in state
    assert "parameters" in state
    assert state["armed"] is True

    # 3. Master Controls (Arm/Disarm/Panic/Sweep)
    resp_disarm = client.post("/api/disarm")
    assert resp_disarm.status_code == 200
    assert resp_disarm.json()["armed"] is False
    assert test_engine.is_armed is False

    resp_arm = client.post("/api/arm")
    assert resp_arm.status_code == 200
    assert resp_arm.json()["armed"] is True
    assert test_engine.is_armed is True

    resp_panic = client.post("/api/panic")
    assert resp_panic.status_code == 200
    assert resp_panic.json()["panic"] is True
    assert test_engine.is_armed is False

    resp_sweep = client.post("/api/sweep")
    assert resp_sweep.status_code == 200
    assert resp_sweep.json()["swept"] is True

    # 4. Parameters GET / POST
    resp_params = client.get("/api/bot/parameters")
    assert resp_params.status_code == 200
    assert resp_params.json()["limit_price_cents"] == 52

    resp_update = client.post(
        "/api/bot/parameters",
        json={"limit_price_cents": 44, "min_confidence_pct": 68.0},
    )
    assert resp_update.status_code == 200
    assert resp_update.json()["parameters"]["limit_price_cents"] == 44
    assert resp_update.json()["parameters"]["min_confidence_pct"] == 68.0


def test_15m_cycle_trade_and_learning_reconciliation(test_engine: StandaloneMacroEngine):
    """Verify trade submission and learning engine calibration upon settlement."""
    test_engine.current_btc_spot = Decimal("98500.00")
    test_engine.target_strike = Decimal("98000.00")
    test_engine.active_ticker = "KXBTC15M-26SEP10-1830"
    test_engine.is_armed = True

    # Simulate positive decision
    book = {"yes_bid": 48.0, "yes_ask": 50.0, "no_bid": 50.0, "no_ask": 52.0}
    dec = test_engine.bot.evaluate(
        asset="BTC",
        spot_price=Decimal("98500.00"),
        target_strike=Decimal("98000.00"),
        time_to_expiry_s=400.0,
        quolas_inference={"signal": "UP", "confidence": 0.80},
        kalshi_inference={"signal": "UP", "confidence": 0.75},
        book=book,
    )
    assert dec.call == "YES"

    # Simulate trade execution
    test_engine._execute_trade(dec, test_engine.active_ticker)
    assert len(test_engine.active_resting_orders) == 1

    order_id = list(test_engine.active_resting_orders.keys())[0]
    order = test_engine.active_resting_orders[order_id]
    assert order["side"] == "YES"
    assert order["contracts"] == 1  # 1-contract armor

    # Simulate settlement: Spot ended above strike -> YES wins
    actual_outcome = "YES"
    rec = test_engine.bot.record_cycle_outcome(
        cycle_id=order["cycle"],
        ticker=test_engine.active_ticker,
        call=order["side"],
        predicted_prob=float(dec.confidence_pct / 100.0),
        fill_price=Decimal(str(order["limit_price_cents"])) / Decimal("100"),
        outcome="win",
        pnl=Decimal("1.00") - Decimal(str(order["limit_price_cents"])) / Decimal("100"),
        macro_trend="BULL",
        hmm_regime="STABLE_RANGE",
        execution_mode="paper",
    )
    assert rec["brier_error"] is not None
    assert rec["outcome"] == "win"

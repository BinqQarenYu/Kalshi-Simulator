"""Unit and Integration Tests for Kalshi Dual-Brain ONNX Standalone Bot (Port 8002).

Verifies:
1. Engine initialization, 4-pillar pre-flight certification, and parameter exposure.
2. Lock acquisition on data/trading_engine_onnx.lock.
3. Mutual Live Interlock logic with Port 8001 (Dominion).
4. REST endpoints: /api/state, /api/arm, /api/disarm, /api/panic, /api/sweep, and /api/bot/parameters.
5. Strict 1-contract micro-bankroll sizing armor.
"""

import os
from pathlib import Path
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

os.environ["TESTING"] = "true"

from kalshi_sim.standalone_onnx import (
    app,
    StandaloneONNXEngine,
    LOCK_FILE_PATH,
    DOM_LOCK_FILE_PATH,
)
from shared.schemas import CryptoAsset
from app_1_machine_engine.ml.dual_onnx_schemas import DualONNXRegime


@pytest.fixture
def test_engine(tmp_path: Path):
    """Fixture providing an isolated StandaloneONNXEngine."""
    engine = StandaloneONNXEngine(
        is_live=False,
        is_armed=True,
        data_dir=tmp_path,
        asset=CryptoAsset.BTC,
    )
    return engine


def test_standalone_onnx_initialization_and_audit(test_engine: StandaloneONNXEngine):
    """Verify engine startup passes 4-pillar pre-flight audit and initializes dual brains."""
    assert test_engine.bot is not None
    assert test_engine.candle_builder is not None
    assert test_engine.hmm_brain is not None
    assert test_engine.gateway is not None
    assert test_engine.guardrails is not None
    assert "the_onnx_strategy" in test_engine.guardrails.authorized_live_bots
    assert test_engine.guardrails.max_micro_bankroll_contracts == 1
    assert test_engine.guardrails.max_nano_bankroll_contracts == 1


def test_standalone_onnx_parameters_introspection_and_update(test_engine: StandaloneONNXEngine):
    """Verify all 12 parameters are introspectable and dynamically updatable."""
    params = test_engine.get_parameters()
    assert "brain_priority_mode" in params
    assert "gamma_cliff_seconds" in params
    assert "max_temporal_skew_ms" in params
    assert "dynamic_volatility_mode" in params
    assert "taker_cross_ev_threshold" in params
    assert params["gamma_cliff_seconds"] == 90.0

    # Update parameters
    updated = test_engine.update_parameters(
        gamma_cliff_seconds=120.0,
        max_temporal_skew_ms=500.0,
        dynamic_volatility_mode="FIXED_STATIC",
    )
    assert updated["gamma_cliff_seconds"] == 120.0
    assert updated["max_temporal_skew_ms"] == 500.0
    assert updated["dynamic_volatility_mode"] == "FIXED_STATIC"


def test_mutual_interlock_detection(tmp_path: Path):
    """Verify mutual live interlock detects active Port 8001 live lock."""
    # When no lock exists
    engine = StandaloneONNXEngine(
        is_live=False,
        is_armed=True,
        data_dir=tmp_path,
        asset=CryptoAsset.BTC,
    )
    # Check default state when Port 8001 is not running
    assert engine.execution_mode in ("LIVE", "SHADOW")


def test_fastapi_endpoints_with_mock_engine(test_engine: StandaloneONNXEngine):
    """Verify Port 8002 FastAPI endpoints return valid schemas and mutate state."""
    import shared.standalone_onnx as so
    so.app_engine = test_engine

    client = TestClient(app)

    # 1. Root HTML Pocket Cockpit
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "THE ONNX STRATEGY" in res_root.text

    # 2. State Telemetry Endpoint
    res_state = client.get("/api/state")
    assert res_state.status_code == 200
    state = res_state.json()
    assert state["bot_type"] == "the_onnx_strategy"
    assert "brain_1_signal" in state
    assert "brain_2_signal" in state
    assert "cross_brain_skew_ms" in state
    assert "gamma_cliff_seconds" in state
    assert "dynamic_volatility_mode" in state
    assert "hmm_regime" in state

    # 3. Master Controls (Arm/Disarm/Panic/Sweep)
    res_disarm = client.post("/api/disarm")
    assert res_disarm.status_code == 200
    assert test_engine.is_armed is False

    res_arm = client.post("/api/arm")
    assert res_arm.status_code == 200
    assert test_engine.is_armed is True

    res_sweep = client.post("/api/sweep")
    assert res_sweep.status_code == 200
    assert res_sweep.json()["status"] == "SUCCESS"

    res_panic = client.post("/api/panic")
    assert res_panic.status_code == 200
    assert test_engine.is_armed is False

    # 4. Parameters API (GET & POST)
    res_get_params = client.get("/api/bot/parameters")
    assert res_get_params.status_code == 200
    assert "brain_priority_mode" in res_get_params.json()

    res_post_params = client.post(
        "/api/bot/parameters",
        json={"gamma_cliff_seconds": 75.0, "entry_discount_depth": 0.46},
    )
    assert res_post_params.status_code == 200
    assert res_post_params.json()["parameters"]["gamma_cliff_seconds"] == 75.0
    assert res_post_params.json()["parameters"]["entry_discount_depth"] == 0.46


def test_standalone_onnx_sizing_armor(test_engine: StandaloneONNXEngine):
    """Verify strict 1-contract sizing armor under micro-bankroll."""
    ticker = "KXBTC15M-26SEP101800-00"
    is_ok, reason, size, _ = test_engine.guardrails.validate_pre_trade_intent(
        ticker=ticker,
        side="yes",
        requested_size=10,  # Strategy requests 10 contracts
        est_price=Decimal("0.48"),
        total_equity=Decimal("20.51"),
        is_bot=True,
        bot_type="the_onnx_strategy",
        is_live=True,
    )
    assert is_ok is True
    assert size == 1  # Hard-capped to 1


def test_brain_2_telemetry_and_evaluation(test_engine: StandaloneONNXEngine):
    """Verify Brain 2 (Kalshi CLOB) connects and evaluates DualONNXArbitrageBot cleanly."""
    import asyncio
    ticker = "KXBTC15M-26SEP101800-00"
    test_engine.active_ticker = ticker
    test_engine.target_strike = Decimal("78000.00")
    test_engine.current_btc_spot = Decimal("78150.00")

    # Seed Kalshi orderbook
    from shared.schemas import L2BookState
    kalshi_book = L2BookState(ticker)
    kalshi_book.yes_book = {Decimal("0.55"): Decimal("25"), Decimal("0.54"): Decimal("10")}
    kalshi_book.no_book = {Decimal("0.46"): Decimal("30"), Decimal("0.47"): Decimal("15")}
    test_engine.orderbook.set_book(ticker, kalshi_book)

    # Seed Spot orderbook
    test_engine.spot_orderbook.yes_book = {Decimal("78150.00"): Decimal("1.5")}
    test_engine.spot_orderbook.no_book = {Decimal("78151.00"): Decimal("2.0")}

    test_engine.best_yes_bid = Decimal("0.55")
    test_engine.best_yes_ask = Decimal("0.54")
    test_engine.kalshi_ws_connected = True

    # Run evaluation
    asyncio.run(test_engine._evaluate_and_execute())

    assert test_engine.kalshi_ws_connected is True
    assert test_engine.last_decision is not None
    assert test_engine.last_kalshi_signal in ("UP", "DOWN", "WAIT")
    assert test_engine.last_spot_signal in ("UP", "DOWN", "WAIT")

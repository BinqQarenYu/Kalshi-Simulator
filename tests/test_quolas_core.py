"""Comprehensive Unit Tests for QuoLas Core ML & Microstructure Subsystem."""

import asyncio
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pytest

from app_1_machine_engine.ml.quolas_core import (
    DepthSnapshot,
    FlowSignal,
    HMMBrain,
    HMMConfig,
    MarketRegime,
    NanoMatrixBuilder,
    OrderFlowConfig,
    OrderFlowIntegrity,
    QuoLasCoreConfig,
    StreamConfig,
    StreamManager,
    TradeEvent,
)


# ==============================================================================
# 1. Configuration & Enum Invariants
# ==============================================================================


def test_quolas_core_configs():
    config = QuoLasCoreConfig()
    assert config.order_flow.vpin_bucket_size == 2.0
    assert config.order_flow.cvd_divergence_sigma == 2.0
    assert config.stream.ping_interval == 180
    assert "BTCUSDT" in config.stream.default_pairs
    assert config.hmm.n_states == 3
    assert config.hmm.min_training_samples == 288


def test_market_regime_properties():
    assert MarketRegime.STABLE_RANGE.is_tradeable is True
    assert MarketRegime.VOL_EXPANSION.is_tradeable is True
    assert MarketRegime.RISK_OFF.is_tradeable is False

    assert "mean-reverting" in MarketRegime.STABLE_RANGE.description.lower()
    assert "trending" in MarketRegime.VOL_EXPANSION.description.lower()
    assert "stress" in MarketRegime.RISK_OFF.description.lower()

    assert MarketRegime.STABLE_RANGE.emoji == "🟢"
    assert MarketRegime.VOL_EXPANSION.emoji == "🟡"
    assert MarketRegime.RISK_OFF.emoji == "🔴"


# ==============================================================================
# 2. OrderFlowIntegrity & Truth Layer
# ==============================================================================


def test_order_flow_integrity_trade_processing():
    engine = OrderFlowIntegrity()
    sym = "BTCUSDT"

    # Process buy trade (seller is maker -> buyer initiated -> positive CVD)
    buy_trade = TradeEvent(
        timestamp=int(time.time() * 1000),
        price=60000.0,
        quantity=0.5,
        is_buyer_maker=False,
        symbol=sym,
    )
    sig = engine.process_trade(buy_trade)
    assert sig == FlowSignal.CLEAN
    assert engine.states[sym].cvd == 0.5

    # Process sell trade (buyer is maker -> seller initiated -> negative CVD)
    sell_trade = TradeEvent(
        timestamp=int(time.time() * 1000),
        price=60000.0,
        quantity=0.3,
        is_buyer_maker=True,
        symbol=sym,
    )
    engine.process_trade(sell_trade)
    assert pytest.approx(engine.states[sym].cvd, 0.001) == 0.2


def test_order_flow_vpin_bucket_and_manipulation():
    engine = OrderFlowIntegrity(OrderFlowConfig(vpin_bucket_size=1.0))
    sym = "BTCUSDT"

    # Accumulate 1.0 BTC of volume
    t1 = TradeEvent(
        timestamp=int(time.time() * 1000),
        price=65000.0,
        quantity=0.6,
        is_buyer_maker=False,
        symbol=sym,
    )
    t2 = TradeEvent(
        timestamp=int(time.time() * 1000),
        price=65000.0,
        quantity=0.5,
        is_buyer_maker=True,
        symbol=sym,
    )
    engine.process_trade(t1)
    engine.process_trade(t2)

    status = engine.get_status(sym)
    assert status["symbol"] == sym
    assert "vpin" in status
    assert status["vpin"] >= 0.0


def test_order_flow_depth_processing_and_ofi():
    engine = OrderFlowIntegrity()
    sym = "BTCUSDT"

    now_ms = int(time.time() * 1000)
    snap1 = DepthSnapshot(
        timestamp=now_ms,
        symbol=sym,
        bids=[[65000.0, 2.0], [64990.0, 5.0]],
        asks=[[65010.0, 1.5], [65020.0, 4.0]],
        total_bid_depth=7.0,
        total_ask_depth=5.5,
    )
    engine.process_depth(snap1)
    assert engine.is_flow_clean(sym) is True

    # Next tick with higher bid size -> positive OFI
    snap2 = DepthSnapshot(
        timestamp=now_ms + 100,
        symbol=sym,
        bids=[[65000.0, 4.0], [64990.0, 5.0]],
        asks=[[65010.0, 1.5], [65020.0, 4.0]],
        total_bid_depth=9.0,
        total_ask_depth=5.5,
    )
    engine.process_depth(snap2)
    assert engine.states[sym].ofi > 0.0


def test_order_flow_spoofing_detection():
    engine = OrderFlowIntegrity(OrderFlowConfig(spoof_cancel_pct=0.30, spoof_cooldown_seconds=5.0))
    sym = "BTCUSDT"
    now_ms = int(time.time() * 1000)

    snap1 = DepthSnapshot(
        timestamp=now_ms,
        symbol=sym,
        bids=[[65000.0, 10.0]],
        asks=[[65010.0, 10.0]],
        total_bid_depth=10.0,
        total_ask_depth=10.0,
    )
    engine.process_depth(snap1)

    # Rapid cancellation of 50% bid depth within 200ms -> spoofing
    snap2 = DepthSnapshot(
        timestamp=now_ms + 200,
        symbol=sym,
        bids=[[65000.0, 4.0]],
        asks=[[65010.0, 10.0]],
        total_bid_depth=4.0,
        total_ask_depth=10.0,
    )
    sig = engine.process_depth(snap2)
    assert sig == FlowSignal.SPOOFING
    assert engine.get_flow_signal(sym) == FlowSignal.SPOOFING
    assert engine.is_flow_clean(sym) is False


# ==============================================================================
# 3. NanoMatrixBuilder (28-Feature Tensor Generation)
# ==============================================================================


def test_nano_matrix_builder_tensor_shape_and_finite():
    builder = NanoMatrixBuilder(target_depth=15)

    # Empty payload returns 28 zeros
    zeros = builder.extract_features({})
    assert zeros.shape == (28,)
    assert zeros.dtype == np.float32
    assert np.all(zeros == 0.0)

    # Valid depth payload
    depth_payload = {
        "bids": [[float(65000 - i * 5), float(1.0 + i * 0.2)] for i in range(15)],
        "asks": [[float(65005 + i * 5), float(1.2 + i * 0.1)] for i in range(15)],
    }

    trades = [
        {"p": 65001.0, "q": 0.25, "m": False, "T": int(time.time() * 1000)},
        {"p": 65002.0, "q": 0.50, "m": True, "T": int(time.time() * 1000)},
        {"p": 65003.0, "q": 5.50, "m": False, "T": int(time.time() * 1000)},  # whale trade
    ]

    tensor = builder.extract_features(depth_payload, trade_batch=trades)

    assert tensor.shape == (28,)
    assert tensor.dtype == np.float32
    assert not np.isnan(tensor).any(), "Tensor contains NaN"
    assert not np.isinf(tensor).any(), "Tensor contains Inf"

    # Check that current tensor retrieval matches
    cached = builder.get_current_tensor()
    assert np.array_equal(tensor, cached)

    # Check specific features
    spread_bps = tensor[0]
    assert spread_bps > 0.0  # Spread between 65005 and 65000 must be positive
    whale_tx = tensor[11]
    assert whale_tx >= 1.0  # One whale trade >= 5 BTC was submitted


# ==============================================================================
# 4. StreamManager & Async Dispatch
# ==============================================================================


def test_stream_manager_dispatch():
    async def _test():
        config = StreamConfig(testnet=True)
        manager = StreamManager(config=config)

        received_trades: List[Dict] = []
        received_depths: List[Dict] = []

        async def trade_handler(data):
            received_trades.append(data)

        def depth_handler(data):
            received_depths.append(data)

        await manager.start(
            pairs=["BTCUSDT"],
            on_trade=trade_handler,
            on_depth=depth_handler,
        )

        status = manager.get_status()
        assert status["running"] is True
        assert status["registered_callbacks"]["aggTrade"] == 1
        assert status["registered_callbacks"]["depth"] == 1

        # Simulate dispatching incoming websocket frames
        await manager._dispatch({
            "stream": "btcusdt@aggTrade",
            "data": {"p": "65000.00", "q": "0.10", "m": False},
        })
        await manager._dispatch({
            "stream": "btcusdt@depth@100ms",
            "data": {"bids": [["65000", "1.0"]], "asks": [["65005", "1.0"]]},
        })

        assert len(received_trades) == 1
        assert received_trades[0]["p"] == "65000.00"
        assert len(received_depths) == 1

        await manager.stop()
        assert manager._running is False

    asyncio.run(_test())


# ==============================================================================
# 5. HMMBrain & Regime Detection
# ==============================================================================


def test_hmm_brain_untrained_fallback():
    brain = HMMBrain(model_dir=Path("models/test_nonexistent_dir"))
    assert brain.current_regime == MarketRegime.STABLE_RANGE
    assert len(brain.regime_probabilities) == 3

    regime, probs = brain.predict_regime({})
    assert regime == MarketRegime.STABLE_RANGE
    assert len(probs) == 3


def test_hmm_brain_training_and_prediction(tmp_path):
    brain = HMMBrain(model_dir=tmp_path)

    # Generate 300 synthetic 5m candles
    np.random.seed(42)
    base_price = 60000.0
    candles = []
    for i in range(300):
        ret = np.random.normal(0.0001, 0.002)
        base_price *= np.exp(ret)
        candles.append({
            "timestamp": 1700000000 + i * 300,
            "open": base_price * 0.999,
            "high": base_price * 1.002,
            "low": base_price * 0.998,
            "close": base_price,
            "volume": float(np.random.uniform(10.0, 50.0)),
            "funding_rate": 0.0001,
        })

    data_bundle = {"BTCUSDT": candles}

    success = brain.train(data_bundle)
    assert success is True
    assert brain.model is not None
    assert brain.last_train_time is not None

    # Predict regime
    regime, probs = brain.predict_regime(data_bundle)
    assert isinstance(regime, MarketRegime)
    assert len(probs) == 3
    assert pytest.approx(float(np.sum(probs)), 0.01) == 1.0

    # Test model persistence and reload
    brain2 = HMMBrain(model_dir=tmp_path)
    assert brain2.model is not None
    regime2, probs2 = brain2.predict_regime(data_bundle)
    assert regime2 == regime
    assert np.allclose(probs2, probs)


# ==============================================================================
# 6. Dual-ONNX Gateway & Strategy Integration with QuoLas Core
# ==============================================================================


def test_dual_onnx_gateway_and_hmm_strategy_integration():
    from decimal import Decimal
    from app_1_machine_engine.ml.dual_onnx_gateway import DualONNXGateway
    from app_1_machine_engine.ml.dual_onnx_strategy import DualONNXArbitrageBot
    from app_1_machine_engine.ml.dual_onnx_schemas import DualONNXRegime
    from shared.schemas import L2BookState

    # 1. Gateway with NanoMatrixBuilder
    builder = NanoMatrixBuilder(target_depth=15)
    # Generate mock tensor
    depth_payload = {
        "bids": [[65000.0 - i * 5, 1.0] for i in range(15)],
        "asks": [[65005.0 + i * 5, 1.0] for i in range(15)],
    }
    tensor = builder.extract_features(depth_payload)

    gateway = DualONNXGateway(matrix_builder=builder)

    kalshi_l2 = L2BookState(market_ticker="KXBTC15M-T65000", is_spot=False)
    kalshi_l2.yes_book[Decimal("0.45")] = Decimal("20")
    kalshi_l2.no_book[Decimal("0.55")] = Decimal("20")

    q_res, k_res = gateway.infer_both(
        spot_book=None,
        kalshi_book=kalshi_l2,
        spot_tensor=tensor,
    )
    assert "signal" in q_res
    assert "confidence" in q_res

    # 2. Strategy with HMMBrain RISK_OFF veto check
    brain = HMMBrain()
    brain.current_regime = MarketRegime.RISK_OFF

    bot = DualONNXArbitrageBot(gateway=gateway, hmm_brain=brain)
    assert bot.get_parameters()["hmm_regime"] == "RISK_OFF"

    # Spot book
    spot_l2 = L2BookState(market_ticker="BTC_SPOT", is_spot=True)
    spot_l2.yes_book[Decimal("0.50")] = Decimal("50")
    spot_l2.no_book[Decimal("0.50")] = Decimal("50")

    # Evaluate opportunity with synthetic high confidence QuoLas LONG
    fake_quolas = {
        "signal": "LONG",
        "confidence": 0.85,
        "vpin_score": 0.10,
        "vpin_veto": False,
    }
    fake_kalshi = {
        "signal": "LONG",
        "confidence": 0.85,
        "vpin_score": 0.10,
        "vpin_veto": False,
    }

    decision = bot.evaluate(
        spot_l2=spot_l2,
        kalshi_l2=kalshi_l2,
        quolas_inference=fake_quolas,
        kalshi_inference=fake_kalshi,
    )

    assert decision.action == "HOLD"
    assert decision.regime == DualONNXRegime.TOXIC_VETO
    assert "RISK_OFF" in decision.rationale

    # Clear RISK_OFF to verify parameters update
    brain.current_regime = MarketRegime.STABLE_RANGE
    assert bot.get_parameters()["hmm_regime"] == "STABLE_RANGE"


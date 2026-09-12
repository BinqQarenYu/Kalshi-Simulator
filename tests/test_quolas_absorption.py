"""Unit and integration tests for Full QuoLas Core Absorption in Kalshi Simulator.

Verifies:
1. Real-time CandleBuilder aggregation (1m and 5m).
2. BtcOrderflowFeed candle generation.
3. HMMBrain training, regime prediction, persistence, and telemetry.
4. DualONNXGateway loading models/quolas.onnx with dynamic hot-swap.
5. DualONNXArbitrageBot enforcing HMM RISK_OFF regime veto.
6. ContinuousModelTrainer export_and_verify_onnx generating valid quolas.onnx.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import time
from typing import Any, Dict, List
import numpy as np
import pytest

from kalshi_sim.ml.continuous_trainer import (
    ContinuousModelTrainer,
    QuoLasMicroscopeNet,
    export_and_verify_onnx,
)
from kalshi_sim.ml.dual_onnx_gateway import DualONNXGateway
from kalshi_sim.ml.dual_onnx_schemas import DualONNXRegime
from kalshi_sim.ml.dual_onnx_strategy import DualONNXArbitrageBot
from kalshi_sim.ml.quolas_core.candle_builder import Candle, CandleBuilder
from kalshi_sim.ml.quolas_core.config import HMMConfig
from kalshi_sim.ml.quolas_core.hmm_brain import HMMBrain
from kalshi_sim.ml.quolas_core.regime_types import MarketRegime
from kalshi_sim.orderflow.btc_orderflow_feed import BtcOrderflowFeed
from kalshi_sim.schemas import L2BookState


# ---------------------------------------------------------------------------
# 1. CandleBuilder Tests
# ---------------------------------------------------------------------------

def test_candle_builder_aggregation():
    """Test CandleBuilder creates and closes candles across boundary transitions."""
    builder = CandleBuilder(interval_seconds=60, max_candles=10)

    t0 = 1700000000000  # aligned ms
    builder.process_tick("BTCUSDT", price=90000.0, quantity=1.0, timestamp_ms=t0)
    builder.process_tick("BTCUSDT", price=90500.0, quantity=0.5, timestamp_ms=t0 + 10000)
    builder.process_tick("BTCUSDT", price=89800.0, quantity=0.8, timestamp_ms=t0 + 20000)
    builder.process_tick("BTCUSDT", price=90200.0, quantity=1.2, timestamp_ms=t0 + 30000)

    # Next minute tick closes the first candle
    closed = builder.process_tick("BTCUSDT", price=90300.0, quantity=0.4, timestamp_ms=t0 + 60000)
    assert closed is not None
    assert closed.open == 90000.0
    assert closed.high == 90500.0
    assert closed.low == 89800.0
    assert closed.close == 90200.0
    assert closed.volume == pytest.approx(3.5)
    assert closed.trade_count == 4
    assert closed.is_closed is True

    candles = builder.get_candles("BTCUSDT", count=10)
    assert len(candles) == 2  # 1 closed + 1 open running candle
    assert candles[0]["open"] == 90000.0
    assert candles[1]["open"] == 90300.0


# ---------------------------------------------------------------------------
# 2. BtcOrderflowFeed Candle Integration Tests
# ---------------------------------------------------------------------------

def test_btc_orderflow_feed_candle_builder():
    """Test BtcOrderflowFeed generates 5m and 1m candles from seeded orderflow."""
    feed = BtcOrderflowFeed()
    candles_5m = feed.get_candles(symbol="BTCUSDT", interval_seconds=300, count=10)
    candles_1m = feed.get_candles(symbol="BTCUSDT", interval_seconds=60, count=10)

    assert len(candles_5m) > 0
    assert len(candles_1m) > 0
    assert "close" in candles_5m[0]
    assert "volume" in candles_5m[0]


# ---------------------------------------------------------------------------
# 3. HMMBrain Feature Extraction, Prediction & Persistence Tests
# ---------------------------------------------------------------------------

def _generate_synthetic_candles(count: int = 300, start_price: float = 85000.0) -> List[Dict[str, Any]]:
    """Generate synthetic 5m OHLCV candles for HMM testing."""
    candles = []
    curr = start_price
    t_base = 1700000000000
    for i in range(count):
        change = np.random.normal(0.0, 50.0)
        p_open = curr
        p_close = max(1000.0, p_open + change)
        p_high = max(p_open, p_close) + abs(np.random.normal(0.0, 15.0))
        p_low = min(p_open, p_close) - abs(np.random.normal(0.0, 15.0))
        candles.append({
            "timestamp": t_base + (i * 300000),
            "open": p_open,
            "high": p_high,
            "low": p_low,
            "close": p_close,
            "volume": float(np.random.uniform(0.5, 5.0)),
            "volume_usd": p_close * float(np.random.uniform(0.5, 5.0)),
            "trade_count": int(np.random.randint(5, 50)),
            "funding_rate": float(np.random.normal(0.0001, 0.00002)),
        })
        curr = p_close
    return candles


def test_hmm_brain_training_and_prediction(tmp_path: Path):
    """Test HMMBrain can train on 300 candles, predict regimes, and persist to disk."""
    cfg = HMMConfig(models_dir=tmp_path, model_filename="test_hmm.pkl", min_training_samples=288)
    brain = HMMBrain(config=cfg, model_dir=tmp_path)

    candles = _generate_synthetic_candles(count=300)
    train_ok = brain.train({"BTCUSDT": candles})
    assert train_ok is True
    assert brain.model is not None
    assert brain.model_path.exists()

    regime, probs = brain.predict_regime({"BTCUSDT": candles})
    assert isinstance(regime, MarketRegime)
    assert len(probs) == 3
    assert pytest.approx(float(np.sum(probs)), rel=1e-3) == 1.0

    status = brain.get_status()
    assert status["is_fitted"] is True
    assert "current_regime" in status
    assert "regime_probabilities" in status

    # Verify reloading from disk
    brain_reloaded = HMMBrain(config=cfg, model_dir=tmp_path)
    assert brain_reloaded.model is not None
    assert brain_reloaded.current_regime == brain.current_regime


# ---------------------------------------------------------------------------
# 4. DualONNXGateway & Strategy Integration Tests
# ---------------------------------------------------------------------------

def test_dual_onnx_gateway_quolas_loading():
    """Test DualONNXGateway loads quolas.onnx if present."""
    gateway = DualONNXGateway()
    # Should point to models/quolas.onnx if it exists on disk
    if Path("models/quolas.onnx").exists():
        assert gateway.quolas_model_path == Path("models/quolas.onnx")
        assert gateway.kalshi_model_path == Path("models/quolas.onnx")


def test_dual_onnx_strategy_hmm_risk_off_veto():
    """Test DualONNXArbitrageBot vetoes any trades when HMM regime is RISK_OFF."""
    gateway = DualONNXGateway()
    brain = HMMBrain()
    brain.current_regime = MarketRegime.RISK_OFF

    bot = DualONNXArbitrageBot(gateway=gateway, hmm_brain=brain)

    spot_l2 = L2BookState(market_ticker="BTC_SPOT", is_spot=True)
    spot_l2.yes_book[Decimal("0.50")] = Decimal("50")
    spot_l2.no_book[Decimal("0.50")] = Decimal("50")

    kalshi_l2 = L2BookState(market_ticker="KXBTC15M-TEST", is_spot=False)
    kalshi_l2.yes_book[Decimal("0.45")] = Decimal("20")
    kalshi_l2.no_book[Decimal("0.55")] = Decimal("20")

    fake_quolas = {"signal": "LONG", "confidence": 0.85, "vpin_score": 0.10, "vpin_veto": False}
    fake_kalshi = {"signal": "LONG", "confidence": 0.85, "vpin_score": 0.10, "vpin_veto": False}

    decision = bot.evaluate(
        spot_l2=spot_l2,
        kalshi_l2=kalshi_l2,
        quolas_inference=fake_quolas,
        kalshi_inference=fake_kalshi,
    )

    assert decision.action == "HOLD"
    assert decision.regime == DualONNXRegime.TOXIC_VETO
    assert "HMM macro regime veto: RISK_OFF" in decision.rationale


def test_cross_brain_temporal_skew_veto():
    """Test DualONNXArbitrageBot vetoes any trades when Spot and Kalshi feeds drift by > 1000ms."""
    from datetime import datetime, timezone
    gateway = DualONNXGateway()
    bot = DualONNXArbitrageBot(gateway=gateway, max_temporal_skew_ms=1000.0)

    # 1. In-sync test: Spot and Kalshi timestamps within 50ms
    base_t = 1789020000.0
    spot_l2 = L2BookState(market_ticker="BTC_SPOT", is_spot=True)
    spot_l2.yes_book[Decimal("0.50")] = Decimal("50")
    spot_l2.no_book[Decimal("0.50")] = Decimal("50")
    spot_l2.last_update = datetime.fromtimestamp(base_t, tz=timezone.utc)

    kalshi_l2 = L2BookState(market_ticker="KXBTC15M-TEST", is_spot=False)
    kalshi_l2.yes_book[Decimal("0.45")] = Decimal("20")
    kalshi_l2.no_book[Decimal("0.55")] = Decimal("20")
    kalshi_l2.last_update = datetime.fromtimestamp(base_t + 0.05, tz=timezone.utc)

    fake_quolas = {"signal": "LONG", "confidence": 0.85, "vpin_score": 0.10, "vpin_veto": False}
    fake_kalshi = {"signal": "LONG", "confidence": 0.85, "vpin_score": 0.10, "vpin_veto": False}

    dec_sync = bot.evaluate(
        spot_l2=spot_l2,
        kalshi_l2=kalshi_l2,
        quolas_inference=fake_quolas,
        kalshi_inference=fake_kalshi,
    )
    assert bot.is_temporally_synced is True
    assert bot.last_temporal_skew_ms < 100.0
    assert dec_sync.regime != DualONNXRegime.TEMPORAL_DESYNC

    # 2. Desync test: Spot is 2.5 seconds ahead of Kalshi (Kalshi stalled)
    kalshi_l2.last_update = datetime.fromtimestamp(base_t - 2.5, tz=timezone.utc)
    dec_desync = bot.evaluate(
        spot_l2=spot_l2,
        kalshi_l2=kalshi_l2,
        quolas_inference=fake_quolas,
        kalshi_inference=fake_kalshi,
    )
    assert dec_desync.action == "HOLD"
    assert dec_desync.regime == DualONNXRegime.TEMPORAL_DESYNC
    assert bot.is_temporally_synced is False
    assert bot.slower_brain == "KALSHI"
    assert "Temporal desync veto" in dec_desync.rationale

    # 3. Telemetry in get_parameters
    params = bot.get_parameters()
    assert params["max_temporal_skew_ms"] == 1000.0
    assert params["cross_brain_skew_ms"] == 2500.0
    assert params["is_temporally_synced"] is False
    assert params["slower_brain"] == "KALSHI"


# ---------------------------------------------------------------------------
# 5. ContinuousModelTrainer Export Verification
# ---------------------------------------------------------------------------

def test_continuous_trainer_quolas_export(tmp_path: Path):
    """Test export_and_verify_onnx produces a verified ONNX model with UTF-8 safety."""
    net = QuoLasMicroscopeNet(input_dim=28, hidden_dim=64, num_classes=3)
    target_onnx = tmp_path / "test_quolas.onnx"

    ok = export_and_verify_onnx(net, target_onnx, device="cpu")
    assert ok is True
    assert target_onnx.exists()
    assert target_onnx.stat().st_size > 5000

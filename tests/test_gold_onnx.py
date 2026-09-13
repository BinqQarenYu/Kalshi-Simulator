"""Unit and integration tests for the 3rd Generation 32-D Gold Spacetime ONNX Engine (gold.onnx)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import time

import numpy as np
import onnxruntime as ort
import pytest

from kalshi_sim.ml.gold_feature_extractor import GoldOrderflowFeatureExtractor
from kalshi_sim.ml.gold_model import QuoLasGoldMicroscopeNet, TORCH_AVAILABLE
from kalshi_sim.ml.export_gold_onnx import export_gold_to_onnx
from kalshi_sim.schemas import L2BookState, OrderSide, TradeEvent


@pytest.fixture
def mock_gold_book() -> L2BookState:
    """Create a mock L2 order book representing Gold (PAXG / XAU) around $2,500/oz."""
    book = L2BookState("KXGOLD-26SEP13-2500")
    # Gold spot around 2500.00
    book.yes_book = {
        Decimal("0.48"): Decimal("150"),
        Decimal("0.47"): Decimal("220"),
        Decimal("0.45"): Decimal("400"),
        Decimal("0.42"): Decimal("600"),
    }
    book.no_book = {
        Decimal("0.52"): Decimal("180"),
        Decimal("0.53"): Decimal("250"),
        Decimal("0.55"): Decimal("450"),
        Decimal("0.58"): Decimal("700"),
    }
    return book


def test_gold_feature_extractor_dimensions(mock_gold_book: L2BookState) -> None:
    """Verify that GoldOrderflowFeatureExtractor outputs exactly 32 dimensions."""
    extractor = GoldOrderflowFeatureExtractor(target_depth=15, default_gold_volatility=2.50)

    features = extractor.extract_features(
        book=mock_gold_book,
        target_strike=Decimal("2500.00"),
        current_spot=Decimal("2505.50"),
        time_to_expiry_s=300.0,
        twap_60s=Decimal("2504.80"),
    )

    assert isinstance(features, np.ndarray)
    assert features.dtype == np.float32
    assert features.shape == (32,)

    # Verify Spacetime Features
    # Feature 28 (Moneyness Z-Score): Spot $2505.50 vs Strike $2500.00 -> z > 0
    z_score = features[28]
    assert z_score > 0.0

    # Feature 29 (Normalized Time-to-Expiry): 300s / 900s = 0.333
    tau_norm = features[29]
    assert pytest.approx(tau_norm, rel=1e-2) == 0.333

    # Feature 31 (TWAP Delta): (2505.50 - 2504.80) / 2.50 = +0.28
    twap_delta = features[31]
    assert twap_delta > 0.0


def test_gold_feature_extractor_trade_processing() -> None:
    """Verify trade flow updates (CVD, VPIN, Whales) on the Gold feature extractor."""
    extractor = GoldOrderflowFeatureExtractor(target_depth=15)
    trade = TradeEvent(
        trade_id="GOLD-T1",
        market_ticker="KXGOLD-26SEP13-2500",
        taker_side=OrderSide.YES,
        price=Decimal("0.48"),
        yes_price=Decimal("0.48"),
        no_price=Decimal("0.52"),
        count=10,
    )
    extractor.process_trade(trade)

    assert extractor._running_cvd == 10.0
    assert len(extractor.rolling_trades) == 1


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch is required for model architecture test")
def test_quolas_gold_model_forward_pass() -> None:
    """Verify QuoLasGoldMicroscopeNet forward pass shapes and probability constraints."""
    import torch

    net = QuoLasGoldMicroscopeNet(input_dim=32, hidden_dim=64, num_classes=3)
    net.eval()

    # Batch of 4 samples
    x = torch.randn(4, 32, dtype=torch.float32)
    with torch.no_grad():
        probs = net(x)

    assert probs.shape == (4, 3)
    # Each row must sum to 1.0 (Softmax invariant)
    row_sums = probs.sum(dim=-1).numpy()
    np.testing.assert_allclose(row_sums, np.ones(4), atol=1e-5)
    assert (probs >= 0.0).all()


def test_export_gold_onnx_and_inference(tmp_path: Path) -> None:
    """Verify export of gold.onnx and benchmark ONNX Runtime CPU inference latency."""
    out_model = tmp_path / "gold.onnx"
    export_gold_to_onnx(output_path=out_model, verify_parity=True)

    assert out_model.exists()

    # Load in ONNX Runtime
    session = ort.InferenceSession(str(out_model), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    # Benchmark 100 single-tick inferences
    latencies = []
    test_tensor = np.random.randn(1, 32).astype(np.float32)
    for _ in range(100):
        t0 = time.perf_counter()
        out = session.run(None, {input_name: test_tensor})[0]
        latencies.append((time.perf_counter() - t0) * 1000.0)

    avg_lat_ms = sum(latencies) / len(latencies)
    assert avg_lat_ms < 5.0  # Ultra-low latency (< 5ms)
    assert out.shape == (1, 3)
    np.testing.assert_allclose(out.sum(), 1.0, atol=1e-4)


def test_kalshi_venue_adapter_evaluation() -> None:
    """Verify KalshiVenueAdapter transforms probabilities into valid Kalshi signals with CFTC fee logic."""
    from kalshi_sim.ml.adapters import KalshiVenueAdapter, SignalDirection

    adapter = KalshiVenueAdapter(min_conviction=Decimal("0.65"), dead_zone_gold_usd=Decimal("0.75"))

    # Test UP probability: [0.80, 0.10, 0.10], spot $2505 > strike $2500
    probs_up = np.array([0.80, 0.10, 0.10], dtype=np.float32)
    sig_up = adapter.evaluate_signal(
        probabilities=probs_up,
        current_spot=Decimal("2505.00"),
        target_strike=Decimal("2500.00"),
        time_to_expiry_s=300.0,
        best_bid=Decimal("0.48"),
        best_ask=Decimal("0.52"),
        bankroll=Decimal("50.00"),
        twap_60s=Decimal("2504.50"),
    )

    assert sig_up.direction == SignalDirection.BUY_YES
    assert sig_up.confidence == Decimal("0.80")
    assert sig_up.max_contracts == 1  # 1-contract armor for < $75 bankroll
    assert sig_up.recommended_limit_price == Decimal("0.48")
    assert sig_up.expected_fee >= Decimal("0.01")  # Kalshi taker fee floor
    assert sig_up.settlement_offset == Decimal("0.50")

    # Test Dead-Zone veto: spot $2500.20 vs strike $2500.00 (diff $0.20 < $0.75 threshold)
    sig_deadzone = adapter.evaluate_signal(
        probabilities=probs_up,
        current_spot=Decimal("2500.20"),
        target_strike=Decimal("2500.00"),
        time_to_expiry_s=300.0,
        best_bid=Decimal("0.48"),
        best_ask=Decimal("0.52"),
        bankroll=Decimal("50.00"),
    )
    assert sig_deadzone.direction == SignalDirection.HOLD
    assert sig_deadzone.telemetry["in_dead_zone"] is True


def test_polymarket_venue_adapter_evaluation() -> None:
    """Verify PolymarketVenueAdapter produces gasless, point-in-time oracle signals."""
    from kalshi_sim.ml.adapters import PolymarketVenueAdapter, SignalDirection

    adapter = PolymarketVenueAdapter(min_conviction=Decimal("0.65"))

    probs_down = np.array([0.10, 0.85, 0.05], dtype=np.float32)
    sig_down = adapter.evaluate_signal(
        probabilities=probs_down,
        current_spot=Decimal("2495.00"),
        target_strike=Decimal("2500.00"),
        time_to_expiry_s=180.0,
        best_bid=Decimal("0.50"),
        best_ask=Decimal("0.54"),
        bankroll=Decimal("60.00"),
    )

    assert sig_down.direction == SignalDirection.BUY_NO
    assert sig_down.confidence == Decimal("0.85")
    assert sig_down.max_contracts == 1
    assert sig_down.expected_fee == Decimal("0.00")  # 0% exchange fee on Polymarket


def test_binance_venue_adapter_evaluation() -> None:
    """Verify BinanceVenueAdapter computes basis point taker fees and index mark signals."""
    from kalshi_sim.ml.adapters import BinanceVenueAdapter, SignalDirection

    adapter = BinanceVenueAdapter(min_conviction=Decimal("0.65"))

    probs_up = np.array([0.75, 0.15, 0.10], dtype=np.float32)
    sig_up = adapter.evaluate_signal(
        probabilities=probs_up,
        current_spot=Decimal("2510.00"),
        target_strike=Decimal("2500.00"),
        time_to_expiry_s=120.0,
        best_bid=Decimal("0.50"),
        best_ask=Decimal("0.52"),
        bankroll=Decimal("50.00"),
        mark_price=Decimal("2509.80"),
    )

    assert sig_up.direction == SignalDirection.BUY_YES
    assert sig_up.confidence == Decimal("0.75")
    assert sig_up.max_contracts == 1
    assert sig_up.expected_fee > Decimal("0.00")  # Basis-point fee


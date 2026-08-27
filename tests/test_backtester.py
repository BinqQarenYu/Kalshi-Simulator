"""Unit and integration tests for strategy backtesting and model comparison engine."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import numpy as np
import pytest

from kalshi_sim.ml.backtester import BacktestEngine, BacktestResult, ModelComparator
from kalshi_sim.ml.dataset_builder import TickFrame
from kalshi_sim.ml.export_onnx import export_to_onnx
from kalshi_sim.ml.model import QuoLasMicroscopeNet


@pytest.fixture
def synthetic_tick_frames() -> list[TickFrame]:
    """Generate 60 synthetic tick frames with price oscillations."""
    np.random.seed(42)
    frames = []
    price = 0.50
    for i in range(60):
        # Create predictable oscillation
        price = 0.50 + 0.05 * np.sin(i / 3.0)
        feat = np.random.randn(28).astype(np.float32)
        feat[6] = 0.20  # Safe VPIN (20%)
        feat[7] = 0.20
        frames.append(
            TickFrame(
                timestamp=1000.0 + i,
                ticker="KXBTC15M-T78650",
                features=feat,
                mid_price=float(price),
            )
        )
    return frames


def test_backtest_engine_execution(synthetic_tick_frames: list[TickFrame]) -> None:
    """Test running a backtest simulation over tick frames."""
    engine = BacktestEngine(
        onnx_model_path=None,  # Use baseline
        starting_capital=10000.0,
        holding_horizon=5,
        min_ev_threshold=0.01,
        fee_per_contract=0.01,
    )

    result = engine.run(synthetic_tick_frames, model_name="BaselineEngine")
    assert isinstance(result, BacktestResult)
    assert result.initial_capital == 10000.0
    assert result.total_trades >= 0
    assert len(result.equity_curve) >= 1
    assert result.max_drawdown_pct >= 0.0
    assert result.win_rate_pct >= 0.0


def test_model_comparator_with_onnx_candidate(tmp_path: Path, synthetic_tick_frames: list[TickFrame]) -> None:
    """Test comparing multiple models with ModelComparator."""
    # 1. Export a candidate ONNX model
    model = QuoLasMicroscopeNet(input_dim=28, hidden_dim=32, num_classes=3, num_blocks=1)
    onnx_path = tmp_path / "model_alpha.onnx"
    export_to_onnx(model, onnx_path, input_dim=28, verify_parity=False)

    comparator = ModelComparator(frames=synthetic_tick_frames, starting_capital=10000.0)
    candidates = [
        ("Baseline", None),
        ("ModelAlpha", onnx_path),
    ]

    results = comparator.compare(candidates)
    assert len(results) == 2
    assert results[0].total_net_pnl >= results[1].total_net_pnl

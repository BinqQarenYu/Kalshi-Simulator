"""Unit and integration tests for ONNX model export, graph parity, and latency benchmarking."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import onnxruntime as ort
import pytest
import torch

from kalshi_sim.ml.export_onnx import (
    benchmark_onnx_inference,
    check_numerical_parity,
    export_to_onnx,
)
from kalshi_sim.ml.model import QuoLasMicroscopeNet


def test_export_to_onnx_and_parity(tmp_path: Path) -> None:
    """Test exporting PyTorch model to ONNX and verifying exact numerical output parity."""
    model = QuoLasMicroscopeNet(input_dim=28, hidden_dim=32, num_classes=3, num_blocks=1)
    model.eval()

    onnx_path = tmp_path / "test_model.onnx"
    export_to_onnx(
        model=model,
        output_path=onnx_path,
        input_dim=28,
        opset_version=17,
        verify_parity=True,
    )

    assert onnx_path.exists()

    # Direct session check
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    assert session.get_inputs()[0].name == "input"
    assert session.get_outputs()[0].name == "output"

    # Parity function check
    is_valid = check_numerical_parity(model, onnx_path, input_dim=28, atol=1e-4)
    assert is_valid is True


def test_benchmark_onnx_inference(tmp_path: Path) -> None:
    """Test ONNX latency benchmarking function returns valid percentiles."""
    model = QuoLasMicroscopeNet(input_dim=28, hidden_dim=32, num_classes=3, num_blocks=1)
    onnx_path = tmp_path / "bench_model.onnx"
    export_to_onnx(model, onnx_path, input_dim=28, verify_parity=False)

    bench = benchmark_onnx_inference(onnx_path, input_dim=28, num_runs=50, warmup_runs=10)
    assert "mean_latency_ms" in bench
    assert "p50_latency_ms" in bench
    assert "p95_latency_ms" in bench
    assert "p99_latency_ms" in bench
    assert bench["mean_latency_ms"] > 0.0
    assert bench["mean_latency_ms"] < 50.0  # Ultra-fast CPU inference


def test_onnx_dynamic_batching(tmp_path: Path) -> None:
    """Test ONNX graph accepts variable dynamic batch sizes."""
    model = QuoLasMicroscopeNet(input_dim=28, hidden_dim=32, num_classes=3, num_blocks=1)
    onnx_path = tmp_path / "dynamic_model.onnx"
    export_to_onnx(model, onnx_path, input_dim=28, verify_parity=False)

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    for b in [1, 7, 32]:
        test_in = np.random.randn(b, 28).astype(np.float32)
        out = session.run(None, {input_name: test_in})[0]
        assert out.shape == (b, 3)
        assert np.allclose(out.sum(axis=-1), np.ones(b), atol=1e-4)

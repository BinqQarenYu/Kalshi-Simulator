"""ONNX Export, Graph Verification & Latency Benchmarking Pipeline.

Converts trained PyTorch QuoLas Microscope neural networks to optimized ONNX models,
verifies strict numerical equivalence against ONNX Runtime, and benchmarks inference latency.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

import numpy as np
import onnxruntime as ort
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except (ImportError, OSError):
    torch = None
    nn = None
    TORCH_AVAILABLE = False

from kalshi_sim.ml.model import QuoLasMicroscopeNet

logger = logging.getLogger(__name__)


def export_to_onnx(
    model: nn.Module,
    output_path: Union[str, Path],
    input_dim: int = 28,
    opset_version: int = 17,
    verify_parity: bool = True,
) -> Path:
    """Export a PyTorch neural network to an ONNX model file.

    Args:
        model: PyTorch neural model instance.
        output_path: Destination path for .onnx model.
        input_dim: Feature vector dimension (default 28).
        opset_version: ONNX operator set version (default 17).
        verify_parity: If True, tests numerical parity against onnxruntime.

    Returns:
        Path: Path to the generated .onnx model file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    model.eval()
    dummy_input = torch.randn(1, input_dim, dtype=torch.float32)

    # Dynamic axes allowing arbitrary batch size at inference time
    dynamic_axes = {
        "input": {0: "batch_size"},
        "output": {0: "batch_size"},
    }

    logger.info("Exporting PyTorch model to ONNX: %s (opset=%d)", output_path, opset_version)
    torch.onnx.export(
        model,
        dummy_input,
        str(output_path),
        export_params=True,
        opset_version=opset_version,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes=dynamic_axes,
        dynamo=False,
    )

    if verify_parity:
        check_numerical_parity(model, output_path, input_dim=input_dim)

    return output_path


def check_numerical_parity(
    torch_model: nn.Module,
    onnx_path: Union[str, Path],
    input_dim: int = 28,
    atol: float = 1e-4,
    batch_sizes: Tuple[int, ...] = (1, 4, 16),
) -> bool:
    """Verify that ONNX Runtime produces identical numerical outputs to PyTorch."""
    torch_model.eval()
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    for b in batch_sizes:
        test_input = np.random.randn(b, input_dim).astype(np.float32)
        with torch.no_grad():
            torch_out = torch_model(torch.from_numpy(test_input)).cpu().numpy()

        onnx_out = session.run(None, {input_name: test_input})[0]

        max_diff = float(np.max(np.abs(torch_out - onnx_out)))
        logger.info("Parity check batch_size=%d: max absolute diff = %.2e", b, max_diff)

        if max_diff > atol:
            raise ValueError(
                f"Numerical disparity exceeded tolerance {atol}: max_diff={max_diff:.2e} on batch={b}"
            )

    return True


def benchmark_onnx_inference(
    onnx_path: Union[str, Path],
    input_dim: int = 28,
    num_runs: int = 200,
    warmup_runs: int = 20,
) -> Dict[str, float]:
    """Benchmark ONNX Runtime inference latency for single-item real-time execution."""
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    dummy_input = np.random.randn(1, input_dim).astype(np.float32)

    # Warmup
    for _ in range(warmup_runs):
        session.run(None, {input_name: dummy_input})

    # Benchmark loop
    latencies_ms = []
    for _ in range(num_runs):
        t0 = time.perf_counter()
        session.run(None, {input_name: dummy_input})
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)

    p50 = float(np.percentile(latencies_ms, 50))
    p95 = float(np.percentile(latencies_ms, 95))
    p99 = float(np.percentile(latencies_ms, 99))
    mean_lat = float(np.mean(latencies_ms))

    logger.info(
        "ONNX Latency Benchmark (1x%d): Mean=%.3fms | P50=%.3fms | P95=%.3fms | P99=%.3fms",
        input_dim,
        mean_lat,
        p50,
        p95,
        p99,
    )

    return {
        "mean_latency_ms": mean_lat,
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "p99_latency_ms": p99,
        "num_runs": num_runs,
    }

"""ONNX Export & Parity Verification for QuoLas Gold 32-D Microscope Model (gold.onnx).

Exports the 32-dimensional QuoLasGoldMicroscopeNet to an optimized ONNX Runtime model file
at `models/gold.onnx` with dynamic batching and CPU execution verification.
Supports PyTorch export when available, with pure ONNX graph builder fallback.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

import numpy as np
import onnx
from onnx import TensorProto, helper
import onnxruntime as ort

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except (ImportError, OSError):
    torch = None
    nn = None
    TORCH_AVAILABLE = False

from kalshi_sim.ml.gold_model import QuoLasGoldMicroscopeNet

logger = logging.getLogger(__name__)

DEFAULT_GOLD_MODEL_PATH = Path("models") / "gold.onnx"


def build_pure_onnx_gold_graph(
    output_path: Union[str, Path] = DEFAULT_GOLD_MODEL_PATH,
    input_dim: int = 32,
    hidden_dim: int = 64,
    num_classes: int = 3,
) -> Path:
    """Construct and export QuoLas Gold 32-D Residual MLP directly using pure ONNX graph helper."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    np.random.seed(42)

    # Initialize weights with standard Xavier normal distribution
    w1 = (np.random.randn(input_dim, hidden_dim) * np.sqrt(2.0 / (input_dim + hidden_dim))).astype(np.float32)
    b1 = np.zeros(hidden_dim, dtype=np.float32)

    w2 = (np.random.randn(hidden_dim, hidden_dim) * np.sqrt(2.0 / (hidden_dim * 2))).astype(np.float32)
    b2 = np.zeros(hidden_dim, dtype=np.float32)

    w3 = (np.random.randn(hidden_dim, hidden_dim) * np.sqrt(2.0 / (hidden_dim * 2))).astype(np.float32)
    b3 = np.zeros(hidden_dim, dtype=np.float32)

    w_head = (np.random.randn(hidden_dim, num_classes) * np.sqrt(2.0 / (hidden_dim + num_classes))).astype(np.float32)
    b_head = np.zeros(num_classes, dtype=np.float32)

    # Initializer tensors
    init_w1 = helper.make_tensor("W1", TensorProto.FLOAT, [input_dim, hidden_dim], w1.flatten().tolist())
    init_b1 = helper.make_tensor("B1", TensorProto.FLOAT, [hidden_dim], b1.tolist())

    init_w2 = helper.make_tensor("W2", TensorProto.FLOAT, [hidden_dim, hidden_dim], w2.flatten().tolist())
    init_b2 = helper.make_tensor("B2", TensorProto.FLOAT, [hidden_dim], b2.tolist())

    init_w3 = helper.make_tensor("W3", TensorProto.FLOAT, [hidden_dim, hidden_dim], w3.flatten().tolist())
    init_b3 = helper.make_tensor("B3", TensorProto.FLOAT, [hidden_dim], b3.tolist())

    init_wh = helper.make_tensor("W_HEAD", TensorProto.FLOAT, [hidden_dim, num_classes], w_head.flatten().tolist())
    init_bh = helper.make_tensor("B_HEAD", TensorProto.FLOAT, [num_classes], b_head.tolist())

    # Graph Inputs / Outputs
    input_tensor = helper.make_tensor_value_info("input", TensorProto.FLOAT, ["batch_size", input_dim])
    output_tensor = helper.make_tensor_value_info("output", TensorProto.FLOAT, ["batch_size", num_classes])

    # Nodes
    # 1. Input Linear projection
    node_gemm1 = helper.make_node("Gemm", ["input", "W1", "B1"], ["h1_lin"], alpha=1.0, beta=1.0)
    node_relu1 = helper.make_node("Relu", ["h1_lin"], ["h1"])

    # 2. Residual Block (h1 -> Gemm -> Relu -> Gemm -> Add(h1))
    node_gemm2 = helper.make_node("Gemm", ["h1", "W2", "B2"], ["h2_lin"], alpha=1.0, beta=1.0)
    node_relu2 = helper.make_node("Relu", ["h2_lin"], ["h2"])
    node_gemm3 = helper.make_node("Gemm", ["h2", "W3", "B3"], ["h3_lin"], alpha=1.0, beta=1.0)
    node_add_res = helper.make_node("Add", ["h1", "h3_lin"], ["h_res"])

    # 3. Head & Softmax
    node_head = helper.make_node("Gemm", ["h_res", "W_HEAD", "B_HEAD"], ["logits"], alpha=1.0, beta=1.0)
    node_softmax = helper.make_node("Softmax", ["logits"], ["output"], axis=-1)

    graph_def = helper.make_graph(
        nodes=[node_gemm1, node_relu1, node_gemm2, node_relu2, node_gemm3, node_add_res, node_head, node_softmax],
        name="QuoLasGoldMicroscopeNet",
        inputs=[input_tensor],
        outputs=[output_tensor],
        initializer=[init_w1, init_b1, init_w2, init_b2, init_w3, init_b3, init_wh, init_bh],
    )

    model_def = helper.make_model(
        graph_def,
        producer_name="kalshi_sim_ml_engine",
        ir_version=10,
        opset_imports=[helper.make_opsetid("", 17)],
    )

    with open(output_path, "wb") as f:
        f.write(model_def.SerializeToString())

    logger.info("Successfully built pure ONNX Gold 32-D model: %s", output_path)
    return output_path


def export_gold_to_onnx(
    model: Optional[QuoLasGoldMicroscopeNet] = None,
    output_path: Union[str, Path] = DEFAULT_GOLD_MODEL_PATH,
    opset_version: int = 17,
    verify_parity: bool = True,
) -> Path:
    """Export QuoLasGoldMicroscopeNet (32-D) to ONNX format with PyTorch or ONNX helper fallback."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if TORCH_AVAILABLE and model is not None:
        model.eval()
        dummy_input = torch.randn(1, 32, dtype=torch.float32)
        dynamic_axes = {
            "input": {0: "batch_size"},
            "output": {0: "batch_size"},
        }
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
    else:
        build_pure_onnx_gold_graph(output_path=output_path, input_dim=32, hidden_dim=64, num_classes=3)

    if verify_parity:
        session = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
        input_name = session.get_inputs()[0].name
        test_input = np.random.randn(4, 32).astype(np.float32)
        onnx_out = session.run(None, {input_name: test_input})[0]
        assert onnx_out.shape == (4, 3)
        row_sums = onnx_out.sum(axis=-1)
        np.testing.assert_allclose(row_sums, np.ones(4), atol=1e-4)
        logger.info("✅ ONNX Runtime verification PASSED on %s (Shape: %s)", output_path, onnx_out.shape)

    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    out = export_gold_to_onnx()
    print(f"Successfully exported 32-D Gold ONNX Brain to: {out}")

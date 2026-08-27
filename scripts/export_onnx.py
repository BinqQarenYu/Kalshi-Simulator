"""CLI script to export PyTorch checkpoint to ONNX format and benchmark latency.

Usage:
    python scripts/export_onnx.py --checkpoint models/best_model.pt --output models/quolas_microscope_v2.onnx --benchmark
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import torch

from kalshi_sim.ml.export_onnx import benchmark_onnx_inference, export_to_onnx
from kalshi_sim.ml.model import QuoLasMicroscopeNet

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("export_onnx")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export PyTorch model to optimized ONNX format.")
    parser.add_argument("--checkpoint", type=str, default="models/best_model.pt", help="Path to PyTorch .pt checkpoint")
    parser.add_argument("--output", type=str, default="models/quolas_microscope_v2.onnx", help="Output .onnx file path")
    parser.add_argument("--opset", type=int, default=17, help="ONNX opset version")
    parser.add_argument("--benchmark", action="store_true", help="Run latency benchmark after export")
    args = parser.parse_args()

    ckpt_path = Path(args.checkpoint)
    if not ckpt_path.exists():
        logger.warning("Checkpoint %s not found. Exporting default initialized QuoLas model.", ckpt_path)
        model = QuoLasMicroscopeNet(input_dim=28, hidden_dim=64, num_classes=3)
    else:
        logger.info("Loading PyTorch checkpoint from %s", ckpt_path)
        ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=True)
        input_dim = ckpt.get("input_dim", 28)
        num_classes = ckpt.get("num_classes", 3)
        model = QuoLasMicroscopeNet(input_dim=input_dim, hidden_dim=64, num_classes=num_classes)
        model.load_state_dict(ckpt["model_state_dict"])

    onnx_file = export_to_onnx(
        model=model,
        output_path=args.output,
        input_dim=model.input_dim,
        opset_version=args.opset,
        verify_parity=True,
    )
    logger.info("Successfully exported model to ONNX: %s", onnx_file)

    if args.benchmark:
        benchmark_onnx_inference(onnx_file, input_dim=model.input_dim)


if __name__ == "__main__":
    main()

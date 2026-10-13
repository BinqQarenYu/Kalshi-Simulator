"""Robust force-retraining and ONNX export for quolas.onnx.

Extracts data from available tick/stream files or falls back to anchor dataset,
trains QuoLasMicroscopeNet, saves best_model.pt, and atomically exports verified quolas.onnx.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import sys
import time

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import numpy as np
import torch

from kalshi_sim.ml.continuous_trainer import ContinuousModelTrainer, export_and_verify_onnx
from kalshi_sim.ml.dataset_builder import DatasetBuilder
from kalshi_sim.ml.model import QuoLasMicroscopeNet
from kalshi_sim.ml.train_model import ModelTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("force_retrain_quolas")


def main() -> None:
    logger.info("🧠 Starting robust retraining and freshness restoration for quolas.onnx...")
    data_dir = Path("data")
    models_dir = Path("models")
    models_dir.mkdir(parents=True, exist_ok=True)

    builder = DatasetBuilder(
        horizon_steps=15,
        horizon_seconds=20.0,
        price_diff_threshold=0.03,
        sample_stride=5,
        max_frames_per_file=10000,
        max_wait_ratio=0.50,
    )

    # 1. Harvest recent tick files if present
    X_recent = np.empty((0, 28), dtype=np.float32)
    y_recent = np.empty((0,), dtype=np.int64)

    for pattern in ("stream_*.jsonl", "ticks_*.jsonl"):
        files = list(data_dir.glob(pattern))
        if files:
            logger.info("Found %d files matching '%s'. Extracting...", len(files), pattern)
            X_part, y_part = builder.build_from_directory(data_dir, file_pattern=pattern, max_files=10)
            if len(X_part) > 0:
                X_recent = X_part
                y_recent = y_part
                logger.info("Extracted %d samples from %s files.", len(X_recent), pattern)
                break

    # 2. Merge with anchor dataset
    anchor_file = models_dir / "dataset_v1.npz"
    if anchor_file.exists():
        logger.info("Loading baseline anchor dataset from %s...", anchor_file)
        anchor_data = np.load(anchor_file)
        X_anchor = anchor_data["X_train"]
        y_anchor = anchor_data["y_train"]
        X_anchor_strat, y_anchor_strat = ContinuousModelTrainer.sample_stratified_anchor(
            X_anchor, y_anchor, max_per_class=500, num_classes=3
        )
        if len(X_recent) > 0:
            X_all = np.vstack([X_anchor_strat, X_recent])
            y_all = np.concatenate([y_anchor_strat, y_recent])
        else:
            X_all = X_anchor_strat
            y_all = y_anchor_strat
    else:
        X_all = X_recent
        y_all = y_recent

    if len(X_all) < 32:
        logger.error("Insufficient samples to train (%d < 32). Cannot retrain.", len(X_all))
        sys.exit(1)

    logger.info("Total dataset assembled: %d samples across classes: %s", len(X_all), np.bincount(y_all))

    # 3. Train / Validation split
    indices = np.random.permutation(len(X_all))
    split = int(len(X_all) * 0.8)
    train_idx, val_idx = indices[:split], indices[split:]
    X_train, y_train = X_all[train_idx], y_all[train_idx]
    X_val, y_val = X_all[val_idx], y_all[val_idx]

    # 4. Instantiate model & restore weights if available
    model = QuoLasMicroscopeNet(input_dim=28, hidden_dim=64, num_classes=3)
    ckpt_path = models_dir / "best_model.pt"
    if ckpt_path.exists():
        try:
            ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=True)
            if "model_state_dict" in ckpt:
                model.load_state_dict(ckpt["model_state_dict"])
                logger.info("Restored baseline weights from %s", ckpt_path)
        except Exception as e:
            logger.warning("Failed loading checkpoint: %s", e)

    trainer = ModelTrainer(model=model, learning_rate=2e-4, weight_decay=1e-4, device="cpu")
    logger.info("Fine-tuning model for 4 epochs...")
    history = trainer.fit(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        epochs=4,
        batch_size=32,
        checkpoint_dir=models_dir,
    )

    # 5. Export fresh ONNX model
    out_onnx = models_dir / "quolas.onnx"
    logger.info("Exporting verified ONNX model to %s...", out_onnx)
    success = export_and_verify_onnx(model, out_onnx)
    if not success:
        logger.error("Failed exporting ONNX model!")
        sys.exit(1)

    # 6. Update feature normalization statistics
    mean = np.mean(X_all, axis=0).astype(float).tolist()
    std = np.std(X_all, axis=0).astype(float).tolist()
    std = [float(s) if float(s) > 1e-6 else 1.0 for s in std]
    stats_file = models_dir / "feature_stats.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump({"mean": mean, "std": std}, f, indent=4)
    logger.info("Saved feature statistics to %s", stats_file)

    # 7. Stamp file heartbeats with current time
    now_ts = time.time()
    import os
    os.utime(out_onnx, (now_ts, now_ts))
    os.utime(stats_file, (now_ts, now_ts))
    logger.info("✅ Model quolas.onnx successfully retrained and timestamp updated (FRESH)!")


if __name__ == "__main__":
    main()

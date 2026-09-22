"""CLI script to build and export machine learning training datasets from tick logs.

Usage:
    python scripts/build_training_dataset.py --data-dir data --output models/dataset_v1.npz --horizon 15 --threshold 0.01
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np

from app_1_machine_engine.ml.dataset_builder import DatasetBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_dataset")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build training datasets from Kalshi tick logs.")
    parser.add_argument("--data-dir", type=str, default="data", help="Directory containing .jsonl tick logs")
    parser.add_argument("--output", type=str, default="models/dataset_v1.npz", help="Output .npz file path")
    parser.add_argument("--horizon", type=int, default=15, help="Forward return horizon steps")
    parser.add_argument("--threshold", type=float, default=0.01, help="Price movement threshold in dollars for UP/DOWN label")
    parser.add_argument("--val-split", type=float, default=0.2, help="Validation set split ratio (0.0 - 1.0)")
    parser.add_argument("--sample-stride", type=int, default=10, help="Sampling stride across ticks to reduce autocorrelation")
    parser.add_argument("--max-frames", type=int, default=1000, help="Maximum frames to extract per tick file")
    parser.add_argument("--file-pattern", type=str, default="ticks_*.jsonl", help="Glob pattern for tick logs")
    parser.add_argument("--max-files", type=int, default=30, help="Maximum number of recent tick files to parse")
    parser.add_argument("--save-stats", type=str, default="models/feature_stats.json", help="Path to save normalization stats JSON")
    args = parser.parse_args()

    builder = DatasetBuilder(
        horizon_steps=args.horizon,
        price_diff_threshold=args.threshold,
        sample_stride=args.sample_stride,
        max_frames_per_file=args.max_frames,
    )

    logger.info("Parsing tick logs from directory: %s (pattern=%s, max_files=%d, stride=%d)",
                args.data_dir, args.file_pattern, args.max_files, args.sample_stride)
    X, y = builder.build_from_directory(args.data_dir, file_pattern=args.file_pattern, max_files=args.max_files)

    logger.info("Extracted %d total labeled feature rows. Shape: %s", len(X), X.shape)
    if len(X) == 0:
        logger.warning("No samples extracted. Please ensure tick logs exist in %s", args.data_dir)
        return

    unique, counts = np.unique(y, return_counts=True)
    class_dist = dict(zip(unique, counts))
    logger.info("Class distribution (0=UP, 1=DOWN, 2=WAIT): %s", class_dist)

    builder.save_dataset_npz(X, y, args.output, val_split=args.val_split)
    logger.info("Successfully compiled and saved training dataset to: %s", args.output)

    if args.save_stats:
        import json
        mean = np.mean(X, axis=0).astype(float).tolist()
        std = np.std(X, axis=0).astype(float).tolist()
        # Avoid zero or tiny std
        std = [float(s) if float(s) > 1e-6 else 1.0 for s in std]
        stats_path = Path(args.save_stats)
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        with open(stats_path, "w") as f:
            json.dump({"mean": mean, "std": std}, f, indent=4)
        logger.info("Saved feature normalization statistics to: %s", stats_path)


if __name__ == "__main__":
    main()

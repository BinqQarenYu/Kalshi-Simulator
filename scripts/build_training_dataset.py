"""CLI script to build and export machine learning training datasets from tick logs.

Usage:
    python scripts/build_training_dataset.py --data-dir data --output models/dataset_v1.npz --horizon 15 --threshold 0.01
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np

from kalshi_sim.ml.dataset_builder import DatasetBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_dataset")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build training datasets from Kalshi tick logs.")
    parser.add_argument("--data-dir", type=str, default="data", help="Directory containing .jsonl tick logs")
    parser.add_argument("--output", type=str, default="models/dataset_v1.npz", help="Output .npz file path")
    parser.add_argument("--horizon", type=int, default=15, help="Forward return horizon steps")
    parser.add_argument("--threshold", type=float, default=0.01, help="Price movement threshold in dollars for UP/DOWN label")
    parser.add_argument("--val-split", type=float, default=0.2, help="Validation set split ratio (0.0 - 1.0)")
    args = parser.parse_args()

    builder = DatasetBuilder(
        horizon_steps=args.horizon,
        price_diff_threshold=args.threshold,
    )

    logger.info("Parsing tick logs from directory: %s", args.data_dir)
    X, y = builder.build_from_directory(args.data_dir)

    logger.info("Extracted %d total labeled feature rows. Shape: %s", len(X), X.shape)
    if len(X) == 0:
        logger.warning("No samples extracted. Please ensure tick logs exist in %s", args.data_dir)
        return

    unique, counts = np.unique(y, return_counts=True)
    class_dist = dict(zip(unique, counts))
    logger.info("Class distribution (0=UP, 1=DOWN, 2=WAIT): %s", class_dist)

    builder.save_dataset_npz(X, y, args.output, val_split=args.val_split)
    logger.info("Successfully compiled and saved training dataset to: %s", args.output)


if __name__ == "__main__":
    main()

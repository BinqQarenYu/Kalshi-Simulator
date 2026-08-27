"""CLI Script to train QuoLas Microscope model on compiled tick datasets.

Usage:
    python scripts/train_model.py --dataset models/dataset_v1.npz --epochs 20 --batch-size 64 --lr 0.001 --output-dir models
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np

from kalshi_sim.ml.model import QuoLasMicroscopeNet
from kalshi_sim.ml.train_model import ModelTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_model")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train QuoLas Microscope neural network on tick dataset.")
    parser.add_argument("--dataset", type=str, default="models/dataset_v1.npz", help="Path to compiled .npz dataset")
    parser.add_argument("--epochs", type=int, default=20, help="Maximum training epochs")
    parser.add_argument("--batch-size", type=int, default=64, help="Mini-batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Initial learning rate")
    parser.add_argument("--weight-decay", type=float, default=1e-4, help="AdamW weight decay")
    parser.add_argument("--patience", type=int, default=5, help="Early stopping patience")
    parser.add_argument("--output-dir", type=str, default="models", help="Directory to save model checkpoints")
    args = parser.parse_args()

    data_path = Path(args.dataset)
    if not data_path.exists():
        logger.error("Dataset not found at %s. Please run build_training_dataset.py first.", data_path)
        return

    data = np.load(data_path)
    X_train = data["X_train"]
    y_train = data["y_train"]
    X_val = data["X_val"]
    y_val = data["y_val"]

    logger.info("Loaded dataset: %d train samples, %d val samples, %d features", len(X_train), len(X_val), X_train.shape[1])

    model = QuoLasMicroscopeNet(
        input_dim=int(data.get("feature_dim", 28)),
        hidden_dim=64,
        num_classes=int(data.get("num_classes", 3)),
    )

    trainer = ModelTrainer(
        model=model,
        learning_rate=args.lr,
        weight_decay=args.weight_decay,
    )

    history = trainer.fit(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        epochs=args.epochs,
        batch_size=args.batch_size,
        patience=args.patience,
        checkpoint_dir=args.output_dir,
    )

    if history:
        best_epoch = min(history, key=lambda m: m.val_loss)
        logger.info(
            "Training completed. Best Epoch %02d: Val Loss=%.4f, Val Acc=%.2f%%, Val Macro F1=%.3f",
            best_epoch.epoch,
            best_epoch.val_loss,
            best_epoch.val_accuracy * 100,
            best_epoch.val_f1_macro,
        )


if __name__ == "__main__":
    main()

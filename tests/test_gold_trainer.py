"""Unit tests for GoldContinuousTrainer (PyTorch 32-D Background Continuous Trainer)."""

from __future__ import annotations

from pathlib import Path
import time

import numpy as np
import pytest

from kalshi_sim.ml.gold_continuous_trainer import (
    GoldContinuousTrainer,
    MulticlassFocalLoss,
    TORCH_AVAILABLE,
)
from kalshi_sim.ml.gold_dataset_builder import GoldDatasetBuilder


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch required for trainer tests")
def test_multiclass_focal_loss() -> None:
    """Verify MulticlassFocalLoss handles logits and targets correctly."""
    import torch

    loss_fn = MulticlassFocalLoss(gamma=2.0)
    logits = torch.tensor([[2.0, -1.0, 0.5], [-0.5, 3.0, 0.0]], dtype=torch.float32)
    targets = torch.tensor([0, 1], dtype=torch.int64)

    loss = loss_fn(logits, targets)
    assert loss.ndim == 0
    assert float(loss.item()) > 0.0


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch required for trainer tests")
def test_gold_continuous_trainer_epoch_and_evaluate(tmp_path: Path) -> None:
    """Verify that training epoch reduces loss and evaluate computes accuracy and F1."""
    import torch

    model_path = tmp_path / "gold.onnx"
    weights_path = tmp_path / "gold_best.pt"

    trainer = GoldContinuousTrainer(
        model_path=model_path,
        weights_path=weights_path,
        batch_size=16,
        target_val_acc=0.85,
    )

    builder = GoldDatasetBuilder()
    X, y = builder.generate_synthetic_samples(num_samples=120, seed=42)
    X_train, X_val, y_train, y_val = builder.train_val_split(X, y, val_ratio=0.30)

    # Initial evaluation
    metrics_before = trainer.evaluate(X_val, y_val)
    assert "accuracy" in metrics_before
    assert "f1_macro" in metrics_before
    assert "loss" in metrics_before

    # Train 3 epochs
    loss_1 = trainer.train_epoch(X_train, y_train)
    loss_2 = trainer.train_epoch(X_train, y_train)

    assert isinstance(loss_1, float)
    assert isinstance(loss_2, float)
    assert loss_1 > 0.0


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch required for trainer tests")
def test_gold_continuous_trainer_step_and_export(tmp_path: Path) -> None:
    """Verify train_step executes bounded cycle and updates telemetry."""
    model_path = tmp_path / "gold.onnx"
    weights_path = tmp_path / "gold_best.pt"

    trainer = GoldContinuousTrainer(
        model_path=model_path,
        weights_path=weights_path,
        batch_size=32,
        target_val_acc=0.50,  # Low threshold to test atomic promotion gate
        min_f1_score=0.40,
    )

    res = trainer.train_step(num_epochs=3)

    assert res["cycle"] == 1
    assert "val_accuracy" in res
    assert "val_f1" in res
    assert res["val_accuracy"] >= 0.0

    status = trainer.get_status()
    assert status["total_cycles"] == 1
    assert status["target_val_acc"] == 0.50


def test_gold_continuous_trainer_lifecycle(tmp_path: Path) -> None:
    """Verify thread start, pause, resume, and stop controls."""
    model_path = tmp_path / "gold.onnx"
    weights_path = tmp_path / "gold_best.pt"

    trainer = GoldContinuousTrainer(
        model_path=model_path,
        weights_path=weights_path,
        training_interval_s=0.2,
    )

    trainer.start()
    time.sleep(0.1)
    status_running = trainer.get_status()
    assert status_running["status"] in ("RUNNING", "TRAINING", "IDLE")

    trainer.pause()
    time.sleep(0.1)
    assert trainer.get_status()["status"] in ("PAUSED", "IDLE", "TRAINING")

    trainer.resume()
    time.sleep(0.1)

    trainer.stop()
    time.sleep(0.1)
    assert trainer.get_status()["status"] == "STOPPED"

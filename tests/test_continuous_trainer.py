"""Unit and integration tests for ContinuousModelTrainer and live trading resource protection."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import torch

from kalshi_sim.ml.continuous_trainer import (
    ContinuousModelTrainer,
    apply_low_priority_to_thread_or_process,
    export_and_verify_onnx,
)
from kalshi_sim.ml.model import QuoLasMicroscopeNet


def test_low_priority_execution() -> None:
    """Verify applying low OS priority class runs without error."""
    # Should not raise any exception on Windows or Linux
    apply_low_priority_to_thread_or_process()


def test_continuous_trainer_initialization(tmp_path: Path) -> None:
    """Verify ContinuousModelTrainer initialization and default telemetry."""
    data_dir = tmp_path / "data"
    models_dir = tmp_path / "models"
    data_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    trainer = ContinuousModelTrainer(
        data_dir=data_dir,
        models_dir=models_dir,
        training_interval_seconds=60.0,
        batch_size=16,
        enabled=True,
    )

    status = trainer.get_status()
    assert status["status"] == "IDLE"
    assert status["is_enabled"] is True
    assert status["is_running"] is False
    assert status["cpu_thread_cap"] == 1
    assert "cycles_completed" in status
    assert "models_promoted" in status


def test_export_and_verify_onnx(tmp_path: Path) -> None:
    """Verify ONNX export, shape verification, and atomic file replacement."""
    model = QuoLasMicroscopeNet(input_dim=28, hidden_dim=32, num_classes=3)
    target_onnx = tmp_path / "test_model.onnx"

    success = export_and_verify_onnx(model, target_onnx, device="cpu")
    assert success is True
    assert target_onnx.exists()
    assert target_onnx.stat().st_size > 0

    # Second export: should back up previous and atomically replace
    success_2 = export_and_verify_onnx(model, target_onnx, device="cpu")
    assert success_2 is True
    backup_onnx = tmp_path / "test_model_backup.onnx"
    assert backup_onnx.exists()


def test_training_cycle_execution(tmp_path: Path) -> None:
    """Test full training cycle execution with synthetic dataset."""
    data_dir = tmp_path / "data"
    models_dir = tmp_path / "models"
    data_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy anchor dataset
    N_samples = 120
    X_train = np.random.randn(N_samples, 28).astype(np.float32)
    y_train = np.random.randint(0, 3, size=(N_samples,)).astype(np.int64)
    np.savez(
        models_dir / "dataset_v1.npz",
        X_train=X_train,
        y_train=y_train,
    )

    trainer = ContinuousModelTrainer(
        data_dir=data_dir,
        models_dir=models_dir,
        training_interval_seconds=10.0,
        batch_size=16,
        epochs_per_cycle=2,
        min_samples_to_train=30,
        enabled=True,
    )

    # Execute one training cycle synchronously
    trainer._execute_training_cycle()

    status = trainer.get_status()
    assert trainer.cycles_completed == 1
    assert trainer.last_val_loss is not None
    assert trainer.last_val_acc is not None
    assert trainer.samples_trained >= 30
    assert trainer.models_promoted >= 1
    assert (models_dir / "nano_microscope_overhauled.onnx").exists()
    assert (models_dir / "feature_stats.json").exists()


def test_pause_resume_lifecycle(tmp_path: Path) -> None:
    """Test start, pause, resume, and stop controls."""
    data_dir = tmp_path / "data"
    models_dir = tmp_path / "models"
    data_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    trainer = ContinuousModelTrainer(
        data_dir=data_dir,
        models_dir=models_dir,
        training_interval_seconds=1.0,
        enabled=True,
    )

    trainer.start()
    assert trainer._running is True

    trainer.pause()
    assert trainer._paused is True
    assert trainer.get_status()["status"] == "PAUSED"

    trainer.resume()
    assert trainer._paused is False
    assert trainer.get_status()["status"] == "IDLE"

    trainer.stop()
    assert trainer._running is False
    assert trainer.get_status()["status"] == "STOPPED"

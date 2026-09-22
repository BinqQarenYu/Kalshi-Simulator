"""Unit and integration tests for PyTorch neural network model and training loop."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from app_1_machine_engine.ml.model import QuoLasMicroscopeNet
from app_1_machine_engine.ml.train_model import FocalLoss, ModelTrainer, OrderflowDataset


def test_quolas_microscope_forward_pass() -> None:
    """Test model forward pass output shape and probability constraints."""
    model = QuoLasMicroscopeNet(input_dim=28, hidden_dim=32, num_classes=3, num_blocks=1)
    x = torch.randn(8, 28)

    # Probabilities output
    probs = model(x)
    assert probs.shape == (8, 3)
    assert torch.all(probs >= 0.0)
    assert torch.all(probs <= 1.0)
    assert torch.allclose(probs.sum(dim=-1), torch.ones(8), atol=1e-5)

    # Logits output
    logits = model(x, return_logits=True)
    assert logits.shape == (8, 3)


def test_focal_loss_computation() -> None:
    """Test FocalLoss computation and class weight application."""
    weights = torch.tensor([1.0, 2.0, 0.5])
    criterion = FocalLoss(alpha=weights, gamma=2.0)

    logits = torch.randn(4, 3)
    targets = torch.tensor([0, 1, 2, 1])

    loss = criterion(logits, targets)
    assert loss.dim() == 0  # Scalar
    assert loss.item() > 0.0
    assert torch.isfinite(loss)


def test_model_trainer_fit_and_checkpoint(tmp_path: Path) -> None:
    """Test full training loop execution, loss convergence, and checkpoint saving."""
    np.random.seed(42)
    torch.manual_seed(42)

    # Generate synthetic training & validation data
    N_train, N_val = 100, 30
    X_train = np.random.randn(N_train, 28).astype(np.float32)
    y_train = np.random.randint(0, 3, size=(N_train,)).astype(np.int64)

    X_val = np.random.randn(N_val, 28).astype(np.float32)
    y_val = np.random.randint(0, 3, size=(N_val,)).astype(np.int64)

    model = QuoLasMicroscopeNet(input_dim=28, hidden_dim=32, num_classes=3, num_blocks=1)
    trainer = ModelTrainer(model=model, learning_rate=0.01, device="cpu")

    history = trainer.fit(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        epochs=3,
        batch_size=16,
        patience=2,
        checkpoint_dir=tmp_path,
    )

    assert len(history) == 3
    assert history[0].train_loss > 0.0

    checkpoint_file = tmp_path / "best_model.pt"
    assert checkpoint_file.exists()

    ckpt = torch.load(checkpoint_file, map_location="cpu", weights_only=True)
    assert "model_state_dict" in ckpt
    assert "val_loss" in ckpt
    assert "val_accuracy" in ckpt
    assert ckpt["input_dim"] == 28
    assert ckpt["num_classes"] == 3


def test_compute_class_weights_inverse_frequency() -> None:
    """Verify calculation of inverse-frequency class weights and normalization."""
    trainer = ModelTrainer(device="cpu")

    # 1. Balanced distribution: 100 samples each
    y_balanced = np.array([0] * 100 + [1] * 100 + [2] * 100)
    w_balanced = trainer.compute_class_weights(y_balanced, num_classes=3)
    assert torch.allclose(w_balanced, torch.tensor([1/3, 1/3, 1/3]), atol=1e-4)
    assert torch.isclose(torch.sum(w_balanced), torch.tensor(1.0))

    # 2. Imbalanced distribution: UP=10, DOWN=20, WAIT=70
    y_imbalanced = np.array([0] * 10 + [1] * 20 + [2] * 70)
    w_imbalanced = trainer.compute_class_weights(y_imbalanced, num_classes=3)
    # Rarest class (UP, 0) must have highest weight, most common (WAIT, 2) lowest
    assert w_imbalanced[0] > w_imbalanced[1] > w_imbalanced[2]
    assert torch.isclose(torch.sum(w_imbalanced), torch.tensor(1.0))
    assert torch.all(torch.isfinite(w_imbalanced))

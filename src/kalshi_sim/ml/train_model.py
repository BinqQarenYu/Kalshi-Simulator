"""PyTorch Neural Training Loop & Optimization Engine for QuoLas Microscope.

Provides data loaders, Focal/Cross-Entropy loss with class weighting, AdamW optimizer,
Cosine Annealing LR scheduling, early stopping, and checkpoint management.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, Dataset
    TORCH_AVAILABLE = True
    _BaseDataset = Dataset
    _BaseModule = nn.Module
except (ImportError, OSError):
    torch = None
    nn = None
    F = None
    DataLoader = None
    Dataset = object
    TORCH_AVAILABLE = False
    _BaseDataset = object
    _BaseModule = object

from kalshi_sim.ml.model import QuoLasMicroscopeNet

logger = logging.getLogger(__name__)


class OrderflowDataset(_BaseDataset):
    """PyTorch Dataset wrapping extracted orderflow features and labels."""

    def __init__(self, X: np.ndarray, y: np.ndarray) -> None:
        if not TORCH_AVAILABLE:
            self.X = X
            self.y = y
            return
        self.X = torch.from_numpy(X.astype(np.float32))
        self.y = torch.from_numpy(y.astype(np.int64))

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, idx: int) -> Tuple[Any, Any]:
        return self.X[idx], self.y[idx]


class FocalLoss(_BaseModule):
    """Focal Loss with class weights and focusing parameter gamma."""

    def __init__(self, alpha: Optional[Any] = None, gamma: float = 2.0) -> None:
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, logits: Any, targets: Any) -> Any:
        ce_loss = F.cross_entropy(logits, targets, reduction="none")
        pt = torch.exp(-ce_loss)
        focal_loss = ((1.0 - pt) ** self.gamma) * ce_loss

        if self.alpha is not None:
            alpha_t = self.alpha[targets]
            focal_loss = alpha_t * focal_loss

        return focal_loss.mean()


@dataclass
class TrainingMetrics:
    """Evaluation metrics for a single epoch."""
    epoch: int
    train_loss: float
    val_loss: float
    val_accuracy: float
    val_f1_macro: float


class ModelTrainer:
    """Orchestrates neural training loop, validation, and model serialization."""

    def __init__(
        self,
        model: Optional[QuoLasMicroscopeNet] = None,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-4,
        device: Optional[str] = None,
    ) -> None:
        if not TORCH_AVAILABLE:
            self.device = None
            self.model = None
            self.lr = learning_rate
            self.weight_decay = weight_decay
            self.optimizer = None
            return
        self.device = torch.device(device if device else ("cuda" if torch.cuda.is_available() else "cpu"))
        self.model = model or QuoLasMicroscopeNet()
        self.model.to(self.device)

        self.lr = learning_rate
        self.weight_decay = weight_decay
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.lr,
            weight_decay=self.weight_decay,
        )

    def compute_class_weights(self, y_train: np.ndarray, num_classes: int = 3) -> torch.Tensor:
        """Calculate inverse-frequency class weights for the training set:
        weights = total_samples / (num_classes * class_counts), normalized across classes.
        """
        total_samples = len(y_train)
        if total_samples == 0:
            return torch.ones(num_classes, dtype=torch.float32, device=self.device) / float(num_classes)

        class_counts = np.array([float(np.sum(y_train == c)) for c in range(num_classes)], dtype=np.float32)
        weights = np.zeros(num_classes, dtype=np.float32)
        valid = class_counts > 0
        if np.any(valid):
            weights[valid] = total_samples / (float(num_classes) * class_counts[valid])
            sum_w = float(np.sum(weights))
            if sum_w > 0:
                weights = weights / sum_w
        else:
            weights = np.ones(num_classes, dtype=np.float32) / float(num_classes)

        return torch.as_tensor(weights, dtype=torch.float32, device=self.device)

    def train_epoch(
        self, dataloader: DataLoader, criterion: nn.Module
    ) -> float:
        """Train model for one epoch."""
        self.model.train()
        total_loss = 0.0
        total_batches = 0

        for X_batch, y_batch in dataloader:
            X_batch = X_batch.to(self.device)
            y_batch = y_batch.to(self.device)

            self.optimizer.zero_grad()
            logits = self.model(X_batch, return_logits=True)
            loss = criterion(logits, y_batch)
            loss.backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()

            total_loss += loss.item()
            total_batches += 1

        return total_loss / max(1, total_batches)

    def evaluate(
        self, dataloader: DataLoader, criterion: nn.Module
    ) -> Tuple[float, float, float]:
        """Evaluate model on validation set (returns val_loss, accuracy, macro_f1)."""
        self.model.eval()
        total_loss = 0.0
        total_batches = 0
        all_preds: List[int] = []
        all_targets: List[int] = []

        with torch.no_grad():
            for X_batch, y_batch in dataloader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)

                logits = self.model(X_batch, return_logits=True)
                loss = criterion(logits, y_batch)

                preds = torch.argmax(logits, dim=-1)
                all_preds.extend(preds.cpu().numpy().tolist())
                all_targets.extend(y_batch.cpu().numpy().tolist())

                total_loss += loss.item()
                total_batches += 1

        val_loss = total_loss / max(1, total_batches)
        preds_arr = np.array(all_preds)
        targets_arr = np.array(all_targets)

        accuracy = float(np.mean(preds_arr == targets_arr)) if len(targets_arr) > 0 else 0.0

        # Compute Macro F1
        f1_scores = []
        for c in range(3):
            tp = np.sum((preds_arr == c) & (targets_arr == c))
            fp = np.sum((preds_arr == c) & (targets_arr != c))
            fn = np.sum((preds_arr != c) & (targets_arr == c))
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            f1_scores.append(f1)
        macro_f1 = float(np.mean(f1_scores))

        return val_loss, accuracy, macro_f1

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        epochs: int = 15,
        batch_size: int = 32,
        patience: int = 5,
        checkpoint_dir: Union[str, Path] = "models",
    ) -> List[TrainingMetrics]:
        """Execute full training loop with validation and early stopping."""
        checkpoint_dir = Path(checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        class_weights = self.compute_class_weights(y_train, num_classes=self.model.num_classes)
        criterion = FocalLoss(alpha=class_weights, gamma=1.5)

        train_ds = OrderflowDataset(X_train, y_train)
        val_ds = OrderflowDataset(X_val, y_val)

        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, drop_last=(len(train_ds) > batch_size))
        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=epochs, eta_min=1e-5
        )

        history: List[TrainingMetrics] = []
        best_val_loss = float("inf")
        patience_counter = 0

        logger.info("Starting neural training: %d train samples, %d val samples, %d epochs", len(train_ds), len(val_ds), epochs)

        for epoch in range(1, epochs + 1):
            train_loss = self.train_epoch(train_loader, criterion)
            val_loss, val_acc, val_f1 = self.evaluate(val_loader, criterion)
            scheduler.step()

            metrics = TrainingMetrics(
                epoch=epoch,
                train_loss=train_loss,
                val_loss=val_loss,
                val_accuracy=val_acc,
                val_f1_macro=val_f1,
            )
            history.append(metrics)

            logger.info(
                "Epoch %02d/%02d | Train Loss: %.4f | Val Loss: %.4f | Val Acc: %.2f%% | Val Macro F1: %.3f",
                epoch,
                epochs,
                train_loss,
                val_loss,
                val_acc * 100,
                val_f1,
            )

            # Checkpoint on validation improvement
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                checkpoint_path = checkpoint_dir / "best_model.pt"
                torch.save(
                    {
                        "epoch": epoch,
                        "model_state_dict": self.model.state_dict(),
                        "optimizer_state_dict": self.optimizer.state_dict(),
                        "val_loss": val_loss,
                        "val_accuracy": val_acc,
                        "val_f1": val_f1,
                        "input_dim": self.model.input_dim,
                        "num_classes": self.model.num_classes,
                    },
                    checkpoint_path,
                )
                logger.info("Saved new best model checkpoint -> %s", checkpoint_path)
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info("Early stopping triggered after %d epochs without improvement.", patience)
                    break

        return history

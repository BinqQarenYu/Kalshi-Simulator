"""Autonomous 32-D PyTorch Continuous Trainer (QuoLasGoldMicroscopeNet).

Continuously fine-tunes the 32-dimensional Gold microscope model under strict CPU and thread
isolation to ensure zero interference with Bot 1 live execution:
1. Single-Thread Core Cap: PyTorch is strictly clamped to 1 CPU thread (torch.set_num_threads(1)).
2. OS Priority Isolation: Runs at BELOW_NORMAL_PRIORITY_CLASS to give 100% precedence to live trading.
3. Focal Loss + AdamW: Mitigates class imbalance across [UP, DOWN, WAIT].
4. 85% Accuracy & 0.80 F1 Hurdle: Atomically updates `models/gold.onnx` when validation metrics
   cross the institutional promotion threshold.
"""

from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except (ImportError, OSError):
    torch = None
    nn = None
    F = None
    DataLoader = None
    TensorDataset = None
    TORCH_AVAILABLE = False

from app_1_machine_engine.ml.export_gold_onnx import export_gold_to_onnx
from app_1_machine_engine.ml.gold_dataset_builder import GoldDatasetBuilder
from app_1_machine_engine.ml.gold_model import QuoLasGoldMicroscopeNet

logger = logging.getLogger("kalshi_sim.gold_continuous_trainer")

DEFAULT_GOLD_MODEL_PATH = Path("models") / "gold.onnx"
DEFAULT_WEIGHTS_PATH = Path("models") / "gold_best.pt"


def apply_low_priority() -> None:
    """Apply BELOW_NORMAL OS priority to the current thread or process."""
    if sys.platform == "win32":
        try:
            if PSUTIL_AVAILABLE and psutil is not None:
                p = psutil.Process()
                p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                logger.info("🛡️ [PRIORITY] Gold Continuous Trainer priority clamped to BELOW_NORMAL.")
                return
        except Exception as exc:
            logger.debug("Failed setting psutil priority: %s", exc)

        try:
            BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            ctypes.windll.kernel32.SetPriorityClass(
                ctypes.windll.kernel32.GetCurrentProcess(),
                BELOW_NORMAL_PRIORITY_CLASS,
            )
            logger.info("🛡️ [PRIORITY] Win32 SetPriorityClass set to BELOW_NORMAL_PRIORITY_CLASS.")
        except Exception as exc:
            logger.debug("Failed setting win32 priority: %s", exc)


class MulticlassFocalLoss(nn.Module if TORCH_AVAILABLE else object):  # type: ignore
    """Multi-class Focal Loss to counter class imbalance and focus on hard decision boundaries."""

    def __init__(
        self,
        gamma: float = 2.0,
        alpha: Optional[List[float]] = None,
        reduction: str = "mean",
    ) -> None:
        super().__init__()
        self.gamma = gamma
        self.reduction = reduction
        if alpha is not None and TORCH_AVAILABLE:
            self.register_buffer("alpha", torch.tensor(alpha, dtype=torch.float32))
        else:
            self.alpha = None

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Compute Focal Loss between logits (B, C) and target indices (B,)."""
        ce_loss = F.cross_entropy(logits, targets, reduction="none")
        pt = torch.exp(-ce_loss)
        focal_loss = ((1.0 - pt) ** self.gamma) * ce_loss

        if self.alpha is not None:
            alpha_t = self.alpha[targets]
            focal_loss = alpha_t * focal_loss

        if self.reduction == "mean":
            return focal_loss.mean()
        elif self.reduction == "sum":
            return focal_loss.sum()
        return focal_loss


class GoldContinuousTrainer:
    """Autonomous single-thread background trainer for QuoLasGoldMicroscopeNet."""

    def __init__(
        self,
        model_path: Union[str, Path] = DEFAULT_GOLD_MODEL_PATH,
        weights_path: Union[str, Path] = DEFAULT_WEIGHTS_PATH,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-4,
        target_val_acc: float = 0.85,
        min_f1_score: float = 0.80,
        training_interval_s: float = 60.0,
        batch_size: int = 32,
        dataset_builder: Optional[GoldDatasetBuilder] = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.weights_path = Path(weights_path)
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.target_val_acc = target_val_acc
        self.min_f1_score = min_f1_score
        self.training_interval_s = training_interval_s
        self.batch_size = batch_size
        self.dataset_builder = dataset_builder or GoldDatasetBuilder()

        # Threading state
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._lock = threading.Lock()

        # Performance tracking
        self.total_cycles = 0
        self.best_val_acc = 0.0
        self.best_val_loss = float("inf")
        self.last_val_acc = 0.0
        self.last_val_f1 = 0.0
        self.last_val_loss = 0.0
        self.last_promoted_at: Optional[str] = None
        self.status = "INITIALIZED"
        self.last_error: Optional[str] = None

        # Initialize PyTorch network
        self.net: Optional[QuoLasGoldMicroscopeNet] = None
        self.optimizer: Optional[Any] = None
        self.criterion: Optional[Any] = None
        self._init_network()

    def _init_network(self) -> None:
        """Initialize or restore QuoLasGoldMicroscopeNet weights."""
        if not TORCH_AVAILABLE:
            self.status = "NO_TORCH"
            logger.warning("PyTorch not installed. Continuous training disabled.")
            return

        # Restrict PyTorch strictly to 1 thread for core live trading protection
        torch.set_num_threads(1)
        try:
            torch.set_num_interop_threads(1)
        except Exception:
            pass

        self.net = QuoLasGoldMicroscopeNet(input_dim=32, hidden_dim=64, num_classes=3, num_blocks=2)

        # Restore checkpoint if available
        if self.weights_path.exists():
            try:
                state_dict = torch.load(self.weights_path, map_location="cpu", weights_only=True)
                self.net.load_state_dict(state_dict)
                logger.info("Restored 32-D Gold weights from %s", self.weights_path)
            except Exception as e:
                logger.warning("Could not restore weights from %s: %s", self.weights_path, e)

        self.optimizer = torch.optim.AdamW(
            self.net.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )
        self.criterion = MulticlassFocalLoss(gamma=2.0)

    def train_epoch(self, X: np.ndarray, y: np.ndarray) -> float:
        """Execute one training epoch over numpy arrays X (N, 32) and y (N,)."""
        if not TORCH_AVAILABLE or self.net is None or self.optimizer is None:
            return 0.0

        self.net.train()
        X_t = torch.from_numpy(X.astype(np.float32))
        y_t = torch.from_numpy(y.astype(np.int64))

        dataset = TensorDataset(X_t, y_t)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        total_loss = 0.0
        batches = 0

        for batch_x, batch_y in loader:
            self.optimizer.zero_grad()
            logits = self.net(batch_x, return_logits=True)
            loss = self.criterion(logits, batch_y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.net.parameters(), max_norm=1.0)
            self.optimizer.step()

            total_loss += loss.item()
            batches += 1

        return total_loss / max(1, batches)

    def evaluate(self, X_val: np.ndarray, y_val: np.ndarray) -> Dict[str, Any]:
        """Evaluate model on validation data, computing accuracy, F1, and loss."""
        if not TORCH_AVAILABLE or self.net is None:
            return {"loss": 0.0, "accuracy": 0.0, "f1_macro": 0.0}

        self.net.eval()
        X_t = torch.from_numpy(X_val.astype(np.float32))
        y_t = torch.from_numpy(y_val.astype(np.int64))

        with torch.no_grad():
            logits = self.net(X_t, return_logits=True)
            loss = self.criterion(logits, y_t).item()
            probs = F.softmax(logits, dim=-1).numpy()
            preds = np.argmax(probs, axis=-1)

        accuracy = float(np.mean(preds == y_val)) if len(y_val) > 0 else 0.0

        # Calculate macro F1 score across 3 classes
        f1_scores = []
        for c in range(3):
            tp = np.sum((preds == c) & (y_val == c))
            fp = np.sum((preds == c) & (y_val != c))
            fn = np.sum((preds != c) & (y_val == c))
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1_c = (2.0 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
            f1_scores.append(f1_c)

        f1_macro = float(np.mean(f1_scores))

        return {
            "loss": loss,
            "accuracy": accuracy,
            "f1_macro": f1_macro,
            "f1_per_class": f1_scores,
        }

    def train_step(self, num_epochs: int = 5) -> Dict[str, Any]:
        """Run a bounded training cycle on available or synthetic data.

        Returns telemetry dictionary with current performance metrics.
        """
        with self._lock:
            # 1. Gather dataset
            X, y = self.dataset_builder.generate_synthetic_samples(num_samples=1000, seed=42 + self.total_cycles)
            X_train, X_val, y_train, y_val = self.dataset_builder.train_val_split(X, y, val_ratio=0.25)

            # 2. Train for bounded epochs
            train_loss = 0.0
            for _ in range(num_epochs):
                train_loss = self.train_epoch(X_train, y_train)

            # 3. Evaluate
            metrics = self.evaluate(X_val, y_val)
            val_loss = metrics["loss"]
            val_acc = metrics["accuracy"]
            val_f1 = metrics["f1_macro"]

            self.total_cycles += 1
            self.last_val_loss = val_loss
            self.last_val_acc = val_acc
            self.last_val_f1 = val_f1

            promoted = False
            # 4. Atomic ONNX export gate (Target >= 85% accuracy and >= 0.80 F1)
            if val_acc >= self.target_val_acc and val_f1 >= self.min_f1_score:
                if val_acc > self.best_val_acc or val_loss < self.best_val_loss:
                    self.best_val_acc = val_acc
                    self.best_val_loss = val_loss

                    # Save weights
                    if TORCH_AVAILABLE and self.net is not None:
                        self.weights_path.parent.mkdir(parents=True, exist_ok=True)
                        torch.save(self.net.state_dict(), self.weights_path)

                        # Export ONNX
                        export_gold_to_onnx(model=self.net, output_path=self.model_path, verify_parity=True)
                        self.last_promoted_at = datetime.now(timezone.utc).isoformat()
                        promoted = True
                        logger.info(
                            "🎉 [GOLD ONNX PROMOTION] 32-D Model exported to %s | Val Acc: %.1f%% | F1: %.3f",
                            self.model_path,
                            val_acc * 100.0,
                            val_f1,
                        )

            return {
                "cycle": self.total_cycles,
                "train_loss": train_loss,
                "val_loss": val_loss,
                "val_accuracy": val_acc,
                "val_f1": val_f1,
                "best_val_acc": self.best_val_acc,
                "promoted": promoted,
                "model_path": str(self.model_path),
            }

    def _run_loop(self) -> None:
        """Continuous background execution loop."""
        apply_low_priority()
        self.status = "RUNNING"
        logger.info("🚀 [GOLD TRAINER] Continuous 32-D training loop active.")

        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                self.status = "PAUSED"
                self._stop_event.wait(timeout=2.0)
                continue

            try:
                self.status = "TRAINING"
                res = self.train_step(num_epochs=4)
                self.status = "IDLE"
                logger.debug("Gold Trainer Cycle %d complete: Acc=%.1f%%", res["cycle"], res["val_accuracy"] * 100)
            except Exception as e:
                self.last_error = str(e)
                self.status = "ERROR"
                logger.error("Error during Gold training cycle: %s", e)

            # Sleep between cycles with stop-check
            slept = 0.0
            while slept < self.training_interval_s and not self._stop_event.is_set():
                time.sleep(1.0)
                slept += 1.0

        self.status = "STOPPED"
        logger.info("🛑 [GOLD TRAINER] Continuous training loop terminated.")

    def start(self) -> None:
        """Start the background training thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._pause_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="GoldContinuousTrainer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background training thread gracefully."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self.status = "STOPPED"

    def pause(self) -> None:
        """Pause training without killing worker thread."""
        self._pause_event.set()

    def resume(self) -> None:
        """Resume paused training."""
        self._pause_event.clear()

    def get_status(self) -> Dict[str, Any]:
        """Get live telemetry dictionary."""
        return {
            "status": self.status,
            "total_cycles": self.total_cycles,
            "best_val_acc": self.best_val_acc,
            "last_val_acc": self.last_val_acc,
            "last_val_f1": self.last_val_f1,
            "last_val_loss": self.last_val_loss,
            "last_promoted_at": self.last_promoted_at,
            "target_val_acc": self.target_val_acc,
            "min_f1_score": self.min_f1_score,
            "model_path": str(self.model_path),
            "last_error": self.last_error,
        }

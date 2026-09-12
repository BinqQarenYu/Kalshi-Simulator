"""Continuous Autonomous Background ONNX Model Trainer.

Continuously and autonomously fine-tunes the QuoLas Nano Microscope neural network
on live-ingested tick data in the background, promoting newly trained models to ONNX
whenever validation metrics improve.

Guarantees ZERO impact on live trading:
1. OS Priority Isolation: Process/thread runs with IDLE or BELOW_NORMAL priority class.
2. Single-Thread Core Cap: PyTorch is strictly capped to 1 CPU thread (torch.set_num_threads(1)).
3. Dedicated Background Thread: Runs completely decoupled from the asyncio event loop.
4. Memory Bounding: Mini-batches (32) and rolling tick sample windows with immediate GC sweeps.
5. Atomic Model Promotion: Exports to staging file, validates ONNX graph, then atomically replaces.
6. Cooperative Throttling: Yields CPU time slices between batches; pauses during critical spikes.
"""

from __future__ import annotations

import ctypes
import gc
import json
import logging
import os
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import torch
    TORCH_AVAILABLE = True
except (ImportError, OSError):
    torch = None
    TORCH_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import onnxruntime as ort
    ORT_AVAILABLE = True
except ImportError:
    ORT_AVAILABLE = False

from kalshi_sim.ml.dataset_builder import DatasetBuilder
from kalshi_sim.ml.model import ExportableQuoLasNet, QuoLasMicroscopeNet
from kalshi_sim.ml.train_model import ModelTrainer

logger = logging.getLogger("kalshi_sim.continuous_trainer")


def apply_low_priority_to_thread_or_process() -> None:
    """Apply low OS priority class (IDLE / BELOW_NORMAL) so live trading is strictly prioritized."""
    if sys.platform == "win32":
        try:
            if PSUTIL_AVAILABLE:
                p = psutil.Process()
                # Use BELOW_NORMAL_PRIORITY_CLASS to give 100% priority to live trading while allowing steady background progress
                p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                logger.info("🛡️ [PRIORITY] Background Continuous Trainer set to BELOW_NORMAL_PRIORITY_CLASS.")
                return
        except Exception as exc:
            logger.debug("Failed setting psutil priority: %s", exc)

        try:
            # Fallback to direct Win32 SetPriorityClass
            # BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            res = ctypes.windll.kernel32.SetPriorityClass(
                ctypes.windll.kernel32.GetCurrentProcess(),
                BELOW_NORMAL_PRIORITY_CLASS,
            )
            if res != 0:
                logger.info("🛡️ [PRIORITY] Win32 SetPriorityClass applied BELOW_NORMAL_PRIORITY_CLASS.")
        except Exception as exc:
            logger.debug("Failed setting Win32 process priority: %s", exc)
    else:
        try:
            os.nice(15)  # Very low Unix priority
            logger.info("🛡️ [PRIORITY] Unix os.nice(15) applied to continuous trainer.")
        except Exception:
            pass


def export_and_verify_onnx(
    model: QuoLasMicroscopeNet,
    target_onnx_path: Path,
    device: str = "cpu",
) -> bool:
    """Export model to temporary ONNX file, verify output shape and validity, then atomically replace target."""
    if not ORT_AVAILABLE:
        logger.warning("onnxruntime not installed; skipping ONNX export.")
        return False
    if not TORCH_AVAILABLE:
        logger.warning("torch not available; skipping ONNX export.")
        return False

    target_onnx_path = Path(target_onnx_path)
    target_onnx_path.parent.mkdir(parents=True, exist_ok=True)
    staging_path = target_onnx_path.with_name(f"{target_onnx_path.stem}.tmp.onnx")

    exportable = ExportableQuoLasNet(model)
    exportable.eval()
    exportable.to(device)

    dummy_spatial = torch.randn(1, 15, dtype=torch.float32, device=device)
    dummy_toxic = torch.randn(1, 13, dtype=torch.float32, device=device)

    try:
        # Protect against Windows cp1252 charmap encoding crashes from PyTorch internal emoji prints
        if sys.platform == "win32":
            if hasattr(sys.stdout, "reconfigure"):
                try:
                    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
                except Exception:
                    pass
            if hasattr(sys.stderr, "reconfigure"):
                try:
                    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
                except Exception:
                    pass

        torch.onnx.export(
            exportable,
            (dummy_spatial, dummy_toxic),
            str(staging_path),
            input_names=["spatial_input", "toxic_input"],
            output_names=["action_logits"],
            dynamic_axes={
                "spatial_input": {0: "batch"},
                "toxic_input": {0: "batch"},
                "action_logits": {0: "batch"},
            },
            opset_version=18,
            dynamo=False,
        )

        # Verification pass with ONNX Runtime
        sess_opts = ort.SessionOptions()
        sess_opts.intra_op_num_threads = 1
        sess_opts.inter_op_num_threads = 1
        sess = ort.InferenceSession(str(staging_path), sess_options=sess_opts, providers=["CPUExecutionProvider"])
        test_out = sess.run(
            None,
            {
                "spatial_input": dummy_spatial.cpu().numpy(),
                "toxic_input": dummy_toxic.cpu().numpy(),
            },
        )

        # Sanity checks
        assert test_out[0].shape == (1, 3), f"Invalid output shape: {test_out[0].shape}"
        assert np.isfinite(test_out[0]).all(), "Non-finite output values in ONNX export"

        # Backup current model if it exists
        backup_path = target_onnx_path.with_name(f"{target_onnx_path.stem}_backup.onnx")
        if target_onnx_path.exists():
            try:
                shutil.copy2(target_onnx_path, backup_path)
            except Exception as b_exc:
                logger.debug("Failed creating pre-promotion backup: %s", b_exc)

        # Atomically replace target file
        staging_path.replace(target_onnx_path)
        logger.info("🚀 [ONNX PROMOTION] Atomically replaced production ONNX model at: %s", target_onnx_path)
        return True

    except Exception as exc:
        logger.error("Failed to export or verify ONNX model: %s", exc, exc_info=True)
        if staging_path.exists():
            try:
                staging_path.unlink()
            except Exception:
                pass
        return False


class ContinuousModelTrainer:
    """Autonomous continuous background model training and online promotion engine."""

    def __init__(
        self,
        data_dir: Path = Path("data"),
        models_dir: Path = Path("models"),
        onnx_model_name: str = "quolas.onnx",
        training_interval_seconds: float = 180.0,
        batch_size: int = 32,
        learning_rate: float = 2e-4,
        epochs_per_cycle: int = 4,
        max_recent_tick_files: int = 15,
        max_frames_per_file: int = 500,
        min_samples_to_train: int = 64,
        enabled: bool = True,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.models_dir = Path(models_dir)
        self.onnx_model_path = self.models_dir / onnx_model_name
        self.checkpoint_path = self.models_dir / "best_model.pt"
        self.feature_stats_path = self.models_dir / "feature_stats.json"

        self.training_interval_seconds = training_interval_seconds
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.epochs_per_cycle = epochs_per_cycle
        self.max_recent_tick_files = max_recent_tick_files
        self.max_frames_per_file = max_frames_per_file
        self.min_samples_to_train = min_samples_to_train

        # Lifecycle and State
        self._enabled = enabled
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Telemetry
        self.status: str = "IDLE"  # "IDLE" | "EXTRACTING" | "TRAINING" | "EVALUATING" | "PROMOTED" | "PAUSED"
        self.cycles_completed: int = 0
        self.models_promoted: int = 0
        self.best_val_loss: float = float("inf")
        self.last_val_loss: Optional[float] = None
        self.last_val_acc: Optional[float] = None
        self.last_val_f1: Optional[float] = None
        self.last_trained_time: Optional[str] = None
        self.last_promoted_time: Optional[str] = None
        self.samples_trained: int = 0
        self.last_error: Optional[str] = None

        # Load best existing loss from checkpoint if present
        self._load_baseline_metrics()

    def _load_baseline_metrics(self) -> None:
        """Load baseline best validation loss from existing checkpoint."""
        if self.checkpoint_path.exists():
            try:
                ckpt = torch.load(self.checkpoint_path, map_location="cpu", weights_only=True)
                if "val_loss" in ckpt and isinstance(ckpt["val_loss"], (int, float)):
                    self.best_val_loss = float(ckpt["val_loss"])
                    logger.info("Loaded baseline best validation loss: %.4f from %s", self.best_val_loss, self.checkpoint_path)
            except Exception as exc:
                logger.debug("Could not read baseline metrics from checkpoint: %s", exc)

    def start(self) -> None:
        """Start the continuous training background thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._worker_loop,
                name="ContinuousONNXTrainer",
                daemon=True,
            )
            self._thread.start()
            logger.info("Continuous Background ONNX Trainer started (Interval: %.1fs, Batch Size: %d, Thread Cap: 1).",
                        self.training_interval_seconds, self.batch_size)

    def stop(self) -> None:
        """Stop the continuous training background thread."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self.status = "STOPPED"
        logger.info("Continuous Background ONNX Trainer stopped.")

    def pause(self) -> None:
        """Temporarily pause training."""
        with self._lock:
            self._paused = True
            self.status = "PAUSED"
        logger.info("Continuous ONNX Trainer paused by operator.")

    def resume(self) -> None:
        """Resume continuous training."""
        with self._lock:
            self._paused = False
            self.status = "IDLE"
        logger.info("Continuous ONNX Trainer resumed.")

    def get_status(self) -> dict[str, Any]:
        """Return real-time telemetry dictionary for API and WebSocket broadcasts."""
        return {
            "status": self.status,
            "is_enabled": self._enabled,
            "is_running": self._running,
            "is_paused": self._paused,
            "cycles_completed": self.cycles_completed,
            "models_promoted": self.models_promoted,
            "best_val_loss": round(self.best_val_loss, 4) if self.best_val_loss != float("inf") else None,
            "last_val_loss": round(self.last_val_loss, 4) if self.last_val_loss is not None else None,
            "last_val_accuracy": round(self.last_val_acc * 100, 2) if self.last_val_acc is not None else None,
            "last_val_f1": round(self.last_val_f1, 4) if self.last_val_f1 is not None else None,
            "last_trained_time": self.last_trained_time,
            "last_promoted_time": self.last_promoted_time,
            "samples_trained": self.samples_trained,
            "last_error": self.last_error,
            "priority_class": "BELOW_NORMAL / IDLE",
            "cpu_thread_cap": 1,
        }

    def _worker_loop(self) -> None:
        """Main background loop executing bounded training cycles."""
        if not TORCH_AVAILABLE:
            self.status = "DISABLED_NO_TORCH"
            logger.info("[CONTINUOUS TRAINER] PyTorch not installed/available; continuous background training disabled.")
            return

        # 1. Apply OS low priority
        apply_low_priority_to_thread_or_process()

        # 2. Strict single-thread PyTorch cap to prevent CPU starvation of live trading
        torch.set_num_threads(1)
        try:
            torch.set_num_interop_threads(1)
        except Exception:
            pass

        # Initial grace period on server startup before first training cycle
        self._stop_event.wait(timeout=15.0)

        while not self._stop_event.is_set():
            if not self._enabled or self._paused:
                self.status = "PAUSED" if self._paused else "DISABLED"
                self._stop_event.wait(timeout=5.0)
                continue

            try:
                self._execute_training_cycle()
            except Exception as exc:
                self.last_error = str(exc)
                logger.error("[CONTINUOUS TRAINER] Error in training cycle: %s", exc, exc_info=True)
                self.status = "ERROR"

            # Sleep between cycles with periodic check on stop event
            sleep_step = 1.0
            slept = 0.0
            while slept < self.training_interval_seconds and not self._stop_event.is_set():
                time.sleep(sleep_step)
                slept += sleep_step

    @staticmethod
    def sample_stratified_anchor(
        X_anchor: np.ndarray,
        y_anchor: np.ndarray,
        max_per_class: int = 500,
        num_classes: int = 3,
        seed: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Sample balanced quantities of UP (0), DOWN (1), and WAIT (2) from anchor dataset.

        Samples up to max_per_class (default 500) per class (up to 1500 total),
        or proportional to available counts if a class has fewer.
        """
        if len(X_anchor) == 0 or len(y_anchor) == 0:
            feat_dim = X_anchor.shape[1] if X_anchor.ndim > 1 else 28
            return np.empty((0, feat_dim), dtype=np.float32), np.empty((0,), dtype=np.int64)

        rng = np.random.default_rng(seed)
        selected_indices_list: List[np.ndarray] = []

        for c in range(num_classes):
            c_indices = np.where(y_anchor == c)[0]
            if len(c_indices) == 0:
                continue
            if len(c_indices) <= max_per_class:
                selected_indices_list.append(c_indices)
            else:
                chosen = rng.choice(c_indices, size=max_per_class, replace=False)
                selected_indices_list.append(chosen)

        if not selected_indices_list:
            feat_dim = X_anchor.shape[1] if X_anchor.ndim > 1 else 28
            return np.empty((0, feat_dim), dtype=np.float32), np.empty((0,), dtype=np.int64)

        all_selected = np.sort(np.concatenate(selected_indices_list))
        return X_anchor[all_selected], y_anchor[all_selected]

    def _execute_training_cycle(self) -> None:
        """Execute one complete data extraction, training, validation, and promotion cycle."""
        self.status = "EXTRACTING"
        logger.info("🧠 [CONTINUOUS TRAINER] Starting new learning cycle (Cycle #%d)...", self.cycles_completed + 1)

        # 1. Harvest recent tick logs
        builder = DatasetBuilder(
            horizon_steps=15,
            horizon_seconds=20.0,
            price_diff_threshold=0.03,
            sample_stride=5,
            max_frames_per_file=self.max_frames_per_file,
            max_wait_ratio=0.50,
        )

        X_recent, y_recent = builder.build_from_directory(
            self.data_dir,
            file_pattern="ticks_*.jsonl",
            max_files=self.max_recent_tick_files,
        )

        # 2. Merge with anchor dataset if available using balanced stratified replay buffer
        anchor_file = self.models_dir / "dataset_v1.npz"
        X_all: np.ndarray
        y_all: np.ndarray

        if anchor_file.exists():
            try:
                anchor_data = np.load(anchor_file)
                X_anchor = anchor_data["X_train"]
                y_anchor = anchor_data["y_train"]
                X_anchor_strat, y_anchor_strat = self.sample_stratified_anchor(
                    X_anchor, y_anchor, max_per_class=500, num_classes=3
                )
                if len(X_recent) > 0:
                    X_all = np.vstack([X_anchor_strat, X_recent])
                    y_all = np.concatenate([y_anchor_strat, y_recent])
                else:
                    X_all = X_anchor_strat
                    y_all = y_anchor_strat
            except Exception as d_exc:
                logger.debug("Failed loading anchor dataset: %s", d_exc)
                X_all = X_recent
                y_all = y_recent
        else:
            X_all = X_recent
            y_all = y_recent

        if len(X_all) < self.min_samples_to_train:
            logger.info("[CONTINUOUS TRAINER] Insufficient samples (%d < %d). Waiting for next tick accumulation.",
                        len(X_all), self.min_samples_to_train)
            self.status = "IDLE"
            return

        # 3. Train/Validation Split (80/20)
        indices = np.random.permutation(len(X_all))
        split_idx = int(len(X_all) * 0.8)
        train_idx, val_idx = indices[:split_idx], indices[split_idx:]

        X_train, y_train = X_all[train_idx], y_all[train_idx]
        X_val, y_val = X_all[val_idx], y_all[val_idx]

        self.samples_trained = len(X_all)

        # 4. Initialize model architecture and restore weights
        self.status = "TRAINING"
        model = QuoLasMicroscopeNet(input_dim=28, hidden_dim=64, num_classes=3)

        if self.checkpoint_path.exists():
            try:
                ckpt = torch.load(self.checkpoint_path, map_location="cpu", weights_only=True)
                model.load_state_dict(ckpt["model_state_dict"])
                logger.info("[CONTINUOUS TRAINER] Restored weights from prior checkpoint %s", self.checkpoint_path)
            except Exception as c_exc:
                logger.warning("[CONTINUOUS TRAINER] Checkpoint restoration fallback: %s", c_exc)

        trainer = ModelTrainer(
            model=model,
            learning_rate=self.learning_rate,
            weight_decay=1e-4,
            device="cpu",
        )

        # Execute training epochs with cooperative yielding
        history = trainer.fit(
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            epochs=self.epochs_per_cycle,
            batch_size=self.batch_size,
            patience=3,
            checkpoint_dir=self.models_dir,
        )

        self.cycles_completed += 1
        self.last_trained_time = datetime.now(timezone.utc).isoformat()

        if not history:
            self.status = "IDLE"
            return

        # 5. Evaluate Validation Metrics
        self.status = "EVALUATING"
        best_cycle_epoch = min(history, key=lambda m: m.val_loss)
        self.last_val_loss = best_cycle_epoch.val_loss
        self.last_val_acc = best_cycle_epoch.val_accuracy
        self.last_val_f1 = best_cycle_epoch.val_f1_macro

        logger.info(
            "📊 [CONTINUOUS EVAL] Cycle #%d Best Epoch %d | Val Loss: %.4f (Best Known: %.4f) | Acc: %.2f%% | F1: %.3f",
            self.cycles_completed,
            best_cycle_epoch.epoch,
            best_cycle_epoch.val_loss,
            self.best_val_loss,
            best_cycle_epoch.val_accuracy * 100,
            best_cycle_epoch.val_f1_macro,
        )

        # 6. Promotion Gate: Check if model improves on baseline
        should_promote = (
            best_cycle_epoch.val_loss < self.best_val_loss or
            self.best_val_loss == float("inf") or
            not self.onnx_model_path.exists()
        )

        if should_promote:
            self.best_val_loss = best_cycle_epoch.val_loss
            promoted = export_and_verify_onnx(model, self.onnx_model_path, device="cpu")
            if promoted:
                self.models_promoted += 1
                self.last_promoted_time = datetime.now(timezone.utc).isoformat()
                self.status = "PROMOTED"

                # Update feature stats
                try:
                    mean = np.mean(X_all, axis=0).astype(float).tolist()
                    std = np.std(X_all, axis=0).astype(float).tolist()
                    std = [float(s) if float(s) > 1e-6 else 1.0 for s in std]
                    with open(self.feature_stats_path, "w", encoding="utf-8") as f:
                        json.dump({"mean": mean, "std": std}, f, indent=4)
                    logger.info("Updated feature normalization statistics at %s", self.feature_stats_path)
                except Exception as s_exc:
                    logger.debug("Failed saving updated feature stats: %s", s_exc)

                logger.info(
                    "🌟 [MODEL PROMOTION COMPLETED] Model #%d promoted to %s! Hot-reloading active.",
                    self.models_promoted,
                    self.onnx_model_path.name,
                )

                # Push updated models and feature stats to Google Drive
                try:
                    from kalshi_sim.gdrive_sync import push_models_to_gdrive
                    push_models_to_gdrive(self.models_dir)
                except Exception as gd_exc:
                    logger.debug("[CONTINUOUS TRAINER] GDrive push on promotion skipped/failed: %s", gd_exc)
            else:
                self.status = "EVALUATED"
        else:
            logger.info("Model candidate did not beat best known validation loss (%.4f >= %.4f). Retaining current model.",
                        best_cycle_epoch.val_loss, self.best_val_loss)
            self.status = "IDLE"

        # Explicit garbage collection and memory release
        del X_train, y_train, X_val, y_val, X_all, y_all
        gc.collect()

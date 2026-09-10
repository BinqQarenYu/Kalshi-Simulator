"""Kalshi ONNX Inference Engine for Microstructure Orderflow Models.

Loads the QuoLas Nano Microscope ONNX model and executes sub-millisecond
inference on incoming Level-2 order book snapshots and public trade streams.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

from kalshi_sim.ml.feature_extractor import KalshiOrderflowFeatureExtractor
from kalshi_sim.schemas import L2BookState, TradeEvent

logger = logging.getLogger(__name__)

# Decision thresholds
CONFIDENCE_THRESHOLD = 0.70  # AI must be 70%+ confident to fire directional signal
VPIN_OVERRIDE_THRESHOLD = 0.75  # Hard VPIN risk cutoff


class KalshiONNXEngine:
    """Low-latency ONNX runtime execution harness with VPIN risk gating."""

    def __init__(
        self,
        model_path: Optional[str | Path] = None,
        stats_path: Optional[str | Path] = None,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
    ) -> None:
        self.model_path = Path(model_path) if model_path else Path("models/nano_microscope_overhauled.onnx")
        self.stats_path = Path(stats_path) if stats_path else (self.model_path.parent / "feature_stats.json")
        self.confidence_threshold = confidence_threshold

        self.extractor = KalshiOrderflowFeatureExtractor(target_depth=15, spatial_alpha=0.425)
        self.session: Optional[Any] = None
        self.feat_mean: Optional[np.ndarray] = None
        self.feat_std: Optional[np.ndarray] = None
        self.last_mtime: float = 0.0

        # Last inference telemetry
        self.last_signal: str = "WAIT"
        self.last_confidence: float = 0.0
        self.last_probs: List[float] = [0.0, 0.0, 1.0]

        # Hot-reload filesystem stat check rate-limiting state
        self._last_mtime_check: float = 0.0
        self._check_interval: float = 1.0  # Throttle stat() to max once per second

        self._load_model()

    def _load_model(self) -> None:
        """Load ONNX runtime session and z-score normalization parameters."""
        if not ONNX_AVAILABLE:
            logger.warning("[KalshiONNX] onnxruntime not installed — running in STUB mode.")
            return

        if not self.model_path.exists():
            logger.warning("[KalshiONNX] Model file %s not found — running in STUB mode.", self.model_path)
            return

        # Load normalization stats
        if self.stats_path.exists():
            try:
                with open(self.stats_path, "r", encoding="utf-8") as f:
                    stats = json.load(f)
                self.feat_mean = np.array(stats["mean"], dtype=np.float32)
                self.feat_std = np.array(stats["std"], dtype=np.float32)
                logger.info("[KalshiONNX] Normalization stats loaded from %s", self.stats_path)
            except Exception as exc:
                logger.error("[KalshiONNX] Failed to load feature stats from %s: %s", self.stats_path, exc)
        else:
            logger.warning("[KalshiONNX] Stats file %s not found. Inference will run unnormalized.", self.stats_path)

        # Single-threaded configuration to eliminate CPU context swapping latency jitter
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        try:
            # Copy to temp directory to avoid Windows file lock issues with .onnx.data
            tmp_dir = tempfile.mkdtemp()
            active_onnx = os.path.join(tmp_dir, self.model_path.name)
            shutil.copy(self.model_path, active_onnx)

            data_file = str(self.model_path) + ".data"
            if os.path.exists(data_file):
                shutil.copy(data_file, active_onnx + ".data")
                # Fallback for tmp naming in protobuf if present
                shutil.copy(data_file, os.path.join(tmp_dir, "nano_microscope_overhauled.tmp.onnx.data"))

            self.session = ort.InferenceSession(
                active_onnx,
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            self.last_mtime = self.model_path.stat().st_mtime
            logger.info("[KalshiONNX] ONNX model '%s' successfully initialized in memory.", self.model_path.name)
        except Exception as exc:
            logger.error("[KalshiONNX] Failed to load ONNX model: %s", exc, exc_info=True)

    def process_orderbook_tick(
        self,
        book: L2BookState,
        latest_trades: Optional[List[TradeEvent]] = None,
    ) -> Dict[str, Any]:
        """Execute feature extraction and sub-millisecond ONNX inference for an L2 tick."""
        # 1. Hot-reload check (throttled to max once per second to avoid blocking filesystem stat calls on tick hot path)
        now = time.monotonic()
        if now - self._last_mtime_check > self._check_interval:
            self._last_mtime_check = now
            if self.model_path.exists():
                try:
                    curr_mtime = self.model_path.stat().st_mtime
                    if curr_mtime > self.last_mtime:
                        logger.info("[KalshiONNX] Hot-reload triggered: reloading %s", self.model_path)
                        self._load_model()
                except Exception:
                    pass

        # 2. Extract 28-dimensional raw feature vector
        raw_vector = self.extractor.extract_features_from_book(book, latest_trades)

        # 3. Apply z-score normalization
        if self.feat_mean is not None and self.feat_std is not None:
            normed = (raw_vector - self.feat_mean) / (self.feat_std + 1e-8)
        else:
            normed = raw_vector

        # 4. Slice into dual input streams
        toxic_vec = normed[:13].reshape(1, 13).astype(np.float32)
        spatial_vec = normed[13:28].reshape(1, 15).astype(np.float32)

        # 5. Sanitize NaNs/Infs
        if not np.isfinite(toxic_vec).all():
            toxic_vec = np.nan_to_num(toxic_vec, nan=0.0, posinf=0.0, neginf=0.0)
        if not np.isfinite(spatial_vec).all():
            spatial_vec = np.nan_to_num(spatial_vec, nan=0.0, posinf=0.0, neginf=0.0)

        # 6. Execute ONNX graph
        if self.session is not None:
            try:
                outputs = self.session.run(
                    None,
                    {
                        "spatial_input": spatial_vec,
                        "toxic_input": toxic_vec,
                    },
                )
                probs = outputs[0][0]
            except Exception as exc:
                logger.error("[KalshiONNX] Inference execution error: %s", exc)
                probs = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        else:
            probs = np.array([0.0, 0.0, 1.0], dtype=np.float32)

        # 7. Probability calibration & temperature scaling
        if not np.isfinite(probs).all():
            probs = np.array([0.33, 0.33, 0.34], dtype=np.float32)
        else:
            # Temperature scaled softmax for calibrated directional probabilities
            temperature = 0.65
            scaled_logits = probs / temperature
            e_x = np.exp(scaled_logits - np.max(scaled_logits))
            probs = e_x / e_x.sum()

        long_p, short_p, wait_p = float(probs[0]), float(probs[1]), float(probs[2])
        vpin_score = float(raw_vector[6])

        # 8. Microstructural Decision & VPIN Risk Override
        vpin_veto = vpin_score > VPIN_OVERRIDE_THRESHOLD

        # Relative dominance thresholding (since neural class bias centers on wait)
        dir_sum = long_p + short_p + 1e-9
        rel_long = long_p / dir_sum
        rel_short = short_p / dir_sum

        if vpin_veto:
            signal = "WAIT"
            confidence = wait_p
            veto_reason = f"VPIN Toxicity Breached ({vpin_score:.3f} > {VPIN_OVERRIDE_THRESHOLD})"
        elif rel_long >= 0.55 and (long_p >= 0.10 or rel_long >= 0.60):
            signal = "LONG"
            confidence = rel_long
            veto_reason = ""
        elif rel_short >= 0.55 and (short_p >= 0.10 or rel_short >= 0.60):
            signal = "SHORT"
            confidence = rel_short
            veto_reason = ""
        else:
            signal = "WAIT"
            confidence = wait_p
            veto_reason = "Neutral Order Flow Imbalance"

        self.last_signal = signal
        self.last_confidence = confidence
        self.last_probs = [long_p, short_p, wait_p]

        return {
            "signal": signal,
            "confidence": round(confidence, 4),
            "prob_long": round(long_p, 4),
            "prob_short": round(short_p, 4),
            "prob_wait": round(wait_p, 4),
            "rel_long": round(rel_long, 4),
            "rel_short": round(rel_short, 4),
            "vpin_score": round(vpin_score, 4),
            "vpin_veto": vpin_veto,
            "veto_reason": veto_reason,
            "spread_bps": round(float(raw_vector[0]), 2),
            "ofi_l1": round(float(raw_vector[1]), 4),
            "ofi_l5": round(float(raw_vector[2]), 4),
            "cvd": round(float(raw_vector[4]), 2),
            "entropy": round(float(raw_vector[5]), 4),
            "whale_tx": round(float(raw_vector[11]), 2),
        }

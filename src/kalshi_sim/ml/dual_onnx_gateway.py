"""Dual-ONNX Inference Gateway for High-Frequency Cross-Market Orderflow.

Coordinates concurrent low-latency inference across two independent ONNX neural brains:
1. QuoLas Brain (models/nano_microscope_overhauled.onnx): Spot BTC microstructure & price discovery.
2. Kalshi Brain (models/kalshi_onnx.onnx): Kalshi binary CLOB microstructure & retail flow.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from kalshi_sim.ml.onnx_engine import KalshiONNXEngine
from kalshi_sim.schemas import L2BookState, TradeEvent

logger = logging.getLogger("kalshi_sim.dual_onnx_gateway")


def _make_neutral_result(reason: str = "Missing order book") -> Dict[str, Any]:
    """Generate default neutral telemetry dictionary when order book is unavailable."""
    return {
        "signal": "WAIT",
        "confidence": 1.0,
        "prob_long": 0.0,
        "prob_short": 0.0,
        "prob_wait": 1.0,
        "rel_long": 0.0,
        "rel_short": 0.0,
        "vpin_score": 0.0,
        "vpin_veto": False,
        "veto_reason": reason,
        "spread_bps": 0.0,
        "ofi_l1": 0.0,
        "ofi_l5": 0.0,
        "cvd": 0.0,
        "entropy": 0.0,
        "whale_tx": 0.0,
    }


class DualONNXGateway:
    """Gateway orchestrating dual ONNX inference for Spot and Kalshi order books."""

    def __init__(
        self,
        quolas_model_path: Optional[Union[str, Path]] = None,
        kalshi_model_path: Optional[Union[str, Path]] = None,
        quolas_stats_path: Optional[Union[str, Path]] = None,
        kalshi_stats_path: Optional[Union[str, Path]] = None,
        fallback_to_quolas: bool = True,
        matrix_builder: Optional[Any] = None,
    ) -> None:
        p_quolas_default = Path("models/quolas.onnx")
        if quolas_model_path:
            self.quolas_model_path = Path(quolas_model_path)
        else:
            self.quolas_model_path = p_quolas_default if p_quolas_default.exists() else Path("models/nano_microscope_overhauled.onnx")

        if kalshi_model_path:
            self.kalshi_model_path = Path(kalshi_model_path)
        else:
            p_kalshi_legacy = Path("models/kalshi_onnx.onnx")
            if p_quolas_default.exists():
                self.kalshi_model_path = p_quolas_default
            elif p_kalshi_legacy.exists():
                self.kalshi_model_path = p_kalshi_legacy
            else:
                self.kalshi_model_path = self.quolas_model_path

        self.quolas_stats_path = Path(quolas_stats_path) if quolas_stats_path else (self.quolas_model_path.parent / "feature_stats.json")
        self.kalshi_stats_path = Path(kalshi_stats_path) if kalshi_stats_path else (self.kalshi_model_path.parent / "feature_stats.json")
        self.fallback_to_quolas = fallback_to_quolas
        self.matrix_builder = matrix_builder

        # 1. Initialize QuoLas Spot Engine
        self.quolas_engine = KalshiONNXEngine(
            model_path=self.quolas_model_path,
            stats_path=self.quolas_stats_path,
        )

        # 2. Initialize Kalshi Engine with graceful fallback
        self.is_kalshi_fallback = False
        if self.kalshi_model_path.exists() and self.kalshi_model_path != self.quolas_model_path:
            self.kalshi_engine = KalshiONNXEngine(
                model_path=self.kalshi_model_path,
                stats_path=self.kalshi_stats_path,
            )
            logger.info("Loaded dedicated Kalshi ONNX model from %s", self.kalshi_model_path)
        elif self.fallback_to_quolas and self.quolas_model_path.exists():
            logger.info(
                "Using unified QuoLas model %s for Spot & Kalshi dual engine.",
                self.quolas_model_path,
            )
            self.kalshi_engine = KalshiONNXEngine(
                model_path=self.quolas_model_path,
                stats_path=self.quolas_stats_path,
            )
            self.is_kalshi_fallback = not p_quolas_default.exists()
        else:
            logger.warning(
                "Kalshi ONNX model %s not found and QuoLas fallback unavailable. Initializing stub Kalshi engine.",
                self.kalshi_model_path,
            )
            self.kalshi_engine = KalshiONNXEngine(
                model_path=self.kalshi_model_path,
                stats_path=self.kalshi_stats_path,
            )
            self.is_kalshi_fallback = True

    def _check_kalshi_model_promotion(self) -> None:
        """Dynamically hot-swap engines if quolas.onnx or dedicated kalshi_onnx is promoted."""
        quolas_target = Path("models/quolas.onnx")
        if quolas_target.exists():
            if self.quolas_model_path != quolas_target or self.is_kalshi_fallback:
                logger.info(
                    "🚀 [DUAL-ONNX GATEWAY] Newly trained unified QuoLas model detected at %s! Hot-reloading active engines.",
                    quolas_target,
                )
                self.quolas_model_path = quolas_target
                self.kalshi_model_path = quolas_target
                self.quolas_engine = KalshiONNXEngine(model_path=quolas_target, stats_path=self.quolas_stats_path)
                self.kalshi_engine = KalshiONNXEngine(model_path=quolas_target, stats_path=self.kalshi_stats_path)
                self.is_kalshi_fallback = False
                return

        if self.is_kalshi_fallback and self.kalshi_model_path.exists():
            logger.info(
                "🚀 [DUAL-ONNX GATEWAY] Newly trained dedicated Kalshi model detected at %s! Upgrading from fallback.",
                self.kalshi_model_path,
            )
            self.kalshi_engine = KalshiONNXEngine(
                model_path=self.kalshi_model_path,
                stats_path=self.kalshi_stats_path,
            )
            self.is_kalshi_fallback = False

    def infer_both(
        self,
        spot_book: Optional[L2BookState],
        kalshi_book: Optional[L2BookState],
        latest_spot_trades: Optional[List[TradeEvent]] = None,
        latest_kalshi_trades: Optional[List[TradeEvent]] = None,
        spot_tensor: Optional[Any] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Execute concurrent or sequential inference on both spot and Kalshi order books.

        Returns:
            Tuple of (quolas_inference_dict, kalshi_inference_dict).
        """
        # Hot-swap check if dedicated Kalshi model has been minted
        self._check_kalshi_model_promotion()

        # QuoLas Spot inference
        if spot_tensor is not None:
            try:
                quolas_res = self.quolas_engine.process_feature_vector(spot_tensor)
            except Exception as exc:
                logger.error("[DUAL-ONNX] Spot tensor inference exception: %s", exc)
                quolas_res = _make_neutral_result(reason=f"Spot tensor inference error: {exc}")
        elif spot_book is not None and hasattr(spot_book, "get_depth"):
            try:
                quolas_res = self.quolas_engine.process_orderbook_tick(
                    book=spot_book,
                    latest_trades=latest_spot_trades,
                )
            except Exception as exc:
                logger.error("[DUAL-ONNX] Spot inference exception: %s", exc)
                quolas_res = _make_neutral_result(reason=f"Spot inference error: {exc}")
        elif self.matrix_builder is not None:
            try:
                tensor = self.matrix_builder.get_current_tensor()
                if tensor is not None and len(tensor) == 28 and any(tensor != 0):
                    quolas_res = self.quolas_engine.process_feature_vector(tensor)
                else:
                    quolas_res = _make_neutral_result(reason="MatrixBuilder tensor empty or uninitialized")
            except Exception as exc:
                logger.error("[DUAL-ONNX] MatrixBuilder inference exception: %s", exc)
                quolas_res = _make_neutral_result(reason=f"MatrixBuilder error: {exc}")
        else:
            quolas_res = _make_neutral_result(reason="Missing spot order book")

        # Kalshi inference
        if kalshi_book is not None and hasattr(kalshi_book, "get_depth"):
            try:
                kalshi_res = self.kalshi_engine.process_orderbook_tick(
                    book=kalshi_book,
                    latest_trades=latest_kalshi_trades,
                )
            except Exception as exc:
                logger.error("[DUAL-ONNX] Kalshi inference exception: %s", exc)
                kalshi_res = _make_neutral_result(reason=f"Kalshi inference error: {exc}")
        else:
            kalshi_res = _make_neutral_result(reason="Missing or invalid kalshi order book")

        return quolas_res, kalshi_res

    def get_status(self) -> Dict[str, Any]:
        """Return operational status of both neural engines."""
        return {
            "quolas_model": str(self.quolas_model_path),
            "quolas_ready": self.quolas_engine.session is not None,
            "kalshi_model": str(self.kalshi_model_path),
            "kalshi_ready": self.kalshi_engine.session is not None,
            "is_kalshi_fallback": self.is_kalshi_fallback,
        }

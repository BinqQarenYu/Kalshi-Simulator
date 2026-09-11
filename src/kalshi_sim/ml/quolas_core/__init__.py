"""QuoLas Core ML & Microstructure Subsystem for Kalshi Simulator.

Transplanted institutional components from QuoLas:
- OrderFlowIntegrity: CVD divergence, absorption, spoofing, VPIN PBC, OFI.
- NanoMatrixBuilder: 28-feature input tensor for nano_microscope_overhauled.onnx.
- StreamManager: Binance multi-stream WebSocket manager (@aggTrade, @depth@100ms, @bookTicker).
- HMMBrain: 3-state Gaussian HMM for macro market regime detection.
"""

from __future__ import annotations

from kalshi_sim.ml.quolas_core.candle_builder import Candle, CandleBuilder
from kalshi_sim.ml.quolas_core.config import (
    HMMConfig,
    OrderFlowConfig,
    QuoLasCoreConfig,
    StreamConfig,
)
from kalshi_sim.ml.quolas_core.hmm_brain import HMMBrain
from kalshi_sim.ml.quolas_core.nano_matrix_builder import NanoMatrixBuilder
from kalshi_sim.ml.quolas_core.order_flow import (
    DepthSnapshot,
    FlowSignal,
    FlowState,
    OrderFlowIntegrity,
    TradeEvent,
)
from kalshi_sim.ml.quolas_core.regime_types import MarketRegime
from kalshi_sim.ml.quolas_core.stream_manager import StreamManager

__all__ = [
    "Candle",
    "CandleBuilder",
    "DepthSnapshot",
    "FlowSignal",
    "FlowState",
    "HMMBrain",
    "HMMConfig",
    "MarketRegime",
    "NanoMatrixBuilder",
    "OrderFlowConfig",
    "OrderFlowIntegrity",
    "QuoLasCoreConfig",
    "StreamConfig",
    "StreamManager",
    "TradeEvent",
]

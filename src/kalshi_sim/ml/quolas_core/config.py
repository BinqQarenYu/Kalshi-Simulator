"""Configuration for QuoLas Core ML components in Kalshi Simulator.

Decoupled from external QuoLas settings to ensure full standalone portability
within the Kalshi Simulator environment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class OrderFlowConfig:
    """Microstructure and order flow integrity thresholds."""

    cvd_divergence_sigma: float = 2.0
    absorption_vol_multiplier: float = 2.5
    spoof_cancel_pct: float = 0.35
    spoof_cooldown_seconds: float = 15.0
    vpin_threshold: float = 0.80
    vpin_bucket_size: float = 2.0  # 2.0 BTC per bucket (VPIN PBC)
    ofi_threshold: float = 2.0


@dataclass
class StreamConfig:
    """Binance multi-stream WebSocket connectivity parameters."""

    testnet: bool = False
    base_url: str = "wss://fstream.binance.com"
    testnet_base_url: str = "wss://stream.binancefuture.com"
    ping_interval: int = 180  # 3 minutes
    ping_timeout: int = 30
    close_timeout: int = 10
    reconnect_base_delay: float = 1.0
    reconnect_max_delay: float = 60.0
    max_streams_per_connection: int = 200
    default_pairs: List[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"])


@dataclass
class HMMConfig:
    """Gaussian Hidden Markov Model regime detector hyperparameters."""

    n_states: int = 3
    n_features: int = 8  # 4 for BTC + 4 for PAXG (or multi-asset bundle)
    min_training_samples: int = 288  # 24h of 5m data
    covariance_type: str = "diag"
    n_iter: int = 50
    models_dir: Path = field(default_factory=lambda: Path("models"))
    model_filename: str = "hmm_latest.pkl"
    stale_hours: int = 48


@dataclass
class QuoLasCoreConfig:
    """Top-level configuration bundle for QuoLas Core."""

    order_flow: OrderFlowConfig = field(default_factory=OrderFlowConfig)
    stream: StreamConfig = field(default_factory=StreamConfig)
    hmm: HMMConfig = field(default_factory=HMMConfig)

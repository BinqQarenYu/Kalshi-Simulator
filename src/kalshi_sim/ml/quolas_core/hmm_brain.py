"""Hidden Markov Model Regime Detector (Transplanted from QuoLas Core).

Detects 3 macro market regimes using a Gaussian HMM:
- STABLE_RANGE (State 0): Low vol, mean-reverting chop (scalp / contradiction focus)
- VOL_EXPANSION (State 1): High vol, trending momentum (momentum scalp focus)
- RISK_OFF (State 2): Extreme stress / cascading liquidation (veto entry)

Provides graceful fallback and offline caching.
"""

from __future__ import annotations

import logging
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from hmmlearn.hmm import GaussianHMM
from numpy.typing import NDArray

from kalshi_sim.ml.quolas_core.config import HMMConfig
from kalshi_sim.ml.quolas_core.regime_types import MarketRegime

logger = logging.getLogger("kalshi_sim.ml.quolas_core.hmm_brain")


class HMMBrain:
    """Gaussian HMM regime detector for cryptocurrency microstructure."""

    N_STATES = 3
    MIN_TRAINING_SAMPLES = 288  # 24 hours of 5-minute data

    def __init__(self, config: Optional[HMMConfig] = None, model_dir: Optional[Path] = None) -> None:
        self.config = config or HMMConfig()
        self.model: Optional[GaussianHMM] = None
        self.current_regime: MarketRegime = MarketRegime.STABLE_RANGE
        self.regime_probabilities: NDArray = np.array([0.5, 0.5, 0.0], dtype=np.float64)
        self.last_train_time: Optional[datetime] = None
        self.state_mapping: Dict[int, MarketRegime] = {}
        self._boot_predicted: bool = False

        if model_dir is not None:
            self.model_path = Path(model_dir) / self.config.model_filename
        else:
            self.model_path = self.config.models_dir / self.config.model_filename

        self._load_model()

    def train(self, data_bundle: Dict[str, List[Dict]]) -> bool:
        """Train HMM on a bundle of asset candles (e.g., BTCUSDT)."""
        try:
            btc_data = data_bundle.get("BTCUSDT", data_bundle.get("BTC", []))
            if len(btc_data) < self.MIN_TRAINING_SAMPLES:
                logger.warning(
                    "Insufficient data for HMM training: %d < %d",
                    len(btc_data),
                    self.MIN_TRAINING_SAMPLES,
                )
                return False

            features = self._extract_features(btc_data)
            if features is None or len(features) < self.MIN_TRAINING_SAMPLES:
                return False

            model = GaussianHMM(
                n_components=self.N_STATES,
                covariance_type=self.config.covariance_type,
                n_iter=self.config.n_iter,
                random_state=42,
            )
            model.fit(features)

            self.state_mapping = self._map_states_to_regimes(model)
            self.model = model
            self.last_train_time = datetime.now(timezone.utc)
            self.predict_regime(data_bundle)
            self._save_model()
            logger.info("Successfully trained HMMBrain on %d samples (Initial regime: %s)", len(features), self.current_regime.name)
            return True
        except Exception as e:
            logger.error("HMM training failed: %s", e)
            return False

    def predict_regime(self, data_bundle: Dict[str, List[Dict]]) -> Tuple[MarketRegime, NDArray]:
        """Predict regime using recent candle data."""
        if self.model is None:
            return self.current_regime, self.regime_probabilities

        try:
            btc_data = data_bundle.get("BTCUSDT", data_bundle.get("BTC", []))
            features = self._extract_features(btc_data)
            if features is None or len(features) < 1:
                return self.current_regime, self.regime_probabilities

            posteriors = self.model.predict_proba(features)
            current_probs = posteriors[-1]
            raw_state = int(np.argmax(current_probs))

            old_regime = self.current_regime
            self.current_regime = self.state_mapping.get(raw_state, MarketRegime.VOL_EXPANSION)
            self.regime_probabilities = current_probs
            self._boot_predicted = True

            if old_regime != self.current_regime:
                logger.info(
                    "HMM regime transition: %s -> %s (confidence=%.2f)",
                    old_regime.name,
                    self.current_regime.name,
                    float(max(current_probs)),
                )
                self._save_model()

            return self.current_regime, current_probs
        except Exception as e:
            logger.error("HMM prediction failed: %s", e)
            return self.current_regime, self.regime_probabilities

    def get_status(self) -> Dict[str, Any]:
        """Return HMM brain telemetry for API and WebSocket broadcast."""
        probs = self.regime_probabilities
        return {
            "current_regime": self.current_regime.name,
            "regime_probabilities": {
                "STABLE_RANGE": round(float(probs[0]), 4) if len(probs) > 0 else 0.0,
                "VOL_EXPANSION": round(float(probs[1]), 4) if len(probs) > 1 else 0.0,
                "RISK_OFF": round(float(probs[2]), 4) if len(probs) > 2 else 0.0,
            },
            "is_fitted": self.model is not None,
            "last_train_time": self.last_train_time.isoformat() if self.last_train_time else None,
            "model_path": str(self.model_path),
        }

    def _extract_features(self, ohlcv_data: List[Dict]) -> Optional[NDArray]:
        """Extract [log_returns, realized_vol, vol_sma, funding] from OHLCV dictionaries."""
        try:
            if not ohlcv_data or len(ohlcv_data) < 2:
                return None

            closes = np.array([float(d["close"]) for d in ohlcv_data], dtype=np.float64)
            volumes = np.array([float(d.get("volume", 1.0)) for d in ohlcv_data], dtype=np.float64)

            # Avoid log(0)
            closes = np.maximum(closes, 1e-6)
            log_returns = np.diff(np.log(closes))

            window = min(288, len(log_returns))
            realized_vol = np.zeros(len(log_returns))
            for i in range(len(log_returns)):
                start = max(0, i - window + 1)
                realized_vol[i] = np.std(log_returns[start : i + 1]) if i > 0 else 0.0

            vol_sma = np.zeros(len(log_returns))
            for i in range(len(vol_sma)):
                start = max(0, i - window + 1)
                avg = np.mean(volumes[start : i + 1])
                vol_sma[i] = volumes[i + 1] / avg if avg > 0 else 1.0

            funding = np.array([float(d.get("funding_rate", 0.0)) for d in ohlcv_data[1:]], dtype=np.float64)
            features = np.column_stack([log_returns, realized_vol, vol_sma, funding])
            return np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
        except Exception as e:
            logger.error("HMM feature extraction error: %s", e)
            return None

    def _map_states_to_regimes(self, model: GaussianHMM) -> Dict[int, MarketRegime]:
        """Map HMM component indices to meaningful market regimes based on volatility and returns."""
        means = model.means_
        vol_sorted = np.argsort(means[:, 1])  # Ascending by realized vol

        mapping: Dict[int, MarketRegime] = {}
        mapping[int(vol_sorted[0])] = MarketRegime.STABLE_RANGE  # Lowest vol = stable range

        high_vol_states = vol_sorted[1:]
        for state_idx in high_vol_states:
            s_idx = int(state_idx)
            mean_return = float(means[s_idx, 0])
            mean_vol = float(means[s_idx, 1])
            baseline_vol = float(means[int(vol_sorted[0]), 1])

            if mean_return < -0.001 and mean_vol > baseline_vol * 2.0:
                mapping[s_idx] = MarketRegime.RISK_OFF
            else:
                mapping[s_idx] = MarketRegime.VOL_EXPANSION

        for i in range(self.N_STATES):
            if i not in mapping:
                mapping[i] = MarketRegime.VOL_EXPANSION

        return mapping

    def _save_model(self) -> None:
        """Persist model to disk safely."""
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.model_path, "wb") as f:
                pickle.dump(
                    {
                        "model": self.model,
                        "state_mapping": self.state_mapping,
                        "last_train_time": self.last_train_time,
                        "current_regime": self.current_regime,
                        "regime_probabilities": self.regime_probabilities,
                    },
                    f,
                )
            logger.info("Saved HMM model to %s", self.model_path)
        except Exception as e:
            logger.error("Failed to save HMM model: %s", e)

    def _load_model(self) -> None:
        """Load persisted model if available."""
        if self.model_path.exists():
            try:
                with open(self.model_path, "rb") as f:
                    data = pickle.load(f)
                    self.model = data.get("model")
                    self.state_mapping = data.get("state_mapping", {})
                    self.last_train_time = data.get("last_train_time")
                    self.current_regime = data.get("current_regime", self.current_regime)
                    self.regime_probabilities = data.get("regime_probabilities", self.regime_probabilities)
                logger.info("Loaded HMM model from %s", self.model_path)
            except Exception as e:
                logger.warning("Could not load HMM model from %s: %s", self.model_path, e)

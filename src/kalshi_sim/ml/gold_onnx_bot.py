"""Gold 32-D ONNX Spacetime Inference Bot (QuoLasGoldONNXBot).

Executes ultra-low latency (<0.8ms) SIMD ONNX Runtime inference on 32-dimensional
orderflow and spacetime physics tensors for Kalshi 15M Gold (KXGOLD15M).

Inference & Risk Invariants:
1. Directional Conviction Gate: Requires P(direction) >= 0.70 (70% model confidence).
2. Dynamic Moat & Dead-Zone Check: Distance from strike |S_t - K| >= $0.75 threshold.
3. Flow Toxicity Veto: Blocks entries when VPIN >= 0.60.
4. Spot Velocity Shield: Rejects entries when 5-second spot velocity exceeds $0.50/oz.
5. Macro Blackout: Strict embargo during US economic releases (CPI/NFP/FOMC).
6. Micro-Bankroll Sizing Armor: Strictly 1 contract per trade.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import onnxruntime as ort

from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.ml.export_gold_onnx import DEFAULT_GOLD_MODEL_PATH, export_gold_to_onnx
from kalshi_sim.ml.gold_feature_extractor import GoldOrderflowFeatureExtractor
from kalshi_sim.ml.gold_inversion_bot import GoldInversionDecision
from kalshi_sim.schemas import (
    CryptoAsset,
    L2BookState,
    MarketInfo,
    OrderSide,
    OrderType,
    TradeEvent,
)

logger = logging.getLogger("GoldONNXBot")


class GoldONNXBot:
    """Institutional 32-D ONNX inference trading bot for Kalshi Gold contracts."""

    def __init__(
        self,
        model_path: Union[str, Path] = DEFAULT_GOLD_MODEL_PATH,
        min_confidence: float = 0.70,
        dead_zone_gold_usd: Decimal = Decimal("0.75"),
        spot_velocity_limit: Decimal = Decimal("0.50"),
        max_vpin_threshold: float = 0.60,
        max_contracts: int = 1,
        entry_price: Decimal = Decimal("0.50"),
    ) -> None:
        self.model_path = Path(model_path)
        self.min_confidence = min_confidence
        self.dead_zone_gold_usd = dead_zone_gold_usd
        self.spot_velocity_limit = spot_velocity_limit
        self.max_vpin_threshold = max_vpin_threshold
        self.max_contracts = max_contracts
        self.entry_price = entry_price

        # Feature extractor instance
        self.extractor = GoldOrderflowFeatureExtractor(target_depth=15, default_gold_volatility=2.50)

        # Rolling state for velocity & TWAP
        self._spot_history: List[Tuple[float, Decimal]] = []
        self._twap_buffer: List[Decimal] = []

        # ONNX Runtime session with single-threaded CPU configuration
        self.session: Optional[ort.InferenceSession] = None
        self._init_session()

    def _init_session(self) -> None:
        """Initialize or reload single-threaded ONNX inference session."""
        if not self.model_path.exists():
            logger.info("Gold ONNX model %s not found. Auto-generating base model...", self.model_path)
            export_gold_to_onnx(output_path=self.model_path, verify_parity=True)

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.session = ort.InferenceSession(
            str(self.model_path),
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )
        logger.info("QuoLasGoldONNXBot initialized ONNX Session from %s", self.model_path)

    def reload_model(self) -> None:
        """Hot-reload ONNX weights after a new continuous training promotion."""
        try:
            self._init_session()
            logger.info("Successfully reloaded ONNX model from %s", self.model_path)
        except Exception as e:
            logger.error("Failed hot-reloading ONNX model: %s", e)

    def update_spot(self, ts: float, spot_price: Decimal) -> None:
        """Update spot history for 5-second velocity calculation."""
        self._spot_history.append((ts, spot_price))
        cutoff = ts - 10.0
        self._spot_history = [(t, p) for t, p in self._spot_history if t >= cutoff]

        self._twap_buffer.append(spot_price)
        if len(self._twap_buffer) > 60:
            self._twap_buffer.pop(0)

    def get_spot_velocity(self) -> Decimal:
        """Calculate maximum price change over the last 5 seconds."""
        if len(self._spot_history) < 2:
            return Decimal("0.00")
        now_ts = self._spot_history[-1][0]
        recent = [p for t, p in self._spot_history if t >= now_ts - 5.0]
        if len(recent) < 2:
            return Decimal("0.00")
        return max(recent) - min(recent)

    def get_twap_60s(self) -> Optional[Decimal]:
        """Compute rolling 60-second TWAP."""
        if not self._twap_buffer:
            return None
        return sum(self._twap_buffer) / Decimal(str(len(self._twap_buffer)))

    def infer(self, features: np.ndarray) -> np.ndarray:
        """Run forward inference returning [P(UP), P(DOWN), P(WAIT)]."""
        if self.session is None:
            self._init_session()
        assert self.session is not None

        input_name = self.session.get_inputs()[0].name
        batch = np.expand_dims(features.astype(np.float32), axis=0)  # Shape (1, 32)
        outputs = self.session.run(None, {input_name: batch})[0]     # Shape (1, 3)
        return outputs[0]

    def decide(
        self,
        market: MarketInfo,
        orderbook: Optional[L2BookState],
        spot_price: Decimal,
        time_remaining_s: int,
        ofi_imbalance: float = 0.0,
        now_utc: Optional[datetime] = None,
        latest_trades: Optional[List[TradeEvent]] = None,
    ) -> GoldInversionDecision:
        """Evaluate 32-D features and produce a trading decision."""
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)

        # 1. Update spot history
        self.update_spot(now_utc.timestamp(), spot_price)

        # 2. Macro Blackout Check
        guardrails = AgentGuardrails()
        is_blackout, blackout_reason = guardrails.verify_macro_event_embargo(
            ticker_or_asset="KXGOLD15M", now_dt=now_utc
        )
        if is_blackout:
            return GoldInversionDecision(
                action="WAIT",
                rationale=f"[MACRO BLACKOUT] {blackout_reason}",
            )

        # 3. Spot Velocity Shield
        vel = self.get_spot_velocity()
        if vel > self.spot_velocity_limit:
            return GoldInversionDecision(
                action="WAIT",
                rationale=(
                    f"[VELOCITY SHIELD] Spot 5s volatility ${vel:.2f} exceeds "
                    f"limit ${self.spot_velocity_limit:.2f}."
                ),
            )

        # 4. Timing Window Gate: 120s <= T <= 480s
        if time_remaining_s > 480:
            return GoldInversionDecision(
                action="WAIT",
                rationale=f"[TIMING GATE] Awaiting late-cycle window (T={time_remaining_s}s > 480s).",
            )
        if time_remaining_s < 120:
            return GoldInversionDecision(
                action="WAIT",
                rationale=f"[TIMING GATE] Expiration quarantine (T={time_remaining_s}s < 120s).",
            )

        # 5. Strike Extraction
        strike = getattr(market, "target_strike", None) or getattr(market, "floor_strike", None)
        if strike is None or strike <= Decimal("0.00"):
            return GoldInversionDecision(
                action="WAIT",
                rationale="[DATA ERROR] Market strike price missing or invalid.",
            )

        # 6. Extract 32-D Feature Tensor
        twap_60s = self.get_twap_60s()
        if orderbook is None:
            return GoldInversionDecision(
                action="WAIT",
                rationale="[DATA ERROR] Orderbook state unavailable for 32-D feature extraction.",
            )

        features = self.extractor.extract_features(
            book=orderbook,
            latest_trades=latest_trades,
            target_strike=strike,
            current_spot=spot_price,
            time_to_expiry_s=float(time_remaining_s),
            twap_60s=twap_60s,
            spot_volatility=2.50,
        )

        # 7. VPIN Flow Toxicity Gate
        vpin_score = features[6]
        if vpin_score >= self.max_vpin_threshold:
            return GoldInversionDecision(
                action="WAIT",
                rationale=f"[FLOW TOXICITY VETO] VPIN {vpin_score:.2f} >= threshold {self.max_vpin_threshold:.2f}.",
            )

        # 8. Run 32-D ONNX Inference
        probs = self.infer(features)
        p_up, p_down, p_wait = float(probs[0]), float(probs[1]), float(probs[2])

        spot_diff = spot_price - strike

        # 9. Evaluate UP (BUY_YES) Signal
        if p_up >= self.min_confidence:
            # Dynamic Moat / Dead-zone check:
            # If spot is significantly below strike, don't buy YES even if model says UP unless spot >= strike - dead_zone
            if spot_diff < -self.dead_zone_gold_usd:
                return GoldInversionDecision(
                    action="WAIT",
                    rationale=(
                        f"[DEAD-ZONE VETO] Spot Diff ${spot_diff:+.2f} below dead-zone "
                        f"-${self.dead_zone_gold_usd:.2f} despite P(UP)={p_up:.1%}"
                    ),
                )

            limit_p = Decimal("0.50")
            if orderbook.best_yes_ask and orderbook.best_yes_ask <= Decimal("0.52"):
                limit_p = orderbook.best_yes_ask

            return GoldInversionDecision(
                action="BUY",
                side=OrderSide.YES,
                price=limit_p,
                contracts=self.max_contracts,
                order_type=OrderType.LIMIT,
                confidence=p_up * 100.0,
                edge_pct=(p_up - 0.50) * 100.0,
                rationale=(
                    f"[32-D ONNX YES] P(UP)={p_up:.1%} >= {self.min_confidence:.0%} | "
                    f"Spot Diff: ${spot_diff:+.2f} | T={time_remaining_s}s | Limit: ${limit_p:.2f}"
                ),
                playbook="QuoLas 32-D ONNX Spacetime Dominance (YES)",
            )

        # 10. Evaluate DOWN (BUY_NO) Signal
        if p_down >= self.min_confidence:
            # Dynamic Moat / Dead-zone check:
            # If spot is significantly above strike, don't buy NO unless spot <= strike + dead_zone
            if spot_diff > self.dead_zone_gold_usd:
                return GoldInversionDecision(
                    action="WAIT",
                    rationale=(
                        f"[DEAD-ZONE VETO] Spot Diff ${spot_diff:+.2f} above dead-zone "
                        f"+${self.dead_zone_gold_usd:.2f} despite P(DOWN)={p_down:.1%}"
                    ),
                )

            limit_p = Decimal("0.50")
            if orderbook.best_no_ask and orderbook.best_no_ask <= Decimal("0.52"):
                limit_p = orderbook.best_no_ask

            return GoldInversionDecision(
                action="BUY",
                side=OrderSide.NO,
                price=limit_p,
                contracts=self.max_contracts,
                order_type=OrderType.LIMIT,
                confidence=p_down * 100.0,
                edge_pct=(p_down - 0.50) * 100.0,
                rationale=(
                    f"[32-D ONNX NO] P(DOWN)={p_down:.1%} >= {self.min_confidence:.0%} | "
                    f"Spot Diff: ${spot_diff:+.2f} | T={time_remaining_s}s | Limit: ${limit_p:.2f}"
                ),
                playbook="QuoLas 32-D ONNX Spacetime Dominance (NO)",
            )

        # 11. Low conviction or WAIT class winner
        return GoldInversionDecision(
            action="WAIT",
            rationale=(
                f"[32-D ONNX MONITOR] Low Conviction: P(UP)={p_up:.1%}, P(DOWN)={p_down:.1%}, "
                f"P(WAIT)={p_wait:.1%} (Hurdle {self.min_confidence:.0%})"
            ),
        )

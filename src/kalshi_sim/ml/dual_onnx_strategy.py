"""Dual-ONNX Contradiction Arbitrage Strategy Engine.

Exploits microsecond lead-lag latency discrepancies between the institutional Spot BTC
orderbook (QuoLas Nano Microscope Brain) and Kalshi's retail CLOB (Kalshi Brain).

Contradiction Matrix:
- QuoLas UP + Kalshi UP   -> MOMENTUM_SCALP (BUY_YES)
- QuoLas DOWN + Kalshi DOWN -> MOMENTUM_SCALP (BUY_NO)
- QuoLas UP + Kalshi DOWN -> CONTRADICTION_ARBITRAGE (BUY_YES at discount <= discount_ceiling)
- QuoLas DOWN + Kalshi UP -> CONTRADICTION_ARBITRAGE (BUY_NO at discount <= discount_ceiling)
- Spot WAIT or VPIN Toxic -> CHOP_WAIT / TOXIC_VETO (HOLD)
"""

from __future__ import annotations

import logging
import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple, Union

from kalshi_sim.ml.dual_onnx_gateway import DualONNXGateway
from kalshi_sim.ml.dual_onnx_schemas import DualONNXDecision, DualONNXRegime
from kalshi_sim.schemas import CryptoAsset, L2BookState, OrderSide, TradeEvent

logger = logging.getLogger("kalshi_sim.dual_onnx_strategy")


def _standard_normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function Phi(x)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _classify_signal(sig: str) -> str:
    """Normalize raw model signal to 'UP', 'DOWN', or 'WAIT'."""
    s = str(sig).strip().upper()
    if s in ("LONG", "UP", "BUY", "YES"):
        return "UP"
    if s in ("SHORT", "DOWN", "SELL", "NO"):
        return "DOWN"
    return "WAIT"


class DualONNXArbitrageBot:
    """Institutional High-Frequency Dual-ONNX Contradiction Arbitrage Strategy Engine."""

    STRATEGY_ID = "dual_onnx_contradiction"
    STRATEGY_NAME = "Dual-ONNX Contradiction Arbitrage"

    def __init__(
        self,
        gateway: Optional[DualONNXGateway] = None,
        discount_ceiling: Decimal = Decimal("0.48"),
        momentum_max_price: Decimal = Decimal("0.62"),
        min_ev_dollars: Decimal = Decimal("0.02"),
        min_confidence: float = 0.52,
        vpin_toxic_threshold: float = 0.70,
        fee_per_contract: Decimal = Decimal("0.01"),
        typical_1m_volatility: float = 14.0,
        asset: Union[CryptoAsset, str] = CryptoAsset.BTC,
    ) -> None:
        self.gateway = gateway or DualONNXGateway()
        self.discount_ceiling = Decimal(str(discount_ceiling))
        self.momentum_max_price = Decimal(str(momentum_max_price))
        self.min_ev_dollars = Decimal(str(min_ev_dollars))
        self.min_confidence = float(min_confidence)
        self.vpin_toxic_threshold = float(vpin_toxic_threshold)
        self.fee_per_contract = Decimal(str(fee_per_contract))
        self.typical_1m_volatility = float(typical_1m_volatility)
        self.asset = CryptoAsset(str(asset).upper()) if not isinstance(asset, CryptoAsset) else asset

    def get_parameters(self) -> Dict[str, Any]:
        """Return current live strategy parameters."""
        return {
            "strategy_id": self.STRATEGY_ID,
            "strategy_name": self.STRATEGY_NAME,
            "asset": self.asset.value,
            "discount_ceiling": float(self.discount_ceiling),
            "momentum_max_price": float(self.momentum_max_price),
            "min_ev_dollars": float(self.min_ev_dollars),
            "min_confidence": round(self.min_confidence, 4),
            "vpin_toxic_threshold": round(self.vpin_toxic_threshold, 3),
            "fee_per_contract": float(self.fee_per_contract),
            "typical_1m_volatility": self.typical_1m_volatility,
        }

    def update_parameters(
        self,
        discount_ceiling: Optional[Union[float, Decimal, str]] = None,
        momentum_max_price: Optional[Union[float, Decimal, str]] = None,
        min_ev_dollars: Optional[Union[float, Decimal, str]] = None,
        min_confidence: Optional[float] = None,
        vpin_toxic_threshold: Optional[float] = None,
        fee_per_contract: Optional[Union[float, Decimal, str]] = None,
        typical_1m_volatility: Optional[float] = None,
        asset: Optional[Union[CryptoAsset, str]] = None,
    ) -> Dict[str, Any]:
        """Dynamically update strategy parameters on the fly."""
        if discount_ceiling is not None:
            self.discount_ceiling = max(Decimal("0.10"), min(Decimal("0.85"), Decimal(str(discount_ceiling))))
        if momentum_max_price is not None:
            self.momentum_max_price = max(Decimal("0.50"), min(Decimal("0.85"), Decimal(str(momentum_max_price))))
        if min_ev_dollars is not None:
            self.min_ev_dollars = max(Decimal("0.00"), min(Decimal("0.50"), Decimal(str(min_ev_dollars))))
        if min_confidence is not None:
            self.min_confidence = max(0.34, min(0.99, float(min_confidence)))
        if vpin_toxic_threshold is not None:
            self.vpin_toxic_threshold = max(0.40, min(0.95, float(vpin_toxic_threshold)))
        if fee_per_contract is not None:
            self.fee_per_contract = max(Decimal("0.00"), Decimal(str(fee_per_contract)))
        if typical_1m_volatility is not None:
            self.typical_1m_volatility = max(1.0, float(typical_1m_volatility))
        if asset is not None:
            self.asset = CryptoAsset(str(asset).upper()) if not isinstance(asset, CryptoAsset) else asset

        logger.info("[DUAL-ONNX BOT] Parameters updated: %s", self.get_parameters())
        return self.get_parameters()

    def evaluate(
        self,
        market_state: Any = None,
        spot_l2: Optional[L2BookState] = None,
        kalshi_l2: Optional[L2BookState] = None,
        time_to_expiry_s: float = 300.0,
        spot_diff: float = 0.0,
        quolas_inference: Optional[Dict[str, Any]] = None,
        kalshi_inference: Optional[Dict[str, Any]] = None,
        latest_spot_trades: Optional[List[TradeEvent]] = None,
        latest_kalshi_trades: Optional[List[TradeEvent]] = None,
    ) -> DualONNXDecision:
        """Evaluate market state and L2 books through the Contradiction Arbitrage Engine.

        Returns a frozen DualONNXDecision with action, regime, limit price, and EV.
        """
        # 1. Order book validation
        if spot_l2 is None or kalshi_l2 is None:
            return DualONNXDecision(
                action="HOLD",
                regime=DualONNXRegime.CHOP_WAIT,
                side=None,
                quolas_signal="WAIT",
                quolas_confidence=0.0,
                kalshi_signal="WAIT",
                kalshi_confidence=0.0,
                recommended_limit_price=Decimal("0.00"),
                expected_value=Decimal("0.00"),
                recommended_contracts=0,
                rationale="Missing Spot or Kalshi Level-2 order book.",
            )

        if time_to_expiry_s <= 0:
            return DualONNXDecision(
                action="HOLD",
                regime=DualONNXRegime.CHOP_WAIT,
                side=None,
                quolas_signal="WAIT",
                quolas_confidence=0.0,
                kalshi_signal="WAIT",
                kalshi_confidence=0.0,
                recommended_limit_price=Decimal("0.00"),
                expected_value=Decimal("0.00"),
                recommended_contracts=0,
                rationale="Market cycle has already expired.",
            )

        # 2. Dual ONNX Inference
        if quolas_inference is None or kalshi_inference is None:
            q_res, k_res = self.gateway.infer_both(
                spot_book=spot_l2,
                kalshi_book=kalshi_l2,
                latest_spot_trades=latest_spot_trades,
                latest_kalshi_trades=latest_kalshi_trades,
            )
            q_res = quolas_inference if quolas_inference is not None else q_res
            k_res = kalshi_inference if kalshi_inference is not None else k_res
        else:
            q_res = quolas_inference
            k_res = kalshi_inference

        q_raw_sig = q_res.get("signal", "WAIT")
        k_raw_sig = k_res.get("signal", "WAIT")
        q_conf = float(q_res.get("confidence", 0.0))
        k_conf = float(k_res.get("confidence", 0.0))
        q_vpin = float(q_res.get("vpin_score", 0.0))
        k_vpin = float(k_res.get("vpin_score", 0.0))
        q_veto = bool(q_res.get("vpin_veto", False)) or (q_vpin > self.vpin_toxic_threshold)
        k_veto = bool(k_res.get("vpin_veto", False)) or (k_vpin > self.vpin_toxic_threshold)

        q_sig = _classify_signal(q_raw_sig)
        k_sig = _classify_signal(k_raw_sig)

        # 3. Microstructural Toxicity Veto Check
        if q_veto or k_veto:
            toxic_source = "Spot" if q_veto else "Kalshi"
            score = q_vpin if q_veto else k_vpin
            return DualONNXDecision(
                action="HOLD",
                regime=DualONNXRegime.TOXIC_VETO,
                side=None,
                quolas_signal=q_sig,
                quolas_confidence=q_conf,
                kalshi_signal=k_sig,
                kalshi_confidence=k_conf,
                recommended_limit_price=Decimal("0.00"),
                expected_value=Decimal("0.00"),
                recommended_contracts=0,
                rationale=f"Toxic flow veto: {toxic_source} VPIN toxicity ({score:.3f} > {self.vpin_toxic_threshold:.3f}).",
            )

        # 4. Spot Conviction Filter
        # Spot Brain is the source of truth for price discovery. If Spot is WAIT or below confidence threshold, CHOP_WAIT
        if q_sig == "WAIT" or q_conf < self.min_confidence:
            return DualONNXDecision(
                action="HOLD",
                regime=DualONNXRegime.CHOP_WAIT,
                side=None,
                quolas_signal=q_sig,
                quolas_confidence=q_conf,
                kalshi_signal=k_sig,
                kalshi_confidence=k_conf,
                recommended_limit_price=Decimal("0.00"),
                expected_value=Decimal("0.00"),
                recommended_contracts=0,
                rationale=f"Spot brain neutral or low confidence ({q_conf:.2f} < {self.min_confidence:.2f}).",
            )

        # 5. Extract Best Bids and Asks on Kalshi CLOB
        best_yes_ask = kalshi_l2.best_yes_ask
        best_yes_bid = kalshi_l2.best_yes_bid
        best_no_ask = kalshi_l2.best_no_ask
        best_no_bid = kalshi_l2.best_no_bid

        # If direct NO book prices are missing, derive from complementary YES book
        if best_no_ask is None and best_yes_bid is not None:
            best_no_ask = Decimal("1.00") - best_yes_bid
        if best_no_bid is None and best_yes_ask is not None:
            best_no_bid = Decimal("1.00") - best_yes_ask

        # 6. Estimate Probability of Win (Analytical Spot Diffusion + ONNX Confidence)
        # Spot digital probability: Phi(spot_diff / (sigma * sqrt(T/60)))
        t_minutes = max(0.1, time_to_expiry_s / 60.0)
        sigma_t = max(1.0, self.typical_1m_volatility * math.sqrt(t_minutes))
        z_score = spot_diff / sigma_t
        p_spot_digital = _standard_normal_cdf(z_score)

        # 7. Evaluate the Contradiction Matrix
        # Case A: Both UP -> MOMENTUM_SCALP (BUY_YES)
        if q_sig == "UP" and k_sig == "UP":
            regime = DualONNXRegime.MOMENTUM_SCALP
            action = "BUY_YES"
            side = "yes"

            # Probability of winning YES
            p_win = 0.60 * q_conf + 0.20 * k_conf + 0.20 * p_spot_digital
            p_win = max(0.05, min(0.95, p_win))

            # Limit Price: Willing to take marketable ask up to momentum_max_price
            if best_yes_ask is not None and best_yes_ask <= self.momentum_max_price:
                limit_price = best_yes_ask
            elif best_yes_bid is not None:
                limit_price = min(self.momentum_max_price, best_yes_bid + Decimal("0.01"))
            else:
                limit_price = Decimal("0.50")

            # EV Calculation: p_win * ($1.00 - price) - (1 - p_win) * price - fee
            # Simplifies to: p_win * $1.00 - price - fee
            ev = Decimal(str(p_win)) * Decimal("1.00") - limit_price - self.fee_per_contract

            if ev < self.min_ev_dollars:
                return DualONNXDecision(
                    action="HOLD",
                    regime=regime,
                    side=side,
                    quolas_signal=q_sig,
                    quolas_confidence=q_conf,
                    kalshi_signal=k_sig,
                    kalshi_confidence=k_conf,
                    recommended_limit_price=limit_price,
                    expected_value=ev,
                    recommended_contracts=0,
                    rationale=f"Momentum Scalp EV ${ev:.3f} below minimum ${self.min_ev_dollars:.3f}.",
                )

            return DualONNXDecision(
                action=action,
                regime=regime,
                side=side,
                quolas_signal=q_sig,
                quolas_confidence=q_conf,
                kalshi_signal=k_sig,
                kalshi_confidence=k_conf,
                recommended_limit_price=limit_price,
                expected_value=ev.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
                recommended_contracts=1,
                rationale=f"Dual UP Momentum Scalp: Spot ({q_conf:.2f}) & Kalshi ({k_conf:.2f}) aligned | Limit: ${limit_price:.2f} | EV: +${ev:.2f}.",
            )

        # Case B: Both DOWN -> MOMENTUM_SCALP (BUY_NO)
        if q_sig == "DOWN" and k_sig == "DOWN":
            regime = DualONNXRegime.MOMENTUM_SCALP
            action = "BUY_NO"
            side = "no"

            # Probability of winning NO: (1 - p_spot_digital)
            p_win = 0.60 * q_conf + 0.20 * k_conf + 0.20 * (1.0 - p_spot_digital)
            p_win = max(0.05, min(0.95, p_win))

            if best_no_ask is not None and best_no_ask <= self.momentum_max_price:
                limit_price = best_no_ask
            elif best_no_bid is not None:
                limit_price = min(self.momentum_max_price, best_no_bid + Decimal("0.01"))
            else:
                limit_price = Decimal("0.50")

            ev = Decimal(str(p_win)) * Decimal("1.00") - limit_price - self.fee_per_contract

            if ev < self.min_ev_dollars:
                return DualONNXDecision(
                    action="HOLD",
                    regime=regime,
                    side=side,
                    quolas_signal=q_sig,
                    quolas_confidence=q_conf,
                    kalshi_signal=k_sig,
                    kalshi_confidence=k_conf,
                    recommended_limit_price=limit_price,
                    expected_value=ev,
                    recommended_contracts=0,
                    rationale=f"Momentum Scalp EV ${ev:.3f} below minimum ${self.min_ev_dollars:.3f}.",
                )

            return DualONNXDecision(
                action=action,
                regime=regime,
                side=side,
                quolas_signal=q_sig,
                quolas_confidence=q_conf,
                kalshi_signal=k_sig,
                kalshi_confidence=k_conf,
                recommended_limit_price=limit_price,
                expected_value=ev.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
                recommended_contracts=1,
                rationale=f"Dual DOWN Momentum Scalp: Spot ({q_conf:.2f}) & Kalshi ({k_conf:.2f}) aligned | Limit: ${limit_price:.2f} | EV: +${ev:.2f}.",
            )

        # Case C: Spot UP, Kalshi DOWN -> CONTRADICTION_ARBITRAGE (BUY_YES at discount)
        if q_sig == "UP" and k_sig in ("DOWN", "WAIT"):
            regime = DualONNXRegime.CONTRADICTION_ARBITRAGE
            action = "BUY_YES"
            side = "yes"

            # QuoLas Spot Brain is the leader: 80% weight on QuoLas conviction, 20% on spot drift
            p_win = 0.80 * q_conf + 0.20 * p_spot_digital
            p_win = max(0.10, min(0.95, p_win))

            # Contradiction Arbitrage limit pricing:
            # We strictly demand a discount <= discount_ceiling (e.g. $0.48).
            # If best ask is available and <= discount_ceiling, execute immediately at best ask.
            # Otherwise, place a passive limit order at discount_ceiling.
            if best_yes_ask is not None and best_yes_ask <= self.discount_ceiling:
                limit_price = best_yes_ask
            else:
                limit_price = self.discount_ceiling

            ev = Decimal(str(p_win)) * Decimal("1.00") - limit_price - self.fee_per_contract

            if ev < self.min_ev_dollars:
                return DualONNXDecision(
                    action="HOLD",
                    regime=regime,
                    side=side,
                    quolas_signal=q_sig,
                    quolas_confidence=q_conf,
                    kalshi_signal=k_sig,
                    kalshi_confidence=k_conf,
                    recommended_limit_price=limit_price,
                    expected_value=ev,
                    recommended_contracts=0,
                    rationale=f"Contradiction Arbitrage EV ${ev:.3f} below minimum ${self.min_ev_dollars:.3f}.",
                )

            return DualONNXDecision(
                action=action,
                regime=regime,
                side=side,
                quolas_signal=q_sig,
                quolas_confidence=q_conf,
                kalshi_signal=k_sig,
                kalshi_confidence=k_conf,
                recommended_limit_price=limit_price,
                expected_value=ev.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
                recommended_contracts=1,
                rationale=f"Contradiction Arbitrage: Spot UP ({q_conf:.2f}) vs Kalshi {k_sig} ({k_conf:.2f}) | Sniping discount YES at ${limit_price:.2f} <= ${self.discount_ceiling:.2f} | EV: +${ev:.2f}.",
            )

        # Case D: Spot DOWN, Kalshi UP -> CONTRADICTION_ARBITRAGE (BUY_NO at discount)
        if q_sig == "DOWN" and k_sig in ("UP", "WAIT"):
            regime = DualONNXRegime.CONTRADICTION_ARBITRAGE
            action = "BUY_NO"
            side = "no"

            # QuoLas Spot Brain is the leader: 80% weight on Spot, 20% on spot drift
            p_win = 0.80 * q_conf + 0.20 * (1.0 - p_spot_digital)
            p_win = max(0.10, min(0.95, p_win))

            if best_no_ask is not None and best_no_ask <= self.discount_ceiling:
                limit_price = best_no_ask
            else:
                limit_price = self.discount_ceiling

            ev = Decimal(str(p_win)) * Decimal("1.00") - limit_price - self.fee_per_contract

            if ev < self.min_ev_dollars:
                return DualONNXDecision(
                    action="HOLD",
                    regime=regime,
                    side=side,
                    quolas_signal=q_sig,
                    quolas_confidence=q_conf,
                    kalshi_signal=k_sig,
                    kalshi_confidence=k_conf,
                    recommended_limit_price=limit_price,
                    expected_value=ev,
                    recommended_contracts=0,
                    rationale=f"Contradiction Arbitrage EV ${ev:.3f} below minimum ${self.min_ev_dollars:.3f}.",
                )

            return DualONNXDecision(
                action=action,
                regime=regime,
                side=side,
                quolas_signal=q_sig,
                quolas_confidence=q_conf,
                kalshi_signal=k_sig,
                kalshi_confidence=k_conf,
                recommended_limit_price=limit_price,
                expected_value=ev.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
                recommended_contracts=1,
                rationale=f"Contradiction Arbitrage: Spot DOWN ({q_conf:.2f}) vs Kalshi {k_sig} ({k_conf:.2f}) | Sniping discount NO at ${limit_price:.2f} <= ${self.discount_ceiling:.2f} | EV: +${ev:.2f}.",
            )

        # Fallback default: CHOP_WAIT
        return DualONNXDecision(
            action="HOLD",
            regime=DualONNXRegime.CHOP_WAIT,
            side=None,
            quolas_signal=q_sig,
            quolas_confidence=q_conf,
            kalshi_signal=k_sig,
            kalshi_confidence=k_conf,
            recommended_limit_price=Decimal("0.00"),
            expected_value=Decimal("0.00"),
            recommended_contracts=0,
            rationale=f"Indeterminate market state: Spot {q_sig} ({q_conf:.2f}), Kalshi {k_sig} ({k_conf:.2f}).",
        )

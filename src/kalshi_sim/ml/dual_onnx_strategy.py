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


def calculate_kalshi_taker_fee(price: Union[Decimal, float], contracts: int = 1) -> Decimal:
    """Calculate authentic Kalshi CFTC taker fee with $0.01 floor and $0.02 cap per contract.
    Formula: ceil(0.07 * C * P * (1 - P))
    """
    p = float(price)
    c = float(contracts)
    raw = 0.07 * c * p * (1.0 - p)
    cents = math.ceil(round(raw * 100.0, 6))
    fee_per_ct = max(1, min(2, cents))
    return (Decimal(str(fee_per_ct * contracts)) / Decimal("100")).quantize(Decimal("0.01"))


class DualONNXArbitrageBot:
    """The ONNX Strategy: Institutional High-Frequency Dual-Brain Arbitrage Engine."""

    STRATEGY_ID = "the_onnx_strategy"
    STRATEGY_NAME = "The ONNX Strategy"

    def __init__(
        self,
        gateway: Optional[DualONNXGateway] = None,
        discount_ceiling: Decimal = Decimal("0.52"),
        entry_discount_depth: Optional[Union[Decimal, float, str]] = None,
        momentum_max_price: Decimal = Decimal("0.62"),
        min_ev_dollars: Decimal = Decimal("0.02"),
        min_confidence: float = 0.60,
        brain_priority_mode: str = "TREND_ALIGNED_SCALP",
        contract_scaling_mode: str = "TIER_0_STRICT_1",
        volatility_floor: Decimal = Decimal("10.0"),
        volatility_ceiling: Decimal = Decimal("45.0"),
        tape_confirmation_ticks: int = 2,
        taker_cross_ev_threshold: Decimal = Decimal("0.04"),
        dynamic_moat_multiplier: float = 1.36,
        vpin_toxic_threshold: float = 0.70,
        fee_per_contract: Decimal = Decimal("0.01"),
        typical_1m_volatility: float = 14.0,
        asset: Union[CryptoAsset, str] = CryptoAsset.BTC,
        hmm_brain: Optional[Any] = None,
        max_temporal_skew_ms: float = 1000.0,
        gamma_cliff_seconds: float = 90.0,
        auto_cancel_on_veto: bool = True,
        dynamic_volatility_mode: str = "REALIZED_ATR",
        candle_builder: Optional[Any] = None,
    ) -> None:
        self.gateway = gateway or DualONNXGateway()
        self.hmm_brain = hmm_brain
        self.candle_builder = candle_builder
        self.max_temporal_skew_ms = float(max_temporal_skew_ms)
        self.gamma_cliff_seconds = float(gamma_cliff_seconds)
        self.auto_cancel_on_veto = bool(auto_cancel_on_veto)
        self.dynamic_volatility_mode = str(dynamic_volatility_mode).upper()
        self.last_temporal_skew_ms: float = 0.0
        self.is_temporally_synced: bool = True
        self.slower_brain: str = "IN_SYNC"
        effective_discount = entry_discount_depth if entry_discount_depth is not None else discount_ceiling
        self.entry_discount_depth = Decimal(str(effective_discount))
        self.discount_ceiling = self.entry_discount_depth
        self.momentum_max_price = Decimal(str(momentum_max_price))
        self.min_ev_dollars = Decimal(str(min_ev_dollars))
        self.min_confidence = float(min_confidence)
        self.brain_priority_mode = str(brain_priority_mode).upper()
        self.contract_scaling_mode = str(contract_scaling_mode).upper()
        self.volatility_floor = Decimal(str(volatility_floor))
        self.volatility_ceiling = Decimal(str(volatility_ceiling))
        self.tape_confirmation_ticks = int(tape_confirmation_ticks)
        self.taker_cross_ev_threshold = Decimal(str(taker_cross_ev_threshold))
        self.dynamic_moat_multiplier = float(dynamic_moat_multiplier)
        self.vpin_toxic_threshold = float(vpin_toxic_threshold)
        self.fee_per_contract = Decimal(str(fee_per_contract))
        self.typical_1m_volatility = float(typical_1m_volatility)
        self.asset = CryptoAsset(str(asset).upper()) if not isinstance(asset, CryptoAsset) else asset
        self.current_atr: float = self.typical_1m_volatility
        self.tape_streak: int = 0

    def calculate_taker_fee(self, price: Union[Decimal, float], contracts: int = 1) -> Decimal:
        """Calculate taker fee using authentic CFTC schedule."""
        return calculate_kalshi_taker_fee(price, contracts)

    def _resolve_current_volatility(self) -> float:
        """Resolve rolling 1-minute equivalent realized volatility from CandleBuilder or fallback."""
        if self.dynamic_volatility_mode != "REALIZED_ATR" or self.candle_builder is None:
            return self.typical_1m_volatility

        try:
            symbol = f"{self.asset.value}USDT" if not self.asset.value.endswith("USDT") else self.asset.value
            candles = self.candle_builder.get_candles(symbol, count=15, include_current=True)
            if not candles or len(candles) < 2:
                return self.typical_1m_volatility

            trs = []
            for i in range(1, len(candles)):
                h = float(candles[i]["high"])
                l = float(candles[i]["low"])
                prev_c = float(candles[i - 1]["close"])
                tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
                trs.append(tr)

            if not trs:
                return self.typical_1m_volatility

            mean_tr = sum(trs) / len(trs)
            interval_ms = float(getattr(self.candle_builder, "interval_ms", 60000))
            time_scale = math.sqrt(max(1.0, interval_ms / 60000.0))
            vol_1m = max(1.0, mean_tr / time_scale)
            return float(vol_1m)
        except Exception as exc:
            logger.debug("[DUAL-ONNX] Realized volatility calculation fallback: %s", exc)
            return self.typical_1m_volatility

    def get_parameters(self) -> Dict[str, Any]:
        """Return current live strategy parameters."""
        return {
            "strategy_id": self.STRATEGY_ID,
            "strategy_name": self.STRATEGY_NAME,
            "asset": self.asset.value,
            "brain_priority_mode": self.brain_priority_mode,
            "contract_scaling_mode": self.contract_scaling_mode,
            "volatility_floor": float(self.volatility_floor),
            "volatility_ceiling": float(self.volatility_ceiling),
            "entry_discount_depth": float(self.entry_discount_depth),
            "discount_ceiling": float(self.entry_discount_depth),
            "tape_confirmation_ticks": self.tape_confirmation_ticks,
            "discount_limit_price": float(self.entry_discount_depth),
            "momentum_max_price": float(self.momentum_max_price),
            "min_ev_dollars": float(self.min_ev_dollars),
            "min_confidence": round(self.min_confidence, 4),
            "taker_cross_ev_threshold": float(self.taker_cross_ev_threshold),
            "dynamic_moat_multiplier": round(self.dynamic_moat_multiplier, 2),
            "vpin_toxic_threshold": round(self.vpin_toxic_threshold, 3),
            "fee_per_contract": float(self.fee_per_contract),
            "typical_1m_volatility": self.typical_1m_volatility,
            "current_atr": round(self.current_atr, 2),
            "gamma_cliff_seconds": self.gamma_cliff_seconds,
            "auto_cancel_on_veto": self.auto_cancel_on_veto,
            "dynamic_volatility_mode": self.dynamic_volatility_mode,
            "max_contracts": 1,
            "hmm_regime": self.hmm_brain.current_regime.name if (self.hmm_brain and hasattr(self.hmm_brain, "current_regime")) else "NONE",
            "max_temporal_skew_ms": self.max_temporal_skew_ms,
            "cross_brain_skew_ms": round(self.last_temporal_skew_ms, 2),
            "is_temporally_synced": self.is_temporally_synced,
            "slower_brain": self.slower_brain,
        }

    def update_parameters(
        self,
        discount_ceiling: Optional[Union[float, Decimal, str]] = None,
        entry_discount_depth: Optional[Union[float, Decimal, str]] = None,
        discount_limit_price: Optional[Union[float, Decimal, str]] = None,
        momentum_max_price: Optional[Union[float, Decimal, str]] = None,
        min_ev_dollars: Optional[Union[float, Decimal, str]] = None,
        min_confidence: Optional[float] = None,
        brain_priority_mode: Optional[str] = None,
        contract_scaling_mode: Optional[str] = None,
        volatility_floor: Optional[Union[float, Decimal, str]] = None,
        volatility_ceiling: Optional[Union[float, Decimal, str]] = None,
        tape_confirmation_ticks: Optional[int] = None,
        taker_cross_ev_threshold: Optional[Union[float, Decimal, str]] = None,
        dynamic_moat_multiplier: Optional[float] = None,
        vpin_toxic_threshold: Optional[float] = None,
        fee_per_contract: Optional[Union[float, Decimal, str]] = None,
        typical_1m_volatility: Optional[float] = None,
        asset: Optional[Union[CryptoAsset, str]] = None,
        max_temporal_skew_ms: Optional[Union[float, int]] = None,
        gamma_cliff_seconds: Optional[Union[float, int]] = None,
        auto_cancel_on_veto: Optional[bool] = None,
        dynamic_volatility_mode: Optional[str] = None,
        candle_builder: Optional[Any] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Dynamically update strategy parameters on the fly."""
        if gamma_cliff_seconds is not None:
            self.gamma_cliff_seconds = max(10.0, min(300.0, float(gamma_cliff_seconds)))
        if auto_cancel_on_veto is not None:
            self.auto_cancel_on_veto = bool(auto_cancel_on_veto)
        if dynamic_volatility_mode is not None:
            dvm = str(dynamic_volatility_mode).upper()
            if dvm in ("REALIZED_ATR", "FIXED_14", "FIXED_STATIC"):
                self.dynamic_volatility_mode = dvm
        if candle_builder is not None:
            self.candle_builder = candle_builder
        if max_temporal_skew_ms is not None:
            self.max_temporal_skew_ms = max(100.0, min(10000.0, float(max_temporal_skew_ms)))
        disc = entry_discount_depth if entry_discount_depth is not None else (discount_ceiling if discount_ceiling is not None else discount_limit_price)
        if disc is not None:
            self.entry_discount_depth = max(Decimal("0.10"), min(Decimal("0.85"), Decimal(str(disc))))
            self.discount_ceiling = self.entry_discount_depth
        if momentum_max_price is not None:
            self.momentum_max_price = max(Decimal("0.50"), min(Decimal("0.85"), Decimal(str(momentum_max_price))))
        if min_ev_dollars is not None:
            self.min_ev_dollars = max(Decimal("0.00"), min(Decimal("0.50"), Decimal(str(min_ev_dollars))))
        if min_confidence is not None:
            self.min_confidence = max(0.40, min(0.95, float(min_confidence)))
        if brain_priority_mode is not None:
            bpm = str(brain_priority_mode).upper()
            if bpm in ("TREND_ALIGNED_SCALP", "CONTRADICTION_SNIPER", "UNANIMOUS_CONSENSUS"):
                self.brain_priority_mode = bpm
        if contract_scaling_mode is not None:
            csm = str(contract_scaling_mode).upper()
            if csm in ("TIER_0_STRICT_1", "TIER_1_CONVICTION_2", "TIER_2_KELLY"):
                self.contract_scaling_mode = csm
        if volatility_floor is not None:
            self.volatility_floor = max(Decimal("1.0"), Decimal(str(volatility_floor)))
        if volatility_ceiling is not None:
            self.volatility_ceiling = max(self.volatility_floor + Decimal("1.0"), Decimal(str(volatility_ceiling)))
        if tape_confirmation_ticks is not None:
            self.tape_confirmation_ticks = max(1, min(3, int(tape_confirmation_ticks)))
        if taker_cross_ev_threshold is not None:
            self.taker_cross_ev_threshold = max(Decimal("0.00"), min(Decimal("0.20"), Decimal(str(taker_cross_ev_threshold))))
        if dynamic_moat_multiplier is not None:
            self.dynamic_moat_multiplier = max(0.80, min(2.50, float(dynamic_moat_multiplier)))
        if vpin_toxic_threshold is not None:
            self.vpin_toxic_threshold = max(0.40, min(0.95, float(vpin_toxic_threshold)))
        if fee_per_contract is not None:
            self.fee_per_contract = max(Decimal("0.00"), Decimal(str(fee_per_contract)))
        if typical_1m_volatility is not None:
            self.typical_1m_volatility = max(1.0, float(typical_1m_volatility))
        if asset is not None:
            self.asset = CryptoAsset(str(asset).upper()) if not isinstance(asset, CryptoAsset) else asset
        if "hmm_brain" in kwargs:
            self.hmm_brain = kwargs["hmm_brain"]

        logger.info("[THE ONNX STRATEGY] Parameters updated: %s", self.get_parameters())
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
                cancel_resting_orders=self.auto_cancel_on_veto,
                rationale="Market cycle has already expired.",
            )

        # 1c. Gamma Cliff Guard (Anti-Pin Risk Late Cycle)
        if time_to_expiry_s < self.gamma_cliff_seconds:
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
                cancel_resting_orders=self.auto_cancel_on_veto,
                rationale=f"Gamma cliff veto: Cycle expiry imminent ({time_to_expiry_s:.0f}s < {self.gamma_cliff_seconds:.0f}s). All entries halted & resting orders purged (Late-cycle pin-risk shield).",
            )

        # 1b. Cross-Brain Temporal Synchronization & Lead-Lag Shield
        t_spot_dt = getattr(spot_l2, "last_update", None)
        t_kalshi_dt = getattr(kalshi_l2, "last_update", None)
        if t_spot_dt is not None and t_kalshi_dt is not None and spot_l2 is not kalshi_l2:
            try:
                ts_spot = t_spot_dt.timestamp() if hasattr(t_spot_dt, "timestamp") else float(t_spot_dt)
                ts_kalshi = t_kalshi_dt.timestamp() if hasattr(t_kalshi_dt, "timestamp") else float(t_kalshi_dt)
                skew_ms = abs(ts_spot - ts_kalshi) * 1000.0
                self.last_temporal_skew_ms = skew_ms

                if skew_ms > self.max_temporal_skew_ms:
                    self.is_temporally_synced = False
                    self.slower_brain = "KALSHI" if ts_spot > ts_kalshi else "SPOT"
                    return DualONNXDecision(
                        action="HOLD",
                        regime=DualONNXRegime.TEMPORAL_DESYNC,
                        side=None,
                        quolas_signal="WAIT",
                        quolas_confidence=0.0,
                        kalshi_signal="WAIT",
                        kalshi_confidence=0.0,
                        recommended_limit_price=Decimal("0.00"),
                        expected_value=Decimal("0.00"),
                        recommended_contracts=0,
                        cancel_resting_orders=self.auto_cancel_on_veto,
                        rationale=f"Temporal desync veto: Cross-brain skew ({skew_ms:.1f}ms > {self.max_temporal_skew_ms:.0f}ms). Slower feed ({self.slower_brain}) must catch up before trade authorization (Anti-ghosting shield).",
                    )
                else:
                    self.is_temporally_synced = True
                    self.slower_brain = "IN_SYNC"
            except Exception as t_exc:
                logger.debug("[DUAL-ONNX] Temporal skew calculation fallback: %s", t_exc)
        else:
            self.last_temporal_skew_ms = 0.0
            self.is_temporally_synced = True
            self.slower_brain = "IN_SYNC"

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
                cancel_resting_orders=self.auto_cancel_on_veto,
                rationale=f"Toxic flow veto: {toxic_source} VPIN toxicity ({score:.3f} > {self.vpin_toxic_threshold:.3f}).",
            )

        # 3b. HMM Macro Regime Veto Check
        if self.hmm_brain is not None:
            curr_regime = getattr(self.hmm_brain, "current_regime", None)
            if curr_regime is not None and getattr(curr_regime, "name", "") == "RISK_OFF":
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
                    cancel_resting_orders=self.auto_cancel_on_veto,
                    rationale="HMM macro regime veto: RISK_OFF (Extreme volatility/stress cascade shield).",
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

        # 4b. Volatility Window Guard (Dial 3)
        curr_vol = self._resolve_current_volatility()
        self.current_atr = curr_vol
        self.tape_streak = len(latest_kalshi_trades) if latest_kalshi_trades is not None else 0
        if curr_vol < float(self.volatility_floor):
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
                rationale=f"Volatility floor veto: 1m volatility {curr_vol:.1f} < min {float(self.volatility_floor):.1f} (Dead chop shield).",
            )
        if curr_vol > float(self.volatility_ceiling):
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
                rationale=f"Volatility ceiling veto: 1m volatility {curr_vol:.1f} > max {float(self.volatility_ceiling):.1f} (High-volatility panic shield).",
            )

        # 4c. Anti-Spoof Tape Confirmation Guard (Dial 5)
        if latest_kalshi_trades is not None and len(latest_kalshi_trades) < self.tape_confirmation_ticks:
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
                rationale=f"Tape confirmation veto: Insufficient prints ({len(latest_kalshi_trades)} < {self.tape_confirmation_ticks}) (Anti-spoof shield).",
            )

        # 4d. Brain Priority Arbiter (Dial 1)
        if self.brain_priority_mode == "UNANIMOUS_CONSENSUS":
            if q_sig != k_sig or q_sig == "WAIT":
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
                    rationale=f"Consensus veto: Spot ({q_sig}) != Kalshi ({k_sig}) in UNANIMOUS_CONSENSUS mode.",
                )

        # Sizing rule calculator (Dial 2)
        def _get_contracts(confidence_val: float, net_ev: Decimal) -> int:
            if self.contract_scaling_mode == "TIER_1_CONVICTION_2":
                bankroll = Decimal("25.0")
                if market_state and hasattr(market_state, "bankroll"):
                    bankroll = Decimal(str(market_state.bankroll))
                elif isinstance(market_state, dict) and "bankroll" in market_state:
                    bankroll = Decimal(str(market_state["bankroll"]))
                if bankroll >= Decimal("75.0") and confidence_val >= 0.75 and net_ev >= Decimal("0.06"):
                    return 2
            return 1

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
        t_minutes = max(0.1, time_to_expiry_s / 60.0)
        sigma_t = max(1.0, curr_vol * math.sqrt(t_minutes) * (self.dynamic_moat_multiplier / 1.36))
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

            can_cross = (
                self.taker_cross_ev_threshold > Decimal("0.00")
                and best_yes_ask is not None
                and best_yes_ask <= self.momentum_max_price
            )
            taker_fee = self.calculate_taker_fee(best_yes_ask, contracts=1) if best_yes_ask is not None else self.fee_per_contract
            taker_ev = (
                Decimal(str(p_win)) * Decimal("1.00") - best_yes_ask - taker_fee
                if best_yes_ask is not None
                else Decimal("-1.00")
            )

            if can_cross and taker_ev >= self.taker_cross_ev_threshold:
                limit_price = best_yes_ask
                fee = taker_fee
                exec_type = f"Taker Sweep (EV +${taker_ev:.2f} >= ${self.taker_cross_ev_threshold:.2f}, Fee ${fee:.2f})"
            elif best_yes_bid is not None:
                limit_price = min(self.momentum_max_price, best_yes_bid + Decimal("0.01"))
                fee = Decimal("0.00")
                exec_type = "Maker Resting ($0.00 fee)"
            else:
                limit_price = min(self.momentum_max_price, self.entry_discount_depth)
                fee = Decimal("0.00")
                exec_type = "Maker Resting ($0.00 fee)"

            ev = Decimal(str(p_win)) * Decimal("1.00") - limit_price - fee

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

            ct = _get_contracts(q_conf, ev)
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
                recommended_contracts=ct,
                rationale=f"Dual UP Momentum Scalp [{exec_type}]: Spot ({q_conf:.2f}) & Kalshi ({k_conf:.2f}) aligned | Limit: ${limit_price:.2f} | EV: +${ev:.2f}.",
            )

        # Case B: Both DOWN -> MOMENTUM_SCALP (BUY_NO)
        if q_sig == "DOWN" and k_sig == "DOWN":
            regime = DualONNXRegime.MOMENTUM_SCALP
            action = "BUY_NO"
            side = "no"

            # Probability of winning NO: (1 - p_spot_digital)
            p_win = 0.60 * q_conf + 0.20 * k_conf + 0.20 * (1.0 - p_spot_digital)
            p_win = max(0.05, min(0.95, p_win))

            can_cross = (
                self.taker_cross_ev_threshold > Decimal("0.00")
                and best_no_ask is not None
                and best_no_ask <= self.momentum_max_price
            )
            taker_fee = self.calculate_taker_fee(best_no_ask, contracts=1) if best_no_ask is not None else self.fee_per_contract
            taker_ev = (
                Decimal(str(p_win)) * Decimal("1.00") - best_no_ask - taker_fee
                if best_no_ask is not None
                else Decimal("-1.00")
            )

            if can_cross and taker_ev >= self.taker_cross_ev_threshold:
                limit_price = best_no_ask
                fee = taker_fee
                exec_type = f"Taker Sweep (EV +${taker_ev:.2f} >= ${self.taker_cross_ev_threshold:.2f}, Fee ${fee:.2f})"
            elif best_no_bid is not None:
                limit_price = min(self.momentum_max_price, best_no_bid + Decimal("0.01"))
                fee = Decimal("0.00")
                exec_type = "Maker Resting ($0.00 fee)"
            else:
                limit_price = min(self.momentum_max_price, self.entry_discount_depth)
                fee = Decimal("0.00")
                exec_type = "Maker Resting ($0.00 fee)"

            ev = Decimal(str(p_win)) * Decimal("1.00") - limit_price - fee

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

            ct = _get_contracts(q_conf, ev)
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
                recommended_contracts=ct,
                rationale=f"Dual DOWN Momentum Scalp [{exec_type}]: Spot ({q_conf:.2f}) & Kalshi ({k_conf:.2f}) aligned | Limit: ${limit_price:.2f} | EV: +${ev:.2f}.",
            )

        # Case C: Spot UP, Kalshi DOWN -> CONTRADICTION_ARBITRAGE (BUY_YES at discount)
        if q_sig == "UP" and k_sig in ("DOWN", "WAIT"):
            # Fallback guard: If Kalshi brain is in uncalibrated fallback, require high QuoLas conviction
            if getattr(self.gateway, "is_kalshi_fallback", False) and k_sig in ("DOWN", "WAIT") and q_conf < 0.70:
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
                    rationale=f"Fallback guard: Kalshi brain in uncalibrated fallback requires QuoLas confidence >= 0.70 ({q_conf:.2f} < 0.70).",
                )

            regime = DualONNXRegime.CONTRADICTION_ARBITRAGE
            action = "BUY_YES"
            side = "yes"

            # QuoLas Spot Brain is the leader: 80% weight on QuoLas conviction, 20% on spot drift
            p_win = 0.80 * q_conf + 0.20 * p_spot_digital
            p_win = max(0.10, min(0.95, p_win))

            can_cross = (
                self.taker_cross_ev_threshold > Decimal("0.00")
                and best_yes_ask is not None
                and best_yes_ask <= self.entry_discount_depth
            )
            taker_fee = self.calculate_taker_fee(best_yes_ask, contracts=1) if best_yes_ask is not None else self.fee_per_contract
            taker_ev = (
                Decimal(str(p_win)) * Decimal("1.00") - best_yes_ask - taker_fee
                if best_yes_ask is not None
                else Decimal("-1.00")
            )

            if can_cross and taker_ev >= self.taker_cross_ev_threshold:
                limit_price = best_yes_ask
                fee = taker_fee
                exec_type = f"Taker Discount Snipe (EV +${taker_ev:.2f} >= ${self.taker_cross_ev_threshold:.2f}, Fee ${fee:.2f})"
            elif best_yes_bid is not None:
                limit_price = min(self.entry_discount_depth, best_yes_bid + Decimal("0.01"))
                fee = Decimal("0.00")
                exec_type = "Maker Resting ($0.00 fee)"
            else:
                limit_price = self.entry_discount_depth
                fee = Decimal("0.00")
                exec_type = "Maker Resting ($0.00 fee)"

            ev = Decimal(str(p_win)) * Decimal("1.00") - limit_price - fee

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

            ct = _get_contracts(q_conf, ev)
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
                recommended_contracts=ct,
                rationale=f"Contradiction Arbitrage [{exec_type}]: Spot UP ({q_conf:.2f}) vs Kalshi {k_sig} ({k_conf:.2f}) | Sniping discount YES at ${limit_price:.2f} <= ${self.entry_discount_depth:.2f} | EV: +${ev:.2f}.",
            )

        # Case D: Spot DOWN, Kalshi UP -> CONTRADICTION_ARBITRAGE (BUY_NO at discount)
        if q_sig == "DOWN" and k_sig in ("UP", "WAIT"):
            # Fallback guard: If Kalshi brain is in uncalibrated fallback, require high QuoLas conviction
            if getattr(self.gateway, "is_kalshi_fallback", False) and k_sig in ("UP", "WAIT") and q_conf < 0.70:
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
                    rationale=f"Fallback guard: Kalshi brain in uncalibrated fallback requires QuoLas confidence >= 0.70 ({q_conf:.2f} < 0.70).",
                )

            regime = DualONNXRegime.CONTRADICTION_ARBITRAGE
            action = "BUY_NO"
            side = "no"

            # QuoLas Spot Brain is the leader: 80% weight on Spot, 20% on spot drift
            p_win = 0.80 * q_conf + 0.20 * (1.0 - p_spot_digital)
            p_win = max(0.10, min(0.95, p_win))

            can_cross = (
                self.taker_cross_ev_threshold > Decimal("0.00")
                and best_no_ask is not None
                and best_no_ask <= self.entry_discount_depth
            )
            taker_fee = self.calculate_taker_fee(best_no_ask, contracts=1) if best_no_ask is not None else self.fee_per_contract
            taker_ev = (
                Decimal(str(p_win)) * Decimal("1.00") - best_no_ask - taker_fee
                if best_no_ask is not None
                else Decimal("-1.00")
            )

            if can_cross and taker_ev >= self.taker_cross_ev_threshold:
                limit_price = best_no_ask
                fee = taker_fee
                exec_type = f"Taker Discount Snipe (EV +${taker_ev:.2f} >= ${self.taker_cross_ev_threshold:.2f}, Fee ${fee:.2f})"
            elif best_no_bid is not None:
                limit_price = min(self.entry_discount_depth, best_no_bid + Decimal("0.01"))
                fee = Decimal("0.00")
                exec_type = "Maker Resting ($0.00 fee)"
            else:
                limit_price = self.entry_discount_depth
                fee = Decimal("0.00")
                exec_type = "Maker Resting ($0.00 fee)"

            ev = Decimal(str(p_win)) * Decimal("1.00") - limit_price - fee

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

            ct = _get_contracts(q_conf, ev)
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
                recommended_contracts=ct,
                rationale=f"Contradiction Arbitrage [{exec_type}]: Spot DOWN ({q_conf:.2f}) vs Kalshi {k_sig} ({k_conf:.2f}) | Sniping discount NO at ${limit_price:.2f} <= ${self.entry_discount_depth:.2f} | EV: +${ev:.2f}.",
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

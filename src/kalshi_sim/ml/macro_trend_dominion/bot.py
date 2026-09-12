"""Bot 3: Macro Trend Dominion Strategy Engine.

Fuses 3 Machine Learning & Statistical Brains:
1. Brain 1: QuoLas Spot Lead (28-D Microstructure Tensor via nano_microscope_overhauled.onnx)
2. HMM Brain: 3-State AI Markov Regime (STABLE_RANGE, VOL_EXPANSION, RISK_OFF)
3. Brain 2: Kalshi CLOB Microstructure Lag (15-Level Binary Orderbook)

Delivers a streamlined 15-minute execution decision:
- Call: YES | NO | DONT
- Confidence % (Empirically Brier-calibrated)
- Limit Price: 1c to 89c with Mathematical Expected Value (EV) Gate
- Continuous Learning: Diagnoses mistakes across paper and live cycles.
"""

from __future__ import annotations

import logging
import math
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

from kalshi_sim.ml.macro_trend_dominion.learning_engine import MacroDominionLearningEngine
from kalshi_sim.ml.macro_trend_dominion.schemas import MacroDominionDecision
from kalshi_sim.schemas import CryptoAsset, L2BookState, OrderSide

logger = logging.getLogger("kalshi_sim.macro_trend_dominion.bot")


def _classify_signal(sig: Any) -> str:
    """Normalize signal string to 'UP', 'DOWN', or 'WAIT'."""
    s = str(sig).strip().upper()
    if s in ("LONG", "UP", "BUY", "YES"):
        return "UP"
    if s in ("SHORT", "DOWN", "SELL", "NO"):
        return "DOWN"
    return "WAIT"


class MacroTrendDominionBot:
    """Macro Trend Dominion Quantitative Strategy Bot (Bot 3)."""

    STRATEGY_ID = "macro_trend_dominion"
    STRATEGY_NAME = "Macro Trend Dominion"
    ALIASES = ("macro_onnx", "macro_trend_dominion_bot", "onnx_macro_v2", "macro_trend")

    def __init__(
        self,
        strategy_id: str = "macro_trend_dominion",
        strategy_name: str = "Macro Trend Dominion",
        limit_price_cents: int = 52,
        min_confidence_pct: float = 65.0,
        min_ev_dollars: Union[Decimal, float, str] = Decimal("0.03"),
        volatility_moat_dollars: Union[Decimal, float, str] = Decimal("28.00"),
        hmm_risk_off_veto: bool = True,
        macro_trend_window: str = "15m+30m",
        max_contracts: int = 1,
        take_profit_harvest_cents: int = 95,
        adaptive_learning_rate: float = 0.20,
        asset: Union[CryptoAsset, str] = CryptoAsset.BTC,
        hmm_brain: Optional[Any] = None,
        candle_builder: Optional[Any] = None,
        gateway: Optional[Any] = None,
    ) -> None:
        self.strategy_id = strategy_id
        self.strategy_name = strategy_name
        self.limit_price_cents = max(1, min(89, int(limit_price_cents)))
        self.min_confidence_pct = max(50.0, min(90.0, float(min_confidence_pct)))
        self.min_ev_dollars = Decimal(str(min_ev_dollars))
        self.volatility_moat_dollars = Decimal(str(volatility_moat_dollars))
        self.hmm_risk_off_veto = bool(hmm_risk_off_veto)
        self.macro_trend_window = str(macro_trend_window)
        self.max_contracts = 1  # Strict Micro-Bankroll Armor invariant
        self.take_profit_harvest_cents = max(80, min(98, int(take_profit_harvest_cents)))
        self.adaptive_learning_rate = max(0.0, min(0.5, float(adaptive_learning_rate)))
        self.asset = CryptoAsset(str(asset).upper()) if not isinstance(asset, CryptoAsset) else asset

        # Upstream components (piggybacking on shared platform engines)
        self.hmm_brain = hmm_brain
        self.candle_builder = candle_builder
        self.gateway = gateway

        # Dedicated Mistake Learning & Adaptation Engine
        self.learning_engine = MacroDominionLearningEngine(
            rolling_window_size=50,
            min_samples_for_adaptation=5,
            default_price_cap=Decimal(str(self.limit_price_cents)) / Decimal("100"),
            adaptation_rate=self.adaptive_learning_rate,
        )

        logger.info(
            "🧠 [MACRO TREND DOMINION] Bot 3 Initialized | Limit: %dc | MinConf: %.1f%% | Moat: $%s | Asset: %s",
            self.limit_price_cents,
            self.min_confidence_pct,
            self.volatility_moat_dollars,
            self.asset.value,
        )

    def get_parameters(self) -> Dict[str, Any]:
        """Expose all 9 Strategy Dials and dynamic diagnostics for UI consoles."""
        diag = self.learning_engine.get_diagnostics()
        hmm_status = "UNKNOWN"
        if self.hmm_brain is not None:
            cr = getattr(self.hmm_brain, "current_regime", None)
            hmm_status = getattr(cr, "name", str(cr)) if cr is not None else "UNFITTED"

        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            # The 9 Tunable Dials
            "limit_price_cents": self.limit_price_cents,
            "entry_discount_depth": float(Decimal(str(self.limit_price_cents)) / Decimal("100")),
            "discount_limit_price": float(Decimal(str(self.limit_price_cents)) / Decimal("100")),
            "min_confidence_pct": self.min_confidence_pct,
            "min_confidence": self.min_confidence_pct / 100.0,
            "min_ev_dollars": float(self.min_ev_dollars),
            "volatility_moat_dollars": float(self.volatility_moat_dollars),
            "min_spot_diff": float(self.volatility_moat_dollars),
            "hmm_risk_off_veto": self.hmm_risk_off_veto,
            "macro_trend_window": self.macro_trend_window,
            "max_contracts": self.max_contracts,
            "take_profit_harvest_cents": self.take_profit_harvest_cents,
            "take_profit_price_threshold": float(Decimal(str(self.take_profit_harvest_cents)) / Decimal("100")),
            "adaptive_learning_rate": self.adaptive_learning_rate,
            # Upstream state
            "hmm_regime": hmm_status,
            # Learning Engine Diagnostics
            "shrinkage_factor": diag["shrinkage_factor"],
            "active_price_cap_cents": diag["active_price_cap_cents"],
            "learning_summary": diag["summary"],
            "empirical_win_rate_pct": diag["win_rate_pct"],
            "total_cycles_recorded": diag["total_cycles_recorded"],
        }

    def update_parameters(self, **kwargs: Any) -> Dict[str, Any]:
        """Dynamically update strategy dials and learning settings on the fly."""
        if "limit_price_cents" in kwargs and kwargs["limit_price_cents"] is not None:
            self.limit_price_cents = max(1, min(89, int(kwargs["limit_price_cents"])))
        elif "entry_discount_depth" in kwargs and kwargs["entry_discount_depth"] is not None:
            self.limit_price_cents = max(1, min(89, int(round(float(kwargs["entry_discount_depth"]) * 100))))
        elif "discount_limit_price" in kwargs and kwargs["discount_limit_price"] is not None:
            self.limit_price_cents = max(1, min(89, int(round(float(kwargs["discount_limit_price"]) * 100))))

        if "min_confidence_pct" in kwargs and kwargs["min_confidence_pct"] is not None:
            self.min_confidence_pct = max(50.0, min(90.0, float(kwargs["min_confidence_pct"])))
        elif "min_confidence" in kwargs and kwargs["min_confidence"] is not None:
            self.min_confidence_pct = max(50.0, min(90.0, float(kwargs["min_confidence"]) * 100.0))

        if "min_ev_dollars" in kwargs and kwargs["min_ev_dollars"] is not None:
            self.min_ev_dollars = max(Decimal("0.00"), min(Decimal("0.25"), Decimal(str(kwargs["min_ev_dollars"]))))

        if "volatility_moat_dollars" in kwargs and kwargs["volatility_moat_dollars"] is not None:
            self.volatility_moat_dollars = max(Decimal("5.00"), min(Decimal("100.00"), Decimal(str(kwargs["volatility_moat_dollars"]))))
        elif "min_spot_diff" in kwargs and kwargs["min_spot_diff"] is not None:
            self.volatility_moat_dollars = max(Decimal("5.00"), min(Decimal("100.00"), Decimal(str(kwargs["min_spot_diff"]))))

        if "hmm_risk_off_veto" in kwargs and kwargs["hmm_risk_off_veto"] is not None:
            self.hmm_risk_off_veto = bool(kwargs["hmm_risk_off_veto"])

        if "macro_trend_window" in kwargs and kwargs["macro_trend_window"] is not None:
            self.macro_trend_window = str(kwargs["macro_trend_window"])

        if "take_profit_harvest_cents" in kwargs and kwargs["take_profit_harvest_cents"] is not None:
            self.take_profit_harvest_cents = max(80, min(98, int(kwargs["take_profit_harvest_cents"])))
        elif "take_profit_price_threshold" in kwargs and kwargs["take_profit_price_threshold"] is not None:
            self.take_profit_harvest_cents = max(80, min(98, int(round(float(kwargs["take_profit_price_threshold"]) * 100))))

        if "adaptive_learning_rate" in kwargs and kwargs["adaptive_learning_rate"] is not None:
            self.adaptive_learning_rate = max(0.0, min(0.5, float(kwargs["adaptive_learning_rate"])))
            self.learning_engine.adaptation_rate = self.adaptive_learning_rate

        if "hmm_brain" in kwargs and kwargs["hmm_brain"] is not None:
            self.hmm_brain = kwargs["hmm_brain"]

        if "candle_builder" in kwargs and kwargs["candle_builder"] is not None:
            self.candle_builder = kwargs["candle_builder"]

        # Update learning engine default cap
        new_cap = Decimal(str(self.limit_price_cents)) / Decimal("100")
        self.learning_engine.default_price_cap = new_cap
        if self.learning_engine.active_price_cap != Decimal("0.55"):
            self.learning_engine.active_price_cap = new_cap

        logger.info("[MACRO TREND DOMINION] Dials updated: %s", self.get_parameters())
        return self.get_parameters()

    def evaluate(
        self,
        spot_price: Union[Decimal, float] = Decimal("0.0"),
        target_strike: Union[Decimal, float] = Decimal("0.0"),
        time_to_expiry_s: float = 600.0,
        spot_l2: Optional[L2BookState] = None,
        kalshi_l2: Optional[L2BookState] = None,
        quolas_inference: Optional[Dict[str, Any]] = None,
        kalshi_inference: Optional[Dict[str, Any]] = None,
        spot_diff: Optional[float] = None,
        **kwargs: Any,
    ) -> MacroDominionDecision:
        # Extract kwargs fallbacks for platform compatibility
        if kalshi_l2 is None and "book" in kwargs:
            kalshi_l2 = kwargs["book"]
        if quolas_inference is None and kwargs.get("onnx_result") is not None:
            quolas_inference = kwargs["onnx_result"]
        if kalshi_inference is None and kwargs.get("onnx_result") is not None:
            kalshi_inference = kwargs["onnx_result"]

        s_price = float(spot_price)
        k_strike = float(target_strike)
        diff = float(spot_diff) if spot_diff is not None else (s_price - k_strike)
        abs_diff = abs(diff)

        # 1. Expiration & Gamma Cliff Cutoff
        if time_to_expiry_s <= 15.0:
            return MacroDominionDecision(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                call="DONT",
                confidence_pct=50.0,
                limit_price=Decimal("0.00"),
                expected_value=Decimal("0.00"),
                net_edge_pct=0.0,
                recommended_contracts=0,
                macro_trend="CHOP",
                hmm_regime="UNKNOWN",
                spot_signal="WAIT",
                spot_confidence=0.50,
                kalshi_signal="WAIT",
                kalshi_confidence=0.50,
                is_ev_positive=False,
                rationale="Market cycle expiring in <= 15s. Zero new risk allowed.",
                cancel_resting_orders=True,
            )

        # 2. HMM Markov Macro Regime Gate
        hmm_state = "UNKNOWN"
        if self.hmm_brain is not None:
            curr = getattr(self.hmm_brain, "current_regime", None)
            if curr is not None:
                hmm_state = getattr(curr, "name", str(curr))

        if self.hmm_risk_off_veto and hmm_state == "RISK_OFF":
            return MacroDominionDecision(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                call="DONT",
                confidence_pct=50.0,
                limit_price=Decimal("0.00"),
                expected_value=Decimal("0.00"),
                net_edge_pct=0.0,
                recommended_contracts=0,
                macro_trend="CHOP",
                hmm_regime=hmm_state,
                spot_signal="WAIT",
                spot_confidence=0.50,
                kalshi_signal="WAIT",
                kalshi_confidence=0.50,
                is_ev_positive=False,
                rationale="HMM macro regime veto: RISK_OFF (Cascade liquidation shield active).",
                cancel_resting_orders=True,
            )

        # 3. Macro Trend Classification
        macro_trend = "BULL" if diff > 0 else "BEAR"

        # 4. Extract Inferences from Brain 1 (Spot) & Brain 2 (CLOB)
        q_sig = "WAIT"
        q_conf = 0.50
        if quolas_inference is not None:
            q_sig = _classify_signal(quolas_inference.get("signal", "WAIT"))
            q_conf = float(quolas_inference.get("confidence", 0.50))
        elif spot_l2 is not None and hasattr(spot_l2, "get_depth") and self.gateway is not None:
            try:
                q_res, _ = self.gateway.infer_both(spot_book=spot_l2, kalshi_book=None)
                q_sig = _classify_signal(q_res.get("signal", "WAIT"))
                q_conf = float(q_res.get("confidence", 0.50))
            except Exception:
                pass

        k_sig = "WAIT"
        k_conf = 0.50
        if kalshi_inference is not None:
            k_sig = _classify_signal(kalshi_inference.get("signal", "WAIT"))
            k_conf = float(kalshi_inference.get("confidence", 0.50))
        elif kalshi_l2 is not None and hasattr(kalshi_l2, "get_depth") and self.gateway is not None:
            try:
                _, k_res = self.gateway.infer_both(spot_book=None, kalshi_book=kalshi_l2)
                k_sig = _classify_signal(k_res.get("signal", "WAIT"))
                k_conf = float(k_res.get("confidence", 0.50))
            except Exception:
                pass
        elif isinstance(kalshi_l2, dict):
            y_bid = float(kalshi_l2.get("yes_bid", 50))
            n_bid = float(kalshi_l2.get("no_bid", 50))
            if y_bid > n_bid + 2:
                k_sig = "UP"
                k_conf = min(0.85, 0.50 + (y_bid - n_bid) / 100.0)
            elif n_bid > y_bid + 2:
                k_sig = "DOWN"
                k_conf = min(0.85, 0.50 + (n_bid - y_bid) / 100.0)

        # 5. Dynamic Volatility Moat Barrier
        moat_val = float(self.volatility_moat_dollars)
        if abs_diff < moat_val:
            return MacroDominionDecision(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                call="DONT",
                confidence_pct=50.0,
                limit_price=Decimal("0.00"),
                expected_value=Decimal("0.00"),
                net_edge_pct=0.0,
                recommended_contracts=0,
                macro_trend=macro_trend,
                hmm_regime=hmm_state,
                spot_signal=q_sig,
                spot_confidence=q_conf,
                kalshi_signal=k_sig,
                kalshi_confidence=k_conf,
                is_ev_positive=False,
                rationale=f"Proximity trap: Spot too close to strike (|${diff:+.1f}| < ${moat_val:.1f} Moat).",
            )

        # 6. Directional Fusion
        proposed_call = "DONT"
        raw_prob = 0.50

        # Consensus Alignment
        if macro_trend == "BULL" and q_sig == "UP":
            proposed_call = "YES"
            # 60% spot lead weight, 40% CLOB lag weight
            raw_prob = 0.60 * q_conf + 0.40 * (k_conf if k_sig == "UP" else (1.0 - k_conf))
        elif macro_trend == "BEAR" and q_sig == "DOWN":
            proposed_call = "NO"
            raw_prob = 0.60 * q_conf + 0.40 * (k_conf if k_sig == "DOWN" else (1.0 - k_conf))
        elif q_sig in ("UP", "DOWN") and q_sig != k_sig:
            # Contradiction Snipe permitted only in STABLE_RANGE
            if hmm_state == "STABLE_RANGE" and q_conf >= 0.70:
                proposed_call = "YES" if q_sig == "UP" else "NO"
                raw_prob = q_conf * 0.90  # 10% contradiction discount penalty
            else:
                proposed_call = "DONT"
                raw_prob = 0.50

        # If no directional agreement, hold
        if proposed_call == "DONT":
            return MacroDominionDecision(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                call="DONT",
                confidence_pct=round(raw_prob * 100.0, 1),
                limit_price=Decimal("0.00"),
                expected_value=Decimal("0.00"),
                net_edge_pct=0.0,
                recommended_contracts=0,
                macro_trend=macro_trend,
                hmm_regime=hmm_state,
                spot_signal=q_sig,
                spot_confidence=q_conf,
                kalshi_signal=k_sig,
                kalshi_confidence=k_conf,
                is_ev_positive=False,
                rationale="Macro tide and Spot order flow do not have consensus. Capital preserved.",
            )

        # 7. Apply Brier Shrinkage Calibration from Learning Engine
        calibrated_prob, shrinkage = self.learning_engine.calibrate_probability(raw_prob)
        confidence_pct = calibrated_prob * 100.0

        if confidence_pct < self.min_confidence_pct:
            return MacroDominionDecision(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                call="DONT",
                confidence_pct=round(confidence_pct, 1),
                limit_price=Decimal("0.00"),
                expected_value=Decimal("0.00"),
                net_edge_pct=0.0,
                recommended_contracts=0,
                macro_trend=macro_trend,
                hmm_regime=hmm_state,
                spot_signal=q_sig,
                spot_confidence=q_conf,
                kalshi_signal=k_sig,
                kalshi_confidence=k_conf,
                is_ev_positive=False,
                rationale=f"Confidence ({confidence_pct:.1f}%) below minimum hurdle ({self.min_confidence_pct:.1f}%). Shrinkage: {shrinkage:.2f}.",
                brier_shrinkage_factor=shrinkage,
            )

        # 8. Expected Value (EV) Gate on Limit Price
        effective_limit_price = self.learning_engine.get_effective_price_cap(self.limit_price_cents)
        p_dec = Decimal(str(round(calibrated_prob, 4)))
        fee_buffer = Decimal("0.01")  # Conservative $0.01 fee buffer
        ev_val = (p_dec * Decimal("1.00")) - effective_limit_price - fee_buffer
        net_edge = (calibrated_prob - float(effective_limit_price) - 0.01) * 100.0

        if ev_val < self.min_ev_dollars:
            return MacroDominionDecision(
                strategy_id=self.strategy_id,
                strategy_name=self.strategy_name,
                call="DONT",
                confidence_pct=round(confidence_pct, 1),
                limit_price=effective_limit_price,
                expected_value=ev_val,
                net_edge_pct=net_edge,
                recommended_contracts=0,
                macro_trend=macro_trend,
                hmm_regime=hmm_state,
                spot_signal=q_sig,
                spot_confidence=q_conf,
                kalshi_signal=k_sig,
                kalshi_confidence=k_conf,
                is_ev_positive=False,
                rationale=f"EV Gate Veto: EV (+${float(ev_val):.2f}) below threshold (+${float(self.min_ev_dollars):.2f}) at limit ${float(effective_limit_price):.2f}.",
                brier_shrinkage_factor=shrinkage,
                active_price_cap=self.learning_engine.active_price_cap,
            )

        # 9. Successful Trade Authorization!
        return MacroDominionDecision(
            strategy_id=self.strategy_id,
            strategy_name=self.strategy_name,
            call=proposed_call,
            confidence_pct=round(confidence_pct, 1),
            limit_price=effective_limit_price,
            expected_value=ev_val,
            net_edge_pct=net_edge,
            recommended_contracts=self.max_contracts,
            macro_trend=macro_trend,
            hmm_regime=hmm_state,
            spot_signal=q_sig,
            spot_confidence=q_conf,
            kalshi_signal=k_sig,
            kalshi_confidence=k_conf,
            is_ev_positive=True,
            rationale=(
                f"Macro {macro_trend} + Spot {q_sig} ({q_conf*100:.0f}%) -> {proposed_call} authorized. "
                f"Limit: ${float(effective_limit_price):.2f} (EV: +${float(ev_val):.2f}, Edge: {net_edge:+.1f}%). "
                f"HMM: {hmm_state}."
            ),
            brier_shrinkage_factor=shrinkage,
            active_price_cap=self.learning_engine.active_price_cap,
        )

    def record_cycle_outcome(
        self,
        cycle_id: str,
        ticker: str,
        call: str,
        predicted_prob: float,
        fill_price: Union[Decimal, float],
        outcome: str,
        pnl: Union[Decimal, float],
        spot_diff_at_entry: float = 0.0,
        spot_diff_at_settle: float = 0.0,
        macro_trend: str = "CHOP",
        hmm_regime: str = "UNKNOWN",
        execution_mode: str = "paper",
    ) -> Dict[str, Any]:
        """Record trade result into learning engine to trigger adaptive recalibration."""
        return self.learning_engine.record_cycle_result(
            cycle_id=cycle_id,
            ticker=ticker,
            call=call,
            predicted_prob=predicted_prob,
            fill_price=Decimal(str(fill_price)),
            outcome=outcome,
            pnl=Decimal(str(pnl)),
            spot_diff_at_entry=spot_diff_at_entry,
            spot_diff_at_settle=spot_diff_at_settle,
            macro_trend=macro_trend,
            hmm_regime=hmm_regime,
            execution_mode=execution_mode,
        )

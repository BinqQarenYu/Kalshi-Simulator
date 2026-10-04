"""Bot 1 Version 4 (Strict Quantitative Domination Engine).

Distinct from historical 3-Step Dominion v3.2:
- Enforces strict 1-Trade-Per-Cycle (max_turnover_per_event = 1).
- Strictly 1 contract held at any given instant (Micro-Bankroll Armor).
- Coupling EV math slider (Net EV = P_win - P_entry).
- Passive Maker limit entries at discount sniper ceiling ($0.52 max).
- 4-Regime Fading Mathematics spot velocity front-running ($28.00 BTC / 2.0σ).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

from kalshi_sim.ml.domination_exit_evaluator import (
    DominationExitDecision,
    DominationExitEvaluator,
)
from kalshi_sim.ml.lead_deer_quant_brain import LeadDeerQuantBrain
from kalshi_sim.ml.statistical_ev_engine import ExpectedValueResult, StatisticalEVEngine
from kalshi_sim.schemas import CryptoAsset, L2BookState, OrderSide, TradeEvent, get_asset_config

logger = logging.getLogger("kalshi_sim.bot1_v4_engine")


@dataclass(frozen=True)
class Bot1V4Decision:
    """Structured decision output from Bot 1 Version 4 Engine."""
    strategy_id: str
    strategy_name: str
    active_playbook: str
    playbook_stage: str  # 'breakout' | 'drift' | 'gamma_snub' | 'none'
    p_up: float
    p_down: float
    p_wait: float
    vpin: float
    vpin_is_safe: bool
    ev_yes: float
    ev_no: float
    edge_yes: float
    edge_no: float
    kelly_f_yes: float
    kelly_f_no: float
    recommended_side: str  # 'yes' | 'no' | 'wait'
    recommended_contracts: int
    rationale: str
    edge_pct: float
    time_to_expiry_s: float
    spot_diff: float
    order_type: str = "limit"
    limit_price: float = 0.52
    turnovers_completed: int = 0
    max_turnovers: int = 3
    ev_hurdle_dollars: float = 0.02
    onnx_signal: str = "WAIT"
    onnx_confidence: float = 0.0
    fused_source: str = "macro_erf"


class Bot1V4DominationEngine:
    """Institutional Bot 1 Version 4 Multi-Turnover Quantitative Strategy Engine."""

    STRATEGY_ID = "bot1_v4_domination"
    STRATEGY_NAME = "Bot 1 V4 (Multi-Turnover Domination)"

    def __init__(
        self,
        max_turnover_per_event: int = 1,  # Strictly 1-trade-per-cycle invariant matching Bot 1
        min_ev_hurdle_dollars: Decimal = Decimal("0.02"),  # $0.02 minimum net EV hurdle
        discount_limit_price: Decimal = Decimal("0.52"),  # 52c maker discount floor (V3.2 standard)
        min_edge_pct: float = 0.015,  # 1.5% min edge
        vpin_toxic_threshold: float = 0.60,
        vpin_safe_threshold: float = 0.35,
        default_btc_1m_volatility: float = 14.0,
        take_profit_price_threshold: Decimal = Decimal("0.92"),
        enable_take_profit_ceiling: bool = True,
        require_reversal_for_tp_ceiling: bool = True,
        enable_reverse_take_profit_roi: bool = True,
        reverse_indicator_threshold: float = 0.85,
        min_take_profit_roi: float = 0.40,  # Council Spec: 40% allowable profit scalp ROI default ($0.826 exit)
        maker_entry_timeout_seconds: float = 45.0,  # Council Spec: 45s Maker entry queue timeout
        late_cycle_roi: float = 0.15,
        fee_per_contract: Decimal = Decimal("0.01"),
        min_spot_diff: Optional[float] = None,
        max_entry_price: Decimal = Decimal("0.55"),  # 55c hard ceiling: eliminate negative R:R entries (>55c)
        min_confidence: float = 0.81,
        enable_trailing_ratchet: bool = True,
        trailing_ratchet_buffer: Decimal = Decimal("0.08"),
        spot_delta_front_run_threshold: float = 28.0,
        enable_dynamic_spot_velocity: bool = True,
        velocity_z_score_threshold: float = 2.50,
        reentry_cooldown_seconds: float = 15.0,
        enable_doubt_harvest: bool = True,
        doubt_threshold: float = 0.80,
        upside_capture_ratio_threshold: float = 0.50,
        asymmetric_peak_bid: Decimal = Decimal("0.85"),  # Council recommendation: 85c asymmetric ceiling
        onnx_engine: Optional[Any] = None,
        fusion_weight_micro: float = 0.40,
        opening_quarantine_seconds: float = 90.0,  # 90s opening noise quarantine (V3.2 shield)
        max_clob_spread_cents: float = 0.05,  # Max allowable bid-ask spread corridor cap ($0.05)
        moneyness_moat_multiplier: float = 1.36,  # 1.36x sigma*sqrt(t) deep ITM protection moat
        asset: CryptoAsset | str = CryptoAsset.BTC,
    ) -> None:
        self.asset = CryptoAsset(str(asset).upper()) if not isinstance(asset, CryptoAsset) else asset
        self.max_turnover_per_event = max_turnover_per_event
        self.min_ev_hurdle_dollars = min_ev_hurdle_dollars
        self.discount_limit_price = discount_limit_price
        self.min_edge_pct = min_edge_pct
        self.vpin_toxic_threshold = vpin_toxic_threshold
        self.vpin_safe_threshold = vpin_safe_threshold
        self.default_btc_1m_volatility = default_btc_1m_volatility
        self.typical_1m_volatility = float(default_btc_1m_volatility)
        self.moneyness_moat_multiplier = float(moneyness_moat_multiplier)
        self.take_profit_price_threshold = take_profit_price_threshold
        self.enable_take_profit_ceiling = enable_take_profit_ceiling
        self.require_reversal_for_tp_ceiling = require_reversal_for_tp_ceiling
        self.enable_reverse_take_profit_roi = enable_reverse_take_profit_roi
        self.reverse_indicator_threshold = reverse_indicator_threshold
        self.min_take_profit_roi = min_take_profit_roi
        self.maker_entry_timeout_seconds = maker_entry_timeout_seconds
        self.late_cycle_roi = late_cycle_roi
        self.fee_per_contract = fee_per_contract
        self.min_spot_diff = min_spot_diff if min_spot_diff is not None else 25.0
        self.max_entry_price = max_entry_price
        self.min_confidence = min_confidence
        self.enable_trailing_ratchet = enable_trailing_ratchet
        self.trailing_ratchet_buffer = trailing_ratchet_buffer
        self.spot_delta_front_run_threshold = spot_delta_front_run_threshold
        self.enable_dynamic_spot_velocity = enable_dynamic_spot_velocity
        self.velocity_z_score_threshold = velocity_z_score_threshold
        self.reentry_cooldown_seconds = reentry_cooldown_seconds
        self.enable_doubt_harvest = enable_doubt_harvest
        self.doubt_threshold = doubt_threshold
        self.upside_capture_ratio_threshold = upside_capture_ratio_threshold
        self.asymmetric_peak_bid = asymmetric_peak_bid
        self.twap_fading_quarantine_seconds: float = 15.0
        self.twap_fading_window_seconds: float = 60.0
        self.enable_dynamic_reversal_curve: bool = True
        self.onnx_engine = onnx_engine
        self.fusion_weight_micro = fusion_weight_micro
        self.opening_quarantine_seconds = opening_quarantine_seconds
        self.max_clob_spread_cents = max_clob_spread_cents
        self.enable_lead_deer_peak_harvester: bool = True
        self.lead_deer_brain = LeadDeerQuantBrain(
            min_confidence=float(self.min_confidence),
            min_ev_dollars=float(self.min_ev_hurdle_dollars),
            maker_discount_ceiling=float(self.discount_limit_price),
        )

        self.ev_engine = StatisticalEVEngine()
        self.exit_evaluator = DominationExitEvaluator(self)
        self.vpin_window: list[float] = []

        # Cycle turnover state tracking
        self._current_cycle_id: Optional[str] = None
        self._completed_turnovers_map: dict[str, int] = {}
        self._last_exit_timestamp: float = 0.0

    def reset_cycle_turnover(self, cycle_id: str) -> None:
        """Reset turnover count for a new 15M cycle."""
        self._current_cycle_id = cycle_id
        self._completed_turnovers_map[cycle_id] = 0

    def get_completed_turnovers(self, cycle_id: str) -> int:
        """Get number of completed round-trip trades for a cycle."""
        return self._completed_turnovers_map.get(cycle_id, 0)

    def record_completed_turnover(self, cycle_id: str) -> None:
        """Record a completed round-trip trade."""
        current = self._completed_turnovers_map.get(cycle_id, 0)
        self._completed_turnovers_map[cycle_id] = current + 1

    def compute_required_win_probability(self, limit_price: Decimal) -> float:
        """EV Math Coupling: P_win = P_entry + EV_hurdle."""
        return float(limit_price + self.min_ev_hurdle_dollars)

    def compute_dynamic_reversal_threshold(self, time_to_expiry_s: float) -> float:
        """Calculate dynamic reversal threshold decaying from base down to 50% as tau -> 0."""
        if not getattr(self, "enable_dynamic_reversal_curve", True):
            return self.reverse_indicator_threshold
        tau_mins = max(0.5, min(15.0, time_to_expiry_s / 60.0))
        scaled = 0.50 + 0.035 * tau_mins
        return min(self.reverse_indicator_threshold, scaled)

    def compute_dynamic_limit_price(self, win_prob: float) -> Decimal:
        """Dynamic EV Math Coupling:
        Entry Limit = min(win_prob - EV_hurdle, max_entry_price)
        Dynamically scales entry ceiling up to max_entry_price ($0.55) when model conviction is high,
        while maintaining at least min_ev_hurdle_dollars ($0.02) net EV edge.
        Strictly hard-vetoes > $0.55 entry orders to eliminate negative risk/reward asymmetry.
        """
        ev_hurdle = float(self.min_ev_hurdle_dollars)
        max_cap = min(float(self.max_entry_price), 0.55)  # Hard $0.55 limit ceiling
        base_floor = float(self.discount_limit_price)

        dynamic_price = win_prob - ev_hurdle
        clamped_price = max(base_floor, min(dynamic_price, max_cap))
        return Decimal(str(round(clamped_price, 2)))

    def get_dynamic_proximity_threshold(
        self,
        time_to_expiry_s: float,
        cycle_duration_s: float = 900.0,
    ) -> float:
        """Compute self-calibrating time-and-volatility-scaled minimum spot distance threshold (V3.2 Moat)."""
        tau_mins = max(0.2, time_to_expiry_s / 60.0)
        cycle_mins = max(1.0, cycle_duration_s / 60.0)
        try:
            cfg = get_asset_config(self.asset)
            baseline_vol = float(cfg.typical_1m_volatility)
            base_min_diff = float(cfg.min_spot_diff)
        except Exception:
            baseline_vol = 14.0
            base_min_diff = 25.0
        live_vol = self.default_btc_1m_volatility if self.default_btc_1m_volatility > 0 else baseline_vol

        # Dynamic Strike Distance Scaling: Scale minimum separation proportionally with spot price
        # Baseline is self.min_spot_diff (or asset config default), scaling dynamically to prevent tight noise trades
        base_diff = float(self.min_spot_diff) if getattr(self, "min_spot_diff", None) is not None else base_min_diff
        effective_min_diff = max(base_diff, getattr(self, "_last_spot_price", 0.0) * 0.00025)
        floor_moat = effective_min_diff * 1.15
        ceiling_moat = effective_min_diff * 2.15

        expected_full_cycle_noise = baseline_vol * math.sqrt(cycle_mins)
        if expected_full_cycle_noise > 1e-9:
            z_asset = ceiling_moat / expected_full_cycle_noise
        else:
            z_asset = 1.40

        dynamic_moat = z_asset * live_vol * math.sqrt(tau_mins)
        return max(floor_moat, min(ceiling_moat, dynamic_moat))

    def compute_fused_probabilities(
        self,
        spot_diff: float,
        time_to_expiry_s: float,
        l2_book: Optional[L2BookState] = None,
    ) -> Tuple[float, float, float, Optional[Dict[str, Any]]]:
        """Compute Bayesian fused win probabilities combining macro Gaussian drift and ONNX orderflow.

        Returns:
            (p_up, p_down, p_wait, onnx_telemetry)
        """
        vol = max(1.0, self.default_btc_1m_volatility)
        t_factor = math.sqrt(max(1.0, time_to_expiry_s / 60.0))
        p_up_macro = 0.5 * (1.0 + math.erf(spot_diff / (vol * t_factor)))
        p_down_macro = 1.0 - p_up_macro

        if self.onnx_engine is None or l2_book is None:
            return p_up_macro, p_down_macro, 0.0, None

        try:
            onnx_res = self.onnx_engine.process_orderbook_tick(l2_book)
            if not isinstance(onnx_res, dict):
                return p_up_macro, p_down_macro, 0.0, None

            p_long_micro = float(onnx_res.get("prob_long", 0.333))
            p_short_micro = float(onnx_res.get("prob_short", 0.333))
            p_wait_micro = float(onnx_res.get("prob_wait", 0.334))

            micro_dir_sum = p_long_micro + p_short_micro
            if micro_dir_sum > 0.001:
                p_up_micro = p_long_micro / micro_dir_sum
                p_down_micro = p_short_micro / micro_dir_sum
            else:
                p_up_micro, p_down_micro = 0.5, 0.5

            # Dynamic time decay weighting
            # T_rem > 300s: orderflow micro has maximum weight
            # T_rem <= 60s: settlement TWAP moneyness dictates near 100%
            decay = min(1.0, max(0.0, time_to_expiry_s / 900.0))
            w_micro = self.fusion_weight_micro * decay
            w_macro = 1.0 - w_micro

            p_up = float((w_macro * p_up_macro) + (w_micro * p_up_micro))
            p_down = float((w_macro * p_down_macro) + (w_micro * p_down_micro))

            total = p_up + p_down
            if total > 0.0:
                p_up /= total
                p_down /= total

            return p_up, p_down, p_wait_micro, onnx_res
        except Exception as exc:
            logger.warning("[BOT1_V4] ONNX inference fallback to macro drift: %s", exc)
            return p_up_macro, p_down_macro, 0.0, None

    def compute_market_probabilities(
        self,
        book: Optional[L2BookState] = None,
        spot_price: float = 0.0,
        target_strike: float = 0.0,
        time_to_expiry_s: float = 300.0,
    ) -> Tuple[float, float]:
        """Compute market probabilities with Bayesian ONNX fusion for exit evaluator."""
        spot_diff = spot_price - target_strike if spot_price > 0.0 and target_strike > 0.0 else 0.0
        p_up, p_down, _, _ = self.compute_fused_probabilities(
            spot_diff=spot_diff,
            time_to_expiry_s=time_to_expiry_s,
            l2_book=book,
        )
        return p_up, p_down

    def evaluate_exit(
        self,
        side: OrderSide | str,
        entry_price: Decimal,
        size: int,
        book: Optional[L2BookState],
        time_to_expiry_s: float,
        spot_price: float = 0.0,
        target_strike: float = 0.0,
        peak_bid: Optional[Decimal] = None,
        spot_velocity_3s: float = 0.0,
        twap_60s: Optional[float] = None,
        rolling_vol_1m: Optional[float] = None,
        **kwargs: Any,
    ) -> DominationExitDecision:
        """Evaluate open position against quantitative Take-Profit and Early Liquidation rules using upgraded Doubt Harvest math."""
        return self.exit_evaluator.evaluate_exit(
            side=side,
            entry_price=entry_price,
            size=size,
            book=book,
            time_to_expiry_s=time_to_expiry_s,
            spot_price=spot_price,
            target_strike=target_strike,
            peak_bid=peak_bid,
            spot_velocity_3s=spot_velocity_3s,
            twap_60s=twap_60s,
            rolling_vol_1m=rolling_vol_1m,
            **kwargs,
        )

    def get_parameters(self) -> dict[str, Any]:
        """Return current strategy parameters."""
        return {
            "asset": self.asset.value if hasattr(self.asset, "value") else str(self.asset),
            "discount_limit_price": float(self.discount_limit_price),
            "max_entry_price": float(self.max_entry_price),
            "min_confidence": round(float(self.min_confidence) * 100.0, 1) if self.min_confidence <= 1.0 else round(float(self.min_confidence), 1),
            "min_edge_pct": round(float(self.min_edge_pct) * 100.0, 1),
            "min_ev_hurdle_dollars": float(self.min_ev_hurdle_dollars),
            "min_spot_diff": float(self.min_spot_diff),
            "default_btc_1m_volatility": float(self.default_btc_1m_volatility),
            "vpin_toxic_threshold": round(float(self.vpin_toxic_threshold), 2),
            "take_profit_price_threshold": float(self.take_profit_price_threshold),
            "opening_quarantine_seconds": float(self.opening_quarantine_seconds),
            "max_clob_spread_cents": float(self.max_clob_spread_cents),
            "max_turnover_per_event": int(self.max_turnover_per_event),
            "enable_doubt_harvest": bool(self.enable_doubt_harvest),
        }

    def update_parameters(
        self,
        min_confidence: Optional[float] = None,
        min_spot_diff: Optional[float] = None,
        discount_limit_price: Optional[float] = None,
        max_entry_price: Optional[float] = None,
        vpin_toxic_threshold: Optional[float] = None,
        opening_quarantine_seconds: Optional[float] = None,
        max_clob_spread_cents: Optional[float] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Dynamically update strategy parameters on the fly."""
        if min_confidence is not None:
            val = float(min_confidence)
            self.min_confidence = val if val <= 1.0 else (val / 100.0)
        if min_spot_diff is not None:
            self.min_spot_diff = float(min_spot_diff)
        if discount_limit_price is not None:
            self.discount_limit_price = Decimal(str(discount_limit_price))
        if max_entry_price is not None:
            self.max_entry_price = Decimal(str(max_entry_price))
        if vpin_toxic_threshold is not None:
            self.vpin_toxic_threshold = float(vpin_toxic_threshold)
        if opening_quarantine_seconds is not None:
            self.opening_quarantine_seconds = float(opening_quarantine_seconds)
        if max_clob_spread_cents is not None:
            self.max_clob_spread_cents = float(max_clob_spread_cents)
        return self.get_parameters()

    def evaluate(
        self,
        book: L2BookState,
        spot_price: float,
        target_strike: float,
        time_to_expiry_s: float,
        recent_trades: Optional[list[TradeEvent]] = None,
        total_equity: Decimal = Decimal("100.00"),
        max_position_size: int = 1,
        estimated_vpin: float = 0.20,
        cycle_id: str = "DEFAULT_CYCLE",
        spot_velocity_3s: float = 0.0,
        asset: CryptoAsset = CryptoAsset.BTC,
        **kwargs: Any,
    ) -> Bot1V4Decision:
        """Unified evaluation adapter conforming to BaseStrategyEngine/StrategyEvaluationCoordinator."""
        return self.evaluate_market_opportunity(
            spot_price=spot_price,
            target_strike=target_strike,
            time_to_expiry_s=time_to_expiry_s,
            l2_book=book,
            vpin=estimated_vpin,
            asset=asset,
            cycle_id=cycle_id,
            spot_velocity_3s=spot_velocity_3s,
        )

    def evaluate_market_opportunity(
        self,
        spot_price: float,
        target_strike: float,
        time_to_expiry_s: float,
        l2_book: L2BookState,
        vpin: float = 0.20,
        asset: CryptoAsset = CryptoAsset.BTC,
        cycle_id: str = "DEFAULT_CYCLE",
        spot_velocity_3s: float = 0.0,
    ) -> Bot1V4Decision:
        """Evaluate Bot 1 V4 Quantitative Signal with Turnover and EV Math coupling."""
        # Auto-sync with Single Source of Truth on disk before evaluation
        try:
            from kalshi_sim.truth_synchronizer import truth_synchronizer
            truth_synchronizer.sync_engine(self, asset=asset.value if hasattr(asset, "value") else str(asset))
        except Exception:
            pass

        self._last_spot_price = spot_price
        spot_diff = spot_price - target_strike
        turnovers = self.get_completed_turnovers(cycle_id)

        # 1. Check Max Turnover Cap
        if turnovers >= self.max_turnover_per_event:
            return Bot1V4Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="max_turnover_cap",
                playbook_stage="none",
                p_up=0.5, p_down=0.5, p_wait=1.0,
                vpin=vpin, vpin_is_safe=True,
                ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                kelly_f_yes=0.0, kelly_f_no=0.0,
                recommended_side="wait", recommended_contracts=0,
                rationale=f"Max Turnover Cap Hit ({turnovers}/{self.max_turnover_per_event} round-trips completed)",
                edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                limit_price=float(self.discount_limit_price),
                turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
            )

        # 2. Bayesian Fused Win Probability & VPIN Check
        p_up, p_down, p_wait_micro, onnx_res = self.compute_fused_probabilities(
            spot_diff=spot_diff,
            time_to_expiry_s=time_to_expiry_s,
            l2_book=l2_book,
        )
        onnx_sig = str(onnx_res.get("signal", "WAIT")) if onnx_res else "NONE"
        onnx_conf = float(onnx_res.get("confidence", 0.0)) if onnx_res else 0.0
        fused_source = "bayesian_fusion" if onnx_res is not None else "macro_erf"

        # Check VPIN Toxicity Veto (from book VPIN or ONNX VPIN)
        vpin_eval = float(onnx_res.get("vpin_score", vpin)) if onnx_res else vpin
        onnx_vpin_veto = bool(onnx_res.get("vpin_veto", False)) if onnx_res else False
        vpin_safe = (vpin_eval < self.vpin_toxic_threshold) and not onnx_vpin_veto
        if not vpin_safe:
            return Bot1V4Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="vpin_toxicity_veto",
                playbook_stage="none",
                p_up=p_up, p_down=p_down, p_wait=1.0,
                vpin=vpin_eval, vpin_is_safe=False,
                ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                kelly_f_yes=0.0, kelly_f_no=0.0,
                recommended_side="wait", recommended_contracts=0,
                rationale=f"VPIN Toxicity Veto (VPIN {vpin_eval:.2f} >= {self.vpin_toxic_threshold:.2f})",
                edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                limit_price=float(self.discount_limit_price),
                turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                onnx_signal=onnx_sig,
                onnx_confidence=onnx_conf,
                fused_source=fused_source,
            )

        # 2.2 CLOB Spread Corridor Cap (Vance Liquidity Gate)
        if l2_book is not None and l2_book.best_yes_ask is not None and l2_book.best_yes_bid is not None:
            clob_spread = float(l2_book.best_yes_ask - l2_book.best_yes_bid)
            if clob_spread > self.max_clob_spread_cents:
                return Bot1V4Decision(
                    strategy_id=self.STRATEGY_ID,
                    strategy_name=self.STRATEGY_NAME,
                    active_playbook="wide_clob_spread_veto",
                    playbook_stage="none",
                    p_up=0.5, p_down=0.5, p_wait=1.0,
                    vpin=vpin_eval, vpin_is_safe=True,
                    ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                    kelly_f_yes=0.0, kelly_f_no=0.0,
                    recommended_side="wait", recommended_contracts=0,
                    rationale=f"Wide CLOB Spread Veto: Spread ${clob_spread:.2f} > ${self.max_clob_spread_cents:.2f} corridor cap. Suppressing entry.",
                    edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                    limit_price=float(self.discount_limit_price),
                    turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                    ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                    onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
                )

        # 2.3 Opening Cycle Noise Quarantine Gate (Anti-False Breakout Shield)
        cycle_duration_s = 900.0
        p1_max_s = cycle_duration_s - self.opening_quarantine_seconds
        if time_to_expiry_s > p1_max_s:
            quarantine_remaining = int(time_to_expiry_s - p1_max_s)
            return Bot1V4Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="opening_cycle_quarantine",
                playbook_stage="none",
                p_up=p_up, p_down=p_down, p_wait=1.0,
                vpin=vpin_eval, vpin_is_safe=True,
                ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                kelly_f_yes=0.0, kelly_f_no=0.0,
                recommended_side="wait", recommended_contracts=0,
                rationale=f"Opening Cycle Quarantine Active: T={int(time_to_expiry_s)}s left > {int(p1_max_s)}s threshold ({quarantine_remaining}s left). Quarantining early noise.",
                edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                limit_price=float(self.discount_limit_price),
                turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
            )

        # 2.4 Dynamic Proximity Moat Filter (Volatility-Scaled Distance Filter)
        dynamic_moat = self.get_dynamic_proximity_threshold(time_to_expiry_s, cycle_duration_s=cycle_duration_s)
        if abs(spot_diff) < dynamic_moat:
            return Bot1V4Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="dynamic_proximity_moat_veto",
                playbook_stage="none",
                p_up=p_up, p_down=p_down, p_wait=1.0,
                vpin=vpin_eval, vpin_is_safe=True,
                ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                kelly_f_yes=0.0, kelly_f_no=0.0,
                recommended_side="wait", recommended_contracts=0,
                rationale=f"Proximity Moat Veto: |Diff| ${abs(spot_diff):.2f} < ${dynamic_moat:.2f} dynamic threshold at T={int(time_to_expiry_s)}s. Too close to strike.",
                edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                limit_price=float(self.discount_limit_price),
                turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
            )

        # 3. Dynamic EV & Win Probability Coupling
        req_p_win_base = self.compute_required_win_probability(self.discount_limit_price)
        dynamic_limit_yes = self.compute_dynamic_limit_price(p_up)
        dynamic_limit_no = self.compute_dynamic_limit_price(p_down)

        recommended_side = "wait"
        rationale = "No edge meeting EV hurdle"
        chosen_limit_price = float(self.discount_limit_price)

        ev_yes = p_up * 1.0 - float(dynamic_limit_yes)
        ev_no = p_down * 1.0 - float(dynamic_limit_no)

        ai_tag = f" [AI Conf {onnx_conf*100:.0f}%]" if fused_source == "bayesian_fusion" else ""
        if p_up >= (float(dynamic_limit_yes) + float(self.min_ev_hurdle_dollars)) or ev_yes >= float(self.min_ev_hurdle_dollars):
            if p_up >= req_p_win_base:
                recommended_side = "yes"
                chosen_limit_price = min(float(dynamic_limit_yes), float(self.max_entry_price))
                rationale = f"Bot 1 V4 YES Signal{ai_tag}: P_win {p_up:.1%} (Dynamic Limit ${chosen_limit_price:.2f}, Net EV +${ev_yes:.3f})"
        elif p_down >= (float(dynamic_limit_no) + float(self.min_ev_hurdle_dollars)) or ev_no >= float(self.min_ev_hurdle_dollars):
            if p_down >= req_p_win_base:
                recommended_side = "no"
                chosen_limit_price = min(float(dynamic_limit_no), float(self.max_entry_price))
                rationale = f"Bot 1 V4 NO Signal{ai_tag}: P_win {p_down:.1%} (Dynamic Limit ${chosen_limit_price:.2f}, Net EV +${ev_no:.3f})"

        return Bot1V4Decision(
            strategy_id=self.STRATEGY_ID,
            strategy_name=self.STRATEGY_NAME,
            active_playbook="playbook2_drift",
            playbook_stage="drift",
            p_up=p_up, p_down=p_down, p_wait=1.0 - max(p_up, p_down),
            vpin=vpin_eval, vpin_is_safe=True,
            ev_yes=ev_yes, ev_no=ev_no,
            edge_yes=p_up - chosen_limit_price,
            edge_no=p_down - chosen_limit_price,
            kelly_f_yes=0.25 if recommended_side == "yes" else 0.0,
            kelly_f_no=0.25 if recommended_side == "no" else 0.0,
            recommended_side=recommended_side,
            recommended_contracts=(
                StatisticalEVEngine.compute_conviction_tier(
                    ai_prob=p_up if recommended_side == "yes" else p_down,
                    price=Decimal(str(chosen_limit_price)),
                    vpin=vpin_eval,
                    time_to_expiry_s=time_to_expiry_s,
                    spot_distance_to_strike=spot_diff,
                )
                if recommended_side != "wait" else 0
            ),
            rationale=rationale,
            edge_pct=max(p_up, p_down) - chosen_limit_price,
            time_to_expiry_s=time_to_expiry_s,
            spot_diff=spot_diff,
            limit_price=chosen_limit_price,
            turnovers_completed=turnovers,
            max_turnovers=self.max_turnover_per_event,
            ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
            onnx_signal=onnx_sig,
            onnx_confidence=onnx_conf,
            fused_source=fused_source,
        )

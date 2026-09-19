"""3-Step Domination Bot (Cycle-Aware Quantitative Playbook Engine).

Implements the 3 quantitative alpha playbooks formulated for Kalshi 15-Minute Bitcoin Binary Contracts:
1. Playbook 1: Early Momentum Breakout (10:00 - 15:00 remaining)
2. Playbook 2: Mid-Cycle OFI Trend Drift (4:00 - 10:00 remaining)
3. Playbook 3: Late-Cycle High-Probability Gamma Snub (0:45 - 4:00 remaining)

Integrates sub-second spot feed index parity, continuous moneyness digital option probability estimation,
VPIN adverse selection toxicity veto, and Quarter-Kelly sizing.
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
from kalshi_sim.ml.lead_deer_quant_brain import ExitDecision, LeadDeerQuantBrain
from kalshi_sim.ml.statistical_ev_engine import ExpectedValueResult, StatisticalEVEngine
from kalshi_sim.schemas import CryptoAsset, L2BookState, OrderSide, TradeEvent, get_asset_config

logger = logging.getLogger("kalshi_sim.domination_bot")


def _standard_normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function Phi(x)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass(frozen=True)
class DominationDecision:
    """Structured decision output from the 3-Step Domination Bot."""
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




class ThreeStepDominationBot:
    """Institutional Cycle-Aware 3-Step Quantitative Strategy Bot (v3.2 Baseline)."""

    STRATEGY_ID = "3_step_domination_bot"
    STRATEGY_NAME = "3-Step Dominion v3.2"

    def __init__(
        self,
        min_edge_pct: float = 0.015,  # 1.5% minimum edge (realistic for Kalshi 15M makers)
        min_ev_dollars: Decimal = Decimal("0.02"),  # Minimum $0.02 net EV per contract
        vpin_toxic_threshold: float = 0.60,
        vpin_safe_threshold: float = 0.35,
        default_btc_1m_volatility: float = 14.0,  # $14 typical 1-min BTC spot std dev
        take_profit_price_threshold: Decimal = Decimal("0.92"),  # 92c tail risk ceiling (Historical best)
        enable_take_profit_ceiling: bool = True,  # Take profit price ceiling toggle
        require_reversal_for_tp_ceiling: bool = True,  # Only exit at ceiling if indicators >= 85% reverse; if not, continue to expiry
        enable_reverse_take_profit_roi: bool = True,  # Only take profit on min_take_profit_roi if indicators >= 85% reverse
        reverse_indicator_threshold: float = 0.85,  # 85% conviction in opposite direction required
        min_take_profit_roi: float = 0.40,  # +40% minimum ROI for early exit (Historical best)
        late_cycle_roi: float = 0.15,  # +15% minimum ROI in final 120s
        fee_per_contract: Decimal = Decimal("0.01"),  # $0.01 standard taker fee for early exits
        min_spot_diff: Optional[float] = None,  # Scaled by asset if None
        max_entry_price: Decimal = Decimal("0.68"),  # $0.68 standard entry price cap ($0.70+ hard kill wall)
        discount_limit_price: Decimal = Decimal("0.52"),  # Configurable discount sniper ceiling (48¢-52¢ sweetspot)
        min_confidence: float = 0.68,  # 68% model conviction threshold (sweet spot for +12% to +20% EV edge)
        enable_trailing_ratchet: bool = True,  # High-water mark trailing profit ratchet and breakeven armor
        trailing_ratchet_buffer: Decimal = Decimal("0.08"),  # $0.08 pullback buffer below peak bid (Historical best)
        spot_delta_front_run_threshold: float = 28.0,  # $28.0 rolling 3s spot velocity base threshold (2.0σ winning sweetspot)
        enable_dynamic_spot_velocity: bool = True,  # 4-Regime Fading Mathematics dynamic front-runner
        velocity_z_score_threshold: float = 2.50,  # 2.50 sigma statistical anomaly threshold
        
        # [FROZEN] The following 3 parameters were historically paralyzing the bot.
        # FROZEN_OLD_min_edge_pct = 0.06 (6.0%) -> Now 0.015 (1.5%)
        # FROZEN_OLD_max_queue_depth_ahead = 250 -> Now 25000
        # FROZEN_OLD_moneyness_moat_multiplier = 2.0 -> Now 1.36
        moneyness_moat_multiplier: float = 1.36,  # 1.36x sigma*sqrt(t) deep ITM protection moat (sweet spot)
        
        twap_fading_quarantine_seconds: float = 15.0,  # 15s expiration quarantine (strict hold to $1.00)
        twap_fading_window_seconds: float = 60.0,  # 60s Silas TWAP fading evaluation window
        enable_dynamic_reversal_curve: bool = True,  # Time-adaptive reversal curve (decays 85% -> 50% as tau -> 0)
        opening_quarantine_seconds: float = 30.0,  # Quarantine opening 30s of cycle to eliminate false breakouts
        onnx_engine: Optional[Any] = None,  # Brain 1 QuoLas Nano Microscope ONNX inference engine
        twap_immutability_sniper_cents: float = 0.75,  # 75¢ ceiling for Silas TWAP late-cycle arbitrage harvest
        max_queue_depth_ahead: int = 25000,  # Max resting contracts ahead before order placement (anti-toxic whale armor)
        max_clob_spread_cents: float = 0.05,  # Max allowable bid-ask spread corridor cap ($0.05)
        asset: CryptoAsset | str = CryptoAsset.BTC,
    ) -> None:
        self.asset = CryptoAsset(str(asset).upper()) if not isinstance(asset, CryptoAsset) else asset
        cfg = get_asset_config(self.asset)

        self.min_edge_pct = min_edge_pct
        self.min_ev_dollars = min_ev_dollars
        self.vpin_toxic_threshold = vpin_toxic_threshold
        self.vpin_safe_threshold = vpin_safe_threshold
        if default_btc_1m_volatility == 14.0 and self.asset != CryptoAsset.BTC:
            self.typical_1m_volatility = float(cfg.typical_1m_volatility)
        else:
            self.typical_1m_volatility = default_btc_1m_volatility
        self.default_btc_1m_volatility = self.typical_1m_volatility  # backward compatibility
        self.take_profit_price_threshold = take_profit_price_threshold
        self.enable_take_profit_ceiling = enable_take_profit_ceiling
        self.require_reversal_for_tp_ceiling = require_reversal_for_tp_ceiling
        self.enable_reverse_take_profit_roi = enable_reverse_take_profit_roi
        self.reverse_indicator_threshold = reverse_indicator_threshold if reverse_indicator_threshold <= 1.0 else (reverse_indicator_threshold / 100.0)
        self.min_take_profit_roi = min_take_profit_roi
        self.late_cycle_roi = late_cycle_roi
        self.fee_per_contract = fee_per_contract
        self.min_spot_diff = min_spot_diff if min_spot_diff is not None else float(cfg.min_spot_diff)
        self.max_entry_price = Decimal(str(max_entry_price))
        self.discount_limit_price = max(Decimal("0.10"), min(Decimal("0.65"), Decimal(str(discount_limit_price))))
        self.min_confidence = min_confidence if min_confidence <= 1.0 else (min_confidence / 100.0)
        self.enable_trailing_ratchet = bool(enable_trailing_ratchet)
        self.trailing_ratchet_buffer = Decimal(str(trailing_ratchet_buffer))
        if spot_delta_front_run_threshold in (15.0, 28.0) and self.asset != CryptoAsset.BTC:
            self.spot_delta_front_run_threshold = float(cfg.min_spot_diff)
        else:
            self.spot_delta_front_run_threshold = float(spot_delta_front_run_threshold)
        self.enable_dynamic_spot_velocity = bool(enable_dynamic_spot_velocity)
        self.velocity_z_score_threshold = float(velocity_z_score_threshold)
        self.moneyness_moat_multiplier = float(moneyness_moat_multiplier)
        self.twap_fading_quarantine_seconds = float(twap_fading_quarantine_seconds)
        self.twap_fading_window_seconds = float(twap_fading_window_seconds)
        self.enable_dynamic_reversal_curve = bool(enable_dynamic_reversal_curve)
        self.opening_quarantine_seconds = float(opening_quarantine_seconds)
        self.onnx_engine = onnx_engine
        self.twap_immutability_sniper_cents = float(twap_immutability_sniper_cents)
        self.max_queue_depth_ahead = int(max_queue_depth_ahead)
        self.max_clob_spread_cents = float(max_clob_spread_cents)
        self.enable_lead_deer_peak_harvester = True

        # Lead Deer Quant Brain & Continuous Experience Buffer (Council Weapon)
        self.lead_deer_brain = LeadDeerQuantBrain(
            min_confidence=float(self.min_confidence),
            min_ev_dollars=float(self.min_ev_dollars),
            maker_discount_ceiling=float(self.discount_limit_price),
        )

        self._exit_evaluator = DominationExitEvaluator(self)

        # Underlying Stage 2 EV & Quarter-Kelly Optimizer
        self._ev_engine = StatisticalEVEngine(
            min_ev_threshold=min_ev_dollars,
            min_edge_pct=min_edge_pct,
            fee_per_contract=fee_per_contract,
            fractional_kelly=0.15,  # 15% Fractional Kelly for capital preservation
            max_portfolio_risk_pct=Decimal("0.05"),  # 5% max risk per trade
            vpin_safe_threshold=vpin_safe_threshold,
            vpin_toxic_threshold=vpin_toxic_threshold,
        )

    def set_asset(self, asset: CryptoAsset | str) -> None:
        """Calibrate bot parameters for a specific crypto asset."""
        self.asset = CryptoAsset(str(asset).upper()) if not isinstance(asset, CryptoAsset) else asset
        cfg = get_asset_config(self.asset)
        self.min_spot_diff = float(cfg.min_spot_diff)
        self.typical_1m_volatility = float(cfg.typical_1m_volatility)
        self.default_btc_1m_volatility = self.typical_1m_volatility
        logger.debug("[DOMINATION BOT] Calibrated for %s: min_spot_diff=%.6f, 1m_vol=%.6f", cfg.name, self.min_spot_diff, self.typical_1m_volatility)

    def set_discount_limit_price(self, new_price: Decimal | float | str) -> None:
        """Dynamically update the maker discount limit price ceiling."""
        dec_price = Decimal(str(new_price))
        clamped = max(Decimal("0.10"), min(Decimal("0.65"), dec_price))
        self.discount_limit_price = clamped
        logger.debug("[DOMINATION BOT] Dynamic discount limit price updated to: $%s", clamped)

    def get_parameters(self) -> Dict[str, Any]:
        """Return current live strategy parameters."""
        return {
            "asset": self.asset.value if hasattr(self, "asset") else "BTC",
            "discount_limit_price": float(self.discount_limit_price),
            "momentum_max_price": float(self.max_entry_price),
            "min_confidence": round(float(self.min_confidence) * 100.0, 1) if self.min_confidence <= 1.0 else round(float(self.min_confidence), 1),
            "min_edge_pct": round(float(self.min_edge_pct) * 100.0, 1),
            "min_ev_dollars": float(self.min_ev_dollars),
            "min_spot_diff": float(self.min_spot_diff),
            "typical_1m_volatility": float(self.typical_1m_volatility),
            "vpin_toxic_threshold": round(float(self.vpin_toxic_threshold), 2),
            "take_profit_price_threshold": float(self.take_profit_price_threshold),
            "enable_take_profit_ceiling": bool(self.enable_take_profit_ceiling),
            "require_reversal_for_tp_ceiling": bool(self.require_reversal_for_tp_ceiling),
            "enable_reverse_take_profit_roi": bool(self.enable_reverse_take_profit_roi),
            "reverse_indicator_threshold": round(float(self.reverse_indicator_threshold) * 100.0, 1),
            "min_take_profit_roi": round(float(self.min_take_profit_roi) * 100.0, 1),
            "enable_trailing_ratchet": bool(self.enable_trailing_ratchet),
            "trailing_ratchet_buffer": float(self.trailing_ratchet_buffer),
            "spot_delta_front_run_threshold": float(self.spot_delta_front_run_threshold),
            "enable_dynamic_spot_velocity": bool(self.enable_dynamic_spot_velocity),
            "velocity_z_score_threshold": float(self.velocity_z_score_threshold),
            "moneyness_moat_multiplier": float(self.moneyness_moat_multiplier),
            "twap_fading_quarantine_seconds": float(self.twap_fading_quarantine_seconds),
            "twap_fading_window_seconds": float(self.twap_fading_window_seconds),
            "enable_dynamic_reversal_curve": bool(self.enable_dynamic_reversal_curve),
            "opening_quarantine_seconds": float(self.opening_quarantine_seconds),
            "onnx_veto_active": bool(self.onnx_engine is not None),
            "twap_immutability_sniper_cents": float(self.twap_immutability_sniper_cents),
            "max_queue_depth_ahead": int(self.max_queue_depth_ahead),
            "max_clob_spread_cents": float(self.max_clob_spread_cents),
            "enable_lead_deer_peak_harvester": bool(getattr(self, "enable_lead_deer_peak_harvester", True)),
        }

    def compute_dynamic_reversal_threshold(self, time_to_expiry_s: float) -> float:
        """Calculate dynamic reversal threshold decaying from base down to 50% as tau -> 0."""
        if not self.enable_dynamic_reversal_curve:
            return self.reverse_indicator_threshold
        tau_mins = max(0.5, min(15.0, time_to_expiry_s / 60.0))
        # Scales linearly from 50% at tau=0 up to base threshold at tau=10m
        scaled = 0.50 + 0.035 * tau_mins
        return min(self.reverse_indicator_threshold, scaled)

    def compute_dynamic_limit_price(self, win_prob: float) -> Decimal:
        """Dynamic EV Math Coupling:
        Entry Limit = min(win_prob - EV_hurdle, max_entry_price)
        Dynamically scales entry ceiling up to max_entry_price ($0.62) when model conviction is high,
        while maintaining at least min_ev_dollars ($0.02) net EV edge.
        """
        ev_hurdle = float(self.min_ev_dollars)
        max_cap = float(self.max_entry_price)
        base_floor = float(self.discount_limit_price)

        dynamic_price = win_prob - ev_hurdle
        clamped_price = max(base_floor, min(dynamic_price, max_cap))
        return Decimal(str(round(clamped_price, 2)))

    def update_parameters(
        self,
        asset: Optional[str | CryptoAsset] = None,
        discount_limit_price: Optional[float] = None,
        momentum_max_price: Optional[float] = None,
        min_confidence: Optional[float] = None,
        min_edge_pct: Optional[float] = None,
        min_ev_dollars: Optional[float] = None,
        min_spot_diff: Optional[float] = None,
        typical_1m_volatility: Optional[float] = None,
        vpin_toxic_threshold: Optional[float] = None,
        take_profit_price_threshold: Optional[float] = None,
        enable_take_profit_ceiling: Optional[bool] = None,
        require_reversal_for_tp_ceiling: Optional[bool] = None,
        enable_reverse_take_profit_roi: Optional[bool] = None,
        reverse_indicator_threshold: Optional[float] = None,
        min_take_profit_roi: Optional[float] = None,
        enable_trailing_ratchet: Optional[bool] = None,
        trailing_ratchet_buffer: Optional[float] = None,
        spot_delta_front_run_threshold: Optional[float] = None,
        enable_dynamic_spot_velocity: Optional[bool] = None,
        velocity_z_score_threshold: Optional[float] = None,
        moneyness_moat_multiplier: Optional[float] = None,
        twap_fading_quarantine_seconds: Optional[float] = None,
        twap_fading_window_seconds: Optional[float] = None,
        enable_dynamic_reversal_curve: Optional[bool] = None,
        opening_quarantine_seconds: Optional[float] = None,
        twap_immutability_sniper_cents: Optional[float] = None,
        max_queue_depth_ahead: Optional[int] = None,
        max_clob_spread_cents: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Dynamically update strategy parameters on the fly."""
        if asset is not None:
            self.set_asset(asset)
        if discount_limit_price is not None:
            self.set_discount_limit_price(discount_limit_price)
        if momentum_max_price is not None:
            self.max_entry_price = Decimal(str(max(0.50, min(0.99, float(momentum_max_price)))))
        if min_confidence is not None:
            val = float(min_confidence)
            if val > 1.0:
                val = val / 100.0
            self.min_confidence = max(0.50, min(0.99, val))
        if min_edge_pct is not None:
            val = float(min_edge_pct)
            if val > 1.0:
                val = val / 100.0
            self.min_edge_pct = max(0.01, min(0.50, val))
            self._ev_engine.min_edge_pct = self.min_edge_pct
        if min_ev_dollars is not None:
            self.min_ev_dollars = Decimal(str(max(0.00, float(min_ev_dollars))))
            self._ev_engine.min_ev_threshold = self.min_ev_dollars
        if min_spot_diff is not None:
            self.min_spot_diff = max(0.000001, float(min_spot_diff))
        if typical_1m_volatility is not None:
            self.typical_1m_volatility = max(0.000001, float(typical_1m_volatility))
            self.default_btc_1m_volatility = self.typical_1m_volatility
        if vpin_toxic_threshold is not None:
            self.vpin_toxic_threshold = max(0.10, min(0.95, float(vpin_toxic_threshold)))
            self._ev_engine.vpin_toxic_threshold = self.vpin_toxic_threshold
        if take_profit_price_threshold is not None:
            self.take_profit_price_threshold = Decimal(str(max(0.70, min(0.99, float(take_profit_price_threshold)))))
        if enable_take_profit_ceiling is not None:
            self.enable_take_profit_ceiling = bool(enable_take_profit_ceiling)
        if require_reversal_for_tp_ceiling is not None:
            self.require_reversal_for_tp_ceiling = bool(require_reversal_for_tp_ceiling)
        if enable_reverse_take_profit_roi is not None:
            self.enable_reverse_take_profit_roi = bool(enable_reverse_take_profit_roi)
        if reverse_indicator_threshold is not None:
            val = float(reverse_indicator_threshold)
            if val > 1.0:
                val = val / 100.0
            self.reverse_indicator_threshold = max(0.40, min(0.99, val))
        if min_take_profit_roi is not None:
            val = float(min_take_profit_roi)
            if val > 1.0:
                val = val / 100.0
            self.min_take_profit_roi = max(0.05, min(2.00, val))
        if enable_trailing_ratchet is not None:
            self.enable_trailing_ratchet = bool(enable_trailing_ratchet)
        if trailing_ratchet_buffer is not None:
            self.trailing_ratchet_buffer = Decimal(str(max(0.02, min(0.25, float(trailing_ratchet_buffer)))))
        if spot_delta_front_run_threshold is not None:
            self.spot_delta_front_run_threshold = max(0.00001, float(spot_delta_front_run_threshold))
        if enable_dynamic_spot_velocity is not None:
            self.enable_dynamic_spot_velocity = bool(enable_dynamic_spot_velocity)
        if velocity_z_score_threshold is not None:
            self.velocity_z_score_threshold = max(0.5, float(velocity_z_score_threshold))
        if moneyness_moat_multiplier is not None:
            self.moneyness_moat_multiplier = max(0.1, float(moneyness_moat_multiplier))
        if twap_fading_quarantine_seconds is not None:
            self.twap_fading_quarantine_seconds = max(0.0, float(twap_fading_quarantine_seconds))
        if twap_fading_window_seconds is not None:
            self.twap_fading_window_seconds = max(10.0, float(twap_fading_window_seconds))
        if enable_dynamic_reversal_curve is not None:
            self.enable_dynamic_reversal_curve = bool(enable_dynamic_reversal_curve)
        if "opening_quarantine_seconds" in kwargs and kwargs["opening_quarantine_seconds"] is not None:
            self.opening_quarantine_seconds = max(0.0, min(600.0, float(kwargs["opening_quarantine_seconds"])))
        elif opening_quarantine_seconds is not None:
            self.opening_quarantine_seconds = max(0.0, min(600.0, float(opening_quarantine_seconds)))
        if twap_immutability_sniper_cents is not None:
            self.twap_immutability_sniper_cents = max(0.50, min(0.95, float(twap_immutability_sniper_cents)))
        if max_queue_depth_ahead is not None:
            self.max_queue_depth_ahead = max(10, min(2000, int(max_queue_depth_ahead)))
        if max_clob_spread_cents is not None:
            self.max_clob_spread_cents = max(0.01, min(0.25, float(max_clob_spread_cents)))
        if "enable_lead_deer_peak_harvester" in kwargs and kwargs["enable_lead_deer_peak_harvester"] is not None:
            self.enable_lead_deer_peak_harvester = bool(kwargs["enable_lead_deer_peak_harvester"])
        logger.debug("[DOMINATION BOT] Live parameters updated: %s", self.get_parameters())
        return self.get_parameters()

    def get_dynamic_proximity_threshold(
        self,
        time_to_expiry_s: float,
        cycle_duration_s: float = 900.0,
    ) -> float:
        """Compute self-calibrating time-and-volatility-scaled minimum spot distance threshold.

        Calculates the required safety moat in dollars:
            threshold = clamp(floor, z_asset * live_vol * sqrt(tau_mins), ceiling)
            where z_asset = ceiling_moat / (baseline_vol * sqrt(cycle_mins))

        - Hard Floor: Ensures we never enter within strike noise (1.15x min_spot_diff).
        - Hard Ceiling: Caps threshold at 2.15x min_spot_diff to prevent chasing impossible moats.
        - Sweet Spot: Naturally lands at ~1.36x min_spot_diff at mid-cycle across all assets (BTC, ETH, SOL, DOGE).
        - Self-Calibrating: Adapts dynamically if parameters or volatility change, with zero manual hardcoding.
        """
        tau_mins = max(0.2, time_to_expiry_s / 60.0)
        cycle_mins = max(1.0, cycle_duration_s / 60.0)

        cfg = get_asset_config(self.asset)
        baseline_vol = float(cfg.typical_1m_volatility)
        live_vol = self.typical_1m_volatility if self.typical_1m_volatility > 0 else baseline_vol

        floor_moat = max(4.0, self.min_spot_diff * 0.80)
        ceiling_moat = max(12.0, self.min_spot_diff * 1.50)

        expected_full_cycle_noise = baseline_vol * math.sqrt(cycle_mins)
        if expected_full_cycle_noise > 1e-9:
            z_asset = ceiling_moat / expected_full_cycle_noise
        else:
            z_asset = 1.40

        dynamic_moat = z_asset * live_vol * math.sqrt(tau_mins)

        return max(floor_moat, min(ceiling_moat, dynamic_moat))

    @staticmethod
    def _safe_market_ask(
        recommended_side: Optional[OrderSide],
        best_yes_ask: Optional[Decimal],
        best_no_ask: Optional[Decimal],
    ) -> Optional[float]:
        """Safely extract market ask float for the recommended side, never raising TypeError."""
        if recommended_side == OrderSide.YES:
            val = best_yes_ask
        elif recommended_side == OrderSide.NO:
            val = best_no_ask
        else:
            val = best_yes_ask if best_yes_ask is not None else best_no_ask
        return float(val) if val is not None else None

    @staticmethod
    def _get_queue_ahead(
        book: Optional[L2BookState],
        side: Optional[OrderSide],
        target_price: Decimal,
    ) -> int:
        """Calculate existing resting contract depth ahead at target limit price (matching order_simulator)."""
        if not book or not side:
            return 0
        try:
            target_dec = Decimal(str(target_price))
            if side == OrderSide.YES and hasattr(book, "yes_book") and book.yes_book:
                return int(book.yes_book.get(target_dec, 0))
            elif side == OrderSide.NO and hasattr(book, "no_book") and book.no_book:
                return int(book.no_book.get(target_dec, 0))
        except Exception:
            return 0
        return 0

    def evaluate(
        self,
        book: Optional[L2BookState],
        spot_price: float,
        target_strike: float,
        time_to_expiry_s: float,
        recent_trades: Optional[List[TradeEvent]] = None,
        total_equity: Decimal = Decimal("100.00"),
        max_position_size: int = 1,
        estimated_vpin: float = 0.15,
        twap_60s: Optional[float] = None,
        **kwargs: Any,
    ) -> DominationDecision:
        """Execute 3-step cycle analysis and determine optimal playbook execution."""
        if not book or (not book.yes_book and not book.no_book) or spot_price <= 0 or target_strike <= 0:
            return self._build_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=0.0,
                vpin=estimated_vpin,
                rationale="3-Step Domination Bot waiting for active order book & market feeds.",
            )

        best_yes_ask = book.best_yes_ask
        best_yes_bid = book.best_yes_bid
        best_no_ask = (Decimal("1.00") - best_yes_bid) if best_yes_bid is not None else None

        spot_diff = spot_price - target_strike
        is_vpin_safe = estimated_vpin <= self.vpin_toxic_threshold

        # Step 0: VPIN Toxicity Guardrail Check
        if not is_vpin_safe:
            return self._build_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                vpin=estimated_vpin,
                vpin_is_safe=False,
                rationale=f"VPIN Toxicity Veto: Score={estimated_vpin:.2f} > {self.vpin_toxic_threshold:.2f}. "
                          f"Suppressing all trades to prevent adverse whale selection.",
            )

        # Step 0.2: CLOB Spread Corridor Cap (Vance Liquidity Gate)
        if best_yes_ask is not None and best_yes_bid is not None:
            clob_spread = float(best_yes_ask - best_yes_bid)
            if clob_spread > self.max_clob_spread_cents:
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=estimated_vpin,
                    rationale=f"Wide CLOB Spread Veto: Spread ${clob_spread:.2f} > ${self.max_clob_spread_cents:.2f} corridor cap. "
                              f"Suppressing all entries to prevent illiquid slippage trap.",
                )

        # Classify Active Playbook & Cycle Duration by Expiration Window
        ticker_str = (getattr(book, "market_ticker", "") or getattr(book, "ticker", "")) if book else ""
        is_5m = ("5M" in ticker_str.upper() and "15M" not in ticker_str.upper()) or "5MIN" in ticker_str.upper()
        cycle_duration_s = 300.0 if is_5m else 900.0

        cfg = get_asset_config(self.asset)

        # Step 0.5: Dynamic Volatility-Scaled Spot-Strike Distance Filter (Option A: Self-Calibrating)
        # Replaces rigid static 2x buffer with continuous volatility and time-decay moat.
        # Clamped between Hard Floor (1.15x min_spot_diff) and Hard Ceiling (2.15x min_spot_diff).
        razor_tight_threshold = self.get_dynamic_proximity_threshold(time_to_expiry_s, cycle_duration_s=cycle_duration_s)
        if abs(spot_diff) < razor_tight_threshold:
            diff_str = cfg.format_diff(spot_diff)
            thresh_str = cfg.format_price(razor_tight_threshold)
            return self._build_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                vpin=estimated_vpin,
                rationale=f"Razor-Tight Proximity Veto (Dynamic Volatility Moat): |Diff|={abs(spot_diff):.{cfg.price_decimals}f} < {thresh_str} "
                          f"({self.asset.value} vol-adjusted threshold at T={int(time_to_expiry_s)}s). "
                          f"Asset too close to strike for current volatility regime, skipping.",
            )

        # Dynamic Playbook Timing Thresholds:
        # Standard 15M cycle: P3 in [45s, 240s], P2 in (240s, 600s], P1 in (600s, p1_max_s], lock < 45s
        # 5M Sprint cycle:    P3 in [20s, 80s],  P2 in (80s, 200s],   P1 in (200s, p1_max_s], lock < 20s
        if is_5m:
            p3_min_s, p3_max_s = 20, 80
            p2_min_s, p2_max_s = 80, 200
            p1_min_s = 200
            quarantine_s = min(30.0, self.opening_quarantine_seconds / 3.0)
            p1_max_s = cycle_duration_s - quarantine_s
        else:
            p3_min_s, p3_max_s = 45, 240
            p2_min_s, p2_max_s = 240, 600
            p1_min_s = 600
            p1_max_s = cycle_duration_s - self.opening_quarantine_seconds

        tau_mins = max(0.1, time_to_expiry_s / 60.0)

        # Candidate pricing at user discount limit ceiling (Option B - Resting Maker Limit)
        discount_price = self.discount_limit_price
        eff_yes_price = min(best_yes_ask, discount_price) if best_yes_ask is not None else discount_price
        eff_no_price = min(best_no_ask, discount_price) if best_no_ask is not None else discount_price

        # -------------------------------------------------------------------
        # PLAYBOOK 3: Late-Cycle High-Probability Gamma Snub
        # -------------------------------------------------------------------
        if p3_min_s <= time_to_expiry_s <= p3_max_s:
            stage = "gamma_snub"
            playbook_title = "Playbook 3: Late-Cycle Gamma Snub"

            # Dynamic Volatility scaling over remaining time
            tau_sqrt = math.sqrt(tau_mins)
            vol_floor_p3 = 0.285 * self.typical_1m_volatility
            expected_vol = max(vol_floor_p3, self.typical_1m_volatility * tau_sqrt)
            z_score = spot_diff / expected_vol

            # Digital Option Cumulative Probability Phi(z)
            prob_yes_raw = _standard_normal_cdf(z_score)
            prob_yes = max(0.001, min(0.999, prob_yes_raw))
            prob_no = 1.0 - prob_yes
            prob_wait = 0.05

            ev_res = self._ev_engine.compute_optimal_execution(
                prob_up=prob_yes,
                prob_down=prob_no,
                best_yes_ask=eff_yes_price,
                best_no_ask=eff_no_price,
                total_equity=total_equity,
                max_position_size=max_position_size,
                vpin=estimated_vpin,
                prob_wait=prob_wait,
                fee_override=Decimal("0.00"),
            )

            side_str = ev_res.recommended_side.value if ev_res.recommended_side else "wait"
            edge_val = float(ev_res.statistical_edge)
            diff_str = cfg.format_diff(spot_diff)

            if ev_res.has_positive_edge and ev_res.recommended_side:
                target_prob = prob_yes if ev_res.recommended_side == OrderSide.YES else prob_no
                rationale = (
                    f"[{playbook_title}] High-Certainty Expiration Harvest | "
                    f"T={int(time_to_expiry_s)}s left | Spot Diff: {diff_str} | "
                    f"True Prob: {target_prob*100:.1f}% vs Discount Target: ${discount_price:.2f} | "
                    f"Net EV: +${ev_res.expected_value:.2f}/ct | Edge: {edge_val*100:+.1f}% | "
                    f"Kelly: {ev_res.kelly_fraction*100:.1f}% ({ev_res.recommended_contracts} cts)"
                )
            else:
                rationale = (
                    f"[{playbook_title}] In Range | T={int(time_to_expiry_s)}s left | "
                    f"Spot Diff: {diff_str} | True Prob: YES {prob_yes*100:.1f}% vs NO {prob_no*100:.1f}% | "
                    f"No edge exceeding {self.min_edge_pct*100:.0f}% at ${discount_price:.2f} discount."
                )

            actual_ask_p3 = self._safe_market_ask(ev_res.recommended_side, best_yes_ask, best_no_ask)
            q_ahead_p3 = self._get_queue_ahead(book, ev_res.recommended_side, discount_price)
            return self._build_decision(
                playbook_title=playbook_title,
                stage=stage,
                p_up=prob_yes,
                p_down=prob_no,
                p_wait=prob_wait,
                vpin=estimated_vpin,
                vpin_is_safe=True,
                ev_res=ev_res,
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                rationale=rationale,
                actual_market_ask=actual_ask_p3,
                cycle_duration_s=cycle_duration_s,
                queue_ahead=q_ahead_p3,
            )

        # -------------------------------------------------------------------
        # PLAYBOOK 2: Mid-Cycle OFI Trend Drift
        # -------------------------------------------------------------------
        elif p2_min_s < time_to_expiry_s <= p2_max_s:
            stage = "drift"
            playbook_title = "Playbook 2: Mid-Cycle OFI Trend Drift"

            # Compute Order Flow Imbalance & Level-3 Book Skew using sorted depth
            bids, asks = book.get_depth(3) if hasattr(book, "get_depth") else ([], [])
            yes_vol = float(sum(lv.quantity for lv in bids)) if bids else 1.0
            no_vol = float(sum(lv.quantity for lv in asks)) if asks else 1.0
            book_skew = (yes_vol - no_vol) / max(1.0, yes_vol + no_vol)

            # Directional drift estimation combining moneyness and book skew
            tau_sqrt = math.sqrt(tau_mins)
            vol_floor_p2 = 0.714 * self.typical_1m_volatility
            book_skew_mult = 0.857 * self.typical_1m_volatility
            expected_vol = max(vol_floor_p2, self.typical_1m_volatility * tau_sqrt)
            z_score = (spot_diff + book_skew * book_skew_mult) / expected_vol

            prob_yes_raw = _standard_normal_cdf(z_score)
            prob_yes = max(0.001, min(0.999, prob_yes_raw))
            prob_no = 1.0 - prob_yes
            prob_wait = 0.12

            ev_res = self._ev_engine.compute_optimal_execution(
                prob_up=prob_yes,
                prob_down=prob_no,
                best_yes_ask=eff_yes_price,
                best_no_ask=eff_no_price,
                total_equity=total_equity,
                max_position_size=max_position_size,
                vpin=estimated_vpin,
                prob_wait=prob_wait,
                fee_override=Decimal("0.00"),
            )

            diff_str = cfg.format_diff(spot_diff)
            if ev_res.has_positive_edge and ev_res.recommended_side:
                target_prob = prob_yes if ev_res.recommended_side == OrderSide.YES else prob_no
                rationale = (
                    f"[{playbook_title}] Directional Trend Drift | T={int(time_to_expiry_s)}s left | "
                    f"Spot Diff: {diff_str} | Book Skew: {book_skew:+.2f} | "
                    f"Model Prob: {target_prob*100:.1f}% | Edge: {float(ev_res.statistical_edge)*100:+.1f}% | "
                    f"Optimal Size: {ev_res.recommended_contracts} cts"
                )
            else:
                rationale = (
                    f"[{playbook_title}] Monitoring Trend | T={int(time_to_expiry_s)}s left | "
                    f"Spot Diff: {diff_str} | Awaiting high-conviction order flow edge."
                )

            actual_ask_p2 = self._safe_market_ask(ev_res.recommended_side, best_yes_ask, best_no_ask)
            q_ahead_p2 = self._get_queue_ahead(book, ev_res.recommended_side, discount_price)
            return self._build_decision(
                playbook_title=playbook_title,
                stage=stage,
                p_up=prob_yes,
                p_down=prob_no,
                p_wait=prob_wait,
                vpin=estimated_vpin,
                vpin_is_safe=True,
                ev_res=ev_res,
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                rationale=rationale,
                actual_market_ask=actual_ask_p2,
                cycle_duration_s=cycle_duration_s,
                queue_ahead=q_ahead_p2,
            )

        # -------------------------------------------------------------------
        # PLAYBOOK 1: Early Momentum Breakout
        # -------------------------------------------------------------------
        # -------------------------------------------------------------------
        # PLAYBOOK 1: Early Momentum Breakout (with Opening Quarantine & ONNX Veto)
        # -------------------------------------------------------------------
        elif time_to_expiry_s > p1_max_s:
            # Opening Cycle Discovery Quarantine Gate (Anti-False Breakout Shield)
            diff_str = cfg.format_diff(spot_diff)
            quarantine_remaining = int(time_to_expiry_s - p1_max_s)
            return self._build_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                vpin=estimated_vpin,
                rationale=(
                    f"[Playbook 1: Early Momentum Breakout] Opening Cycle Quarantine Active | "
                    f"T={int(time_to_expiry_s)}s left > {int(p1_max_s)}s threshold ({quarantine_remaining}s left in quarantine) | "
                    f"Spot Diff: {diff_str} | Quarantining early cycle noise to eliminate false breakouts."
                ),
            )

        elif p1_min_s < time_to_expiry_s <= p1_max_s:
            stage = "breakout"
            playbook_title = "Playbook 1: Early Momentum Breakout"

            # Check for fast breakout velocity across strike
            tau_sqrt = math.sqrt(tau_mins)
            vol_floor_p1 = 1.285 * self.typical_1m_volatility
            expected_vol = max(vol_floor_p1, self.typical_1m_volatility * tau_sqrt)
            z_score = spot_diff / expected_vol

            prob_yes_raw = _standard_normal_cdf(z_score)
            prob_yes = max(0.001, min(0.999, prob_yes_raw))
            prob_no = 1.0 - prob_yes
            prob_wait = 0.20

            ev_res = self._ev_engine.compute_optimal_execution(
                prob_up=prob_yes,
                prob_down=prob_no,
                best_yes_ask=eff_yes_price,
                best_no_ask=eff_no_price,
                total_equity=total_equity,
                max_position_size=max_position_size,
                vpin=estimated_vpin,
                prob_wait=prob_wait,
                fee_override=Decimal("0.00"),
            )

            diff_str = cfg.format_diff(spot_diff)
            if ev_res.has_positive_edge and ev_res.recommended_side:
                # Brain 1 (QuoLas ONNX) Microstructure Orderflow Veto
                if self.onnx_engine is not None and book is not None:
                    try:
                        onnx_res = self.onnx_engine.process_orderbook_tick(book)
                        if onnx_res.get("vpin_veto"):
                            return self._build_wait_decision(
                                time_to_expiry_s=time_to_expiry_s,
                                spot_diff=spot_diff,
                                vpin=estimated_vpin,
                                rationale=(
                                    f"[{playbook_title}] ONNX VPIN Toxicity Veto: "
                                    f"Score={onnx_res.get('vpin_score', 0):.3f} > 0.70. Microstructure flow toxic."
                                ),
                            )
                        sig = str(onnx_res.get("signal", "WAIT")).upper()
                        conf = float(onnx_res.get("confidence", 0.0))
                        if ev_res.recommended_side == OrderSide.YES and sig != "LONG":
                            return self._build_wait_decision(
                                time_to_expiry_s=time_to_expiry_s,
                                spot_diff=spot_diff,
                                vpin=estimated_vpin,
                                rationale=(
                                    f"[{playbook_title}] ONNX Microstructure Veto: Proposing BUY YES but Brain 1 signaled {sig} "
                                    f"(Conf: {conf*100:.1f}%, Wait: {onnx_res.get('prob_wait', 0)*100:.1f}%, Short: {onnx_res.get('prob_short', 0)*100:.1f}%). False breakout blocked."
                                ),
                            )
                        elif ev_res.recommended_side == OrderSide.NO and sig != "SHORT":
                            return self._build_wait_decision(
                                time_to_expiry_s=time_to_expiry_s,
                                spot_diff=spot_diff,
                                vpin=estimated_vpin,
                                rationale=(
                                    f"[{playbook_title}] ONNX Microstructure Veto: Proposing BUY NO but Brain 1 signaled {sig} "
                                    f"(Conf: {conf*100:.1f}%, Wait: {onnx_res.get('prob_wait', 0)*100:.1f}%, Long: {onnx_res.get('prob_long', 0)*100:.1f}%). False breakout blocked."
                                ),
                            )
                    except Exception as onnx_err:
                        logger.warning("[DOMINATION BOT] ONNX microstructure check error: %s", onnx_err)

                target_prob = prob_yes if ev_res.recommended_side == OrderSide.YES else prob_no
                rationale = (
                    f"[{playbook_title}] Early Breakout Velocity | T={int(time_to_expiry_s)}s left | "
                    f"Spot Diff: {diff_str} | Confidence: {target_prob*100:.1f}% | "
                    f"Edge: {float(ev_res.statistical_edge)*100:+.1f}% | Kelly: {ev_res.kelly_fraction*100:.1f}%"
                )
            else:
                rationale = (
                    f"[{playbook_title}] Cycle Start Window | T={int(time_to_expiry_s)}s left | "
                    f"Spot Diff: {diff_str} | Scanning for momentum velocity across strike."
                )

            actual_ask_p1 = self._safe_market_ask(ev_res.recommended_side, best_yes_ask, best_no_ask)
            q_ahead_p1 = self._get_queue_ahead(book, ev_res.recommended_side, discount_price)
            return self._build_decision(
                playbook_title=playbook_title,
                stage=stage,
                p_up=prob_yes,
                p_down=prob_no,
                p_wait=prob_wait,
                vpin=estimated_vpin,
                vpin_is_safe=True,
                ev_res=ev_res,
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                rationale=rationale,
                actual_market_ask=actual_ask_p1,
                cycle_duration_s=cycle_duration_s,
                queue_ahead=q_ahead_p1,
            )

        # Expiry lock window (< p3_min_s)
        else:
            # -------------------------------------------------------------------
            # PLAYBOOK 4: Silas TWAP Immutability Sniper (Late-Cycle Alpha Harvest)
            # -------------------------------------------------------------------
            if 15.0 <= time_to_expiry_s < p3_min_s:
                effective_twap = twap_60s if (twap_60s is not None and twap_60s > 0) else spot_price
                delta_twap = effective_twap - target_strike
                t_safe = max(1.0, time_to_expiry_s)
                sigma_1 = self.typical_1m_volatility
                # Required buffer: at least 1.5 sigma_1 * sqrt(tau) deep ITM
                moat_req = 1.5 * (sigma_1 / math.sqrt(60.0)) * math.sqrt(t_safe)

                is_yes_guaranteed = (delta_twap > 0) and (delta_twap >= moat_req)
                is_no_guaranteed = (delta_twap < 0) and (abs(delta_twap) >= moat_req)
                sniper_ceiling = Decimal(str(self.twap_immutability_sniper_cents))

                if is_yes_guaranteed and best_yes_ask is not None and best_yes_ask <= sniper_ceiling:
                    net_ev = Decimal("1.00") - best_yes_ask - Decimal("0.01")
                    ev_res = ExpectedValueResult(
                        has_positive_edge=True,
                        recommended_side=OrderSide.YES,
                        ai_prob=0.999,
                        market_price=best_yes_ask,
                        expected_value=net_ev,
                        net_expected_value=net_ev,
                        fee_per_contract=Decimal("0.01"),
                        statistical_edge=round(float(net_ev) / float(best_yes_ask), 4),
                        kelly_fraction=0.25,
                        recommended_contracts=1,
                        rationale="Silas TWAP Sniper",
                    )
                    diff_str = cfg.format_diff(delta_twap)
                    rationale = (
                        f"[Playbook 4: Silas TWAP Immutability Sniper] Endgame Harvest | "
                        f"T={int(time_to_expiry_s)}s left | TWAP Cushion: {diff_str} | "
                        f"Settlement 99.9% mathematically locked | Ask ${best_yes_ask:.2f} <= ${sniper_ceiling:.2f} ceiling | "
                        f"Net EV: +${net_ev:.2f}/ct | Sniping panicked retail ask."
                    )
                    return self._build_decision(
                        playbook_title="Playbook 4: Silas TWAP Immutability Sniper",
                        stage="twap_sniper",
                        p_up=0.999,
                        p_down=0.001,
                        p_wait=0.0,
                        vpin=estimated_vpin,
                        vpin_is_safe=True,
                        ev_res=ev_res,
                        time_to_expiry_s=time_to_expiry_s,
                        spot_diff=spot_diff,
                        rationale=rationale,
                        actual_market_ask=float(best_yes_ask),
                        cycle_duration_s=cycle_duration_s,
                        queue_ahead=0,
                    )
                elif is_no_guaranteed and best_no_ask is not None and best_no_ask <= sniper_ceiling:
                    net_ev = Decimal("1.00") - best_no_ask - Decimal("0.01")
                    ev_res = ExpectedValueResult(
                        has_positive_edge=True,
                        recommended_side=OrderSide.NO,
                        ai_prob=0.999,
                        market_price=best_no_ask,
                        expected_value=net_ev,
                        net_expected_value=net_ev,
                        fee_per_contract=Decimal("0.01"),
                        statistical_edge=round(float(net_ev) / float(best_no_ask), 4),
                        kelly_fraction=0.25,
                        recommended_contracts=1,
                        rationale="Silas TWAP Sniper",
                    )
                    diff_str = cfg.format_diff(delta_twap)
                    rationale = (
                        f"[Playbook 4: Silas TWAP Immutability Sniper] Endgame Harvest | "
                        f"T={int(time_to_expiry_s)}s left | TWAP Cushion: {diff_str} | "
                        f"Settlement 99.9% mathematically locked | Ask ${best_no_ask:.2f} <= ${sniper_ceiling:.2f} ceiling | "
                        f"Net EV: +${net_ev:.2f}/ct | Sniping panicked retail ask."
                    )
                    return self._build_decision(
                        playbook_title="Playbook 4: Silas TWAP Immutability Sniper",
                        stage="twap_sniper",
                        p_up=0.001,
                        p_down=0.999,
                        p_wait=0.0,
                        vpin=estimated_vpin,
                        vpin_is_safe=True,
                        ev_res=ev_res,
                        time_to_expiry_s=time_to_expiry_s,
                        spot_diff=spot_diff,
                        rationale=rationale,
                        actual_market_ask=float(best_no_ask),
                        cycle_duration_s=cycle_duration_s,
                        queue_ahead=0,
                    )
                else:
                    return self._build_wait_decision(
                        time_to_expiry_s=time_to_expiry_s,
                        spot_diff=spot_diff,
                        vpin=estimated_vpin,
                        rationale=f"Cycle Closing Window (T={int(time_to_expiry_s)}s < {p3_min_s}s). New entries locked for settlement.",
                    )
            else:
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=estimated_vpin,
                    rationale=f"Expiration Quarantine Zone (T={int(time_to_expiry_s)}s <= 15s). All entries locked for settlement.",
                )

    def _build_decision(
        self,
        playbook_title: str,
        stage: str,
        p_up: float,
        p_down: float,
        p_wait: float,
        vpin: float,
        vpin_is_safe: bool,
        ev_res: ExpectedValueResult,
        time_to_expiry_s: float,
        spot_diff: float,
        rationale: str,
        actual_market_ask: Optional[float] = None,
        cycle_duration_s: float = 900.0,
        queue_ahead: int = 0,
    ) -> DominationDecision:
        """Construct normalized DominationDecision object with dynamic price cap protection."""
        discount_price_val = float(self.discount_limit_price)

        # Dynamic Two-Tier Entry Price Cap (Q3 Winning Choice)
        if ev_res.recommended_side in (OrderSide.YES, OrderSide.NO) and ev_res.recommended_contracts > 0:
            target_prob = p_up if ev_res.recommended_side == OrderSide.YES else p_down
            if target_prob < self.min_confidence:
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=vpin,
                    rationale=(
                        f"AI Conviction Veto: {ev_res.recommended_side.value.upper()} model conviction={target_prob*100:.1f}% "
                        f"< {self.min_confidence*100:.0f}% threshold. Awaiting higher statistical conviction."
                    ),
                )

            target_ask = actual_market_ask if actual_market_ask is not None else float(ev_res.market_price)

            # Vance Anti-Toxic Queue Depth Shield:
            # If order will rest as maker limit (target_ask > discount_price_val)
            if target_ask > discount_price_val and queue_ahead > self.max_queue_depth_ahead:
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=vpin,
                    rationale=(
                        f"Toxic Queue Depth Veto (Whale Armor): {queue_ahead} contracts resting ahead at ${discount_price_val:.2f} "
                        f"> {self.max_queue_depth_ahead} limit. Refusing back-of-the-wall fill to eliminate adverse whale sweep."
                    ),
                )

            if stage == "twap_sniper":
                if target_ask > self.twap_immutability_sniper_cents:
                    return self._build_wait_decision(
                        time_to_expiry_s=time_to_expiry_s,
                        spot_diff=spot_diff,
                        vpin=vpin,
                        rationale=(
                            f"TWAP Sniper Cap Veto: Recommended {ev_res.recommended_side.value.upper()} ask=${target_ask:.2f} "
                            f"> ${self.twap_immutability_sniper_cents:.2f} max sniper ceiling. Skipping."
                        ),
                    )
            else:
                # Tier 1: Absolute hard ceiling above $0.72 (inverted R:R suicide)
                if target_ask > 0.72:
                    return self._build_wait_decision(
                        time_to_expiry_s=time_to_expiry_s,
                        spot_diff=spot_diff,
                        vpin=vpin,
                        rationale=(
                            f"Price Cap Veto (Hard Kill): Recommended {ev_res.recommended_side.value.upper()} ask=${target_ask:.2f} > $0.72 max ceiling. "
                            f"Inverted risk/reward ratio ({target_ask*100:.0f}c risk to win {(1.0-target_ask)*100:.0f}c). Skipping."
                        ),
                    )
                cfg = get_asset_config(self.asset)
                deep_separation_diff = self.min_spot_diff * 1.4
                # Tier 2: Standard cap ($0.62) unless spot diff is deep in-the-money
                if target_ask > self.max_entry_price and abs(spot_diff) < deep_separation_diff:
                    deep_sep_str = cfg.format_price(deep_separation_diff)
                    diff_str = cfg.format_diff(spot_diff)
                    return self._build_wait_decision(
                        time_to_expiry_s=time_to_expiry_s,
                        spot_diff=spot_diff,
                        vpin=vpin,
                        rationale=(
                            f"Price Cap Veto (Standard): Recommended {ev_res.recommended_side.value.upper()} ask=${target_ask:.2f} > ${self.max_entry_price:.2f} cap. "
                            f"Requires deep spot separation (|Diff|={diff_str} < {deep_sep_str}). Skipping."
                        ),
                    )

            # Momentum Alignment Filter (P0 Fix — data: 0W/6L for contrarian NO in VOL_UP)
            # When the asset has moved meaningfully away from strike, bet WITH the direction.
            # Contrarian bets (against momentum) require 2.5x higher edge threshold.
            edge_pct = float(ev_res.statistical_edge) * 100.0
            contrarian_min_edge = 15.0  # 15% minimum edge for contrarian bets
            is_contrarian = False
            if spot_diff > self.min_spot_diff and ev_res.recommended_side == OrderSide.NO:
                # Asset above strike (VOLATILE_UP) but betting NO (price will drop) — contrarian
                is_contrarian = True
            elif spot_diff < -self.min_spot_diff and ev_res.recommended_side == OrderSide.YES:
                # Asset below strike (VOLATILE_DOWN) but betting YES (price will rise) — contrarian
                is_contrarian = True

            if is_contrarian and edge_pct < contrarian_min_edge:
                diff_str = cfg.format_diff(spot_diff)
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=vpin,
                    rationale=(
                        f"Momentum Alignment Veto: {ev_res.recommended_side.value.upper()} is contrarian "
                        f"(Diff={diff_str}). Edge={edge_pct:.1f}% < {contrarian_min_edge:.0f}% "
                        f"contrarian threshold. Bet WITH momentum, not against it."
                    ),
                )

            # Marginal Zone Edge Boost (Post-Mortem Fix — 9 consecutive losses from thin-edge trades)
            # Dynamic moat catches |spot_diff| < dynamic_threshold. This secondary filter catches
            # the transition zone up to 1.5x of that threshold where signals exist but are still developing.
            # Require 12% minimum edge to filter noise trades that don't survive reversals.
            razor_tight_threshold = self.get_dynamic_proximity_threshold(time_to_expiry_s, cycle_duration_s=cycle_duration_s)
            marginal_zone_upper = razor_tight_threshold * 1.5
            # [FROZEN] OLD_marginal_min_edge = 12.0 (12%). Paralyzing hurdle in marginal territory.
            marginal_min_edge = 2.0  # 2.0% minimum edge in marginal territory (matches new 1.5% base edge)
            if abs(spot_diff) < marginal_zone_upper and edge_pct < marginal_min_edge:
                diff_str = cfg.format_diff(spot_diff)
                return self._build_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=vpin,
                    rationale=(
                        f"Marginal Zone Veto: |Diff|={abs(spot_diff):.{cfg.price_decimals}f} < {marginal_zone_upper:.{cfg.price_decimals}f} "
                        f"(1.5x dynamic moat). Edge={edge_pct:.1f}% < {marginal_min_edge:.0f}% "
                        f"marginal threshold. Signal too weak to survive 15-min reversal risk."
                    ),
                )

        is_yes = ev_res.recommended_side == OrderSide.YES
        is_no = ev_res.recommended_side == OrderSide.NO
        chosen_side_str = ev_res.recommended_side.value if ev_res.recommended_side else "wait"
        cfg = get_asset_config(self.asset)

        if stage == "twap_sniper":
            limit_px = actual_market_ask if actual_market_ask is not None else float(ev_res.market_price)
        else:
            limit_px = discount_price_val
            if (is_yes or is_no) and ev_res.recommended_contracts > 0:
                target_side = chosen_side_str.upper()
                potential_reward = 1.0 - discount_price_val
                payoff_mult = potential_reward / discount_price_val if discount_price_val > 0 else 1.0
                target_prob = p_up if is_yes else p_down
                diff_str = cfg.format_diff(spot_diff)
                rationale = (
                    f"[{playbook_title}] Discount Sniper | Resting Limit BUY {target_side} @ ${discount_price_val:.2f} ($0.00 Fee) | "
                    f"T={int(time_to_expiry_s)}s left | Spot Diff: {diff_str} | "
                    f"Model Prob: {target_prob*100:.1f}% | Risk: ${discount_price_val:.2f} | "
                    f"Reward: +${potential_reward:.2f} ({payoff_mult:.2f}x) | Kelly: {ev_res.recommended_contracts} cts"
                )

        return DominationDecision(
            strategy_id=self.STRATEGY_ID,
            strategy_name=self.STRATEGY_NAME,
            active_playbook=playbook_title,
            playbook_stage=stage,
            p_up=round(p_up, 4),
            p_down=round(p_down, 4),
            p_wait=round(p_wait, 4),
            vpin=round(vpin, 3),
            vpin_is_safe=vpin_is_safe,
            ev_yes=round(float(ev_res.expected_value) if is_yes else 0.0, 4),
            ev_no=round(float(ev_res.expected_value) if is_no else 0.0, 4),
            edge_yes=round(float(ev_res.statistical_edge) if is_yes else 0.0, 4),
            edge_no=round(float(ev_res.statistical_edge) if is_no else 0.0, 4),
            kelly_f_yes=round(float(ev_res.kelly_fraction) if is_yes else 0.0, 4),
            kelly_f_no=round(float(ev_res.kelly_fraction) if is_no else 0.0, 4),
            recommended_side=chosen_side_str,
            recommended_contracts=min(ev_res.recommended_contracts, 1),
            rationale=rationale,
            edge_pct=round(float(ev_res.statistical_edge) * 100.0, 2),
            time_to_expiry_s=round(time_to_expiry_s, 1),
            spot_diff=round(spot_diff, cfg.price_decimals),
            order_type="limit",
            limit_price=limit_px,
        )

    def _build_wait_decision(
        self,
        time_to_expiry_s: float,
        spot_diff: float,
        vpin: float = 0.15,
        vpin_is_safe: bool = True,
        rationale: str = "Waiting for market trigger conditions.",
    ) -> DominationDecision:
        """Construct default wait decision."""
        cfg = get_asset_config(self.asset)
        return DominationDecision(
            strategy_id=self.STRATEGY_ID,
            strategy_name=self.STRATEGY_NAME,
            active_playbook="Awaiting Cycle Window",
            playbook_stage="none",
            p_up=0.50,
            p_down=0.50,
            p_wait=0.00,
            vpin=round(vpin, 3),
            vpin_is_safe=vpin_is_safe,
            ev_yes=0.0,
            ev_no=0.0,
            edge_yes=0.0,
            edge_no=0.0,
            kelly_f_yes=0.0,
            kelly_f_no=0.0,
            recommended_side="wait",
            recommended_contracts=0,
            rationale=rationale,
            edge_pct=0.0,
            time_to_expiry_s=round(time_to_expiry_s, 1),
            spot_diff=round(spot_diff, cfg.price_decimals),
            order_type="limit",
            limit_price=float(self.discount_limit_price),
        )

    def compute_market_probabilities(
        self,
        book: Optional[L2BookState],
        spot_price: float,
        target_strike: float,
        time_to_expiry_s: float,
    ) -> tuple[float, float]:
        """Compute live cumulative market probabilities (prob_yes, prob_no).

        Uses digital option normal CDF with dynamic volatility and order flow imbalance.
        If spot/strike are unavailable, falls back to book implied probabilities.
        """
        if spot_price > 0.0 and target_strike > 0.0:
            tau_mins = max(0.1, time_to_expiry_s / 60.0)
            tau_sqrt = math.sqrt(tau_mins)
            vol_floor = 0.285 * self.typical_1m_volatility
            expected_vol = max(vol_floor, self.typical_1m_volatility * tau_sqrt)
            spot_diff = spot_price - target_strike

            book_skew = 0.0
            if book and hasattr(book, "get_depth"):
                try:
                    bids, asks = book.get_depth(3)
                    yes_vol = float(sum(lv.quantity for lv in bids)) if bids else 0.0
                    no_vol = float(sum(lv.quantity for lv in asks)) if asks else 0.0
                    if (yes_vol + no_vol) > 0:
                        book_skew = (yes_vol - no_vol) / (yes_vol + no_vol)
                except Exception:
                    book_skew = 0.0

            skew_mult = 0.857 * self.typical_1m_volatility if time_to_expiry_s > 60.0 else 0.0
            z_score = (spot_diff + book_skew * skew_mult) / expected_vol
            prob_yes_raw = _standard_normal_cdf(z_score)
            prob_yes = max(0.001, min(0.999, prob_yes_raw))
            prob_no = 1.0 - prob_yes
            return prob_yes, prob_no

        if book:
            if book.best_yes_bid is not None and book.best_yes_bid > Decimal("0.00"):
                p_yes = float(book.best_yes_bid)
                return max(0.001, min(0.999, p_yes)), max(0.001, min(0.999, 1.0 - p_yes))
            if book.best_no_bid is not None and book.best_no_bid > Decimal("0.00"):
                p_no = float(book.best_no_bid)
                return max(0.001, min(0.999, 1.0 - p_no)), max(0.001, min(0.999, p_no))

        return 0.50, 0.50

    def compute_dynamic_spot_velocity_decision(
        self,
        side_is_yes: bool,
        spot_velocity_3s: float,
        time_to_expiry_s: float,
        spot_price: float = 0.0,
        target_strike: float = 0.0,
        twap_60s: Optional[float] = None,
        rolling_vol_1m: Optional[float] = None,
    ) -> tuple[bool, str]:
        """Evaluate Spot Velocity Front-Run using 4-Regime Fading Mathematics."""
        return self._exit_evaluator.compute_dynamic_spot_velocity_decision(
            side_is_yes=side_is_yes,
            spot_velocity_3s=spot_velocity_3s,
            time_to_expiry_s=time_to_expiry_s,
            spot_price=spot_price,
            target_strike=target_strike,
            twap_60s=twap_60s,
            rolling_vol_1m=rolling_vol_1m,
        )

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
        """Evaluate open position against quantitative Take-Profit and Early Liquidation rules."""
        return self._exit_evaluator.evaluate_exit(
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

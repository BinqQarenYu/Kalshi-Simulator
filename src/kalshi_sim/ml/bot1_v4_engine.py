"""Bot 1 Version 4 (Strict Quantitative Domination Engine).

Distinct from historical 3-Step Dominion v3.2:
- Enforces strict 1-Trade-Per-Cycle (max_turnover_per_event = 1).
- Strictly 1 contract held at any given instant (Micro-Bankroll Armor).
- Coupling EV math slider (Net EV = P_win - P_entry).
- Passive Maker limit entries at discount sniper ceiling ($0.52 max).
- 4-Regime Fading Mathematics spot velocity front-running ($28.00 BTC / 2.0σ).
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from kalshi_sim.ml.domination_exit_evaluator import (
    DominationExitDecision,
    DominationExitEvaluator,
)
from kalshi_sim.ml.experience_buffer import ContinuousExperienceBuffer
from kalshi_sim.ml.lead_deer_quant_brain import LeadDeerQuantBrain
from kalshi_sim.ml.statistical_ev_engine import ExpectedValueResult, StatisticalEVEngine
from kalshi_sim.ml.wave_classifier import MarketWavePhysics, WaveRegimeClassifier, compute_wave_physics
from kalshi_sim.ml.bleed_defender import BleedDefender
from kalshi_sim.ml.healing_protocol import HealingProtocol
from kalshi_sim.schemas import (
    CryptoAsset,
    L2BookState,
    OrderSide,
    QualificationTicket,
    TradeEvent,
    extract_strike_from_ticker,
    get_asset_config,
)

logger = logging.getLogger("kalshi_sim.bot1_v4_engine")


@dataclass(frozen=True)
class Bot1V4Decision:
    """Structured decision output from Bot 1 Version 4 Engine."""
    strategy_id: str
    strategy_name: str
    active_playbook: str
    playbook_stage: str  # 'breakout' | 'drift' | 'chop' | 'gamma_snub' | 'none'
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
    regime: str = "STORM"  # 'STORM' (Warrior 1) | 'CHOP' (Warrior 2)
    ticket_id: str = ""
    first_failed_gate: str = "NONE"
    first_failed_reason: str = ""
    candidate_side: str = "wait"
    clob_depth_available: int = 0
    adverse_ev: Optional[float] = None
    contract_truth_verified: bool = True

    def to_qualification_ticket(
        self,
        asset: str = "BTC",
        target_strike: float = 0.0,
        spot_price: float = 0.0,
        ticker: str = "",
    ) -> QualificationTicket:
        """Convert decision into immutable QualificationTicket (Sweet Spot Architecture)."""
        action = (
            "BUY_YES" if self.recommended_side == "yes"
            else ("BUY_NO" if self.recommended_side == "no" else "WAIT")
        )
        cand = self.candidate_side if self.candidate_side != "wait" else (
            "yes" if self.p_up > self.p_down and self.p_up > 0.50
            else ("no" if self.p_down > self.p_up and self.p_down > 0.50 else "wait")
        )
        cand_p = self.p_up if cand == "yes" else (self.p_down if cand == "no" else max(self.p_up, self.p_down))
        cand_ev = self.ev_yes if cand == "yes" else (self.ev_no if cand == "no" else 0.0)

        t_id = self.ticket_id or f"TICK-{asset.upper()}-{int(time.time()*1000)}"
        return QualificationTicket(
            ticket_id=t_id,
            timestamp_iso=datetime.now(timezone.utc).isoformat(),
            asset=asset.upper(),
            ticker=ticker,
            action=action,
            first_failed_gate=self.first_failed_gate,
            first_failed_reason=self.first_failed_reason or self.rationale,
            candidate_side=cand,
            calibrated_probability=round(float(cand_p), 4),
            executable_price=Decimal(str(round(self.limit_price, 2))),
            net_ev=Decimal(str(round(cand_ev, 4))),
            required_edge=Decimal(str(round(self.ev_hurdle_dollars, 4))),
            approved_contracts=int(self.recommended_contracts),
            spot_price=Decimal(str(round(spot_price, 2))),
            target_strike=Decimal(str(round(target_strike, 2))),
            time_to_expiry_s=round(float(self.time_to_expiry_s), 1),
            vpin=round(float(self.vpin), 3),
            l2_spread=Decimal("0.00"),
            adverse_ev=Decimal(str(round(self.adverse_ev, 4))) if self.adverse_ev is not None else None,
            evidence_hashes={
                "strategy_id": self.strategy_id,
                "regime": self.regime,
                "onnx_signal": self.onnx_signal,
                "fused_source": self.fused_source,
            },
        )




class Bot1V4DominationEngine:
    """Institutional Bot 1 Version 4 Multi-Turnover Quantitative Strategy Engine."""

    STRATEGY_ID = "bot1_v4_domination"
    STRATEGY_NAME = "Bot 1 V4 (Multi-Turnover Domination)"

    def __init__(
        self,
        max_turnover_per_event: int = 1,  # Strictly 1-trade-per-cycle invariant matching Bot 1
        min_ev_hurdle_dollars: Decimal = Decimal("0.04"),  # $0.04 minimum net EV hurdle
        discount_limit_price: Decimal = Decimal("0.42"),  # 42c maker discount floor
        min_edge_pct: float = 0.03,  # 3.0% min edge
        vpin_toxic_threshold: float = 0.70,  # Council Veto: Hard kill orders above 0.70 toxic flow
        vpin_safe_threshold: float = 0.55,
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
        max_entry_price: Decimal = Decimal("0.45"),  # 45c hard ceiling: eliminate negative R:R entries (>45c)
        min_confidence: float = 0.72,  # 72% minimum conviction requirement
        enable_trailing_ratchet: bool = True,
        trailing_ratchet_buffer: Decimal = Decimal("0.08"),
        spot_delta_front_run_threshold: float = 28.0,
        enable_dynamic_spot_velocity: bool = True,
        velocity_z_score_threshold: float = 2.50,
        reentry_cooldown_seconds: float = 15.0,
        enable_doubt_harvest: bool = True,
        doubt_threshold: float = 0.80,
        upside_capture_ratio_threshold: float = 0.50,
        asymmetric_peak_bid: Decimal = Decimal("0.75"),  # Council recommendation: $0.75 asymmetric chop harvest (+50% ROI)
        enable_fast_win_lock: bool = True,  # Council fast taker win lock with fee advantage
        fast_lock_asymmetric_bid: Decimal = Decimal("0.78"),  # Asymmetric 3.5:1 risk trap threshold ($0.78)
        min_fast_lock_bid: Decimal = Decimal("0.68"),  # Min bid to trigger chop/late-cycle lock ($0.68)
        min_fast_lock_roi: float = 0.35,  # +35% net ROI in chop/bleed
        fast_lock_late_cycle_roi: float = 0.20,  # +20% net ROI in late cycle T <= 180s
        require_reversal_for_asymmetric_peak: bool = False,  # Unconditional peak harvest at asymmetric floor
        enable_taker_breakout_entry: bool = True,  # Part 3: Taker Dynamic Breakout Entry
        taker_breakout_min_velocity: float = 15.0,  # Min spot velocity ($/3s) for taker entry
        taker_breakout_min_confidence: float = 0.78,  # Min conviction threshold for taker entry
        max_taker_entry_price: Decimal = Decimal("0.52"),  # Max price cap for taker entry
        onnx_engine: Optional[Any] = None,
        fusion_weight_micro: float = 0.40,
        opening_quarantine_seconds: float = 90.0,  # 90s opening noise quarantine (V3.2 shield)
        max_clob_spread_cents: float = 0.05,  # Max allowable bid-ask spread corridor cap ($0.05)
        moneyness_moat_multiplier: float = 1.50,  # 1.50x sigma*sqrt(t) deep ITM protection moat
        asset: CryptoAsset | str = CryptoAsset.BTC,
        chop_discount_limit_price: Decimal = Decimal("0.38"),  # Warrior 2 deep discount floor
        chop_max_entry_price: Decimal = Decimal("0.42"),       # Warrior 2 discount ceiling
        chop_min_time_s: float = 150.0,                       # Sweet Spot: 2.5 mins late bound
        chop_max_time_s: float = 450.0,                       # Sweet Spot: 7.5 mins early bound
        chop_range_threshold: float = 165.0,                  # Calibrated 0.20% spot range threshold
        chop_vol_threshold: float = 12.0,                     # 1m rolling vol < $12 defines low kinetic energy
        hysteresis_cooldown_seconds: float = 45.0,            # 45s sustained calm to return to chop
        experience_buffer: Optional[ContinuousExperienceBuffer] = None,
        enable_warrior_2_chop: bool = False,                  # Stand down in chop by default (anti-adverse selection)
        order_client: Optional[Any] = None,
        orderflow_feed: Optional[Any] = None,
        target_ticker: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.asset = CryptoAsset(str(asset).upper()) if not isinstance(asset, CryptoAsset) else asset
        self.order_client = order_client
        self.orderflow_feed = orderflow_feed
        self.target_ticker = target_ticker
        self._cached_market: Optional[Any] = None
        self._last_market_fetch_ts: float = 0.0
        self.enable_warrior_2_chop = enable_warrior_2_chop
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
        self.min_spot_diff = min_spot_diff if min_spot_diff is not None else float(get_asset_config(self.asset).min_spot_diff)
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
        self.enable_fast_win_lock = enable_fast_win_lock
        self.fast_lock_asymmetric_bid = fast_lock_asymmetric_bid
        self.min_fast_lock_bid = min_fast_lock_bid
        self.min_fast_lock_roi = min_fast_lock_roi
        self.fast_lock_late_cycle_roi = fast_lock_late_cycle_roi
        self.require_reversal_for_asymmetric_peak = require_reversal_for_asymmetric_peak
        self.enable_taker_breakout_entry = enable_taker_breakout_entry
        self.taker_breakout_min_velocity = taker_breakout_min_velocity
        self.taker_breakout_min_confidence = taker_breakout_min_confidence
        self.max_taker_entry_price = max_taker_entry_price
        self.twap_fading_quarantine_seconds: float = 15.0
        self.twap_fading_window_seconds: float = 60.0
        self.enable_dynamic_reversal_curve: bool = True
        self.onnx_engine = onnx_engine
        self.fusion_weight_micro = fusion_weight_micro
        self.opening_quarantine_seconds = opening_quarantine_seconds
        self.max_clob_spread_cents = max_clob_spread_cents
        self.enable_lead_deer_peak_harvester: bool = True

        # Warrior 2 (Chop Harvester) parameters
        self.chop_discount_limit_price = chop_discount_limit_price
        self.chop_max_entry_price = chop_max_entry_price
        self.chop_min_time_s = chop_min_time_s
        self.chop_max_time_s = chop_max_time_s
        self.chop_range_threshold = chop_range_threshold
        self.chop_vol_threshold = chop_vol_threshold
        self.hysteresis_cooldown_seconds = hysteresis_cooldown_seconds

        # 1 Boat, 3 Warriors across 4 Regions Infrastructure (Asset-calibrated scales)
        self.bleed_discount_limit_price = Decimal("0.30")
        self.bleed_max_entry_price = Decimal("0.35")
        if self.asset == CryptoAsset.ETH:
            self.min_spot_diff_bleed = 8.50
            eff_chop_range = 7.50 if chop_range_threshold == 48.0 else chop_range_threshold
            eff_chop_vol = 0.60 if chop_vol_threshold == 12.0 else chop_vol_threshold
            eff_tsunami = 15.0
        elif self.asset == CryptoAsset.SOL:
            self.min_spot_diff_bleed = 1.50
            eff_chop_range = 1.00
            eff_chop_vol = 0.08
            eff_tsunami = 2.50
        else:
            self.min_spot_diff_bleed = 85.0
            eff_chop_range = chop_range_threshold
            eff_chop_vol = chop_vol_threshold
            eff_tsunami = 250.0

        self.wave_classifier = WaveRegimeClassifier(
            chop_range_threshold=eff_chop_range,
            chop_vol_threshold=eff_chop_vol,
            tsunami_threshold=eff_tsunami,
        )
        self.bleed_defender = BleedDefender(
            bleed_discount_limit_price=self.bleed_discount_limit_price,
            bleed_max_entry_price=self.bleed_max_entry_price,
            min_spot_diff_bleed=self.min_spot_diff_bleed,
        )
        self.healing_protocol = HealingProtocol()

        # Multi-Warrior dynamic regime state tracking
        self._cycle_spot_open: Dict[str, float] = {}
        self._cycle_spot_high: Dict[str, float] = {}
        self._cycle_spot_low: Dict[str, float] = {}
        self._last_wave_physics: Optional[MarketWavePhysics] = None
        self._recent_spot_history: deque[Tuple[float, float]] = deque(maxlen=120)
        self._current_regime: str = "STORM"
        self._last_storm_ts: float = 0.0
        self._regime_reason: str = "Session boot initial state"

        self.experience_buffer = experience_buffer
        self.lead_deer_brain = LeadDeerQuantBrain(
            experience_buffer=experience_buffer,
            min_confidence=float(self.min_confidence),
            min_ev_dollars=float(self.min_ev_hurdle_dollars),
            maker_discount_ceiling=float(self.discount_limit_price),
        )

        self.ev_engine = StatisticalEVEngine()
        self.exit_evaluator = DominationExitEvaluator(self)
        self.vpin_window: list[float] = []

        self._current_cycle_id: Optional[str] = None
        self._completed_turnovers_map: dict[str, int] = {}
        self._last_exit_timestamp: float = 0.0
        self._session: Optional[aiohttp.ClientSession] = None

        # Unified One-Decision Framework (Sweet Spot Edition) Qualification Ticket Stores
        self._latest_qualification_ticket: Optional[QualificationTicket] = None
        self._recent_qualification_tickets: list[QualificationTicket] = []
        self._skipped_qualification_tickets: list[QualificationTicket] = []

    def _record_decision(
        self,
        decision: Bot1V4Decision,
        asset: CryptoAsset | str,
        target_strike: float,
        spot_price: float,
        ticker: str = "",
    ) -> Bot1V4Decision:
        """Record and serialize the evaluation as an immutable QualificationTicket."""
        try:
            asset_str = asset.value if hasattr(asset, "value") else str(asset).upper()

            # Auto-infer first failed gate from playbook if not already explicitly set
            gate = decision.first_failed_gate
            reason = decision.first_failed_reason or decision.rationale
            if gate == "NONE" and decision.recommended_side == "wait":
                playbook = decision.active_playbook.lower()
                if "contract_truth" in playbook or "pinning" in playbook:
                    gate = "G1_CONTRACT_TRUTH"
                elif "frozen_sensor" in playbook or "vpin" in playbook:
                    gate = "G2_DATA_HEALTH"
                elif "clob_spread" in playbook or "otm_ask" in playbook or "insufficient_clob_depth" in playbook:
                    gate = "G5_NOT_EXECUTABLE"
                elif "quarantine" in playbook or "blackout" in playbook or "stand_down" in playbook or "freeze" in playbook:
                    gate = "G1_CONTRACT_TRUTH"
                elif "proximity" in playbook or "pruning" in playbook or "edge" in playbook:
                    gate = "G8_EDGE_TOO_SMALL"
                elif "slippage" in playbook or "adverse" in playbook:
                    gate = "G12_ADVERSE_EXECUTION"
                elif "turnover" in playbook:
                    gate = "G10_MAX_TURNOVERS"
                else:
                    gate = "G3_PROBABILITY_LOW"

            ticket = decision.to_qualification_ticket(
                asset=asset_str,
                target_strike=target_strike,
                spot_price=spot_price,
                ticker=ticker or getattr(self, "target_ticker", "") or "",
            )
            if gate != "NONE" and ticket.first_failed_gate == "NONE":
                ticket = ticket.model_copy(update={"first_failed_gate": gate, "first_failed_reason": reason})

            self._latest_qualification_ticket = ticket
            self._recent_qualification_tickets.append(ticket)
            if len(self._recent_qualification_tickets) > 100:
                self._recent_qualification_tickets.pop(0)

            # Counterfactual Regret Tracking: record skipped candidate trades
            cand = decision.candidate_side if decision.candidate_side in ("yes", "no") else ticket.candidate_side
            if decision.recommended_side == "wait" and cand in ("yes", "no"):
                self._skipped_qualification_tickets.append(ticket)
                if len(self._skipped_qualification_tickets) > 100:
                    self._skipped_qualification_tickets.pop(0)
        except Exception as e:
            logger.debug("Failed recording qualification ticket: %s", e)
        return decision


    def get_latest_qualification_ticket(self) -> Optional[QualificationTicket]:
        """Return the latest emitted qualification ticket."""
        return self._latest_qualification_ticket

    def get_skipped_qualification_tickets(self, limit: int = 20) -> list[QualificationTicket]:
        """Return recently skipped qualification tickets for counterfactual regret auditing."""
        return self._skipped_qualification_tickets[-limit:]


    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or reuse connection-pooled HTTP session to prevent socket exhaustion."""
        from kalshi_sim.ws_connection import create_aiohttp_connector
        import aiohttp
        if self.order_client and hasattr(self.order_client, "_get_session"):
            return await self.order_client._get_session()
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(connector=create_aiohttp_connector())
        return self._session

    def compute_chop_limit_price(self, win_prob: float) -> Decimal:
        """Warrior 2 Chop Harvester pricing coupling:
        Guarantees asymmetric deep discount maker entry clamped strictly between $0.38 and $0.42.
        """
        ev_hurdle = float(self.min_ev_hurdle_dollars)
        dynamic_price = win_prob - ev_hurdle
        min_p = float(self.chop_discount_limit_price)
        max_p = float(self.chop_max_entry_price)
        clamped = max(min_p, min(dynamic_price, max_p))
        return Decimal(str(round(clamped, 2)))

    def detect_market_regime(
        self,
        spot_price: float,
        time_to_expiry_s: float,
        cycle_id: str,
        spot_velocity_3s: float = 0.0,
        vpin: float = 0.20,
        onnx_res: Optional[Dict[str, Any]] = None,
        now_mono: Optional[float] = None,
        now_utc: Optional[datetime] = None,
    ) -> Tuple[str, str]:
        """Classify real-time market regime across 4 Regions: CHOP, STORM, BLEED, and HEALING.
        Delegates to WaveRegimeClassifier for multi-warrior fleet governance.
        """
        if now_mono is None:
            now_mono = time.monotonic()
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)

        # 1. Update cycle open/high/low range
        if cycle_id not in self._cycle_spot_open:
            self._cycle_spot_open[cycle_id] = spot_price
        open_price = self._cycle_spot_open[cycle_id]

        high = max(self._cycle_spot_high.get(cycle_id, spot_price), spot_price)
        low = min(self._cycle_spot_low.get(cycle_id, spot_price), spot_price)
        self._cycle_spot_high[cycle_id] = high
        self._cycle_spot_low[cycle_id] = low
        cycle_range = high - low

        # 2. Update rolling spot history & compute rolling vol
        self._recent_spot_history.append((now_mono, spot_price))
        cutoff = now_mono - 60.0
        recent_spots = [p for ts, p in self._recent_spot_history if ts >= cutoff]
        if len(recent_spots) >= 5:
            rolling_vol = float(np.std(recent_spots))
        else:
            rolling_vol = float(self.default_btc_1m_volatility)

        onnx_sig = str(onnx_res.get("signal", "WAIT")) if onnx_res else "NONE"
        onnx_conf = float(onnx_res.get("confidence", 0.0)) if onnx_res else 0.0

        # 3. Classify Region using WaveRegimeClassifier
        region, physics, reason = self.wave_classifier.classify_region(
            open_price=open_price,
            high_price=high,
            low_price=low,
            current_price=spot_price,
            rolling_vol_1m=rolling_vol,
            spot_velocity_3s=spot_velocity_3s,
            onnx_signal=onnx_sig,
            onnx_confidence=onnx_conf,
        )

        if region in ("BLEED", "HEALING"):
            self._current_regime = region
            self._regime_reason = reason
            self._last_wave_physics = physics
            return region, reason

        effective_chop_range = max(self.chop_range_threshold, spot_price * 0.0020)
        is_volcano = (
            abs(spot_velocity_3s) >= 15.0
            or cycle_range > effective_chop_range
            or (onnx_sig in ("LONG", "SHORT") and onnx_conf >= 0.75)
            or rolling_vol >= self.chop_vol_threshold * 1.5
        )

        if is_volcano:
            self._current_regime = "STORM"
            self._last_storm_ts = now_mono
            reason = (
                f"Volcano Breakout detected: vel={spot_velocity_3s:+.1f}$/s, "
                f"range=${cycle_range:.1f}, vol=${rolling_vol:.1f}, ONNX={onnx_sig}({onnx_conf:.0%})"
            )
            self._regime_reason = reason
            self._last_wave_physics = physics
            return "STORM", reason

        # 4. Cooldown Transition Check (Storm -> Chop with Hysteresis)
        if self._current_regime == "STORM":
            is_calm = (
                cycle_range <= self.chop_range_threshold
                and abs(spot_velocity_3s) < 5.0
                and rolling_vol < self.chop_vol_threshold
                and onnx_sig in ("WAIT", "NONE")
            )
            if is_calm:
                if not hasattr(self, "_last_storm_ts") or self._last_storm_ts is None or self._last_storm_ts == 0.0:
                    self._last_storm_ts = now_mono
                calm_duration = now_mono - self._last_storm_ts
                if calm_duration >= self.hysteresis_cooldown_seconds:
                    self._current_regime = "CHOP"
                    reason = f"Cooldown Hysteresis Passed: Sustained calm for {int(calm_duration)}s"
                    self._regime_reason = reason
                    self._last_wave_physics = physics
                    return "CHOP", reason
                else:
                    rem = int(self.hysteresis_cooldown_seconds - calm_duration)
                    reason = f"Calm detected, cooling down ({rem}s remaining in hysteresis)"
                    self._regime_reason = reason
                    self._last_wave_physics = physics
                    return "STORM", reason
            else:
                self._last_storm_ts = now_mono
                self._regime_reason = "Active volatility expansion"
                self._last_wave_physics = physics
                return "STORM", "Active volatility expansion"

        self._current_regime = "CHOP"
        self._regime_reason = f"Sustained Chop Box: range=${cycle_range:.1f} <= ${self.chop_range_threshold:.1f}, vol=${rolling_vol:.1f}"
        self._last_wave_physics = physics
        return "CHOP", self._regime_reason

    def record_cycle_settlement(self, won: bool) -> None:
        """Records cycle settlement across wave classifier, bleed defender, and healing protocol."""
        self.wave_classifier.record_settled_cycle(won)
        if not won:
            self.bleed_defender.trigger_loss_cooldown()
        graduated = self.healing_protocol.record_settled_cycle(won)
        if graduated:
            self.wave_classifier.current_region = "CHOP"

    def arm_healing_protocol(self, reason: str = "Convalescence initiated") -> None:
        """Arms Region 4 Healing Protocol and synchronizes wave classifier."""
        self.wave_classifier.transition_to_healing(reason)
        self.healing_protocol.arm_healing_quarantine(reason)
        self._current_regime = "HEALING"

    def reset_cycle_turnover(self, cycle_id: str) -> None:
        """Reset turnover count and step bleed defender cooldown for a new 15M cycle."""
        self._current_cycle_id = cycle_id
        self._completed_turnovers_map[cycle_id] = 0
        if hasattr(self, "bleed_defender"):
            self.bleed_defender.step_cycle()

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

    def compute_dynamic_limit_price(self, win_prob: float, vpin: float = 0.20) -> Decimal:
        """Dual-Regime Dynamic EV Math Coupling:
        - High Conviction / Trend Regime (VPIN <= 0.28 and win_prob >= 0.75):
            Entry Limit up to $0.55 max cap to capture explosive breakouts.
        - Chop / High-Entropy Regime (VPIN > 0.28 or win_prob < 0.75):
            Entry Limit capped strictly at $0.48 to eliminate adverse selection in whipsaw markets.
        - Absolute Toxicity Veto: VPIN > 0.35 hard blocks order entry.
        """
        ev_hurdle = float(self.min_ev_hurdle_dollars)
        # Chop regime detection:
        is_chop = (vpin > 0.28) or (win_prob < 0.75)
        regime_max = 0.48 if is_chop else 0.55

        max_cap = min(float(self.max_entry_price), regime_max)
        base_floor = min(float(self.discount_limit_price), max_cap)

        dynamic_price = win_prob - ev_hurdle
        clamped_price = max(base_floor, min(dynamic_price, max_cap))
        return Decimal(str(round(clamped_price, 2)))

    def get_dynamic_proximity_threshold(
        self,
        time_to_expiry_s: float,
        cycle_duration_s: float = 900.0,
        regime: Optional[str] = None,
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

        if regime is None:
            regime = getattr(self, "_current_regime", "STORM")

        # Dynamic Strike Distance Scaling: Scale minimum separation proportionally with spot price
        base_diff = float(self.min_spot_diff) if getattr(self, "min_spot_diff", None) is not None else base_min_diff
        effective_min_diff = max(base_diff, getattr(self, "_last_spot_price", 0.0) * 0.00025)

        # Regional Moat Adaptation:
        if regime == "STORM":
            # Storm Vanguard: Wide Moat (1.5x - 2.6x) to absorb violent Brownian expansion
            moat_mult = max(1.50, float(getattr(self, "moneyness_moat_multiplier", 1.50)))
            floor_moat = effective_min_diff * moat_mult
            ceiling_moat = effective_min_diff * (moat_mult + 1.10)
        elif regime == "BLEED":
            # Bleed Defender: Super-Moat >= $85
            bleed_moat = float(getattr(self, "min_spot_diff_bleed", 85.0))
            floor_moat = max(bleed_moat, effective_min_diff * 1.55)
            ceiling_moat = max(bleed_moat * 1.65, effective_min_diff * 2.60)
        else:
            # Chop Harvester: Standard Moat
            floor_moat = effective_min_diff * 1.05
            ceiling_moat = effective_min_diff * 2.05

        expected_full_cycle_noise = baseline_vol * math.sqrt(cycle_mins)
        if expected_full_cycle_noise > 1e-9:
            z_asset = ceiling_moat / expected_full_cycle_noise
        else:
            z_asset = 1.40

        dynamic_moat = z_asset * live_vol * math.sqrt(tau_mins)
        if self.experience_buffer is not None:
            dynamic_moat *= getattr(self.experience_buffer, "adaptive_proximity_moat_multiplier", 1.0)
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
        # Mathematically exact Standard Normal CDF Phi(z) = 0.5 * (1 + erf(z / sqrt(2)))
        z_norm = spot_diff / (vol * t_factor)
        p_up_macro = 0.5 * (1.0 + math.erf(z_norm / math.sqrt(2.0)))
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
            # T_rem > 300s: ONNX orderflow micro dominates at 60%
            # T_rem <= 60s: settlement TWAP moneyness dictates near 100%
            decay = min(1.0, max(0.0, time_to_expiry_s / 900.0))
            w_micro = 0.60 * decay
            w_macro = 1.0 - w_micro

            p_up = float((w_macro * p_up_macro) + (w_micro * p_up_micro))
            p_down = float((w_macro * p_down_macro) + (w_micro * p_down_micro))

            total = p_up + p_down
            if total > 0.0:
                p_up /= total
                p_down /= total

            # Apply Online Platt Scaling Calibration if ContinuousExperienceBuffer is wired
            if self.experience_buffer is not None:
                p_up = self.experience_buffer.calibrate_probability(p_up)
                p_down = max(0.01, min(0.99, round(1.0 - p_up, 3)))

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
        physics = getattr(self, "_last_wave_physics", None)
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
            "chop_discount_limit_price": float(self.chop_discount_limit_price),
            "chop_max_entry_price": float(self.chop_max_entry_price),
            "chop_range_threshold": float(self.chop_range_threshold),
            "chop_vol_threshold": float(self.chop_vol_threshold),
            "current_regime": self._current_regime,
            "regime_reason": self._regime_reason,
            "wave_summary": physics.wave_summary if physics else "NORMAL WAVE",
            "is_tsunami": bool(physics.is_tsunami) if physics else False,
            "is_double_wick_meatgrinder": bool(physics.is_double_wick_meatgrinder) if physics else False,
            "is_false_breakout": bool(physics.is_false_breakout) if physics else False,
            "bleed_discount_limit_price": float(self.bleed_defender.bleed_discount_limit_price),
            "bleed_max_entry_price": float(self.bleed_defender.bleed_max_entry_price),
            "min_spot_diff_bleed": float(self.bleed_defender.min_spot_diff_bleed),
            "enable_taker_breakout_entry": bool(self.enable_taker_breakout_entry),
            "max_taker_entry_price": float(self.max_taker_entry_price),
            "taker_breakout_min_velocity": float(self.taker_breakout_min_velocity),
            "taker_breakout_min_confidence": float(self.taker_breakout_min_confidence),
            "enable_warrior_2_chop": bool(self.enable_warrior_2_chop),
            "healing_status": self.healing_protocol.get_status(),
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
        chop_discount_limit_price: Optional[float] = None,
        chop_max_entry_price: Optional[float] = None,
        chop_range_threshold: Optional[float] = None,
        chop_vol_threshold: Optional[float] = None,
        enable_warrior_2_chop: Optional[bool] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Dynamically update strategy parameters on the fly."""
        if enable_warrior_2_chop is not None:
            self.enable_warrior_2_chop = bool(enable_warrior_2_chop)
        if kwargs.get("enable_warrior_2_chop") is not None:
            self.enable_warrior_2_chop = bool(kwargs["enable_warrior_2_chop"])
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
        if chop_discount_limit_price is not None:
            self.chop_discount_limit_price = Decimal(str(chop_discount_limit_price))
        if chop_max_entry_price is not None:
            self.chop_max_entry_price = Decimal(str(chop_max_entry_price))
        if chop_range_threshold is not None:
            self.chop_range_threshold = float(chop_range_threshold)
        if chop_vol_threshold is not None:
            self.chop_vol_threshold = float(chop_vol_threshold)
        if kwargs.get("enable_taker_breakout_entry") is not None:
            self.enable_taker_breakout_entry = bool(kwargs["enable_taker_breakout_entry"])
        if kwargs.get("max_taker_entry_price") is not None:
            self.max_taker_entry_price = Decimal(str(kwargs["max_taker_entry_price"]))
        if kwargs.get("taker_breakout_min_velocity") is not None:
            self.taker_breakout_min_velocity = float(kwargs["taker_breakout_min_velocity"])
        if kwargs.get("taker_breakout_min_confidence") is not None:
            val_c = float(kwargs["taker_breakout_min_confidence"])
            self.taker_breakout_min_confidence = val_c if val_c <= 1.0 else (val_c / 100.0)
        if kwargs.get("bleed_discount_limit_price") is not None:
            val_disc = Decimal(str(kwargs["bleed_discount_limit_price"]))
            self.bleed_discount_limit_price = val_disc
            self.bleed_defender.bleed_discount_limit_price = val_disc
        if kwargs.get("bleed_max_entry_price") is not None:
            val_max = Decimal(str(kwargs["bleed_max_entry_price"]))
            self.bleed_max_entry_price = val_max
            self.bleed_defender.bleed_max_entry_price = val_max
        if kwargs.get("min_spot_diff_bleed") is not None:
            val_moat = float(kwargs["min_spot_diff_bleed"])
            self.min_spot_diff_bleed = val_moat
            self.bleed_defender.min_spot_diff_bleed = val_moat
        if kwargs.get("min_ev_hurdle_dollars") is not None:
            self.min_ev_hurdle_dollars = Decimal(str(kwargs["min_ev_hurdle_dollars"]))
        elif kwargs.get("min_ev_dollars") is not None:
            self.min_ev_hurdle_dollars = Decimal(str(kwargs["min_ev_dollars"]))
        if kwargs.get("min_edge_pct") is not None:
            val = float(kwargs["min_edge_pct"])
            self.min_edge_pct = val if val <= 1.0 else (val / 100.0)
        if kwargs.get("dynamic_moat_multiplier") is not None:
            self.moneyness_moat_multiplier = float(kwargs["dynamic_moat_multiplier"])
        elif kwargs.get("moneyness_moat_multiplier") is not None:
            self.moneyness_moat_multiplier = float(kwargs["moneyness_moat_multiplier"])
        return self.get_parameters()

    def has_star_player_seal(self) -> bool:
        """Check if bot holds Seal of Star Player on disk."""
        try:
            seal_path = Path("data/seal_of_excellence.json")
            if seal_path.exists():
                with open(seal_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                seals = data.get("seals", {})
                bot_seal = seals.get(self.STRATEGY_ID, {})
                seal_status = str(bot_seal.get("seal_status", ""))
                seal_type = str(bot_seal.get("seal_type", ""))
                if "STAR_PLAYER" in seal_status or "STAR_PLAYER" in seal_type or bot_seal.get("star_player_authorized", False):
                    return True
        except Exception:
            pass
        return False

    def has_seal_of_the_brave(self) -> bool:
        """Check if bot holds Seal of the Brave on disk."""
        try:
            seal_path = Path("data/seal_of_excellence.json")
            if seal_path.exists():
                with open(seal_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                seals = data.get("seals", {})
                bot_seal = seals.get(self.STRATEGY_ID, {})
                seal_status = str(bot_seal.get("seal_status", ""))
                if "BRAVE" in seal_status or bot_seal.get("brave_authorized", False):
                    return True
        except Exception:
            pass
        return False

    def evaluate(
        self,
        book: L2BookState,
        spot_price: float,
        target_strike: float,
        time_to_expiry_s: float,
        recent_trades: Optional[list[TradeEvent]] = None,
        total_equity: Decimal = Decimal("35.00"),
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
            total_equity=total_equity,
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
        total_equity: Decimal = Decimal("35.00"),
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

        # Gate 1: Contract Truth & CF Benchmarks Settlement Expiration Parity
        if target_strike <= 0.0 or spot_price <= 0.0:
            return self._record_decision(Bot1V4Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="invalid_contract_truth",
                playbook_stage="none",
                p_up=0.5, p_down=0.5, p_wait=1.0,
                vpin=vpin, vpin_is_safe=True,
                ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                kelly_f_yes=0.0, kelly_f_no=0.0,
                recommended_side="wait", recommended_contracts=0,
                rationale="Contract Truth Veto: Strike price or spot price is non-positive or undefined.",
                edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                limit_price=float(self.discount_limit_price),
                turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                first_failed_gate="G1_CONTRACT_TRUTH",
                first_failed_reason="Strike price or spot price is non-positive or undefined",
                contract_truth_verified=False,
            ), asset=asset, target_strike=target_strike, spot_price=spot_price)

        if time_to_expiry_s <= 120.0:
            vol = max(1.0, self.default_btc_1m_volatility)
            t_factor = math.sqrt(max(0.1, time_to_expiry_s / 60.0))
            z_norm = spot_diff / (vol * t_factor)
            p_up_pin = 0.5 * (1.0 + math.erf(z_norm / math.sqrt(2.0)))
            p_down_pin = 1.0 - p_up_pin
            cand_side = "yes" if spot_diff > 0 else ("no" if spot_diff < 0 else "wait")
            return self._record_decision(Bot1V4Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="twap_pinning_blackout",
                playbook_stage="none",
                p_up=p_up_pin, p_down=p_down_pin, p_wait=1.0,
                vpin=vpin, vpin_is_safe=True,
                ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                kelly_f_yes=0.0, kelly_f_no=0.0,
                recommended_side="wait", recommended_contracts=0,
                rationale=f"Silas TWAP Pinning Veto: T={int(time_to_expiry_s)}s <= 120s remaining. 60s trailing average cannot catch up; trading halted to prevent pin loss.",
                edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                limit_price=float(self.discount_limit_price),
                turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                first_failed_gate="G1_CONTRACT_TRUTH_PINNING",
                first_failed_reason="T <= 120s settlement TWAP pinning window",
                candidate_side=cand_side,
            ), asset=asset, target_strike=target_strike, spot_price=spot_price)

        # 1. Check Max Turnover Cap
        if turnovers >= self.max_turnover_per_event:
            return self._record_decision(Bot1V4Decision(
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
                first_failed_gate="G10_MAX_TURNOVERS",
                first_failed_reason=f"Max turnover cap hit ({turnovers}/{self.max_turnover_per_event})",
            ), asset=asset, target_strike=target_strike, spot_price=spot_price)


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

        # 2.0 ONNX Frozen Sensor Guardrail / Dead Book Veto (Tier 1 Guardrail)
        if onnx_res is not None:
            veto_reason = str(onnx_res.get("veto_reason", ""))
            prob_wait = float(onnx_res.get("prob_wait", 0.0))
            if veto_reason == "FROZEN_SENSOR_ZERO_VARIANCE" or (onnx_sig == "WAIT" and prob_wait >= 0.99):
                return Bot1V4Decision(
                    strategy_id=self.STRATEGY_ID,
                    strategy_name=self.STRATEGY_NAME,
                    active_playbook="frozen_sensor_veto",
                    playbook_stage="none",
                    p_up=p_up, p_down=p_down, p_wait=1.0,
                    vpin=vpin_eval, vpin_is_safe=True,
                    ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                    kelly_f_yes=0.0, kelly_f_no=0.0,
                    recommended_side="wait", recommended_contracts=0,
                    rationale="Frozen Sensor Veto: Order book is static/zero variance. Suppressing trading into dead liquidity.",
                    edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                    limit_price=float(self.discount_limit_price),
                    turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                    ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                    onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
                    regime=self._current_regime,
                )

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
                regime=self._current_regime,
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
                    regime=self._current_regime,
                )

        # 2.25 Universal Opening Cycle Noise Quarantine Gate (Anti-False Breakout Shield)
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
                regime=self._current_regime,
            )

        # 2.26 Universal Late-Cycle 4-Minute Expiration Blackout Gate (User Directive / Anti-Gamma Bleed)
        if time_to_expiry_s <= 240.0:
            return Bot1V4Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="late_cycle_4m_blackout",
                playbook_stage="none",
                p_up=p_up, p_down=p_down, p_wait=1.0,
                vpin=vpin_eval, vpin_is_safe=True,
                ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                kelly_f_yes=0.0, kelly_f_no=0.0,
                recommended_side="wait", recommended_contracts=0,
                rationale=f"Late-Cycle 4-Minute Quarantine Active: T={int(time_to_expiry_s)}s <= 240s remaining. Trading halted near expiration to prevent gamma & pin bleed.",
                edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                limit_price=float(self.discount_limit_price),
                turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
                regime=self._current_regime,
            )

        # 2.3 Real-Time Market Regime Classification (One Boat, Two Warriors)
        regime, regime_reason = self.detect_market_regime(
            spot_price=spot_price,
            time_to_expiry_s=time_to_expiry_s,
            cycle_id=cycle_id,
            spot_velocity_3s=spot_velocity_3s,
            vpin=vpin_eval,
            onnx_res=onnx_res,
        )

        ai_tag = f" [AI Conf {onnx_conf*100:.0f}%]" if fused_source == "bayesian_fusion" else ""

        # 2.4 Empirical Mistake Quadrant Pruning Gate (Continuous Experience Learning)
        if self.experience_buffer is not None and self.experience_buffer.is_quadrant_pruned(time_to_expiry_s, spot_diff):
            return Bot1V4Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="empirical_quadrant_pruning_veto",
                playbook_stage="none",
                p_up=p_up, p_down=p_down, p_wait=1.0,
                vpin=vpin_eval, vpin_is_safe=True,
                ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                kelly_f_yes=0.0, kelly_f_no=0.0,
                recommended_side="wait", recommended_contracts=0,
                rationale="Empirical Mistake Pruning Veto: State quadrant historically unprofitable under current horizon/separation.",
                edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                limit_price=float(self.discount_limit_price),
                turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
                regime=regime,
            )

        # =========================================================================
        # REGION 4: HEALING PROTOCOL (Regime == 'HEALING')
        # =========================================================================
        if regime == "HEALING":
            return Bot1V4Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="healing_convalescence_quarantine",
                playbook_stage="none",
                p_up=p_up, p_down=p_down, p_wait=1.0,
                vpin=vpin_eval, vpin_is_safe=True,
                ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                kelly_f_yes=0.0, kelly_f_no=0.0,
                recommended_side="wait", recommended_contracts=0,
                rationale=regime_reason,
                edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                limit_price=float(self.discount_limit_price),
                turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
                regime="HEALING",
            )

        # =========================================================================
        # WARRIOR 3: BLEED DEFENDER (Regime == 'BLEED')
        # =========================================================================
        if regime == "BLEED":
            physics = getattr(self, "_last_wave_physics", None)
            if physics is None:
                physics = compute_wave_physics(
                    open_price=self._cycle_spot_open.get(cycle_id, spot_price),
                    high_price=self._cycle_spot_high.get(cycle_id, spot_price),
                    low_price=self._cycle_spot_low.get(cycle_id, spot_price),
                    current_price=spot_price,
                )

            best_prob = max(p_up, p_down)
            side = "yes" if p_up >= p_down else "no"

            allow_entry, bleed_limit_price, bleed_rationale = self.bleed_defender.evaluate_bleed_defense(
                physics=physics,
                spot_diff=spot_diff,
                model_win_prob=best_prob,
                time_to_expiry_s=time_to_expiry_s,
            )

            if not allow_entry or bleed_limit_price is None:
                return Bot1V4Decision(
                    strategy_id=self.STRATEGY_ID,
                    strategy_name=self.STRATEGY_NAME,
                    active_playbook="bleed_defender_shield",
                    playbook_stage="none",
                    p_up=p_up, p_down=p_down, p_wait=1.0,
                    vpin=vpin_eval, vpin_is_safe=True,
                    ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                    kelly_f_yes=0.0, kelly_f_no=0.0,
                    recommended_side="wait", recommended_contracts=0,
                    rationale=f"Warrior 3 (Bleed Defender) Veto: {bleed_rationale}",
                    edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                    limit_price=float(self.bleed_defender.bleed_discount_limit_price),
                    turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                    ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                    onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
                    regime="BLEED",
                )

            return Bot1V4Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="bleed_defender_asymmetric_harvest",
                playbook_stage="bleed_armor",
                p_up=p_up, p_down=p_down, p_wait=0.0,
                vpin=vpin_eval, vpin_is_safe=True,
                ev_yes=float(self.min_ev_hurdle_dollars) if side == "yes" else 0.0,
                ev_no=float(self.min_ev_hurdle_dollars) if side == "no" else 0.0,
                edge_yes=p_up - float(bleed_limit_price) if side == "yes" else 0.0,
                edge_no=p_down - float(bleed_limit_price) if side == "no" else 0.0,
                kelly_f_yes=0.25 if side == "yes" else 0.0,
                kelly_f_no=0.25 if side == "no" else 0.0,
                recommended_side=side,
                recommended_contracts=1,
                rationale=bleed_rationale,
                edge_pct=best_prob - float(bleed_limit_price),
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                limit_price=float(bleed_limit_price),
                turnovers_completed=turnovers,
                max_turnovers=self.max_turnover_per_event,
                ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                onnx_signal=onnx_sig,
                onnx_confidence=onnx_conf,
                fused_source=fused_source,
                regime="BLEED",
            )

        # =========================================================================
        # WARRIOR 2: CHOP HARVESTER (Regime == 'CHOP')
        # =========================================================================
        if regime == "CHOP":
            if not self.enable_warrior_2_chop:
                return Bot1V4Decision(
                    strategy_id=self.STRATEGY_ID,
                    strategy_name=self.STRATEGY_NAME,
                    active_playbook="chop_stand_down_quarantine",
                    playbook_stage="none",
                    p_up=p_up, p_down=p_down, p_wait=1.0,
                    vpin=vpin_eval, vpin_is_safe=True,
                    ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                    kelly_f_yes=0.0, kelly_f_no=0.0,
                    recommended_side="wait", recommended_contracts=0,
                    rationale=f"Warrior 2 Chop Stand-Down Directive: Standing down in chop to eliminate adverse selection bleed ({regime_reason}). Awaiting Storm breakout.",
                    edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                    limit_price=float(self.chop_discount_limit_price),
                    turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                    ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                    onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
                    regime="CHOP",
                )

            # A. Timing Window Gates
            if time_to_expiry_s > self.chop_max_time_s:
                return Bot1V4Decision(
                    strategy_id=self.STRATEGY_ID,
                    strategy_name=self.STRATEGY_NAME,
                    active_playbook="chop_early_noise_quarantine",
                    playbook_stage="none",
                    p_up=p_up, p_down=p_down, p_wait=1.0,
                    vpin=vpin_eval, vpin_is_safe=True,
                    ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                    kelly_f_yes=0.0, kelly_f_no=0.0,
                    recommended_side="wait", recommended_contracts=0,
                    rationale=f"Warrior 2 Chop Harvester: T={int(time_to_expiry_s)}s > {int(self.chop_max_time_s)}s. Waiting for range boundaries to solidify.",
                    edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                    limit_price=float(self.chop_discount_limit_price),
                    turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                    ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                    onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
                    regime="CHOP",
                )
            if time_to_expiry_s < self.chop_min_time_s:
                return Bot1V4Decision(
                    strategy_id=self.STRATEGY_ID,
                    strategy_name=self.STRATEGY_NAME,
                    active_playbook="chop_late_cycle_freeze",
                    playbook_stage="none",
                    p_up=p_up, p_down=p_down, p_wait=1.0,
                    vpin=vpin_eval, vpin_is_safe=True,
                    ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                    kelly_f_yes=0.0, kelly_f_no=0.0,
                    recommended_side="wait", recommended_contracts=0,
                    rationale=f"Warrior 2 Chop Harvester: T={int(time_to_expiry_s)}s < {int(self.chop_min_time_s)}s. Near-settlement pin/jump freeze.",
                    edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                    limit_price=float(self.chop_discount_limit_price),
                    turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                    ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                    onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
                    regime="CHOP",
                )

            # B. Asymmetric Deep Discount Limit Pricing ($0.38 - $0.42)
            dynamic_limit_yes = self.compute_chop_limit_price(p_up)
            dynamic_limit_no = self.compute_chop_limit_price(p_down)

            ev_yes = p_up * 1.0 - float(dynamic_limit_yes)
            ev_no = p_down * 1.0 - float(dynamic_limit_no)

            recommended_side = "wait"
            chosen_limit_price = float(self.chop_discount_limit_price)
            rationale = f"Warrior 2 Chop Harvester: No chop edge meeting EV hurdle ({regime_reason})"

            req_p_win_yes = float(dynamic_limit_yes + self.min_ev_hurdle_dollars)
            req_p_win_no = float(dynamic_limit_no + self.min_ev_hurdle_dollars)

            chop_min_conf = min(0.55, float(self.min_confidence))
            min_edge = float(self.min_edge_pct)

            if p_up >= req_p_win_yes and p_up >= p_down and p_up >= chop_min_conf and (p_up - float(dynamic_limit_yes)) >= min_edge:
                recommended_side = "yes"
                chosen_limit_price = float(dynamic_limit_yes)
                rationale = (
                    f"Warrior 2 Chop Harvester YES Signal{ai_tag}: P_win {p_up:.1%} "
                    f"(Deep Discount Limit ${chosen_limit_price:.2f}, Net EV +${ev_yes:.3f}, {regime_reason})"
                )
            elif p_down >= req_p_win_no and p_down > p_up and p_down >= chop_min_conf and (p_down - float(dynamic_limit_no)) >= min_edge:
                recommended_side = "no"
                chosen_limit_price = float(dynamic_limit_no)
                rationale = (
                    f"Warrior 2 Chop Harvester NO Signal{ai_tag}: P_win {p_down:.1%} "
                    f"(Deep Discount Limit ${chosen_limit_price:.2f}, Net EV +${ev_no:.3f}, {regime_reason})"
                )

            # Gate 5: Vance Executable CLOB Depth Availability (CHOP)
            clob_depth_available = 0
            if recommended_side in ("yes", "no"):
                if l2_book is not None:
                    if recommended_side == "yes":
                        yes_items = l2_book.yes_book.items() if hasattr(l2_book.yes_book, "items") else l2_book.yes_book
                        clob_depth_available = int(sum(qty for p, qty in yes_items if p <= Decimal(str(round(chosen_limit_price + 0.05, 2)))))
                    else:
                        if l2_book.no_book:
                            no_items = l2_book.no_book.items() if hasattr(l2_book.no_book, "items") else l2_book.no_book
                            clob_depth_available = int(sum(qty for p, qty in no_items if p <= Decimal(str(round(chosen_limit_price + 0.05, 2)))))
                        elif l2_book.yes_book:
                            yes_items = l2_book.yes_book.items() if hasattr(l2_book.yes_book, "items") else l2_book.yes_book
                            clob_depth_available = int(sum(qty for p, qty in yes_items))

                if clob_depth_available < 1:
                    return self._record_decision(Bot1V4Decision(
                        strategy_id=self.STRATEGY_ID,
                        strategy_name=self.STRATEGY_NAME,
                        active_playbook="insufficient_clob_depth_veto",
                        playbook_stage="none",
                        p_up=p_up, p_down=p_down, p_wait=1.0,
                        vpin=vpin_eval, vpin_is_safe=True,
                        ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                        kelly_f_yes=0.0, kelly_f_no=0.0,
                        recommended_side="wait", recommended_contracts=0,
                        rationale=f"Vance CLOB Depth Veto: 0 contracts available at executable depth for {recommended_side.upper()}. Suppressing phantom fill.",
                        edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                        limit_price=float(self.discount_limit_price),
                        turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                        ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                        onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
                        regime="CHOP",
                        first_failed_gate="G5_NOT_EXECUTABLE",
                        first_failed_reason="Zero executable depth in CLOB",
                        candidate_side=recommended_side,
                        clob_depth_available=clob_depth_available,
                    ), asset=asset, target_strike=target_strike, spot_price=spot_price)

                # Gate 12: Adverse Execution 1-Tick Slippage Stress Test (+ $0.01 slippage)
                cand_p_win = p_up if recommended_side == "yes" else p_down
                stressed_price = chosen_limit_price + 0.01
                taker_fee_f = float(self.fee_per_contract)
                stressed_ev = cand_p_win * (1.0 - stressed_price) - (1.0 - cand_p_win) * stressed_price - taker_fee_f
                if stressed_ev <= 0.0:
                    return self._record_decision(Bot1V4Decision(
                        strategy_id=self.STRATEGY_ID,
                        strategy_name=self.STRATEGY_NAME,
                        active_playbook="adverse_slippage_stress_veto",
                        playbook_stage="none",
                        p_up=p_up, p_down=p_down, p_wait=1.0,
                        vpin=vpin_eval, vpin_is_safe=True,
                        ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                        kelly_f_yes=0.0, kelly_f_no=0.0,
                        recommended_side="wait", recommended_contracts=0,
                        rationale=f"Adverse 1-Tick Slippage Veto: A +$0.01 fill shock drops net EV to ${stressed_ev:+.3f} <= $0.00. Margin of safety insufficient.",
                        edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                        limit_price=float(self.discount_limit_price),
                        turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                        ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                        onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
                        regime="CHOP",
                        first_failed_gate="G12_ADVERSE_EXECUTION",
                        first_failed_reason=f"1-tick slippage shock reduces net EV to ${stressed_ev:.3f} <= $0.00",
                        candidate_side=recommended_side,
                        adverse_ev=stressed_ev,
                    ), asset=asset, target_strike=target_strike, spot_price=spot_price)

            cand_side_chop = recommended_side if recommended_side in ("yes", "no") else (
                "yes" if p_up > p_down and p_up > 0.50 else ("no" if p_down > p_up and p_down > 0.50 else "wait")
            )
            gate_status_chop = "NONE" if recommended_side in ("yes", "no") else "G8_EDGE_TOO_SMALL"
            gate_reason_chop = "" if recommended_side in ("yes", "no") else f"Warrior 2: No chop edge meeting EV hurdle (${self.min_ev_hurdle_dollars:.3f})"

            return self._record_decision(Bot1V4Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="playbook4_chop_harvester",
                playbook_stage="chop",
                p_up=p_up, p_down=p_down, p_wait=1.0 - max(p_up, p_down),
                vpin=vpin_eval, vpin_is_safe=True,
                ev_yes=ev_yes, ev_no=ev_no,
                edge_yes=p_up - chosen_limit_price,
                edge_no=p_down - chosen_limit_price,
                kelly_f_yes=0.25 if recommended_side == "yes" else 0.0,
                kelly_f_no=0.25 if recommended_side == "no" else 0.0,
                recommended_side=recommended_side,
                recommended_contracts=min(1, (
                    StatisticalEVEngine.compute_conviction_tier(
                        ai_prob=p_up if recommended_side == "yes" else p_down,
                        price=Decimal(str(chosen_limit_price)),
                        vpin=vpin_eval,
                        time_to_expiry_s=time_to_expiry_s,
                        spot_distance_to_strike=spot_diff,
                        total_equity=total_equity,
                        regime="CHOP",
                        has_star_player_seal=self.has_star_player_seal(),
                        has_seal_of_the_brave=self.has_seal_of_the_brave(),
                    )
                    if recommended_side != "wait" else 0
                )),
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
                regime="CHOP",
                first_failed_gate=gate_status_chop,
                first_failed_reason=gate_reason_chop,
                candidate_side=cand_side_chop,
                clob_depth_available=clob_depth_available,
            ), asset=asset, target_strike=target_strike, spot_price=spot_price)

        # =========================================================================
        # WARRIOR 1: STORM HUNTER (Regime == 'STORM')
        # =========================================================================
        # 3.1 Opening Cycle Noise Quarantine Gate (Anti-False Breakout Shield)
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
                regime="STORM",
            )

        # 3.2 ONNX Consensus Team Gate (Partner Discipline)
        if onnx_sig == "WAIT" and onnx_conf >= 0.70:
            has_massive_macro_edge = (abs(spot_diff) >= 45.0) and (max(p_up, p_down) >= 0.72)
            if not has_massive_macro_edge:
                return Bot1V4Decision(
                    strategy_id=self.STRATEGY_ID,
                    strategy_name=self.STRATEGY_NAME,
                    active_playbook="onnx_wait_veto",
                    playbook_stage="none",
                    p_up=p_up, p_down=p_down, p_wait=1.0,
                    vpin=vpin_eval, vpin_is_safe=True,
                    ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                    kelly_f_yes=0.0, kelly_f_no=0.0,
                    recommended_side="wait", recommended_contracts=0,
                    rationale=f"ONNX Consensus Veto: Orderflow neural net signals WAIT ({onnx_conf:.0%} conf). Respecting microstructural consensus.",
                    edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                    limit_price=float(self.discount_limit_price),
                    turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                    ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                    onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
                    regime="STORM",
                )

        # 3.3 Dynamic Proximity Moat Filter (Volatility-Scaled Distance Filter)
        dynamic_moat = self.get_dynamic_proximity_threshold(time_to_expiry_s, cycle_duration_s=cycle_duration_s, regime="STORM")
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
                regime="STORM",
            )

        # 3.4 Dynamic EV & Win Probability Coupling (Storm Mode up to $0.55)
        req_p_win_base = self.compute_required_win_probability(self.discount_limit_price)
        dynamic_limit_yes = self.compute_dynamic_limit_price(p_up, vpin=vpin_eval)
        dynamic_limit_no = self.compute_dynamic_limit_price(p_down, vpin=vpin_eval)

        recommended_side = "wait"
        rationale = f"Warrior 1: No storm edge meeting EV hurdle ({regime_reason})"
        chosen_limit_price = float(self.discount_limit_price)

        ev_yes = p_up * 1.0 - float(dynamic_limit_yes)
        ev_no = p_down * 1.0 - float(dynamic_limit_no)

        min_conf = float(self.min_confidence)
        min_edge = float(self.min_edge_pct)

        if (p_up >= (float(dynamic_limit_yes) + float(self.min_ev_hurdle_dollars)) or ev_yes >= float(self.min_ev_hurdle_dollars)) and p_up >= min_conf:
            edge_yes = p_up - float(dynamic_limit_yes)
            if p_up >= req_p_win_base and edge_yes >= min_edge:
                recommended_side = "yes"
                chosen_limit_price = min(float(dynamic_limit_yes), float(self.max_entry_price))
                rationale = f"Warrior 1 Storm YES Signal{ai_tag}: P_win {p_up:.1%} (Dynamic Limit ${chosen_limit_price:.2f}, Net EV +${ev_yes:.3f}, {regime_reason})"
        elif (p_down >= (float(dynamic_limit_no) + float(self.min_ev_hurdle_dollars)) or ev_no >= float(self.min_ev_hurdle_dollars)) and p_down >= min_conf:
            edge_no = p_down - float(dynamic_limit_no)
            if p_down >= req_p_win_base and edge_no >= min_edge:
                recommended_side = "no"
                chosen_limit_price = min(float(dynamic_limit_no), float(self.max_entry_price))
                rationale = f"Warrior 1 Storm NO Signal{ai_tag}: P_win {p_down:.1%} (Dynamic Limit ${chosen_limit_price:.2f}, Net EV +${ev_no:.3f}, {regime_reason})"

        active_playbook = "playbook1_breakout" if abs(spot_velocity_3s) >= 15.0 else "playbook2_drift"
        playbook_stage = "breakout" if active_playbook == "playbook1_breakout" else "drift"
        order_type_val = "limit"

        # Gate 5: Vance Executable CLOB Depth Availability
        clob_depth_available = 0
        if recommended_side in ("yes", "no"):
            if l2_book is not None:
                if recommended_side == "yes":
                    yes_items = l2_book.yes_book.items() if hasattr(l2_book.yes_book, "items") else l2_book.yes_book
                    clob_depth_available = int(sum(qty for p, qty in yes_items if p <= Decimal(str(round(chosen_limit_price + 0.05, 2)))))
                else:
                    if l2_book.no_book:
                        no_items = l2_book.no_book.items() if hasattr(l2_book.no_book, "items") else l2_book.no_book
                        clob_depth_available = int(sum(qty for p, qty in no_items if p <= Decimal(str(round(chosen_limit_price + 0.05, 2)))))
                    elif l2_book.yes_book:
                        yes_items = l2_book.yes_book.items() if hasattr(l2_book.yes_book, "items") else l2_book.yes_book
                        clob_depth_available = int(sum(qty for p, qty in yes_items))

            if clob_depth_available < 1:
                return self._record_decision(Bot1V4Decision(
                    strategy_id=self.STRATEGY_ID,
                    strategy_name=self.STRATEGY_NAME,
                    active_playbook="insufficient_clob_depth_veto",
                    playbook_stage="none",
                    p_up=p_up, p_down=p_down, p_wait=1.0,
                    vpin=vpin_eval, vpin_is_safe=True,
                    ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                    kelly_f_yes=0.0, kelly_f_no=0.0,
                    recommended_side="wait", recommended_contracts=0,
                    rationale=f"Vance CLOB Depth Veto: 0 contracts available at executable depth for {recommended_side.upper()}. Suppressing phantom fill.",
                    edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                    limit_price=float(self.discount_limit_price),
                    turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                    ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                    onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
                    regime="STORM",
                    first_failed_gate="G5_NOT_EXECUTABLE",
                    first_failed_reason="Zero executable depth in CLOB",
                    candidate_side=recommended_side,
                    clob_depth_available=clob_depth_available,
                ), asset=asset, target_strike=target_strike, spot_price=spot_price)

        # Guardrail: Minimum Viable Ask Floor ($0.38) & Non-Crossing Maker Clamp
        if recommended_side in ("yes", "no") and l2_book is not None and (l2_book.yes_book or l2_book.no_book):
            live_side_ask = (
                l2_book.best_yes_ask
                if recommended_side == "yes"
                else ((Decimal("1.00") - l2_book.best_yes_bid) if l2_book.best_yes_bid is not None else l2_book.best_no_ask)
            )
            if live_side_ask is not None:
                ask_f = float(live_side_ask)
                if ask_f < 0.38:
                    return self._record_decision(Bot1V4Decision(
                        strategy_id=self.STRATEGY_ID,
                        strategy_name=self.STRATEGY_NAME,
                        active_playbook="adverse_otm_ask_veto",
                        playbook_stage="none",
                        p_up=p_up, p_down=p_down, p_wait=1.0,
                        vpin=vpin_eval, vpin_is_safe=True,
                        ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                        kelly_f_yes=0.0, kelly_f_no=0.0,
                        recommended_side="wait", recommended_contracts=0,
                        rationale=f"Adverse OTM Ask Veto: Live {recommended_side.upper()} ask ${ask_f:.2f} < $0.38 minimum viable floor (prevents buying doomed OTM dumps).",
                        edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                        limit_price=float(self.discount_limit_price),
                        turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                        ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                        onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
                        regime="STORM",
                        first_failed_gate="G5_ADVERSE_OTM_FLOOR",
                        first_failed_reason=f"Live {recommended_side.upper()} ask ${ask_f:.2f} < $0.38 minimum floor",
                        candidate_side=recommended_side,
                    ), asset=asset, target_strike=target_strike, spot_price=spot_price)

        # Gate 12: Adverse Execution 1-Tick Slippage Stress Test (+ $0.01 slippage)
        stressed_ev = None
        if recommended_side in ("yes", "no"):
            cand_p_win = p_up if recommended_side == "yes" else p_down
            stressed_price = chosen_limit_price + 0.01
            taker_fee_f = float(self.fee_per_contract)
            stressed_ev = cand_p_win * (1.0 - stressed_price) - (1.0 - cand_p_win) * stressed_price - taker_fee_f
            if stressed_ev <= 0.0:
                return self._record_decision(Bot1V4Decision(
                    strategy_id=self.STRATEGY_ID,
                    strategy_name=self.STRATEGY_NAME,
                    active_playbook="adverse_slippage_stress_veto",
                    playbook_stage="none",
                    p_up=p_up, p_down=p_down, p_wait=1.0,
                    vpin=vpin_eval, vpin_is_safe=True,
                    ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                    kelly_f_yes=0.0, kelly_f_no=0.0,
                    recommended_side="wait", recommended_contracts=0,
                    rationale=f"Adverse 1-Tick Slippage Veto: A +$0.01 fill shock drops net EV to ${stressed_ev:+.3f} <= $0.00. Margin of safety insufficient.",
                    edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                    limit_price=float(self.discount_limit_price),
                    turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                    ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
                    onnx_signal=onnx_sig, onnx_confidence=onnx_conf, fused_source=fused_source,
                    regime="STORM",
                    first_failed_gate="G12_ADVERSE_EXECUTION",
                    first_failed_reason=f"1-tick slippage shock reduces net EV to ${stressed_ev:.3f} <= $0.00",
                    candidate_side=recommended_side,
                    adverse_ev=stressed_ev,
                ), asset=asset, target_strike=target_strike, spot_price=spot_price)

        # Part 3: Taker Dynamic Breakout Entry (High-Velocity Wave Penetration)
        # When high kinetic energy and high conviction confirm a runaway breakout,
        # paying the $0.01 taker fee guarantees immediate fill before the market escapes.
        if (
            self.enable_taker_breakout_entry
            and recommended_side in ("yes", "no")
            and abs(spot_velocity_3s) >= self.taker_breakout_min_velocity
        ):
            chosen_conf = p_up if recommended_side == "yes" else p_down
            aligned_vel = spot_velocity_3s if recommended_side == "yes" else -spot_velocity_3s
            if chosen_conf >= self.taker_breakout_min_confidence and aligned_vel >= self.taker_breakout_min_velocity:
                best_ask = None
                if l2_book is not None:
                    if recommended_side == "yes":
                        best_ask = l2_book.best_yes_ask
                    else:
                        best_ask = (Decimal("1.00") - l2_book.best_yes_bid) if l2_book.best_yes_bid is not None else None

                if best_ask is None or best_ask <= self.max_taker_entry_price:
                    order_type_val = "market"
                    if best_ask is not None:
                        chosen_limit_price = float(best_ask)
                    rationale += (
                        f" | ⚡ [TAKER BREAKOUT ENTRY] High-velocity wave (v={spot_velocity_3s:+.1f}$/3s, Conf {chosen_conf:.1%}) "
                        f"taking ask ${chosen_limit_price:.2f} with fee to penetrate momentum wave."
                    )

        cand_side = recommended_side if recommended_side in ("yes", "no") else (
            "yes" if p_up > p_down and p_up > 0.50 else ("no" if p_down > p_up and p_down > 0.50 else "wait")
        )
        gate_status = "NONE" if recommended_side in ("yes", "no") else "G8_EDGE_TOO_SMALL"
        gate_reason = "" if recommended_side in ("yes", "no") else f"Warrior 1: No storm edge meeting EV hurdle (${self.min_ev_hurdle_dollars:.3f})"

        return self._record_decision(Bot1V4Decision(
            strategy_id=self.STRATEGY_ID,
            strategy_name=self.STRATEGY_NAME,
            active_playbook=active_playbook,
            playbook_stage=playbook_stage,
            p_up=p_up, p_down=p_down, p_wait=1.0 - max(p_up, p_down),
            vpin=vpin_eval, vpin_is_safe=True,
            ev_yes=ev_yes, ev_no=ev_no,
            edge_yes=p_up - chosen_limit_price,
            edge_no=p_down - chosen_limit_price,
            kelly_f_yes=0.25 if recommended_side == "yes" else 0.0,
            kelly_f_no=0.25 if recommended_side == "no" else 0.0,
            recommended_side=recommended_side,
            recommended_contracts=min(1, (
                StatisticalEVEngine.compute_conviction_tier(
                    ai_prob=p_up if recommended_side == "yes" else p_down,
                    price=Decimal(str(chosen_limit_price)),
                    vpin=vpin_eval,
                    time_to_expiry_s=time_to_expiry_s,
                    spot_distance_to_strike=spot_diff,
                    total_equity=total_equity,
                    regime="STORM",
                    has_star_player_seal=self.has_star_player_seal(),
                    has_seal_of_the_brave=self.has_seal_of_the_brave(),
                )
                if recommended_side != "wait" else 0
            )),
            rationale=rationale,
            edge_pct=max(p_up, p_down) - chosen_limit_price,
            time_to_expiry_s=time_to_expiry_s,
            spot_diff=spot_diff,
            order_type=order_type_val,
            limit_price=chosen_limit_price,
            turnovers_completed=turnovers,
            max_turnovers=self.max_turnover_per_event,
            ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
            onnx_signal=onnx_sig,
            onnx_confidence=onnx_conf,
            fused_source=fused_source,
            regime="STORM",
            first_failed_gate=gate_status,
            first_failed_reason=gate_reason,
            candidate_side=cand_side,
            clob_depth_available=clob_depth_available,
            adverse_ev=stressed_ev,
        ), asset=asset, target_strike=target_strike, spot_price=spot_price)


    async def fetch_active_market(self, rest_base: Optional[str] = None) -> Optional[Any]:
        """Fetch active 15-minute market for this engine's asset."""
        from kalshi_sim.schemas import MarketInfo, MarketStatus
        from kalshi_sim.auth import PROD_REST_BASE, DEMO_REST_BASE, get_auth_headers
        from kalshi_sim.ws_connection import create_aiohttp_connector
        import aiohttp
        import os

        now_mono = time.monotonic()
        now_utc = datetime.now(timezone.utc)

        if rest_base is None:
            env = os.getenv("KALSHI_ENV", "live").lower()
            rest_base = PROD_REST_BASE if env in ("prod", "live") else DEMO_REST_BASE

        if self._cached_market and (now_mono - self._last_market_fetch_ts < 2.0):
            if getattr(self._cached_market, "close_time", None) and self._cached_market.close_time > now_utc:
                return self._cached_market

        series_ticker = f"KX{self.asset.value.upper()}15M"
        url = f"{rest_base}/markets?series_ticker={series_ticker}&status=open&limit=10"
        connector = create_aiohttp_connector()
        headers = {"User-Agent": "KalshiSim-Bot1V4/1.0", "Accept": "application/json"}

        if self.order_client and hasattr(self.order_client, "api_key_id") and hasattr(self.order_client, "private_key"):
            headers = get_auth_headers(
                self.order_client.api_key_id,
                self.order_client.private_key,
                "GET",
                "/trade-api/v2/markets",
            )

        try:
            timeout = aiohttp.ClientTimeout(total=4.0)
            session = await self._get_session()
            async with session.get(url, headers=headers, timeout=timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    markets_raw = data.get("markets", [])
                    valid_markets = []
                    for m in markets_raw:
                        t_str = m.get("ticker", "")
                        close_str = m.get("close_time")
                        if not t_str or not close_str:
                            continue
                        close_dt = datetime.fromisoformat(close_str.replace("Z", "+00:00"))
                        if close_dt > now_utc:
                            valid_markets.append((close_dt, m))

                    if valid_markets:
                        valid_markets.sort(key=lambda x: x[0])
                        _, chosen = valid_markets[0]
                        floor_str = chosen.get("floor_strike")
                        floor_dec = Decimal(str(floor_str)) if floor_str is not None else None
                        close_dt = datetime.fromisoformat(chosen["close_time"].replace("Z", "+00:00"))
                        open_dt = datetime.fromisoformat(chosen["open_time"].replace("Z", "+00:00")) if chosen.get("open_time") else None

                        minfo = MarketInfo(
                            ticker=chosen.get("ticker", ""),
                            series_ticker=chosen.get("series_ticker", series_ticker),
                            title=chosen.get("title", ""),
                            subtitle=chosen.get("subtitle", ""),
                            status=MarketStatus.OPEN,
                            open_time=open_dt,
                            close_time=close_dt,
                            expiration_time=close_dt,
                            floor_strike=floor_dec,
                            cap_strike=None,
                            strike_type="greater",
                        )
                        self._cached_market = minfo
                        self._last_market_fetch_ts = now_mono
                        return minfo
        except Exception as exc:
            logger.debug("[%s BOT] Error discovering %s market: %s", self.asset.value.upper(), series_ticker, exc)

        return self._cached_market

    async def fetch_orderbook(self, ticker: str, rest_base: Optional[str] = None) -> Optional[L2BookState]:
        """Fetch live Level-2 Orderbook snapshot for the target contract."""
        from kalshi_sim.auth import PROD_REST_BASE, DEMO_REST_BASE
        import aiohttp
        import os

        if rest_base is None:
            env = os.getenv("KALSHI_ENV", "live").lower()
            rest_base = PROD_REST_BASE if env in ("prod", "live") else DEMO_REST_BASE

        url = f"{rest_base}/markets/{ticker}/orderbook"
        headers = {"User-Agent": "KalshiSim-Bot1V4/1.0", "Accept": "application/json"}

        try:
            timeout = aiohttp.ClientTimeout(total=3.0)
            session = await self._get_session()
            async with session.get(url, headers=headers, timeout=timeout) as resp:
                if resp.status == 200:
                        data = await resp.json()
                        raw_book = data.get("orderbook_fp") or data.get("orderbook") or {}
                        bids = raw_book.get("yes_dollars") or raw_book.get("yes") or []
                        asks = raw_book.get("no_dollars") or raw_book.get("no") or []

                        book = L2BookState(ticker)
                        new_yes: dict[Decimal, Decimal] = {}
                        new_no: dict[Decimal, Decimal] = {}
                        for p_val, q_val in bids:
                            new_yes[Decimal(str(p_val))] = Decimal(str(q_val))
                        for p_val, q_val in asks:
                            new_no[Decimal(str(p_val))] = Decimal(str(q_val))

                        book.yes_book = new_yes
                        book.no_book = new_no
                        book.last_update = datetime.now(timezone.utc)
                        book._stale = False
                        return book
        except Exception as exc:
            logger.debug("[%s BOT] Error fetching orderbook for %s: %s", self.asset.value.upper(), ticker, exc)

        return None

    def get_spot_price(self) -> Decimal:
        """Retrieve current asset spot price from feed or live exchange ticker."""
        if self.orderflow_feed and getattr(self.orderflow_feed, "last_spot_price", 0) > 0:
            return self.orderflow_feed.last_spot_price
        symbol = f"{self.asset.value.upper()}USDT"
        fallback_val = "2350.00" if self.asset == CryptoAsset.ETH else "80500.00"
        try:
            import urllib.request
            resp = urllib.request.urlopen(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=2.0)
            data = json.loads(resp.read().decode())
            return Decimal(str(data.get("price", fallback_val)))
        except Exception:
            pass
        return Decimal(fallback_val)

    async def run_cycle(self, ticker: Optional[str] = None) -> Optional[Bot1V4Decision]:
        """Execute a single cycle iteration of the Bot 1 V4 engine.
        
        1. Checks asset-isolated circuit breaker / gate.
        2. Discovers active 15m market.
        3. Ingests L2 orderbook and spot price.
        4. Evaluates market opportunity using Bot 1 V4 quantitative logic.
        5. Places 1 contract adhering to micro-bankroll sizing and 1-trade-per-cycle lock.
        """
        from kalshi_sim.agent_guardrails import get_global_guardrails
        guardrails = get_global_guardrails()

        is_eth = (self.asset == CryptoAsset.ETH)
        is_btc = (self.asset == CryptoAsset.BTC)

        if is_eth and not guardrails.is_eth_bot_armed:
            logger.info("🛑 [ETH BOT 1 V4] Stand down: ETH bot circuit breaker tripped (%d consecutive losses). Stopped per user directive.", guardrails._eth_consecutive_losses)
            return None

        if is_btc and not guardrails.is_btc_bot_armed:
            logger.info("🛑 [BTC BOT 1 V4] Stand down: BTC bot halted after 10 trades with non-positive PnL ($%s). Stopped per user directive.", guardrails._btc_pnl)
            return None

        target_ticker = ticker or self.target_ticker
        market_info = None

        if not target_ticker or "-" not in target_ticker:
            market_info = await self.fetch_active_market()
            if market_info:
                target_ticker = market_info.ticker

        if not target_ticker or "-" not in target_ticker:
            logger.debug("[%s BOT] No active 15M market discovered.", self.asset.value.upper())
            return None

        # Fetch live L2 book
        book = await self.fetch_orderbook(target_ticker)
        if not book or (not book.yes_book and not book.no_book):
            logger.debug("[%s BOT] Orderbook for %s empty or unavailable.", self.asset.value.upper(), target_ticker)
            return None

        # Determine target strike & time to expiry
        now_utc = datetime.now(timezone.utc)
        target_strike = Decimal("2350.00") if is_eth else Decimal("80500.00")
        time_to_expiry_s = 600.0

        if market_info is None and self._cached_market and self._cached_market.ticker == target_ticker:
            market_info = self._cached_market

        if market_info and market_info.floor_strike:
            target_strike = market_info.floor_strike
        else:
            parsed_strike = extract_strike_from_ticker(target_ticker, self.asset)
            if parsed_strike is not None:
                target_strike = parsed_strike

        if market_info and market_info.expiration_time:
            time_to_expiry_s = max(1.0, (market_info.expiration_time - now_utc).total_seconds())

        spot_price = self.get_spot_price()
        now_mono = time.monotonic()
        spot_f = float(spot_price)
        spot_velocity_3s = 0.0
        if self._recent_spot_history:
            for prev_ts, prev_p in reversed(self._recent_spot_history):
                dt = now_mono - prev_ts
                if dt >= 0.5:
                    spot_velocity_3s = (spot_f - prev_p) / max(1.0, dt) * 3.0
                    break

        vpin_score = 0.15
        if self.orderflow_feed:
            vpin_score = min(0.99, max(0.01, abs(getattr(self.orderflow_feed, "ofi_l1", 0.15))))

        decision = self.evaluate(
            book=book,
            spot_price=spot_f,
            target_strike=float(target_strike),
            time_to_expiry_s=time_to_expiry_s,
            recent_trades=[],
            total_equity=Decimal("100.00"),
            max_position_size=1,
            estimated_vpin=vpin_score,
            cycle_id=target_ticker,
            spot_velocity_3s=spot_velocity_3s,
        )

        logger.info(
            "⚡ [%s BOT 1 V4] %s | Side: %s | P(Win): %.1f%% | EV: $%.2f | Price: $%.2f | Action: %s (%s)",
            self.asset.value.upper(),
            target_ticker,
            decision.recommended_side.upper(),
            (decision.p_up if decision.recommended_side == "yes" else decision.p_down) * 100.0,
            decision.ev_yes if decision.recommended_side == "yes" else decision.ev_no,
            float(getattr(decision, "limit_price", 0.42)),
            getattr(decision, "action", decision.recommended_side.upper()),
            decision.rationale[:60],
        )

        # Execution guardrails: 1 trade per cycle & micro-bankroll sizing (1 contract)
        if decision.recommended_side in ("yes", "no") and decision.recommended_contracts > 0:
            if self.order_client:
                # 1-trade-per-cycle lock check
                completed = self.get_completed_turnovers(target_ticker)
                if completed >= self.max_turnover_per_event or guardrails.is_cycle_locked(target_ticker):
                    logger.info("[%s BOT] Cycle %s already locked (turnover limit reached).", self.asset.value.upper(), target_ticker)
                    return decision

                order_side = OrderSide.YES if decision.recommended_side == "yes" else OrderSide.NO
                limit_p = getattr(decision, "limit_price", Decimal("0.42"))
                if not isinstance(limit_p, Decimal):
                    limit_p = Decimal(str(round(limit_p, 2)))

                # Validate with guardrails
                allowed, reason, approved_size, _ = guardrails.validate_pre_trade_intent(
                    ticker=target_ticker,
                    side=order_side.value,
                    requested_size=1,
                    est_price=limit_p,
                    total_equity=Decimal("100.00"),
                    vpin=vpin_score,
                    cycle_id=target_ticker,
                    is_bot=True,
                    bot_type=self.STRATEGY_ID,
                    is_live=True,
                )
                if not allowed:
                    logger.warning("[%s BOT GUARDRAIL BLOCKED] %s", self.asset.value.upper(), reason)
                    return decision

                try:
                    import inspect
                    order_kwargs = {
                        "ticker": target_ticker,
                        "side": order_side.value,
                        "count": 1,
                        "order_type": getattr(decision, "order_type", "limit"),
                    }
                    try:
                        sig = inspect.signature(self.order_client.place_order)
                        if "price_dollars" in sig.parameters:
                            order_kwargs["price_dollars"] = limit_p
                        else:
                            order_kwargs["price"] = limit_p
                    except Exception:
                        order_kwargs["price_dollars"] = limit_p

                    res = await self.order_client.place_order(**order_kwargs)
                    self.record_completed_turnover(target_ticker)
                    logger.info("🚀 [%s BOT ORDER EXECUTED] %s %s 1 ct @ $%s | Result: %s", self.asset.value.upper(), target_ticker, order_side.value, limit_p, res)
                    guardrails.record_trade_inception(
                        trade_id=str(res.get("order_id", f"ord_{int(time.time()*1000)}")) if isinstance(res, dict) else f"ord_{int(time.time()*1000)}",
                        ticker=target_ticker,
                        side=order_side.value,
                        size=1,
                        price=limit_p,
                        cost=limit_p,
                        fee=Decimal("0.01"),
                        bot_type=self.STRATEGY_ID,
                        execution_mode="live",
                        rationale=decision.rationale[:60],
                        vpin=vpin_score,
                        ai_prob=float(decision.p_up if decision.recommended_side == "yes" else decision.p_down),
                        cycle_id=target_ticker,
                    )
                except Exception as exc:
                    logger.error("[%s BOT] Failed to place order: %s", self.asset.value.upper(), exc)
                    guardrails.release_in_flight_intent(target_ticker)

        return decision

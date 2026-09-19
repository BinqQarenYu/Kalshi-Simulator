"""Bot 1 Version 4 (Multi-Turnover Quantitative Domination Engine).

Distinct from historical 3-Step Dominion v3.2:
- Allows sequential multi-turnover execution (max_turnover_per_event = 3) within a single 15M cycle.
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


class Bot1V4DominationEngine:
    """Institutional Bot 1 Version 4 Multi-Turnover Quantitative Strategy Engine."""

    STRATEGY_ID = "bot1_v4_domination"
    STRATEGY_NAME = "Bot 1 V4 (Multi-Turnover Domination)"

    def __init__(
        self,
        max_turnover_per_event: int = 4,  # Empirical SimSim sweet spot: max 4 round-trips per 15M cycle
        min_ev_hurdle_dollars: Decimal = Decimal("0.02"),  # $0.02 minimum net EV hurdle
        discount_limit_price: Decimal = Decimal("0.59"),  # 59c base limit price floor
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
        max_entry_price: Decimal = Decimal("0.68"),  # 68c max cap, hard veto at $0.70+
        min_confidence: float = 0.81,
        enable_trailing_ratchet: bool = True,
        trailing_ratchet_buffer: Decimal = Decimal("0.08"),
        spot_delta_front_run_threshold: float = 28.0,
        enable_dynamic_spot_velocity: bool = True,
        velocity_z_score_threshold: float = 2.50,
        reentry_cooldown_seconds: float = 15.0,
    ) -> None:
        self.max_turnover_per_event = max_turnover_per_event
        self.min_ev_hurdle_dollars = min_ev_hurdle_dollars
        self.discount_limit_price = discount_limit_price
        self.min_edge_pct = min_edge_pct
        self.vpin_toxic_threshold = vpin_toxic_threshold
        self.vpin_safe_threshold = vpin_safe_threshold
        self.default_btc_1m_volatility = default_btc_1m_volatility
        self.take_profit_price_threshold = take_profit_price_threshold
        self.enable_take_profit_ceiling = enable_take_profit_ceiling
        self.require_reversal_for_tp_ceiling = require_reversal_for_tp_ceiling
        self.enable_reverse_take_profit_roi = enable_reverse_take_profit_roi
        self.reverse_indicator_threshold = reverse_indicator_threshold
        self.min_take_profit_roi = min_take_profit_roi
        self.maker_entry_timeout_seconds = maker_entry_timeout_seconds
        self.late_cycle_roi = late_cycle_roi
        self.fee_per_contract = fee_per_contract
        self.min_spot_diff = min_spot_diff
        self.max_entry_price = max_entry_price
        self.min_confidence = min_confidence
        self.enable_trailing_ratchet = enable_trailing_ratchet
        self.trailing_ratchet_buffer = trailing_ratchet_buffer
        self.spot_delta_front_run_threshold = spot_delta_front_run_threshold
        self.enable_dynamic_spot_velocity = enable_dynamic_spot_velocity
        self.velocity_z_score_threshold = velocity_z_score_threshold
        self.reentry_cooldown_seconds = reentry_cooldown_seconds

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

    def compute_dynamic_limit_price(self, win_prob: float) -> Decimal:
        """Dynamic EV Math Coupling:
        Entry Limit = min(win_prob - EV_hurdle, max_entry_price)
        Dynamically scales entry ceiling up to max_entry_price ($0.68) when model conviction is high,
        while maintaining at least min_ev_hurdle_dollars ($0.02) net EV edge.
        Strictly hard-vetoes $0.70+ entry orders to prevent negative risk/reward fee drag.
        """
        ev_hurdle = float(self.min_ev_hurdle_dollars)
        max_cap = min(float(self.max_entry_price), 0.68)  # Strict $0.68 cap, $0.70+ hard veto
        base_floor = float(self.discount_limit_price)

        dynamic_price = win_prob - ev_hurdle
        clamped_price = max(base_floor, min(dynamic_price, max_cap))
        return Decimal(str(round(clamped_price, 2)))

    def update_parameters(
        self,
        min_confidence: Optional[float] = None,
        min_spot_diff: Optional[float] = None,
        discount_limit_price: Optional[float] = None,
        max_entry_price: Optional[float] = None,
        vpin_toxic_threshold: Optional[float] = None,
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
        return {"status": "UPDATED", "min_confidence": self.min_confidence, "min_spot_diff": self.min_spot_diff}

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

        # 2. VPIN Toxicity Veto
        vpin_safe = vpin < self.vpin_toxic_threshold
        if not vpin_safe:
            return Bot1V4Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="vpin_toxicity_veto",
                playbook_stage="none",
                p_up=0.5, p_down=0.5, p_wait=1.0,
                vpin=vpin, vpin_is_safe=False,
                ev_yes=0.0, ev_no=0.0, edge_yes=0.0, edge_no=0.0,
                kelly_f_yes=0.0, kelly_f_no=0.0,
                recommended_side="wait", recommended_contracts=0,
                rationale=f"VPIN Toxicity Veto (VPIN {vpin:.2f} >= {self.vpin_toxic_threshold:.2f})",
                edge_pct=0.0, time_to_expiry_s=time_to_expiry_s, spot_diff=spot_diff,
                limit_price=float(self.discount_limit_price),
                turnovers_completed=turnovers, max_turnovers=self.max_turnover_per_event,
                ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
            )

        # 3. Dynamic EV & Win Probability Coupling
        req_p_win_base = self.compute_required_win_probability(self.discount_limit_price)
        p_up = 0.5 * (1.0 + math.erf(spot_diff / (self.default_btc_1m_volatility * math.sqrt(max(1.0, time_to_expiry_s / 60.0)))))
        p_down = 1.0 - p_up

        dynamic_limit_yes = self.compute_dynamic_limit_price(p_up)
        dynamic_limit_no = self.compute_dynamic_limit_price(p_down)

        recommended_side = "wait"
        rationale = "No edge meeting EV hurdle"
        chosen_limit_price = float(self.discount_limit_price)

        ev_yes = p_up * 1.0 - float(dynamic_limit_yes)
        ev_no = p_down * 1.0 - float(dynamic_limit_no)

        if p_up >= (float(dynamic_limit_yes) + float(self.min_ev_hurdle_dollars)) or ev_yes >= float(self.min_ev_hurdle_dollars):
            if p_up >= req_p_win_base:
                recommended_side = "yes"
                chosen_limit_price = float(dynamic_limit_yes)
                rationale = f"Bot 1 V4 YES Signal: P_win {p_up:.1%} (Dynamic Limit ${chosen_limit_price:.2f}, Net EV +${ev_yes:.3f})"
        elif p_down >= (float(dynamic_limit_no) + float(self.min_ev_hurdle_dollars)) or ev_no >= float(self.min_ev_hurdle_dollars):
            if p_down >= req_p_win_base:
                recommended_side = "no"
                chosen_limit_price = float(dynamic_limit_no)
                rationale = f"Bot 1 V4 NO Signal: P_win {p_down:.1%} (Dynamic Limit ${chosen_limit_price:.2f}, Net EV +${ev_no:.3f})"

        return Bot1V4Decision(
            strategy_id=self.STRATEGY_ID,
            strategy_name=self.STRATEGY_NAME,
            active_playbook="playbook2_drift",
            playbook_stage="drift",
            p_up=p_up, p_down=p_down, p_wait=1.0 - max(p_up, p_down),
            vpin=vpin, vpin_is_safe=True,
            ev_yes=ev_yes, ev_no=ev_no,
            edge_yes=p_up - chosen_limit_price,
            edge_no=p_down - chosen_limit_price,
            kelly_f_yes=0.25 if recommended_side == "yes" else 0.0,
            kelly_f_no=0.25 if recommended_side == "no" else 0.0,
            recommended_side=recommended_side,
            recommended_contracts=1 if recommended_side != "wait" else 0,
            rationale=rationale,
            edge_pct=max(p_up, p_down) - chosen_limit_price,
            time_to_expiry_s=time_to_expiry_s,
            spot_diff=spot_diff,
            limit_price=chosen_limit_price,
            turnovers_completed=turnovers,
            max_turnovers=self.max_turnover_per_event,
            ev_hurdle_dollars=float(self.min_ev_hurdle_dollars),
        )

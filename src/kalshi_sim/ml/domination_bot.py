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

from kalshi_sim.ml.statistical_ev_engine import ExpectedValueResult, StatisticalEVEngine
from kalshi_sim.schemas import L2BookState, OrderSide, TradeEvent

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


class ThreeStepDominationBot:
    """Institutional Cycle-Aware 3-Step Quantitative Strategy Bot."""

    STRATEGY_ID = "3_step_domination_bot"
    STRATEGY_NAME = "3-Step Domination Bot"

    def __init__(
        self,
        min_edge_pct: float = 0.025,  # 2.5% minimum edge (calibrated for active paper alpha capture)
        min_ev_dollars: Decimal = Decimal("0.015"),  # Minimum $0.015 net EV per contract
        vpin_toxic_threshold: float = 0.75,
        vpin_safe_threshold: float = 0.45,
        default_btc_1m_volatility: float = 14.0,  # $14 typical 1-min BTC spot std dev
    ) -> None:
        self.min_edge_pct = min_edge_pct
        self.min_ev_dollars = min_ev_dollars
        self.vpin_toxic_threshold = vpin_toxic_threshold
        self.vpin_safe_threshold = vpin_safe_threshold
        self.default_btc_1m_volatility = default_btc_1m_volatility

        # Underlying Stage 2 EV & Quarter-Kelly Optimizer
        self._ev_engine = StatisticalEVEngine(
            min_ev_threshold=min_ev_dollars,
            min_edge_pct=min_edge_pct,
            fee_per_contract=Decimal("0.01"),
            fractional_kelly=0.30,  # 30% Kelly sizing for faster alpha capture
            vpin_safe_threshold=vpin_safe_threshold,
            vpin_toxic_threshold=vpin_toxic_threshold,
        )

    def evaluate(
        self,
        book: Optional[L2BookState],
        spot_price: float,
        target_strike: float,
        time_to_expiry_s: float,
        recent_trades: Optional[List[TradeEvent]] = None,
        total_equity: Decimal = Decimal("100.00"),
        max_position_size: int = 10,
        estimated_vpin: float = 0.15,
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

        # Classify Active Playbook by Expiration Countdown Window
        # Standard Kalshi 15M cycle: T in [0, 900s]
        tau_mins = max(0.1, time_to_expiry_s / 60.0)

        # -------------------------------------------------------------------
        # PLAYBOOK 3: Late-Cycle High-Probability Gamma Snub (0:45s - 4:00m left)
        # -------------------------------------------------------------------
        if 45 <= time_to_expiry_s <= 240:
            stage = "gamma_snub"
            playbook_title = "Playbook 3: Late-Cycle Gamma Snub"

            # Dynamic Volatility scaling over remaining time
            tau_sqrt = math.sqrt(tau_mins)
            expected_vol = max(4.0, self.default_btc_1m_volatility * tau_sqrt)
            z_score = spot_diff / expected_vol

            # Digital Option Cumulative Probability Phi(z)
            prob_yes_raw = _standard_normal_cdf(z_score)
            prob_yes = max(0.02, min(0.98, prob_yes_raw))
            prob_no = 1.0 - prob_yes
            prob_wait = 0.05

            ev_res = self._ev_engine.compute_optimal_execution(
                prob_up=prob_yes,
                prob_down=prob_no,
                best_yes_ask=best_yes_ask,
                best_no_ask=best_no_ask,
                total_equity=total_equity,
                max_position_size=max_position_size,
                vpin=estimated_vpin,
                prob_wait=prob_wait,
            )

            side_str = ev_res.recommended_side.value if ev_res.recommended_side else "wait"
            edge_val = float(ev_res.statistical_edge)

            if ev_res.has_positive_edge and ev_res.recommended_side:
                target_prob = prob_yes if ev_res.recommended_side == OrderSide.YES else prob_no
                rationale = (
                    f"[{playbook_title}] High-Certainty Expiration Harvest | "
                    f"T={int(time_to_expiry_s)}s left | Spot Diff: {spot_diff:+.2f} | "
                    f"True Prob: {target_prob*100:.1f}% vs Market: ${ev_res.market_price} | "
                    f"Net EV: +${ev_res.expected_value:.2f}/ct | Edge: {edge_val*100:+.1f}% | "
                    f"Kelly: {ev_res.kelly_fraction*100:.1f}% ({ev_res.recommended_contracts} cts)"
                )
            else:
                rationale = (
                    f"[{playbook_title}] In Range | T={int(time_to_expiry_s)}s left | "
                    f"Spot Diff: {spot_diff:+.2f} | True Prob: YES {prob_yes*100:.1f}% vs NO {prob_no*100:.1f}% | "
                    f"No edge exceeding {self.min_edge_pct*100:.0f}% post-fee."
                )

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
            )

        # -------------------------------------------------------------------
        # PLAYBOOK 2: Mid-Cycle OFI Trend Drift (4:00m - 10:00m left)
        # -------------------------------------------------------------------
        elif 240 < time_to_expiry_s <= 600:
            stage = "drift"
            playbook_title = "Playbook 2: Mid-Cycle OFI Trend Drift"

            # Compute Order Flow Imbalance & Level-3 Book Skew using sorted depth
            bids, asks = book.get_depth(3) if hasattr(book, "get_depth") else ([], [])
            yes_vol = float(sum(lv.quantity for lv in bids)) if bids else 1.0
            no_vol = float(sum(lv.quantity for lv in asks)) if asks else 1.0
            book_skew = (yes_vol - no_vol) / max(1.0, yes_vol + no_vol)

            # Directional drift estimation combining moneyness and book skew
            tau_sqrt = math.sqrt(tau_mins)
            expected_vol = max(10.0, self.default_btc_1m_volatility * tau_sqrt)
            z_score = (spot_diff + book_skew * 12.0) / expected_vol

            prob_yes_raw = _standard_normal_cdf(z_score)
            prob_yes = max(0.10, min(0.90, prob_yes_raw))
            prob_no = 1.0 - prob_yes
            prob_wait = 0.12

            ev_res = self._ev_engine.compute_optimal_execution(
                prob_up=prob_yes,
                prob_down=prob_no,
                best_yes_ask=best_yes_ask,
                best_no_ask=best_no_ask,
                total_equity=total_equity,
                max_position_size=max_position_size,
                vpin=estimated_vpin,
                prob_wait=prob_wait,
            )

            if ev_res.has_positive_edge and ev_res.recommended_side:
                target_prob = prob_yes if ev_res.recommended_side == OrderSide.YES else prob_no
                rationale = (
                    f"[{playbook_title}] Directional Trend Drift | T={int(time_to_expiry_s)}s left | "
                    f"Spot Diff: {spot_diff:+.2f} | Book Skew: {book_skew:+.2f} | "
                    f"Model Prob: {target_prob*100:.1f}% | Edge: {float(ev_res.statistical_edge)*100:+.1f}% | "
                    f"Optimal Size: {ev_res.recommended_contracts} cts"
                )
            else:
                rationale = (
                    f"[{playbook_title}] Monitoring Trend | T={int(time_to_expiry_s)}s left | "
                    f"Spot Diff: {spot_diff:+.2f} | Awaiting high-conviction order flow edge."
                )

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
            )

        # -------------------------------------------------------------------
        # PLAYBOOK 1: Early Momentum Breakout (10:00m - 15:00m left)
        # -------------------------------------------------------------------
        elif time_to_expiry_s > 600:
            stage = "breakout"
            playbook_title = "Playbook 1: Early Momentum Breakout"

            # Check for fast breakout velocity across strike
            tau_sqrt = math.sqrt(tau_mins)
            expected_vol = max(18.0, self.default_btc_1m_volatility * tau_sqrt)
            z_score = spot_diff / expected_vol

            prob_yes_raw = _standard_normal_cdf(z_score)
            prob_yes = max(0.20, min(0.80, prob_yes_raw))
            prob_no = 1.0 - prob_yes
            prob_wait = 0.20

            ev_res = self._ev_engine.compute_optimal_execution(
                prob_up=prob_yes,
                prob_down=prob_no,
                best_yes_ask=best_yes_ask,
                best_no_ask=best_no_ask,
                total_equity=total_equity,
                max_position_size=max_position_size,
                vpin=estimated_vpin,
                prob_wait=prob_wait,
            )

            if ev_res.has_positive_edge and ev_res.recommended_side:
                target_prob = prob_yes if ev_res.recommended_side == OrderSide.YES else prob_no
                rationale = (
                    f"[{playbook_title}] Early Breakout Velocity | T={int(time_to_expiry_s)}s left | "
                    f"Spot Diff: {spot_diff:+.2f} | Confidence: {target_prob*100:.1f}% | "
                    f"Edge: {float(ev_res.statistical_edge)*100:+.1f}% | Kelly: {ev_res.kelly_fraction*100:.1f}%"
                )
            else:
                rationale = (
                    f"[{playbook_title}] Cycle Start Window | T={int(time_to_expiry_s)}s left | "
                    f"Spot Diff: {spot_diff:+.2f} | Scanning for momentum velocity across strike."
                )

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
            )

        # Expiry lock window (<45s)
        else:
            return self._build_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                vpin=estimated_vpin,
                rationale=f"Cycle Closing Window (T={int(time_to_expiry_s)}s < 45s). New entries locked for settlement.",
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
    ) -> DominationDecision:
        """Construct normalized DominationDecision object."""
        is_yes = ev_res.recommended_side == OrderSide.YES
        is_no = ev_res.recommended_side == OrderSide.NO

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
            recommended_side=ev_res.recommended_side.value if ev_res.recommended_side else "wait",
            recommended_contracts=ev_res.recommended_contracts,
            rationale=rationale,
            edge_pct=round(float(ev_res.statistical_edge) * 100.0, 2),
            time_to_expiry_s=round(time_to_expiry_s, 1),
            spot_diff=round(spot_diff, 2),
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
            spot_diff=round(spot_diff, 2),
        )

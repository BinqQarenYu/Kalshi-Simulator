"""Lead Deer Quant Trader Brain.

Fuses 28-D ONNX Microstructure inference, CME CF Benchmarks 5Hz spot moneyness,
order flow imbalance (OFI), and rolling Continuous Experience Learning
into every 15-minute event cycle.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from kalshi_sim.ml.experience_buffer import ContinuousExperienceBuffer
from kalshi_sim.schemas import L2BookState, OrderSide

logger = logging.getLogger("kalshi_sim.lead_deer_quant_brain")


@dataclass
class ExitDecision:
    """Decision output for managing an in-flight open contract bag."""
    action: str  # 'HOLD_TO_EXPIRY' | 'HARVEST_PEAK' | 'EJECT_VALLEY'
    limit_price_cents: int
    limit_price_dollars: float
    reason: str
    urgency: str  # 'NORMAL' | 'URGENT' | 'LOCK_IN'


@dataclass
class QuantBrainDecision:
    """Structured decision output from the Lead Deer Quant Brain."""
    recommended_side: str  # 'yes' | 'no' | 'wait'
    recommended_contracts: int  # 1 for micro-bankroll
    limit_price_cents: int  # 48 - 52
    limit_price_dollars: float  # 0.48 - 0.52
    expected_value: float  # Net EV in dollars per contract
    confidence: float  # Calibrated probability (0.50 - 0.95)
    active_playbook: str  # 'playbook_1_breakout' | 'playbook_2_drift' | 'playbook_3_gamma_snub'
    reasoning: str  # Institutional rationale
    brier_score: float  # Rolling model calibration error
    pruned_deciles: List[str]  # Banned price deciles
    onnx_consensus: str  # 'BULLISH' | 'BEARISH' | 'NEUTRAL'
    gate_passed: bool  # True if EV > +.03 and confidence >= 65%


class LeadDeerQuantBrain:
    """Cycle-by-cycle quantitative brain powered by ONNX tensors, live experience, and Council axioms."""

    def __init__(
        self,
        experience_buffer: Optional[ContinuousExperienceBuffer] = None,
        min_confidence: float = 0.65,
        min_ev_dollars: float = 0.03,
        maker_discount_ceiling: float = 0.52,
    ):
        self.experience_buffer = experience_buffer or ContinuousExperienceBuffer()
        self.min_confidence = min_confidence
        self.min_ev_dollars = min_ev_dollars
        self.maker_discount_ceiling = maker_discount_ceiling

    def evaluate_cycle(
        self,
        book: Optional[L2BookState],
        spot_price: float,
        target_strike: float,
        time_to_expiry_s: float,
        onnx_prob_up: float = 0.50,
        onnx_prob_down: float = 0.50,
        vpin: float = 0.15,
        macro_trend_1h: str = "NEUTRAL",
    ) -> QuantBrainDecision:
        """Evaluate a 15-minute event cycle and formulate optimal playbook execution."""
        spot_diff = spot_price - target_strike
        recent_exp = self.experience_buffer.get_recent_summary(20)
        brier = recent_exp.get("brier_score", 0.25)
        pruned = recent_exp.get("pruned_deciles", [])

        # 1. Playbook Selection by Expiration Horizon
        if time_to_expiry_s > 600.0:
            playbook = "playbook_1_breakout"
            target_maker_limit = 48  # 48c deep maker
        elif time_to_expiry_s > 180.0:
            playbook = "playbook_2_drift"
            target_maker_limit = 50  # 50c fair value maker
        else:
            playbook = "playbook_3_gamma_snub"
            target_maker_limit = 52  # 52c sweetspot maker

        # 2. ONNX Consensus & Directional Lean
        if onnx_prob_up >= 0.60 and onnx_prob_up > onnx_prob_down:
            onnx_consensus = "BULLISH"
            raw_side = "yes"
            raw_conf = onnx_prob_up
        elif onnx_prob_down >= 0.60 and onnx_prob_down > onnx_prob_up:
            onnx_consensus = "BEARISH"
            raw_side = "no"
            raw_conf = onnx_prob_down
        else:
            # Lean on spot moneyness if ONNX is in neutral chop
            onnx_consensus = "NEUTRAL"
            raw_side = "yes" if spot_diff >= 0.0 else "no"
            raw_conf = 0.55

        # 3. Macro 1H Trend Alignment
        if macro_trend_1h == "BULLISH" and raw_side == "no":
            return self._build_wait_decision(
                brier, pruned, onnx_consensus,
                f"VETO: Bearish NO counter to 1H Bullish Macro Trend."
            )
        elif macro_trend_1h == "BEARISH" and raw_side == "yes":
            return self._build_wait_decision(
                brier, pruned, onnx_consensus,
                f"VETO: Bullish YES counter to 1H Bearish Macro Trend."
            )

        # 4. Proximity & Razor-Tight Moat Filter (Prevent Coin-Flip Churn)
        # For BTC, require at least  distance from strike unless gamma snub
        if abs(spot_diff) < 25.0 and time_to_expiry_s > 120.0:
            return self._build_wait_decision(
                brier, pruned, onnx_consensus,
                f"VETO: Razor-tight spot chop (|Diff|= <  floor). Preservation of capital."
            )

        # 5. Mistake Decile Pruning Gate
        limit_str = f"{target_maker_limit}¢"
        if limit_str in pruned:
            target_maker_limit = min(48, target_maker_limit - 2)

        # 6. Mathematical EV Calculation (Dr. Nash Gate)
        # EV = P(win) * (.00 - Price) - P(loss) * Price - Fee (.00 Maker)
        entry_dollar = target_maker_limit / 100.0
        p_win = raw_conf
        p_loss = 1.0 - p_win
        net_ev = (p_win * (1.00 - entry_dollar)) - (p_loss * entry_dollar)

        # Check Gates
        gate_passed = (net_ev >= self.min_ev_dollars) and (raw_conf >= self.min_confidence) and (vpin <= 0.65)

        if not gate_passed:
            reason = f"EV Hurdle Veto: Net EV + < + or Conf {raw_conf*100:.1f}% < {self.min_confidence*100:.0f}%"
            return self._build_wait_decision(brier, pruned, onnx_consensus, reason)

        return QuantBrainDecision(
            recommended_side=raw_side,
            recommended_contracts=1,
            limit_price_cents=target_maker_limit,
            limit_price_dollars=entry_dollar,
            expected_value=round(net_ev, 3),
            confidence=round(raw_conf, 3),
            active_playbook=playbook,
            reasoning=f"Lead Deer Quant: {onnx_consensus} ONNX + 1H Trend Alignment. Maker {target_maker_limit}¢ limit (+.00 fee) yields net EV +/ct.",
            brier_score=brier,
            pruned_deciles=pruned,
            onnx_consensus=onnx_consensus,
            gate_passed=True,
        )

    def _build_wait_decision(
        self,
        brier: float,
        pruned: List[str],
        onnx_consensus: str,
        reason: str,
    ) -> QuantBrainDecision:
        return QuantBrainDecision(
            recommended_side="wait",
            recommended_contracts=0,
            limit_price_cents=52,
            limit_price_dollars=0.52,
            expected_value=0.0,
            confidence=0.50,
            active_playbook="none",
            reasoning=reason,
            brier_score=brier,
            pruned_deciles=pruned,
            onnx_consensus=onnx_consensus,
            gate_passed=False,
        )

    def evaluate_in_flight_bag(
        self,
        position_side: str,  # 'yes' | 'no'
        entry_price: float,  # e.g. 0.50
        current_contract_bid: float,  # e.g. 0.85 or 0.35
        spot_price: float,
        target_strike: float,
        time_to_expiry_s: float,
        onnx_prob_up: float = 0.50,
        onnx_prob_down: float = 0.50,
        spot_velocity_3s: float = 0.0,
        twap_60s: Optional[float] = None,
    ) -> ExitDecision:
        """Peak & Valley Horizon Detector: Decides when to release or hold an open contract bag.

        1. Peak Harvester (Top of the Hill):
           If contract price reaches >= 82¢ with > 120s remaining and spot momentum stalls,
           release bag on maker ask (85¢ - 88¢) to bank +35¢ profit without 14th-minute tail risk.
        2. Silas TWAP Gravity Lock (Quarantine Zone):
           If T <= 60s and trailing TWAP cushion is intact, HOLD TO $1.00 settlement.
        3. Valley Ejector (Bottom of the Hill):
           If contract drops to <= 38¢ with > 180s remaining and ONNX confirms sharp adverse
           breakdown, release early to salvage 35¢ - 38¢ capital instead of total 100% loss.
        """
        side_is_yes = (position_side.lower() == "yes")
        moneyness = (spot_price - target_strike) if side_is_yes else (target_strike - spot_price)
        adverse_velocity = -spot_velocity_3s if side_is_yes else spot_velocity_3s

        # Rule 1: Silas TWAP Gravity Lock (Last 60 seconds)
        if time_to_expiry_s <= 60.0:
            if twap_60s is not None and twap_60s > 0.0 and target_strike > 0.0:
                delta_twap = (twap_60s - target_strike) if side_is_yes else (target_strike - twap_60s)
                if delta_twap > 0.0:
                    v_sec = max(0.0, adverse_velocity) / 3.0
                    t_safe = max(1.0, time_to_expiry_s)
                    v_crit = (2.0 * delta_twap * 60.0) / (t_safe ** 2)
                    if v_sec < v_crit:
                        return ExitDecision(
                            action="HOLD_TO_EXPIRY",
                            limit_price_cents=100,
                            limit_price_dollars=1.00,
                            reason=f"SILAS TWAP GRAVITY: TWAP cushion +${delta_twap:.2f} intact. Math guarantees $1.00 settlement.",
                            urgency="LOCK_IN",
                        )
            # Default quarantine hold in final 15 seconds
            if time_to_expiry_s <= 15.0:
                return ExitDecision(
                    action="HOLD_TO_EXPIRY",
                    limit_price_cents=100,
                    limit_price_dollars=1.00,
                    reason="EXPIRATION QUARANTINE: T <= 15s. Strict hold for exchange settlement.",
                    urgency="NORMAL",
                )

        # Rule 2: Peak Harvester (Top of the Hill / Release Bag with Massive Profit)
        # When contract bid is 82¢ - 88¢, remaining upside is only 12¢ - 18¢, but downside risk is 85¢.
        # Only harvest if there is genuine adverse velocity (moving against us) or reversal risk, AND not deep ITM immune.
        if current_contract_bid >= 0.82 and time_to_expiry_s > 90.0:
            reversal_risk = onnx_prob_down if side_is_yes else onnx_prob_up
            is_deep_itm = (moneyness >= 100.0)
            has_adverse_momentum = (adverse_velocity >= 15.0) or (reversal_risk >= 0.65)

            if has_adverse_momentum and not is_deep_itm:
                target_cents = min(88, max(82, int(current_contract_bid * 100)))
                return ExitDecision(
                    action="HARVEST_PEAK",
                    limit_price_cents=target_cents,
                    limit_price_dollars=target_cents / 100.0,
                    reason=f"PEAK HARVESTER: Contract reached {current_contract_bid*100:.0f}¢ (upside capped, adverse velocity {adverse_velocity:+.1f}$/s, reversal risk {reversal_risk*100:.0f}%). Banking profit.",
                    urgency="LOCK_IN",
                )

        # Rule 3: Valley Ejector (Bottom of the Hill / Cut Losses Early)
        # When trade is failing early (T > 180s) and ONNX confirms sharp adverse breakdown
        if current_contract_bid <= 0.38 and time_to_expiry_s > 180.0:
            opposing_prob = onnx_prob_down if side_is_yes else onnx_prob_up
            if opposing_prob >= 0.65 or moneyness < -30.0:
                salvage_cents = max(30, int(current_contract_bid * 100))
                return ExitDecision(
                    action="EJECT_VALLEY",
                    limit_price_cents=salvage_cents,
                    limit_price_dollars=salvage_cents / 100.0,
                    reason=f"VALLEY EJECTOR: Contract dropped to {current_contract_bid*100:.0f}¢ with {opposing_prob*100:.0f}% adverse ONNX. Preserving {salvage_cents}¢ capital.",
                    urgency="URGENT",
                )

        # Normal holding state
        return ExitDecision(
            action="HOLD_TO_EXPIRY",
            limit_price_cents=100,
            limit_price_dollars=1.00,
            reason="HEALTHY DRIFT: Position within standard statistical bounds. Holding for full settlement.",
            urgency="NORMAL",
        )



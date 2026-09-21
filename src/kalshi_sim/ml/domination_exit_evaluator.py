"""Domination Strategy Exit Evaluator.

Implements the 4-Regime Fading Mathematics and 6 quantitative exit rules:
- Rule 1: Asymmetric Tail Risk Ceiling
- Rule 2: High-Frequency Spot Delta Front-Runner (4-Regime Fading Mathematics)
- Rule 3: High-Water Mark Trailing Profit Ratchet & Deep Breakeven Armor
- Rule 4: Late-Cycle Expiration Defense (15s < T <= 120s)
- Rule 5: Dynamic Reversal Take-Profit Harvest
- Rule 5.5: Lead Deer Quant Horizon Bag Evaluator (Peak Harvester)
- Rule 6: Valley Ejector (Early Loss Capping / Dynamic Capital Salvage)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Optional, Tuple

from kalshi_sim.ml.lead_deer_quant_brain import ExitDecision, LeadDeerQuantBrain
from kalshi_sim.schemas import L2BookState, OrderSide

logger = logging.getLogger("kalshi_sim.domination_bot.exit_evaluator")


def standard_normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function Phi(x)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass(frozen=True)
class DominationExitDecision:
    """Structured exit decision output from the 3-Step Domination Bot."""
    should_exit: bool
    exit_reason: str  # 'TAKE_PROFIT_CEILING' | 'TAKE_PROFIT_ROI' | 'LATE_CYCLE_HARVEST' | 'HOLD' | 'NO_BID' | 'NONE'
    exit_price: Decimal
    profit_pct: float
    unrealized_pnl: Decimal
    rationale: str


class DominationExitEvaluator:
    """Evaluates open positions against quantitative Take-Profit and Early Liquidation rules."""

    def __init__(self, bot: Any) -> None:
        self.bot = bot

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
        """Evaluate Spot Velocity Front-Run using 4-Regime Fading Mathematics.

        Regime 1 (T > 240s): Macro Drift Zone (Z-Score >= 2.50σ and outside Deep ITM Moat).
        Regime 2 (60s < T <= 240s): Transition Zone (adaptive moneyness-scaled threshold).
        Regime 3 (15s < T <= 60s): Silas TWAP Fading Invariance (exit vetoed unless |v| >= v_crit).
        Regime 4 (T <= 15s): Expiration Quarantine Zone (strict hold to $1.00 settlement).
        """
        bot = self.bot
        if not bot.enable_dynamic_spot_velocity:
            adverse_spot_dump = False
            if side_is_yes and spot_velocity_3s <= -bot.spot_delta_front_run_threshold:
                adverse_spot_dump = True
            elif (not side_is_yes) and spot_velocity_3s >= bot.spot_delta_front_run_threshold:
                adverse_spot_dump = True
            return adverse_spot_dump, f"Static Threshold: {bot.spot_delta_front_run_threshold:.2f}"

        # Calculate adverse velocity (positive number means moving adversely against our position)
        adverse_vel_3s = -spot_velocity_3s if side_is_yes else spot_velocity_3s

        if adverse_vel_3s <= 0.0:
            return False, f"Favorable drift ({spot_velocity_3s:+.2f})"

        # Regime 4: Expiration Quarantine Zone (T_rem <= 15s)
        quarantine_s = getattr(bot, "twap_fading_quarantine_seconds", 15.0)
        if time_to_expiry_s <= quarantine_s:
            return (
                False,
                f"EXPIRATION QUARANTINE: T={time_to_expiry_s:.1f}s <= {quarantine_s:.0f}s. "
                f"Sells strictly locked out to protect EV and hold for $1.00 settlement."
            )

        # Volatility calibration
        sigma_1 = rolling_vol_1m if (rolling_vol_1m is not None and rolling_vol_1m > 0.001) else getattr(bot, "typical_1m_volatility", getattr(bot, "default_btc_1m_volatility", 14.0))
        sigma_s = sigma_1 / math.sqrt(60.0)
        sigma_3s = max(0.001, sigma_s * math.sqrt(3.0))

        # Moneyness & Deep ITM Moat
        if spot_price > 0.0 and target_strike > 0.0:
            moneyness = (spot_price - target_strike) if side_is_yes else (target_strike - spot_price)
            moat_mult = getattr(bot, "moneyness_moat_multiplier", 1.36)
            moat = moat_mult * sigma_s * math.sqrt(max(10.0, time_to_expiry_s))
            # If position is deep ITM and remaining moneyness after adverse move is still well above moat
            if moneyness > 0 and moneyness >= moat and (moneyness - adverse_vel_3s) > (0.5 * moat):
                return (
                    False,
                    f"DEEP ITM IMMUNITY: Moneyness +${moneyness:.2f} exceeds dynamic moat +${moat:.2f}. "
                    f"Position safe from adverse drift."
                )
        else:
            moneyness = 0.0

        # Regime 3: TWAP Fading Zone (15s < T_rem <= 60s)
        # Silas TWAP Gravity Invariance: Kalshi settles on 60s trailing TWAP.
        # Future spot velocity impact fades quadratically at O(T_rem^2).
        if time_to_expiry_s <= bot.twap_fading_window_seconds and twap_60s is not None and twap_60s > 0.0 and target_strike > 0.0:
            delta_twap = (twap_60s - target_strike) if side_is_yes else (target_strike - twap_60s)
            if delta_twap > 0.0:
                v_sec = adverse_vel_3s / 3.0
                t_safe = max(1.0, time_to_expiry_s)
                v_crit = (2.0 * delta_twap * 60.0) / (t_safe ** 2)
                if v_sec < v_crit:
                    return (
                        False,
                        f"SILAS TWAP GRAVITY VETO: Adverse velocity {v_sec:+.2f}$/s < v_crit {v_crit:.2f}$/s. "
                        f"60s TWAP cushion +${delta_twap:.2f} physically intact. Holding to $1.00 settlement."
                    )
                else:
                    return (
                        True,
                        f"TWAP BREACH HAZARD: Adverse velocity {v_sec:+.2f}$/s >= v_crit {v_crit:.2f}$/s "
                        f"threatens settlement TWAP (+${delta_twap:.2f} cushion). Front-running vacuum!"
                    )

        # Regime 2: Transition Zone (60s < T_rem <= 240s)
        if time_to_expiry_s <= 240.0:
            if spot_price > 0.0 and target_strike > 0.0:
                m_pos = max(0.0, moneyness)
                scale = math.sqrt(time_to_expiry_s / 60.0)
                dyn_thresh = max(0.80 * sigma_1, m_pos / max(0.5, scale))
            else:
                dyn_thresh = bot.spot_delta_front_run_threshold

            if adverse_vel_3s >= dyn_thresh:
                return (
                    True,
                    f"TRANSITION DRIFT HAZARD: 3s adverse velocity {adverse_vel_3s:+.2f} >= dynamic threshold "
                    f"{dyn_thresh:.2f} (T={time_to_expiry_s:.0f}s). Front-running resting bids!"
                )
            else:
                return (
                    False,
                    f"TRANSITION NORMAL: 3s adverse velocity {adverse_vel_3s:+.2f} < dynamic threshold {dyn_thresh:.2f}."
                )

        # Regime 1: Macro Drift Zone (T_rem > 240s)
        z_score = adverse_vel_3s / sigma_3s
        if z_score >= bot.velocity_z_score_threshold:
            return (
                True,
                f"MACRO DRIFT SHIFT: Adverse velocity Z-Score {z_score:.2f}σ >= {bot.velocity_z_score_threshold:.2f}σ "
                f"(Adverse {adverse_vel_3s:+.2f}$ in 3s). Front-running trend reversal."
            )
        else:
            return (
                False,
                f"MACRO STABLE: Adverse velocity Z-Score {z_score:.2f}σ < {bot.velocity_z_score_threshold:.2f}σ."
            )

    def evaluate_exit(
        self,
        side: Optional[OrderSide | str] = None,
        entry_price: Optional[Decimal] = None,
        size: Optional[int] = None,
        book: Optional[L2BookState] = None,
        time_to_expiry_s: float = 600.0,
        spot_price: float = 0.0,
        target_strike: float = 0.0,
        peak_bid: Optional[Decimal] = None,
        spot_velocity_3s: float = 0.0,
        twap_60s: Optional[float] = None,
        rolling_vol_1m: Optional[float] = None,
        position: Optional[Any] = None,
        **kwargs: Any,
    ) -> DominationExitDecision:
        """Evaluate open position against quantitative Take-Profit and Early Liquidation rules."""
        bot = self.bot

        # Handle position object if passed directly or via kwargs
        pos_obj = position or kwargs.get("position")
        if pos_obj is not None:
            if side is None:
                side = getattr(pos_obj, "side", OrderSide.YES)
            if entry_price is None:
                entry_price = getattr(pos_obj, "entry_price", Decimal("0.55"))
            if size is None or size == 0:
                size = getattr(pos_obj, "size", 1)

        if side is None:
            side = OrderSide.YES
        if entry_price is None:
            entry_price = Decimal("0.55")
        if size is None or size <= 0:
            size = 1

        if not book:
            return DominationExitDecision(
                should_exit=False,
                exit_reason="NONE",
                exit_price=Decimal("0.00"),
                profit_pct=0.0,
                unrealized_pnl=Decimal("0.00"),
                rationale="No order book or zero position size.",
            )

        side_is_yes = (side == OrderSide.YES) if isinstance(side, OrderSide) else (str(side).lower() == "yes")
        best_bid = book.best_yes_bid if side_is_yes else book.best_no_bid

        if best_bid is None or best_bid <= Decimal("0.00"):
            return DominationExitDecision(
                should_exit=False,
                exit_reason="NO_BID",
                exit_price=Decimal("0.00"),
                profit_pct=0.0,
                unrealized_pnl=Decimal("0.00"),
                rationale=f"Cannot exit: No active bid on the {'YES' if side_is_yes else 'NO'} book to liquidate against.",
            )

        safe_entry = max(Decimal("0.01"), entry_price)
        gross_pnl_per_ct = best_bid - safe_entry
        net_pnl_per_ct = gross_pnl_per_ct - bot.fee_per_contract
        total_net_pnl = net_pnl_per_ct * Decimal(str(size))
        roi = float(gross_pnl_per_ct / safe_entry)

        # Compute indicator probabilities and reverse direction conviction
        if hasattr(bot, "compute_market_probabilities"):
            prob_yes, prob_no = bot.compute_market_probabilities(
                book=book,
                spot_price=spot_price,
                target_strike=target_strike,
                time_to_expiry_s=time_to_expiry_s,
            )
        else:
            if spot_price > 0.0 and target_strike > 0.0:
                tau_mins = max(0.1, time_to_expiry_s / 60.0)
                vol = max(4.0, getattr(bot, "default_btc_1m_volatility", 14.0) * math.sqrt(tau_mins))
                z = (spot_price - target_strike) / vol
                prob_yes = max(0.001, min(0.999, standard_normal_cdf(z)))
                prob_no = 1.0 - prob_yes
            elif book and book.best_yes_bid is not None:
                prob_yes = float(book.best_yes_bid)
                prob_no = 1.0 - prob_yes
            else:
                prob_yes, prob_no = 0.50, 0.50

        reverse_prob = prob_no if side_is_yes else prob_yes
        if hasattr(bot, "compute_dynamic_reversal_threshold"):
            dyn_reversal_threshold = bot.compute_dynamic_reversal_threshold(time_to_expiry_s)
        else:
            dyn_reversal_threshold = getattr(bot, "reverse_indicator_threshold", 0.70)

        # Rule 1: Asymmetric Tail Risk Ceiling (e.g. Bid >= $0.94 or $0.90)
        # Exits if ceiling reached AND either require_reversal_for_tp_ceiling is False OR reverse_prob >= dyn_reversal_threshold
        if bot.enable_take_profit_ceiling and best_bid >= bot.take_profit_price_threshold and net_pnl_per_ct > Decimal("0.00"):
            reversal_confirmed = (not bot.require_reversal_for_tp_ceiling) or (reverse_prob >= dyn_reversal_threshold)
            if reversal_confirmed:
                rev_text = f" with {reverse_prob*100:.1f}% adverse reversal confirmation" if bot.require_reversal_for_tp_ceiling else ""
                return DominationExitDecision(
                    should_exit=True,
                    exit_reason="TAKE_PROFIT_CEILING",
                    exit_price=best_bid,
                    profit_pct=round(roi * 100.0, 2),
                    unrealized_pnl=round(total_net_pnl, 4),
                    rationale=(
                        f"🎯 [TAKE PROFIT CEILING] Best bid ${best_bid:.2f} >= ${bot.take_profit_price_threshold:.2f} "
                        f"reached{rev_text} | Net profit +${total_net_pnl:.2f} (+{roi*100:.1f}% ROI) | "
                        f"Liquidating immediately to lock in banked gains before gamma cliff."
                    ),
                )
            else:
                logger.debug(
                    "[HOLD TO SETTLEMENT] Bid $%.2f >= $%.2f ceiling, but reverse conviction %.1f%% < %.0f%%. Continuing to $1.00 settlement.",
                    float(best_bid), float(bot.take_profit_price_threshold), reverse_prob * 100.0, dyn_reversal_threshold * 100.0
                )

        # Rule 2: High-Frequency Spot Delta Front-Runner (Fading Mathematics)
        if best_bid >= Decimal("0.85") and net_pnl_per_ct > Decimal("0.00"):
            should_front_run, fr_rationale = self.compute_dynamic_spot_velocity_decision(
                side_is_yes=side_is_yes,
                spot_velocity_3s=spot_velocity_3s,
                time_to_expiry_s=time_to_expiry_s,
                spot_price=spot_price,
                target_strike=target_strike,
                twap_60s=twap_60s,
                rolling_vol_1m=rolling_vol_1m,
            )

            if should_front_run:
                return DominationExitDecision(
                    should_exit=True,
                    exit_reason="SPOT_DELTA_FRONT_RUN",
                    exit_price=best_bid,
                    profit_pct=round(roi * 100.0, 2),
                    unrealized_pnl=round(total_net_pnl, 4),
                    rationale=(
                        f"⚡ [SPOT VELOCITY FRONT-RUN] {fr_rationale} | Front-running orderbook vacuum to lock in bid "
                        f"${best_bid:.2f} (Net +${total_net_pnl:.2f}, +{roi*100:.1f}% ROI) before liquidity evaporates."
                    ),
                )

        # Rule 3: High-Water Mark Trailing Profit Ratchet & Deep Breakeven Armor
        # Calibrated via 5,000-cycle Monte Carlo: only trail after reaching deep profit (peak >= $0.88)
        # to avoid whipsawing out of normal intra-cycle 50c-70c oscillations.
        if bot.enable_trailing_ratchet and peak_bid is not None and peak_bid > best_bid:
            effective_peak = max(entry_price, peak_bid)

            # Tier 2 & 3: Major Profit Trail (Active once peak bid >= $0.88)
            if effective_peak >= Decimal("0.88"):
                buffer = Decimal("0.06") if effective_peak >= Decimal("0.92") else bot.trailing_ratchet_buffer
                tier_floor = effective_peak - buffer
                if best_bid <= tier_floor and net_pnl_per_ct > Decimal("0.00"):
                    return DominationExitDecision(
                        should_exit=True,
                        exit_reason="TRAILING_PROFIT_RATCHET",
                        exit_price=best_bid,
                        profit_pct=round(roi * 100.0, 2),
                        unrealized_pnl=round(total_net_pnl, 4),
                        rationale=(
                            f"🛡️ [TRAILING PROFIT RATCHET] Bid ${best_bid:.2f} dropped to/below trailing floor ${tier_floor:.2f} "
                            f"(Peak was ${effective_peak:.2f}) | Locking in +${total_net_pnl:.2f} profit "
                            f"(+{roi*100:.1f}% ROI) to protect banked gains."
                        ),
                    )

            # Tier 1: Deep Breakeven Armor (Active ONLY once peak reached >= $0.85 and gained >= +20c from entry)
            # Protected by lower bound (entry - 0.04) so it never sells into panic gap-downs
            if effective_peak >= Decimal("0.85") and effective_peak >= entry_price + Decimal("0.20"):
                be_floor = entry_price + bot.fee_per_contract
                if (entry_price - Decimal("0.04")) <= best_bid <= be_floor:
                    return DominationExitDecision(
                        should_exit=True,
                        exit_reason="TRAILING_PROFIT_RATCHET",
                        exit_price=best_bid,
                        profit_pct=round(roi * 100.0, 2),
                        unrealized_pnl=round(total_net_pnl, 4),
                        rationale=(
                            f"🛡️ [BREAKEVEN ARMOR] Bid ${best_bid:.2f} dropped back to entry/fee floor ${be_floor:.2f} "
                            f"(Peak was ${effective_peak:.2f}) | Exiting near breakeven to protect capital from negative reversal."
                        ),
                    )

        # Rule 4: Late-Cycle Expiration Defense (15s < T <= 120s, Bid >= $0.85, ROI >= 15%)
        # In final 2 minutes, binary gamma risk explodes; lock in gains before unpredictable settlement
        quarantine_s = getattr(bot, "twap_fading_quarantine_seconds", 15.0)
        if (
            time_to_expiry_s > quarantine_s
            and time_to_expiry_s <= 120.0
            and best_bid >= Decimal("0.85")
            and roi >= getattr(bot, "late_cycle_roi", 0.15)
            and net_pnl_per_ct > Decimal("0.00")
        ):
            return DominationExitDecision(
                should_exit=True,
                exit_reason="LATE_CYCLE_HARVEST",
                exit_price=best_bid,
                profit_pct=round(roi * 100.0, 2),
                unrealized_pnl=round(total_net_pnl, 4),
                rationale=(
                    f"⏱️ [LATE CYCLE HARVEST] T={int(time_to_expiry_s)}s <= 120s | "
                    f"Bid ${best_bid:.2f} with +{roi*100:.1f}% ROI | "
                    f"Net profit +${total_net_pnl:.2f} | Locking in win before binary settlement volatility."
                ),
            )

        # Rule 5: Dynamic Reversal Take-Profit Harvest (ROI >= min_take_profit_roi ONLY IF reverse_prob >= dyn_reversal_threshold)
        if (
            bot.enable_reverse_take_profit_roi
            and roi >= bot.min_take_profit_roi
            and reverse_prob >= dyn_reversal_threshold
            and net_pnl_per_ct > Decimal("0.00")
        ):
            return DominationExitDecision(
                should_exit=True,
                exit_reason="TAKE_PROFIT_ROI",
                exit_price=best_bid,
                profit_pct=round(roi * 100.0, 2),
                unrealized_pnl=round(total_net_pnl, 4),
                rationale=(
                    f"🚨 [REVERSE SIGNAL TAKE-PROFIT] Indicators show {reverse_prob*100:.1f}% conviction in reverse direction "
                    f"(>= {dyn_reversal_threshold*100:.0f}% target) | "
                    f"Net ROI +{roi*100:.1f}% >= +{bot.min_take_profit_roi*100:.0f}% target at ${best_bid:.2f} | "
                    f"Net profit +${total_net_pnl:.2f} | Securing banked returns before reversal destroys gains."
                ),
            )

        # Rule 5.1: The Council Doubt-Harvest Engine (Horizon-Proportional 50% Profit & Inversion Doubt)
        max_possible_gain = Decimal("1.00") - safe_entry
        upside_capture_ratio = float(gross_pnl_per_ct / max_possible_gain) if max_possible_gain > Decimal("0.00") else 0.0

        our_prob = prob_yes if side_is_yes else prob_no

        # 1. Horizon-proportional time metrics
        tau_rem = max(0.0, min(1.0, time_to_expiry_s / 900.0))
        tau_mins = max(0.25, time_to_expiry_s / 60.0)

        # 2. Time-adaptive conviction hurdle: early in cycle (e.g. 9 min) P_req ~ 0.56; late (1 min) P_req ~ 0.76
        p_req = 0.52 + 0.28 * ((1.0 - tau_rem) ** 2)
        if our_prob >= p_req:
            doubt_brain = 0.0
        else:
            doubt_brain = min(1.0, (p_req - our_prob) / max(0.10, p_req - 0.50))

        # 3. Horizon-proportional adverse velocity threat threshold:
        # At 9 min, Brownian noise envelope is wide ($25+), so minor dips do not panic
        # At 1.5 min, noise envelope collapses ($12), so adverse drift is an acute threat
        adverse_vel = -spot_velocity_3s if side_is_yes else spot_velocity_3s
        moneyness = (spot_price - target_strike) if side_is_yes else (target_strike - spot_price) if (spot_price > 0.0 and target_strike > 0.0) else 0.0
        sigma_1 = rolling_vol_1m if (rolling_vol_1m is not None and rolling_vol_1m > 0.001) else getattr(bot, "typical_1m_volatility", getattr(bot, "default_btc_1m_volatility", 14.0))
        v_threat = max(6.0, (max(0.0, moneyness) / math.sqrt(tau_mins)) * 0.35 + 0.80 * sigma_1)
        doubt_vel = max(0.0, min(1.0, adverse_vel / v_threat)) if adverse_vel > 0.0 else 0.0

        # 4. Quadratic horizon-aware doubt weight acceleration
        omega_t = 0.50 + 0.50 * ((1.0 - tau_rem) ** 1.5)
        doubt_score = min(1.0, (0.55 * doubt_brain + 0.45 * doubt_vel) * (1.0 + omega_t))

        enable_doubt_harvest = getattr(bot, "enable_doubt_harvest", True)
        doubt_thresh = getattr(bot, "doubt_threshold", 0.80)
        upside_thresh = getattr(bot, "upside_capture_ratio_threshold", 0.50)
        asymmetric_peak = getattr(bot, "asymmetric_peak_bid", Decimal("0.88"))

        twap_safe_itm = False
        if time_to_expiry_s <= 120.0 and twap_60s is not None and twap_60s > 0.0 and target_strike > 0.0:
            delta_twap = (twap_60s - target_strike) if side_is_yes else (target_strike - twap_60s)
            if delta_twap >= 10.0:
                twap_safe_itm = True

        if enable_doubt_harvest and net_pnl_per_ct > Decimal("0.04") and not twap_safe_itm:
            # Condition A: 50% Profit reached AND Directional Reversal Doubt confirmed
            if upside_capture_ratio >= upside_thresh and doubt_score >= doubt_thresh:
                return DominationExitDecision(
                    should_exit=True,
                    exit_reason="DOUBT_PROFIT_HARVEST",
                    exit_price=best_bid,
                    profit_pct=round(roi * 100.0, 2),
                    unrealized_pnl=round(total_net_pnl, 4),
                    rationale=(
                        f"🧠 [DOUBT-HARVEST TRIGGERED] Upside captured {upside_capture_ratio*100:.1f}% (Bid ${best_bid:.2f}) | "
                        f"Doubt Score {doubt_score:.2f} >= {doubt_thresh:.2f} (Brain prob {our_prob*100:.1f}%, AdvVel {adverse_vel:+.1f}) | "
                        f"Net profit +${total_net_pnl:.2f} (+{roi*100:.1f}% ROI) | Locking in realized gains before reversal."
                    ),
                )

            # Condition B: Asymmetric Peak Floor (Risking 88c for 12c upside is mathematically negative EV)
            if best_bid >= asymmetric_peak:
                return DominationExitDecision(
                    should_exit=True,
                    exit_reason="ASYMMETRIC_PEAK_HARVEST",
                    exit_price=best_bid,
                    profit_pct=round(roi * 100.0, 2),
                    unrealized_pnl=round(total_net_pnl, 4),
                    rationale=(
                        f"⛰️ [ASYMMETRIC PEAK HARVEST] Bid ${best_bid:.2f} >= ${asymmetric_peak:.2f} ceiling reached | "
                        f"Remaining upside only +${(Decimal('1.00')-best_bid):.2f} vs -${best_bid:.2f} downside | "
                        f"Net profit +${total_net_pnl:.2f} (+{roi*100:.1f}% ROI) | Harvesting optimal EV peak."
                    ),
                )

        # Rule 5.5: Lead Deer Quant Horizon Bag Evaluator (Peak Harvester)
        if getattr(bot, "enable_lead_deer_peak_harvester", False) and hasattr(bot, "lead_deer_brain") and bot.lead_deer_brain is not None:
            bag_eval: ExitDecision = bot.lead_deer_brain.evaluate_in_flight_bag(
                position_side="yes" if side_is_yes else "no",
                entry_price=float(safe_entry),
                current_contract_bid=float(best_bid),
                spot_price=spot_price,
                target_strike=target_strike,
                time_to_expiry_s=time_to_expiry_s,
                onnx_prob_up=prob_yes,
                onnx_prob_down=prob_no,
                spot_velocity_3s=spot_velocity_3s,
                twap_60s=twap_60s,
            )
            if bag_eval.action == "HARVEST_PEAK" and net_pnl_per_ct > Decimal("0.00") and bot.enable_take_profit_ceiling:
                return DominationExitDecision(
                    should_exit=True,
                    exit_reason="PEAK_HARVESTER",
                    exit_price=best_bid,
                    profit_pct=round(roi * 100.0, 2),
                    unrealized_pnl=round(total_net_pnl, 4),
                    rationale=f"🏔️ [{bag_eval.action}] {bag_eval.reason} | Liquidating on maker ask to bank locked-in profits.",
                )

        # Rule 6: Valley Ejector (Early Loss Capping / Dynamic Capital Salvage)
        # 3-Minute Death Window patched. Now operates until expiration, but tightens criteria inside 180s.
        is_valley_crash = best_bid <= Decimal("0.38") and reverse_prob >= 0.70
        if time_to_expiry_s <= 180.0:
            # Inside 3 mins, require higher conviction (85%) to prevent late-cycle jitter spoofing
            is_valley_crash = best_bid <= Decimal("0.38") and reverse_prob >= 0.85
            # Silas TWAP Parity: If TWAP is still safely in our favor, ignore the spot-driven crash.
            if twap_60s is not None and target_strike > 0.0:
                if side_is_yes and twap_60s >= target_strike + 3.0:
                    is_valley_crash = False
                elif not side_is_yes and twap_60s <= target_strike - 3.0:
                    is_valley_crash = False

        if (
            is_valley_crash
            and (peak_bid is None or peak_bid < Decimal("0.80"))
        ):
            return DominationExitDecision(
                should_exit=True,
                exit_reason="VALLEY_EJECTOR",
                exit_price=best_bid,
                profit_pct=round(roi * 100.0, 2),
                unrealized_pnl=round(total_net_pnl, 4),
                rationale=(
                    f"🛑 [VALLEY EJECTOR] Bid collapsed to ${best_bid:.2f} with {reverse_prob*100:.1f}% adverse conviction "
                    f"(T={int(time_to_expiry_s)}s) | Liquidating early to salvage capital (PnL: -${abs(total_net_pnl):.2f}) "
                    f"instead of absorbing a -100% expiration loss."
                ),
            )

        pnl_prefix = "+" if total_net_pnl >= Decimal("0.00") else "-"
        return DominationExitDecision(
            should_exit=False,
            exit_reason="HOLD",
            exit_price=best_bid,
            profit_pct=round(roi * 100.0, 2),
            unrealized_pnl=round(total_net_pnl, 4),
            rationale=f"Holding position: Bid ${best_bid:.2f} (ROI: {roi*100:+.1f}%, PnL: {pnl_prefix}${abs(total_net_pnl):.2f}) has not hit take-profit criteria.",
        )

"""Dominion 2 Bot (Anti-Pin Asymmetric Scalper Engine).

An institutional-grade quantitative strategy formulated specifically for Kalshi 15-Minute Bitcoin Binary Contracts,
incorporating all 4 empirical winning pillars derived from real exchange execution audits:

1. Hard Entry Price Ceiling (<= $0.55): Rejects inverted risk-reward trades to prevent severe drawdown.
2. Asymmetric Value Sweet-Spot ($0.25 - $0.45): Targets high-payout discount contracts (1.5x - 2.5x payout multipliers).
3. Kalshi Tie Rule Exploitation: Exploits the settlement invariant (Spot <= Strike => NO wins $1.00) in ranging regimes.
4. Anti-Pin / Anti-Tie Defense: Strictly vetoes entries within the +/-$25 strike pin zone with < 3 minutes remaining.
5. Dynamic Early Harvest & Loss Salvage: Harvests profits at >= $0.90, salvages capital on confirmed adverse reversals.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from kalshi_sim.ml.statistical_ev_engine import ExpectedValueResult, StatisticalEVEngine
from kalshi_sim.schemas import L2BookState, OrderSide, TradeEvent

logger = logging.getLogger("kalshi_sim.dominion_2_bot")


def _standard_normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function Phi(x)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass(frozen=True)
class Dominion2Decision:
    """Structured decision output from Dominion 2 Bot."""
    strategy_id: str
    strategy_name: str
    active_playbook: str
    playbook_stage: str  # 'asymmetric_breakout' | 'tie_exploiter' | 'moneyness_snub' | 'none'
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
    max_price_veto: bool = False
    anti_pin_veto: bool = False


@dataclass(frozen=True)
class Dominion2ExitDecision:
    """Structured exit decision output from Dominion 2 Bot."""
    should_exit: bool
    exit_reason: str  # 'TAKE_PROFIT_CEILING' | 'TAKE_PROFIT_ROI' | 'ADVERSE_REVERSAL_SALVAGE' | 'HOLD' | 'NO_BID' | 'NONE'
    exit_price: Decimal
    profit_pct: float
    unrealized_pnl: Decimal
    rationale: str


class Dominion2Bot:
    """Dominion 2 Bot: Anti-Pin Asymmetric Scalper & Kalshi Settlement Edge Exploiter."""

    STRATEGY_ID = "dominion_2_bot"
    STRATEGY_NAME = "Dominion 2 Bot (Anti-Pin Scalper)"

    def __init__(
        self,
        max_entry_price: Decimal = Decimal("0.55"),  # Hard ceiling: never buy contracts above $0.55 (no inverted R:R)
        min_edge_pct: float = 0.04,  # 4.0% minimum statistical edge
        min_ev_dollars: Decimal = Decimal("0.02"),  # Minimum $0.02 net EV per contract after fees
        vpin_toxic_threshold: float = 0.55,  # Stricter VPIN toxicity ceiling
        vpin_safe_threshold: float = 0.35,
        default_btc_1m_volatility: float = 14.0,  # $14 typical 1-min BTC spot std dev
        take_profit_price_threshold: Decimal = Decimal("0.90"),  # 90c profit harvest ceiling
        min_take_profit_roi: float = 0.20,  # +20% minimum ROI for early exit
        late_cycle_roi: float = 0.15,  # +15% minimum ROI in final 120s
        fee_per_contract: Decimal = Decimal("0.01"),  # Real exchange taker fee ($0.01)
        anti_pin_time_threshold_s: float = 180.0,  # 3-minute anti-pin window
        anti_pin_diff_threshold: float = 25.0,  # +/- $25 pin zone threshold
        asymmetric_sweet_spot_max: Decimal = Decimal("0.45"),  # $0.25 - $0.45 asymmetric pricing sweet spot
    ) -> None:
        self.max_entry_price = max_entry_price
        self.min_edge_pct = min_edge_pct
        self.min_ev_dollars = min_ev_dollars
        self.vpin_toxic_threshold = vpin_toxic_threshold
        self.vpin_safe_threshold = vpin_safe_threshold
        self.default_btc_1m_volatility = default_btc_1m_volatility
        self.take_profit_price_threshold = take_profit_price_threshold
        self.min_take_profit_roi = min_take_profit_roi
        self.late_cycle_roi = late_cycle_roi
        self.fee_per_contract = fee_per_contract
        self.anti_pin_time_threshold_s = anti_pin_time_threshold_s
        self.anti_pin_diff_threshold = anti_pin_diff_threshold
        self.asymmetric_sweet_spot_max = asymmetric_sweet_spot_max

        # Underlying Statistical EV & Quarter-Kelly Optimizer
        self._ev_engine = StatisticalEVEngine(
            min_ev_threshold=min_ev_dollars,
            min_edge_pct=min_edge_pct,
            fee_per_contract=fee_per_contract,
        )

    # -------------------------------------------------------------------------
    # Evaluation Engine
    # -------------------------------------------------------------------------

    def evaluate(
        self,
        book: Optional[L2BookState],
        spot_price: Union[float, Decimal],
        target_strike: Union[float, Decimal],
        time_to_expiry_s: float,
        recent_trades: Optional[List[TradeEvent]] = None,
        total_equity: Decimal = Decimal("25.00"),
        max_position_size: int = 4,
        estimated_vpin: float = 0.15,
        onnx_p_wait: float = 0.0,
    ) -> Dominion2Decision:
        """Evaluate market state and generate trade decision using Dominion 2 logic."""
        spot_f = float(spot_price)
        strike_f = float(target_strike)

        if not book or (not book.yes_book and not book.no_book) or spot_f <= 0 or strike_f <= 0:
            return self._make_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=0.0,
                vpin=estimated_vpin,
                rationale="Dominion 2 Bot waiting for active order book & market feeds.",
            )

        spot_diff = spot_f - strike_f

        # Extract orderbook inside touch
        best_yes_ask = book.best_yes_ask if book.best_yes_ask is not None else Decimal("0.99")
        best_no_ask = book.best_no_ask if book.best_no_ask is not None else Decimal("0.99")
        best_yes_bid = book.best_yes_bid if book.best_yes_bid is not None else Decimal("0.01")
        best_no_bid = book.best_no_bid if book.best_no_bid is not None else Decimal("0.01")

        # ---------------------------------------------------------------------
        # Guardrail 1: VPIN Order Flow Toxicity Veto
        # ---------------------------------------------------------------------
        if estimated_vpin >= self.vpin_toxic_threshold:
            return self._make_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                vpin=estimated_vpin,
                rationale=f"VPIN toxicity veto ({estimated_vpin:.3f} >= {self.vpin_toxic_threshold:.2f}). Adverse selection risk.",
            )

        # ---------------------------------------------------------------------
        # Guardrail 2: Anti-Pin / Anti-Tie Defense Veto (< 3 Minutes Remaining)
        # ---------------------------------------------------------------------
        if time_to_expiry_s <= self.anti_pin_time_threshold_s and abs(spot_diff) <= self.anti_pin_diff_threshold:
            return self._make_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                vpin=estimated_vpin,
                rationale=f"Anti-Pin Guard: Spot diff (${spot_diff:+.2f}) inside +/-${self.anti_pin_diff_threshold:.0f} tie zone with {time_to_expiry_s:.0f}s left.",
                anti_pin_veto=True,
            )

        # ---------------------------------------------------------------------
        # Guardrail 3: ONNX High-Uncertainty WAIT Regime Veto
        # ---------------------------------------------------------------------
        if onnx_p_wait >= 0.70 and (0.45 <= float(best_yes_ask) <= 0.55 or 0.45 <= float(best_no_ask) <= 0.55):
            return self._make_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                vpin=estimated_vpin,
                rationale=f"ONNX WAIT Regime Veto: P(WAIT)={onnx_p_wait*100:.1f}% in 50-50 pin band ($0.45-$0.55).",
            )

        # ---------------------------------------------------------------------
        # Compute Time-Decayed Volatility & Digital Option Fair Probabilities
        # ---------------------------------------------------------------------
        mins_remaining = max(0.25, time_to_expiry_s / 60.0)
        expected_sigma = self.default_btc_1m_volatility * math.sqrt(mins_remaining)
        z_score = spot_diff / max(1.0, expected_sigma)
        prob_yes_raw = _standard_normal_cdf(z_score)

        # Apply realistic probability bounds
        prob_yes = max(0.05, min(0.95, prob_yes_raw))
        prob_no = 1.0 - prob_yes

        # ---------------------------------------------------------------------
        # Playbook Selection by Expiration Window
        # ---------------------------------------------------------------------
        if time_to_expiry_s >= 600.0:
            # Playbook 1: Asymmetric Momentum Breakout (10:00 - 15:00 remaining)
            return self._eval_playbook1_asymmetric_breakout(
                best_yes_ask=best_yes_ask,
                best_no_ask=best_no_ask,
                prob_yes=prob_yes,
                prob_no=prob_no,
                spot_diff=spot_diff,
                time_to_expiry_s=time_to_expiry_s,
                vpin_score=estimated_vpin,
                account_balance=total_equity,
                max_position_size=max_position_size,
            )
        elif time_to_expiry_s >= 240.0:
            # Playbook 2: Kalshi Tie / NO Exploiter (4:00 - 10:00 remaining)
            return self._eval_playbook2_tie_exploiter(
                best_yes_ask=best_yes_ask,
                best_no_ask=best_no_ask,
                prob_yes=prob_yes,
                prob_no=prob_no,
                spot_diff=spot_diff,
                time_to_expiry_s=time_to_expiry_s,
                vpin_score=estimated_vpin,
                account_balance=total_equity,
                max_position_size=max_position_size,
            )
        else:
            # Playbook 3: Confirmed Moneyness Snub (1:00 - 4:00 remaining)
            return self._eval_playbook3_moneyness_snub(
                best_yes_ask=best_yes_ask,
                best_no_ask=best_no_ask,
                prob_yes=prob_yes,
                prob_no=prob_no,
                spot_diff=spot_diff,
                time_to_expiry_s=time_to_expiry_s,
                vpin_score=estimated_vpin,
                account_balance=total_equity,
                max_position_size=max_position_size,
            )

    # -------------------------------------------------------------------------
    # Playbook 1: Asymmetric Momentum Breakout (10:00 - 15:00 remaining)
    # -------------------------------------------------------------------------

    def _eval_playbook1_asymmetric_breakout(
        self,
        best_yes_ask: Decimal,
        best_no_ask: Decimal,
        prob_yes: float,
        prob_no: float,
        spot_diff: float,
        time_to_expiry_s: float,
        vpin_score: float,
        account_balance: Decimal,
        max_position_size: int,
    ) -> Dominion2Decision:
        # Evaluate statistical EV for both sides
        ev_yes_res = self._ev_engine.calculate_ev(prob_win=prob_yes, market_ask=best_yes_ask)
        ev_no_res = self._ev_engine.calculate_ev(prob_win=prob_no, market_ask=best_no_ask)

        # 1. Check YES Asymmetric Breakout (requires positive delta and cheap entry)
        if spot_diff >= 30.0 and ev_yes_res.has_positive_ev and ev_yes_res.statistical_edge >= self.min_edge_pct:
            if best_yes_ask > self.max_entry_price:
                return self._make_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=vpin_score,
                    rationale=f"Playbook 1 YES Veto: Ask ${best_yes_ask:.2f} exceeds ceiling ${self.max_entry_price:.2f} (Inverted R:R protection).",
                    max_price_veto=True,
                )
            
            # Sizing: Quarter-Kelly with asymmetric sweet-spot bonus
            kelly = self._ev_engine.calculate_quarter_kelly_size(
                ev_result=ev_yes_res,
                bankroll=account_balance,
                ask_price=best_yes_ask,
                max_contracts=max_position_size,
            )
            contracts = max(1, min(max_position_size, kelly.recommended_contracts))
            if best_yes_ask <= self.asymmetric_sweet_spot_max:
                contracts = min(max_position_size, contracts + 1)

            return Dominion2Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="Playbook 1: Asymmetric Momentum Breakout",
                playbook_stage="asymmetric_breakout",
                p_up=prob_yes,
                p_down=prob_no,
                p_wait=0.10,
                vpin=vpin_score,
                vpin_is_safe=True,
                ev_yes=float(ev_yes_res.net_expected_value),
                ev_no=float(ev_no_res.net_expected_value),
                edge_yes=ev_yes_res.statistical_edge,
                edge_no=ev_no_res.statistical_edge,
                kelly_f_yes=kelly.fraction_to_risk,
                kelly_f_no=0.0,
                recommended_side="yes",
                recommended_contracts=contracts,
                rationale=f"Playbook 1 YES: Spot +${spot_diff:.2f} above strike | Ask ${best_yes_ask:.2f} (Edge: +{ev_yes_res.statistical_edge*100:.1f}%)",
                edge_pct=ev_yes_res.statistical_edge,
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
            )

        # 2. Check NO Asymmetric Breakout (downward momentum)
        if spot_diff <= -25.0 and ev_no_res.has_positive_ev and ev_no_res.statistical_edge >= self.min_edge_pct:
            if best_no_ask > self.max_entry_price:
                return self._make_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=vpin_score,
                    rationale=f"Playbook 1 NO Veto: Ask ${best_no_ask:.2f} exceeds ceiling ${self.max_entry_price:.2f}.",
                    max_price_veto=True,
                )

            kelly = self._ev_engine.calculate_quarter_kelly_size(
                ev_result=ev_no_res,
                bankroll=account_balance,
                ask_price=best_no_ask,
                max_contracts=max_position_size,
            )
            contracts = max(1, min(max_position_size, kelly.recommended_contracts))
            if best_no_ask <= self.asymmetric_sweet_spot_max:
                contracts = min(max_position_size, contracts + 1)

            return Dominion2Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="Playbook 1: Asymmetric Momentum Breakout",
                playbook_stage="asymmetric_breakout",
                p_up=prob_yes,
                p_down=prob_no,
                p_wait=0.10,
                vpin=vpin_score,
                vpin_is_safe=True,
                ev_yes=float(ev_yes_res.net_expected_value),
                ev_no=float(ev_no_res.net_expected_value),
                edge_yes=ev_yes_res.statistical_edge,
                edge_no=ev_no_res.statistical_edge,
                kelly_f_yes=0.0,
                kelly_f_no=kelly.fraction_to_risk,
                recommended_side="no",
                recommended_contracts=contracts,
                rationale=f"Playbook 1 NO: Spot ${spot_diff:.2f} below strike | Ask ${best_no_ask:.2f} (Edge: +{ev_no_res.statistical_edge*100:.1f}%)",
                edge_pct=ev_no_res.statistical_edge,
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
            )

        return self._make_wait_decision(
            time_to_expiry_s=time_to_expiry_s,
            spot_diff=spot_diff,
            vpin=vpin_score,
            rationale=f"Playbook 1 WAIT: Insufficient breakout edge (Diff: ${spot_diff:+.2f}, YES Edge: {ev_yes_res.statistical_edge*100:.1f}%, NO Edge: {ev_no_res.statistical_edge*100:.1f}%).",
        )

    # -------------------------------------------------------------------------
    # Playbook 2: Kalshi Tie / NO Range Exploiter (4:00 - 10:00 remaining)
    # -------------------------------------------------------------------------

    def _eval_playbook2_tie_exploiter(
        self,
        best_yes_ask: Decimal,
        best_no_ask: Decimal,
        prob_yes: float,
        prob_no: float,
        spot_diff: float,
        time_to_expiry_s: float,
        vpin_score: float,
        account_balance: Decimal,
        max_position_size: int,
    ) -> Dominion2Decision:
        # In Kalshi: Spot <= Strike settles NO. If ranging (|diff| < $30), NO has structural positive expectancy
        ev_no_res = self._ev_engine.calculate_ev(prob_win=prob_no, market_ask=best_no_ask)
        ev_yes_res = self._ev_engine.calculate_ev(prob_win=prob_yes, market_ask=best_yes_ask)

        # 1. Ranging regime: Exploit NO Tie settlement rule
        if spot_diff <= 15.0 and ev_no_res.statistical_edge >= 0.03:
            if best_no_ask > self.max_entry_price:
                return self._make_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=vpin_score,
                    rationale=f"Playbook 2 NO Veto: Ask ${best_no_ask:.2f} exceeds ceiling ${self.max_entry_price:.2f} (Inverted R:R protection).",
                    max_price_veto=True,
                )
            kelly = self._ev_engine.calculate_quarter_kelly_size(
                ev_result=ev_no_res,
                bankroll=account_balance,
                ask_price=best_no_ask,
                max_contracts=max_position_size,
            )
            contracts = max(1, min(max_position_size, kelly.recommended_contracts))
            return Dominion2Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="Playbook 2: Kalshi Tie / NO Exploiter",
                playbook_stage="tie_exploiter",
                p_up=prob_yes,
                p_down=prob_no,
                p_wait=0.10,
                vpin=vpin_score,
                vpin_is_safe=True,
                ev_yes=float(ev_yes_res.net_expected_value),
                ev_no=float(ev_no_res.net_expected_value),
                edge_yes=ev_yes_res.statistical_edge,
                edge_no=ev_no_res.statistical_edge,
                kelly_f_yes=0.0,
                kelly_f_no=kelly.fraction_to_risk,
                recommended_side="no",
                recommended_contracts=contracts,
                rationale=f"Playbook 2 NO: Ranging regime (Diff: ${spot_diff:+.2f}). Exploiting Kalshi Spot <= Strike Tie Settlement Rule | Ask ${best_no_ask:.2f}",
                edge_pct=ev_no_res.statistical_edge,
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
            )

        # 2. Strong YES trend continuation
        if spot_diff >= 45.0 and ev_yes_res.statistical_edge >= self.min_edge_pct:
            if best_yes_ask > self.max_entry_price:
                return self._make_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=vpin_score,
                    rationale=f"Playbook 2 YES Veto: Ask ${best_yes_ask:.2f} exceeds ceiling ${self.max_entry_price:.2f} (Inverted R:R protection).",
                    max_price_veto=True,
                )
            kelly = self._ev_engine.calculate_quarter_kelly_size(
                ev_result=ev_yes_res,
                bankroll=account_balance,
                ask_price=best_yes_ask,
                max_contracts=max_position_size,
            )
            contracts = max(1, min(max_position_size, kelly.recommended_contracts))
            return Dominion2Decision(
                strategy_id=self.STRATEGY_ID,
                strategy_name=self.STRATEGY_NAME,
                active_playbook="Playbook 2: Kalshi Trend Continuation",
                playbook_stage="tie_exploiter",
                p_up=prob_yes,
                p_down=prob_no,
                p_wait=0.10,
                vpin=vpin_score,
                vpin_is_safe=True,
                ev_yes=float(ev_yes_res.net_expected_value),
                ev_no=float(ev_no_res.net_expected_value),
                edge_yes=ev_yes_res.statistical_edge,
                edge_no=ev_no_res.statistical_edge,
                kelly_f_yes=kelly.fraction_to_risk,
                kelly_f_no=0.0,
                recommended_side="yes",
                recommended_contracts=contracts,
                rationale=f"Playbook 2 YES: Strong trend buffer (+${spot_diff:.2f}) | Ask ${best_yes_ask:.2f} (Edge: +{ev_yes_res.statistical_edge*100:.1f}%)",
                edge_pct=ev_yes_res.statistical_edge,
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
            )

        return self._make_wait_decision(
            time_to_expiry_s=time_to_expiry_s,
            spot_diff=spot_diff,
            vpin=vpin_score,
            rationale=f"Playbook 2 WAIT: Market in unconfirmed zone (Diff: ${spot_diff:+.2f}). Waiting for discount edge.",
        )

    # -------------------------------------------------------------------------
    # Playbook 3: Confirmed Moneyness Snub (1:00 - 4:00 remaining)
    # -------------------------------------------------------------------------

    def _eval_playbook3_moneyness_snub(
        self,
        best_yes_ask: Decimal,
        best_no_ask: Decimal,
        prob_yes: float,
        prob_no: float,
        spot_diff: float,
        time_to_expiry_s: float,
        vpin_score: float,
        account_balance: Decimal,
        max_position_size: int,
    ) -> Dominion2Decision:
        # Late in cycle: Only trade if spot is decisively away from strike (> $35)
        if abs(spot_diff) < 35.0:
            return self._make_wait_decision(
                time_to_expiry_s=time_to_expiry_s,
                spot_diff=spot_diff,
                vpin=vpin_score,
                rationale=f"Playbook 3 VETO: Late cycle pin risk (|Diff|=${abs(spot_diff):.2f} < $35). Vetoing coin-flip expiration.",
                anti_pin_veto=True,
            )

        # High-certainty NO snub
        if spot_diff <= -35.0:
            if best_no_ask > self.max_entry_price:
                return self._make_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=vpin_score,
                    rationale=f"Playbook 3 NO Veto: Ask ${best_no_ask:.2f} exceeds ceiling ${self.max_entry_price:.2f}.",
                    max_price_veto=True,
                )
            ev_no_res = self._ev_engine.calculate_ev(prob_win=prob_no, market_ask=best_no_ask)
            if ev_no_res.has_positive_ev:
                kelly = self._ev_engine.calculate_quarter_kelly_size(
                    ev_result=ev_no_res,
                    bankroll=account_balance,
                    ask_price=best_no_ask,
                    max_contracts=max_position_size,
                )
                contracts = max(1, min(max_position_size, kelly.recommended_contracts))
                return Dominion2Decision(
                    strategy_id=self.STRATEGY_ID,
                    strategy_name=self.STRATEGY_NAME,
                    active_playbook="Playbook 3: Confirmed Moneyness Snub",
                    playbook_stage="moneyness_snub",
                    p_up=prob_yes,
                    p_down=prob_no,
                    p_wait=0.05,
                    vpin=vpin_score,
                    vpin_is_safe=True,
                    ev_yes=0.0,
                    ev_no=float(ev_no_res.net_expected_value),
                    edge_yes=0.0,
                    edge_no=ev_no_res.statistical_edge,
                    kelly_f_yes=0.0,
                    kelly_f_no=kelly.fraction_to_risk,
                    recommended_side="no",
                    recommended_contracts=contracts,
                    rationale=f"Playbook 3 NO Snub: Confirmed OTM (${spot_diff:.2f}) with {time_to_expiry_s:.0f}s left | Ask ${best_no_ask:.2f}",
                    edge_pct=ev_no_res.statistical_edge,
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                )

        # High-certainty YES snub
        if spot_diff >= 45.0:
            if best_yes_ask > self.max_entry_price:
                return self._make_wait_decision(
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                    vpin=vpin_score,
                    rationale=f"Playbook 3 YES Veto: Ask ${best_yes_ask:.2f} exceeds ceiling ${self.max_entry_price:.2f}.",
                    max_price_veto=True,
                )
            ev_yes_res = self._ev_engine.calculate_ev(prob_win=prob_yes, market_ask=best_yes_ask)
            if ev_yes_res.has_positive_ev:
                kelly = self._ev_engine.calculate_quarter_kelly_size(
                    ev_result=ev_yes_res,
                    bankroll=account_balance,
                    ask_price=best_yes_ask,
                    max_contracts=max_position_size,
                )
                contracts = max(1, min(max_position_size, kelly.recommended_contracts))
                return Dominion2Decision(
                    strategy_id=self.STRATEGY_ID,
                    strategy_name=self.STRATEGY_NAME,
                    active_playbook="Playbook 3: Confirmed Moneyness Snub",
                    playbook_stage="moneyness_snub",
                    p_up=prob_yes,
                    p_down=prob_no,
                    p_wait=0.05,
                    vpin=vpin_score,
                    vpin_is_safe=True,
                    ev_yes=float(ev_yes_res.net_expected_value),
                    ev_no=0.0,
                    edge_yes=ev_yes_res.statistical_edge,
                    edge_no=0.0,
                    kelly_f_yes=kelly.fraction_to_risk,
                    kelly_f_no=0.0,
                    recommended_side="yes",
                    recommended_contracts=contracts,
                    rationale=f"Playbook 3 YES Snub: Confirmed ITM (+${spot_diff:.2f}) with {time_to_expiry_s:.0f}s left | Ask ${best_yes_ask:.2f}",
                    edge_pct=ev_yes_res.statistical_edge,
                    time_to_expiry_s=time_to_expiry_s,
                    spot_diff=spot_diff,
                )

        return self._make_wait_decision(
            time_to_expiry_s=time_to_expiry_s,
            spot_diff=spot_diff,
            vpin=vpin_score,
            rationale=f"Playbook 3 WAIT: Late cycle risk protection active.",
        )

    # -------------------------------------------------------------------------
    # Playbook 4: Dynamic Early Harvest & Loss Salvage
    # -------------------------------------------------------------------------

    def evaluate_exit(
        self,
        holding_side: OrderSide,
        contracts: int,
        entry_price: Decimal,
        book: Optional[L2BookState],
        time_to_expiry_s: float,
        spot_price: Optional[Union[float, Decimal]] = None,
        target_strike: Optional[Union[float, Decimal]] = None,
    ) -> Dominion2ExitDecision:
        """Evaluate open position for early profit harvest or adverse loss salvage."""
        if contracts <= 0 or not book:
            return Dominion2ExitDecision(
                should_exit=False,
                exit_reason="NONE",
                exit_price=Decimal("0.0"),
                profit_pct=0.0,
                unrealized_pnl=Decimal("0.0"),
                rationale="No active position or orderbook to evaluate exit.",
            )

        best_bid = book.best_yes_bid if holding_side == OrderSide.YES else book.best_no_bid
        if best_bid is None or best_bid <= Decimal("0.01"):
            return Dominion2ExitDecision(
                should_exit=False,
                exit_reason="NO_BID",
                exit_price=Decimal("0.0"),
                profit_pct=0.0,
                unrealized_pnl=Decimal("0.0"),
                rationale=f"No viable exit bid on {holding_side.value.upper()} orderbook.",
            )

        cost_basis = entry_price * Decimal(str(contracts))
        gross_exit_value = best_bid * Decimal(str(contracts))
        exit_fee = self.fee_per_contract * Decimal(str(contracts))
        net_unrealized_pnl = gross_exit_value - cost_basis - exit_fee
        roi_pct = float(net_unrealized_pnl / cost_basis) if cost_basis > Decimal("0") else 0.0

        # Trigger 1: Tail Risk Profit Ceiling (Bid >= $0.90)
        if best_bid >= self.take_profit_price_threshold:
            return Dominion2ExitDecision(
                should_exit=True,
                exit_reason="TAKE_PROFIT_CEILING",
                exit_price=best_bid,
                profit_pct=roi_pct,
                unrealized_pnl=net_unrealized_pnl,
                rationale=f"Take Profit Ceiling: Bid reached ${best_bid:.2f} >= ${self.take_profit_price_threshold:.2f} (+{roi_pct*100:.1f}% ROI). Locking gains.",
            )

        # Trigger 2: Target ROI Harvest (>= 20% ROI)
        if roi_pct >= self.min_take_profit_roi and time_to_expiry_s <= 300.0:
            return Dominion2ExitDecision(
                should_exit=True,
                exit_reason="TAKE_PROFIT_ROI",
                exit_price=best_bid,
                profit_pct=roi_pct,
                unrealized_pnl=net_unrealized_pnl,
                rationale=f"Target ROI Harvest: Secured +{roi_pct*100:.1f}% ROI (PnL: +${net_unrealized_pnl:.2f}) with {time_to_expiry_s:.0f}s left.",
            )

        # Trigger 3: Adverse Loss Salvage (holding YES but price drops below Strike - $15 with < 90s left)
        if spot_price is not None and target_strike is not None:
            spot_diff = float(spot_price) - float(target_strike)
            if holding_side == OrderSide.YES and spot_diff < -15.0 and time_to_expiry_s <= 90.0 and best_bid >= Decimal("0.10"):
                return Dominion2ExitDecision(
                    should_exit=True,
                    exit_reason="ADVERSE_REVERSAL_SALVAGE",
                    exit_price=best_bid,
                    profit_pct=roi_pct,
                    unrealized_pnl=net_unrealized_pnl,
                    rationale=f"Adverse Salvage: YES position with spot -$15.00 OTM and {time_to_expiry_s:.0f}s left. Salvaging ${gross_exit_value:.2f} residual capital.",
                )

        return Dominion2ExitDecision(
            should_exit=False,
            exit_reason="HOLD",
            exit_price=best_bid,
            profit_pct=roi_pct,
            unrealized_pnl=net_unrealized_pnl,
            rationale=f"Holding position: Bid=${best_bid:.2f} (PnL: ${net_unrealized_pnl:+.2f}, {roi_pct*100:+.1f}% ROI).",
        )

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _make_wait_decision(
        self,
        time_to_expiry_s: float,
        spot_diff: float,
        vpin: float,
        rationale: str,
        max_price_veto: bool = False,
        anti_pin_veto: bool = False,
    ) -> Dominion2Decision:
        return Dominion2Decision(
            strategy_id=self.STRATEGY_ID,
            strategy_name=self.STRATEGY_NAME,
            active_playbook="None (WAIT Regime)",
            playbook_stage="none",
            p_up=0.33,
            p_down=0.33,
            p_wait=0.34,
            vpin=vpin,
            vpin_is_safe=vpin < self.vpin_toxic_threshold,
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
            time_to_expiry_s=time_to_expiry_s,
            spot_diff=spot_diff,
            max_price_veto=max_price_veto,
            anti_pin_veto=anti_pin_veto,
        )

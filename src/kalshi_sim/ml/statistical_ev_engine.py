"""Statistical & Mathematical Expected Value (EV) Engine for Kalshi Binary Contracts.

Translates directional probabilities from Stage 1 AI models into optimal, positive-EV
execution decisions using digital option payoff mathematics, statistical edge estimation,
and Fractional Kelly Criterion position sizing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from kalshi_sim.schemas import OrderSide

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExpectedValueResult:
    """Quantitative decision output from the Stage 2 Mathematical EV Engine."""
    has_positive_edge: bool
    recommended_side: Optional[OrderSide]
    ai_prob: float
    market_price: Decimal
    expected_value: Decimal
    net_expected_value: Decimal
    fee_per_contract: Decimal
    statistical_edge: float
    kelly_fraction: float
    recommended_contracts: int
    rationale: str


class StatisticalEVEngine:
    """Evaluates binary option pricing asymmetry and computes optimal EV executions."""

    def __init__(
        self,
        min_ev_threshold: Decimal = Decimal("0.02"),
        min_edge_pct: float = 0.02,
        fee_per_contract: Decimal = Decimal("0.01"),
        fractional_kelly: float = 0.25,
        max_portfolio_risk_pct: Decimal = Decimal("0.05"),
        vpin_safe_threshold: float = 0.40,
        vpin_warn_threshold: float = 0.55,
        vpin_toxic_threshold: float = 0.65,
    ) -> None:
        """Initialize the Stage 2 Mathematical Optimizer.

        Args:
            min_ev_threshold: Minimum positive expected dollar return per contract after fees (e.g. $0.02).
            min_edge_pct: Minimum statistical edge over market price (e.g. 0.02 = 2%).
            fee_per_contract: Real exchange taker fee per contract (e.g. $0.01 on Kalshi).
            fractional_kelly: Kelly scaling factor (0.25 = Quarter-Kelly for risk preservation).
            max_portfolio_risk_pct: Maximum fraction of total equity to allocate per trade.
            vpin_safe_threshold: VPIN below this is considered fully safe (no taper applied).
            vpin_warn_threshold: VPIN above this begins linear taper down toward zero.
            vpin_toxic_threshold: VPIN above this completely freezes new position sizing.
        """
        self.min_ev_threshold = min_ev_threshold
        self.min_edge_pct = min_edge_pct
        self.fee_per_contract = fee_per_contract
        self.fractional_kelly = fractional_kelly
        self.max_portfolio_risk_pct = max_portfolio_risk_pct
        self.vpin_safe_threshold = vpin_safe_threshold
        self.vpin_warn_threshold = vpin_warn_threshold
        self.vpin_toxic_threshold = vpin_toxic_threshold


    def _compute_vpin_taper(self, vpin: float) -> float:
        """Compute a continuous VPIN toxicity taper multiplier in [0.0, 1.0].

        The taper curve works in three zones:
        - Safe zone (VPIN ≤ safe_threshold):   multiplier = 1.0 (full Kelly sizing)
        - Warning zone (safe < VPIN ≤ toxic):  multiplier linearly decays from 1.0 → 0.0
        - Toxic zone (VPIN > toxic_threshold): multiplier = 0.0 (position sizing frozen)

        Returns:
            float: Multiplier to scale Kelly contracts by.
        """
        if vpin <= self.vpin_safe_threshold:
            return 1.0
        if vpin >= self.vpin_toxic_threshold:
            return 0.0
        # Linear interpolation in the warning band
        taper_range = self.vpin_toxic_threshold - self.vpin_safe_threshold
        return max(0.0, 1.0 - (vpin - self.vpin_safe_threshold) / taper_range)

    def compute_optimal_execution(
        self,
        prob_up: float,
        prob_down: float,
        best_yes_ask: Optional[Decimal],
        best_no_ask: Optional[Decimal],
        total_equity: Decimal,
        max_position_size: int = 50,
        vpin: float = 0.0,
        prob_wait: float = 0.0,
    ) -> ExpectedValueResult:
        """Calculate the most profitable side (YES vs NO) based on Expected Value and Kelly sizing.

        Args:
            prob_up: Estimated probability that contract settles YES (in [0, 1]).
            prob_down: Estimated probability that contract settles NO (in [0, 1]).
            best_yes_ask: Current lowest offer to buy YES contracts.
            best_no_ask: Current lowest offer to buy NO contracts (or 1 - best_yes_bid).
            total_equity: Total virtual or portfolio equity in USD.
            max_position_size: Hard cap on maximum contracts per trade.
            vpin: Current Volume-Synchronized Probability of Informed Trading score.
            prob_wait: Estimated probability of chop / stationary regime (Label 2: WAIT).

        Returns:
            ExpectedValueResult: Actionable execution decision with full math diagnostics.
        """
        # 1. Check if WAIT regime dominates (chop / no momentum)
        if prob_wait > 0.0 and prob_wait >= max(prob_up, prob_down):
            chosen_p = max(prob_up, prob_down)
            chosen_ask = best_yes_ask if best_yes_ask is not None else Decimal("0.50")
            return ExpectedValueResult(
                has_positive_edge=False,
                recommended_side=None,
                ai_prob=chosen_p,
                market_price=chosen_ask,
                expected_value=Decimal("0.00"),
                net_expected_value=Decimal("0.00"),
                fee_per_contract=self.fee_per_contract,
                statistical_edge=0.0,
                kelly_fraction=0.0,
                recommended_contracts=0,
                rationale=(
                    f"AI WAIT Regime: P(WAIT)={prob_wait:.1%} dominates directional signals "
                    f"[P(UP)={prob_up:.1%}, P(DOWN)={prob_down:.1%}]"
                ),
            )

        # 2. Normalize directional probabilities
        dir_sum = prob_up + prob_down
        if dir_sum <= 1e-6:
            p_yes = 0.50
            p_no = 0.50
        else:
            p_yes = prob_up / dir_sum
            p_no = prob_down / dir_sum

        # Ensure valid market quotes
        yes_ask = best_yes_ask if best_yes_ask is not None else Decimal("0.50")
        no_ask = best_no_ask if best_no_ask is not None else Decimal("0.50")

        # Clamp asks within valid binary boundaries [0.01, 0.99]
        yes_ask = max(Decimal("0.01"), min(Decimal("0.99"), yes_ask))
        no_ask = max(Decimal("0.01"), min(Decimal("0.99"), no_ask))

        # 3. Compute Gross and Net Expected Value (EV) for YES:
        # Gross EV: E[YES] = P(YES) - Ask_YES
        # Net EV (post-fee): E[YES_net] = P(YES) - Ask_YES - Fee
        p_yes_dec = Decimal(str(round(p_yes, 4)))
        ev_yes_gross = p_yes_dec * (Decimal("1.00") - yes_ask) - (Decimal("1.00") - p_yes_dec) * yes_ask
        ev_yes_net = ev_yes_gross - self.fee_per_contract
        edge_yes = p_yes - float(yes_ask) - float(self.fee_per_contract)

        # 4. Compute Gross and Net Expected Value (EV) for NO:
        p_no_dec = Decimal(str(round(p_no, 4)))
        ev_no_gross = p_no_dec * (Decimal("1.00") - no_ask) - (Decimal("1.00") - p_no_dec) * no_ask
        ev_no_net = ev_no_gross - self.fee_per_contract
        edge_no = p_no - float(no_ask) - float(self.fee_per_contract)

        # 5. Compare both sides and select the direction with higher Net EV
        if ev_yes_net >= ev_no_net:
            chosen_side = OrderSide.YES
            chosen_ev_gross = ev_yes_gross
            chosen_ev_net = ev_yes_net
            chosen_edge = edge_yes
            chosen_p = p_yes
            chosen_ask = yes_ask
        else:
            chosen_side = OrderSide.NO
            chosen_ev_gross = ev_no_gross
            chosen_ev_net = ev_no_net
            chosen_edge = edge_no
            chosen_p = p_no
            chosen_ask = no_ask

        # 6. Check Minimum Net EV & Net Edge Safety Thresholds (Friction Hardening)
        if chosen_ev_net < self.min_ev_threshold or chosen_edge < self.min_edge_pct:
            return ExpectedValueResult(
                has_positive_edge=False,
                recommended_side=None,
                ai_prob=chosen_p,
                market_price=chosen_ask,
                expected_value=chosen_ev_gross,
                net_expected_value=chosen_ev_net,
                fee_per_contract=self.fee_per_contract,
                statistical_edge=chosen_edge,
                kelly_fraction=0.0,
                recommended_contracts=0,
                rationale=(
                    f"Sub-threshold Net EV: Net EV=${chosen_ev_net:.3f} (< ${self.min_ev_threshold:.2f}) "
                    f"after ${self.fee_per_contract:.2f}/ct fee, or Edge={chosen_edge:.1%} (< {self.min_edge_pct:.1%})"
                ),
            )

        # 7. VPIN Toxicity Taper — continuously scale down allocation in warning zones
        vpin_taper = self._compute_vpin_taper(vpin)
        if vpin_taper <= 0.0:
            return ExpectedValueResult(
                has_positive_edge=False,
                recommended_side=None,
                ai_prob=chosen_p,
                market_price=chosen_ask,
                expected_value=chosen_ev_gross,
                net_expected_value=chosen_ev_net,
                fee_per_contract=self.fee_per_contract,
                statistical_edge=chosen_edge,
                kelly_fraction=0.0,
                recommended_contracts=0,
                rationale=(
                    f"VPIN TOXIC FREEZE: VPIN={vpin:.3f} ≥ {self.vpin_toxic_threshold:.2f} — "
                    f"position sizing frozen. Net EV=${chosen_ev_net:.3f}, Net Edge={chosen_edge:.1%}"
                ),
            )

        # 8. Compute Fractional Kelly Position Sizing on Effective Net Cost
        effective_cost = float(chosen_ask + self.fee_per_contract)
        b = max(0.01, (1.0 - effective_cost) / effective_cost)

        # Kelly fraction f* = (p * b - (1 - p)) / b
        full_kelly = max(0.0, (chosen_p * b - (1.0 - chosen_p)) / b)
        scaled_kelly = max(0.0, full_kelly * self.fractional_kelly)

        # 9. Apply VPIN taper to Kelly fraction (continuous risk reduction)
        tapered_kelly = scaled_kelly * vpin_taper

        # 10. Convert Kelly Fraction to Contract Sizing with Portfolio Guardrails
        max_capital_to_risk = total_equity * self.max_portfolio_risk_pct
        kelly_capital = total_equity * Decimal(str(round(tapered_kelly, 6)))
        allocated_capital = min(max_capital_to_risk, kelly_capital)

        unit_cost = chosen_ask + self.fee_per_contract
        contracts = int(allocated_capital / unit_cost) if unit_cost > 0 else 0
        contracts = max(1, min(max_position_size, contracts))

        # Build informative rationale with VPIN taper and fee visibility
        taper_note = ""
        if vpin_taper < 1.0:
            taper_note = f" | VPIN_taper={vpin_taper:.0%} (VPIN={vpin:.3f})"

        rationale = (
            f"Stage 2 Optimal EV: {chosen_side.value.upper()} | "
            f"AI_P={chosen_p:.1%} vs MktPrice=${chosen_ask:.2f} (Fee=${self.fee_per_contract:.2f}) | "
            f"Net EV=+${chosen_ev_net:.3f}/ct | Net Edge=+{chosen_edge:.1%} | "
            f"Kelly={scaled_kelly:.1%}→{tapered_kelly:.1%}{taper_note}"
        )

        return ExpectedValueResult(
            has_positive_edge=True,
            recommended_side=chosen_side,
            ai_prob=chosen_p,
            market_price=chosen_ask,
            expected_value=chosen_ev_gross,
            net_expected_value=chosen_ev_net,
            fee_per_contract=self.fee_per_contract,
            statistical_edge=chosen_edge,
            kelly_fraction=tapered_kelly,
            recommended_contracts=contracts,
            rationale=rationale,
        )

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
        fractional_kelly: float = 0.25,
        max_portfolio_risk_pct: Decimal = Decimal("0.05"),
    ) -> None:
        """Initialize the Stage 2 Mathematical Optimizer.

        Args:
            min_ev_threshold: Minimum positive expected dollar return per contract (e.g. $0.02).
            min_edge_pct: Minimum statistical edge over market price (e.g. 0.02 = 2%).
            fractional_kelly: Kelly scaling factor (0.25 = Quarter-Kelly for risk preservation).
            max_portfolio_risk_pct: Maximum fraction of total equity to allocate per trade.
        """
        self.min_ev_threshold = min_ev_threshold
        self.min_edge_pct = min_edge_pct
        self.fractional_kelly = fractional_kelly
        self.max_portfolio_risk_pct = max_portfolio_risk_pct

    def compute_optimal_execution(
        self,
        prob_up: float,
        prob_down: float,
        best_yes_ask: Optional[Decimal],
        best_no_ask: Optional[Decimal],
        total_equity: Decimal,
        max_position_size: int = 50,
    ) -> ExpectedValueResult:
        """Calculate the most profitable side (YES vs NO) based on Expected Value and Kelly sizing.

        Args:
            prob_up: Estimated probability that contract settles YES (in [0, 1]).
            prob_down: Estimated probability that contract settles NO (in [0, 1]).
            best_yes_ask: Current lowest offer to buy YES contracts.
            best_no_ask: Current lowest offer to buy NO contracts (or 1 - best_yes_bid).
            total_equity: Total virtual or portfolio equity in USD.
            max_position_size: Hard cap on maximum contracts per trade.

        Returns:
            ExpectedValueResult: Actionable execution decision with full math diagnostics.
        """
        # 1. Normalize directional probabilities
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

        # 2. Compute Expected Value (EV) for YES:
        # E[YES] = P(YES) * ($1.00 - Ask_YES) - (1 - P(YES)) * Ask_YES = P(YES) - Ask_YES
        p_yes_dec = Decimal(str(round(p_yes, 4)))
        ev_yes = p_yes_dec * (Decimal("1.00") - yes_ask) - (Decimal("1.00") - p_yes_dec) * yes_ask
        edge_yes = p_yes - float(yes_ask)

        # 3. Compute Expected Value (EV) for NO:
        # E[NO] = P(NO) * ($1.00 - Ask_NO) - (1 - P(NO)) * Ask_NO = P(NO) - Ask_NO
        p_no_dec = Decimal(str(round(p_no, 4)))
        ev_no = p_no_dec * (Decimal("1.00") - no_ask) - (Decimal("1.00") - p_no_dec) * no_ask
        edge_no = p_no - float(no_ask)

        # 4. Compare both sides and select the direction with higher positive EV
        if ev_yes >= ev_no:
            chosen_side = OrderSide.YES
            chosen_ev = ev_yes
            chosen_edge = edge_yes
            chosen_p = p_yes
            chosen_ask = yes_ask
        else:
            chosen_side = OrderSide.NO
            chosen_ev = ev_no
            chosen_edge = edge_no
            chosen_p = p_no
            chosen_ask = no_ask

        # 5. Check Minimum EV & Edge Safety Thresholds
        if chosen_ev < self.min_ev_threshold or chosen_edge < self.min_edge_pct:
            return ExpectedValueResult(
                has_positive_edge=False,
                recommended_side=None,
                ai_prob=chosen_p,
                market_price=chosen_ask,
                expected_value=chosen_ev,
                statistical_edge=chosen_edge,
                kelly_fraction=0.0,
                recommended_contracts=0,
                rationale=(
                    f"Sub-threshold EV: Max EV=${chosen_ev:.3f} (< ${self.min_ev_threshold:.2f}) "
                    f"or Edge={chosen_edge:.1%} (< {self.min_edge_pct:.1%})"
                ),
            )

        # 6. Compute Fractional Kelly Position Sizing
        # Payoff ratio b = (Payout - Cost) / Cost = (1 - Ask) / Ask
        ask_float = float(chosen_ask)
        b = (1.0 - ask_float) / ask_float
        
        # Kelly fraction f* = (p * b - (1 - p)) / b = (p - ask) / (1 - ask)
        full_kelly = (chosen_p * b - (1.0 - chosen_p)) / b
        scaled_kelly = max(0.0, full_kelly * self.fractional_kelly)

        # 7. Convert Kelly Fraction to Contract Sizing with Portfolio Guardrails
        max_capital_to_risk = total_equity * self.max_portfolio_risk_pct
        kelly_capital = total_equity * Decimal(str(round(scaled_kelly, 4)))
        allocated_capital = min(max_capital_to_risk, kelly_capital)

        contracts = int(allocated_capital / chosen_ask)
        contracts = max(1, min(max_position_size, contracts))

        rationale = (
            f"Stage 2 Optimal EV: {chosen_side.value.upper()} | "
            f"AI_P={chosen_p:.1%} vs MktPrice=${chosen_ask:.2f} | "
            f"EV=+${chosen_ev:.3f}/ct | Edge=+{chosen_edge:.1%} | Kelly={scaled_kelly:.1%}"
        )

        return ExpectedValueResult(
            has_positive_edge=True,
            recommended_side=chosen_side,
            ai_prob=chosen_p,
            market_price=chosen_ask,
            expected_value=chosen_ev,
            statistical_edge=chosen_edge,
            kelly_fraction=scaled_kelly,
            recommended_contracts=contracts,
            rationale=rationale,
        )

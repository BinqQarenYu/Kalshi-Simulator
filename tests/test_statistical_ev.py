"""Unit tests for Stage 2 Statistical EV and Kelly Engine."""

from decimal import Decimal
import pytest

from kalshi_sim.ml.statistical_ev_engine import StatisticalEVEngine, ExpectedValueResult
from kalshi_sim.schemas import OrderSide


def test_positive_ev_yes_trade():
    """When AI prob exceeds market YES ask, it recommends YES with positive EV."""
    engine = StatisticalEVEngine(min_ev_threshold=Decimal("0.02"), min_edge_pct=0.02)
    
    # AI predicts 75% YES, 25% NO. Market YES Ask is $0.50, NO Ask is $0.52.
    res = engine.compute_optimal_execution(
        prob_up=0.75,
        prob_down=0.25,
        best_yes_ask=Decimal("0.50"),
        best_no_ask=Decimal("0.52"),
        total_equity=Decimal("10000"),
        max_position_size=50,
    )

    assert res.has_positive_edge is True
    assert res.recommended_side == OrderSide.YES
    assert res.ai_prob == 0.75
    assert res.expected_value == Decimal("0.250")  # 0.75 - 0.50 = +$0.25
    assert res.statistical_edge == 0.25            # +25%
    assert res.recommended_contracts > 0


def test_odds_inversion_positive_ev_no_trade():
    """When YES is overpriced, buying NO yields positive EV even if AI is mildly bullish."""
    engine = StatisticalEVEngine(min_ev_threshold=Decimal("0.02"), min_edge_pct=0.02)

    # AI predicts 60% YES, 40% NO. But Market YES Ask is $0.85 (overpriced!), NO Ask is $0.15 (cheap!).
    # E[YES] = 0.60 - 0.85 = -$0.25 (LOSS)
    # E[NO]  = 0.40 - 0.15 = +$0.25 (PROFIT)
    res = engine.compute_optimal_execution(
        prob_up=0.60,
        prob_down=0.40,
        best_yes_ask=Decimal("0.85"),
        best_no_ask=Decimal("0.15"),
        total_equity=Decimal("10000"),
        max_position_size=50,
    )

    assert res.has_positive_edge is True
    assert res.recommended_side == OrderSide.NO
    assert res.ai_prob == 0.40
    assert res.expected_value == Decimal("0.250")  # 0.40 - 0.15 = +$0.25
    assert res.statistical_edge == 0.25
    assert res.recommended_contracts > 0


def test_subthreshold_ev_rejection():
    """When market price is efficient or edge is below threshold, no trade is recommended."""
    engine = StatisticalEVEngine(min_ev_threshold=Decimal("0.03"), min_edge_pct=0.05)

    # AI predicts 51% YES, 49% NO. Market YES Ask is $0.50. Edge is only +1% (sub-threshold).
    res = engine.compute_optimal_execution(
        prob_up=0.51,
        prob_down=0.49,
        best_yes_ask=Decimal("0.50"),
        best_no_ask=Decimal("0.51"),
        total_equity=Decimal("10000"),
        max_position_size=50,
    )

    assert res.has_positive_edge is False
    assert res.recommended_side is None
    assert res.recommended_contracts == 0


def test_fractional_kelly_sizing_caps():
    """Kelly position sizing respects hard maximum position size and equity constraints."""
    engine = StatisticalEVEngine(fractional_kelly=0.25, max_portfolio_risk_pct=Decimal("0.05"))

    res = engine.compute_optimal_execution(
        prob_up=0.90,
        prob_down=0.10,
        best_yes_ask=Decimal("0.50"),
        best_no_ask=Decimal("0.55"),
        total_equity=Decimal("10000"),
        max_position_size=30,
    )

    assert res.has_positive_edge is True
    # Max size was capped at 30
    assert res.recommended_contracts <= 30
    assert res.recommended_contracts >= 1

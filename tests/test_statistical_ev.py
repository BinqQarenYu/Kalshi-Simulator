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
    assert res.expected_value == Decimal("0.250")      # Gross EV: 0.75 - 0.50 = +$0.25
    assert res.net_expected_value == Decimal("0.240")  # Net EV: 0.25 - 0.01 = +$0.24
    assert res.statistical_edge == pytest.approx(0.24, 0.001)  # Net Edge: 24%
    assert res.fee_per_contract == Decimal("0.01")
    assert res.recommended_contracts > 0


def test_odds_inversion_positive_ev_no_trade():
    """When YES is overpriced, buying NO yields positive EV even if AI is mildly bullish."""
    engine = StatisticalEVEngine(min_ev_threshold=Decimal("0.02"), min_edge_pct=0.02)

    # AI predicts 60% YES, 40% NO. But Market YES Ask is $0.85 (overpriced!), NO Ask is $0.15 (cheap!).
    # E[YES] = 0.60 - 0.85 = -$0.25 (LOSS)
    # E[NO]  = 0.40 - 0.15 - 0.01 = +$0.24 (PROFIT)
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
    assert res.expected_value == Decimal("0.250")      # Gross: 0.40 - 0.15 = +$0.25
    assert res.net_expected_value == Decimal("0.240")  # Net: 0.25 - 0.01 = +$0.24
    assert res.statistical_edge == pytest.approx(0.24, 0.001)
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


def test_vpin_safe_zone_no_taper():
    """VPIN below safe threshold applies no taper — full Kelly sizing."""
    engine = StatisticalEVEngine()
    res = engine.compute_optimal_execution(
        prob_up=0.75,
        prob_down=0.25,
        best_yes_ask=Decimal("0.50"),
        best_no_ask=Decimal("0.52"),
        total_equity=Decimal("10000"),
        max_position_size=50,
        vpin=0.20,
    )
    assert res.has_positive_edge is True
    assert res.recommended_contracts > 0
    assert "VPIN_taper" not in res.rationale


def test_vpin_warning_zone_tapers_kelly():
    """VPIN in warning zone linearly tapers Kelly fraction and contracts."""
    engine = StatisticalEVEngine()

    # Safe baseline (vpin=0.0)
    res_safe = engine.compute_optimal_execution(
        prob_up=0.75, prob_down=0.25,
        best_yes_ask=Decimal("0.50"), best_no_ask=Decimal("0.52"),
        total_equity=Decimal("10000"), max_position_size=100,
        vpin=0.0,
    )

    # Tapered (vpin=0.52 is in the warning band [0.40, 0.65])
    res_tapered = engine.compute_optimal_execution(
        prob_up=0.75, prob_down=0.25,
        best_yes_ask=Decimal("0.50"), best_no_ask=Decimal("0.52"),
        total_equity=Decimal("10000"), max_position_size=100,
        vpin=0.52,
    )

    assert res_tapered.has_positive_edge is True
    assert res_tapered.kelly_fraction < res_safe.kelly_fraction
    assert res_tapered.recommended_contracts <= res_safe.recommended_contracts
    assert "VPIN_taper" in res_tapered.rationale


def test_vpin_toxic_freeze():
    """VPIN above toxic threshold completely freezes new positions."""
    engine = StatisticalEVEngine()
    res = engine.compute_optimal_execution(
        prob_up=0.90,
        prob_down=0.10,
        best_yes_ask=Decimal("0.50"),
        best_no_ask=Decimal("0.52"),
        total_equity=Decimal("10000"),
        max_position_size=50,
        vpin=0.70,
    )
    assert res.has_positive_edge is False
    assert res.recommended_contracts == 0
    assert "TOXIC FREEZE" in res.rationale


def test_vpin_taper_math_linearity():
    """The taper function produces correct linear interpolation."""
    engine = StatisticalEVEngine(
        vpin_safe_threshold=0.40,
        vpin_warn_threshold=0.55,
        vpin_toxic_threshold=0.65,
    )
    # Exactly at safe boundary
    assert engine._compute_vpin_taper(0.40) == 1.0
    # Exactly at toxic boundary
    assert engine._compute_vpin_taper(0.65) == 0.0
    # Midpoint of warning band: (0.40 + 0.65) / 2 = 0.525
    mid_taper = engine._compute_vpin_taper(0.525)
    assert 0.45 < mid_taper < 0.55  # Should be ~0.50


def test_wait_regime_dominance_rejection():
    """When P(WAIT) dominates directional signals, trade is rejected."""
    engine = StatisticalEVEngine(min_ev_threshold=Decimal("0.02"), min_edge_pct=0.02)
    res = engine.compute_optimal_execution(
        prob_up=0.25,
        prob_down=0.15,
        best_yes_ask=Decimal("0.50"),
        best_no_ask=Decimal("0.50"),
        total_equity=Decimal("10000"),
        max_position_size=50,
        prob_wait=0.60,  # WAIT dominates (60%)
    )
    assert res.has_positive_edge is False
    assert res.recommended_side is None
    assert res.recommended_contracts == 0
    assert "AI WAIT Regime" in res.rationale


def test_exchange_fee_erosion_and_friction_hardening():
    """Exchange fee erodes small gross edges, rejecting trades where net EV is sub-threshold."""
    # Engine requires min net EV of $0.02, with $0.015 exchange fee per contract
    engine = StatisticalEVEngine(
        min_ev_threshold=Decimal("0.02"),
        min_edge_pct=0.02,
        fee_per_contract=Decimal("0.015"),
    )

    # Gross Edge is +$0.025 (P=0.525 vs Ask=$0.50)
    # Net Edge after $0.015 fee = 0.525 - 0.50 - 0.015 = +$0.010 (< $0.02 threshold)
    res = engine.compute_optimal_execution(
        prob_up=0.525,
        prob_down=0.475,
        best_yes_ask=Decimal("0.50"),
        best_no_ask=Decimal("0.50"),
        total_equity=Decimal("10000"),
        max_position_size=50,
    )

    assert res.has_positive_edge is False
    assert res.recommended_side is None
    assert "Sub-threshold Net EV" in res.rationale
    assert res.net_expected_value == Decimal("0.010")




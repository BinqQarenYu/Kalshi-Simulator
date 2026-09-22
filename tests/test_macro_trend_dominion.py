"""Unit tests for Bot 3: Macro Trend Dominion Strategy & Learning Engine."""

from decimal import Decimal
import pytest

from app_1_machine_engine.ml.macro_trend_dominion.bot import MacroTrendDominionBot
from app_1_machine_engine.ml.macro_trend_dominion.learning_engine import MacroDominionLearningEngine
from app_1_machine_engine.ml.quolas_core.regime_types import MarketRegime


class MockHMMBrain:
    """Mock HMM Brain for testing regime vetoes."""
    def __init__(self, regime: MarketRegime = MarketRegime.STABLE_RANGE) -> None:
        self.current_regime = regime


def test_bot_initialization_and_dial_introspection():
    """Verify that Bot 3 exposes all 9 strategy dials with correct default values."""
    bot = MacroTrendDominionBot(
        limit_price_cents=45,
        min_confidence_pct=70.0,
        volatility_moat_dollars=Decimal("25.00"),
    )
    params = bot.get_parameters()
    assert params["strategy_id"] == "macro_trend_dominion"
    assert params["limit_price_cents"] == 45
    assert params["min_confidence_pct"] == 70.0
    assert params["volatility_moat_dollars"] == 25.0
    assert params["max_contracts"] == 1
    assert "shrinkage_factor" in params
    assert "active_price_cap_cents" in params


def test_parameter_updates():
    """Verify that updating strategy dials respects boundary clamps."""
    bot = MacroTrendDominionBot()
    updated = bot.update_parameters(
        limit_price_cents=65,
        min_confidence_pct=75.0,
        volatility_moat_dollars=Decimal("35.00"),
        hmm_risk_off_veto=False,
    )
    assert updated["limit_price_cents"] == 65
    assert updated["min_confidence_pct"] == 75.0
    assert updated["volatility_moat_dollars"] == 35.0
    assert updated["hmm_risk_off_veto"] is False


def test_volatility_moat_veto():
    """If spot price is too close to strike, bot must output DONT to avoid random chop."""
    bot = MacroTrendDominionBot(volatility_moat_dollars=Decimal("30.00"))
    # Spot is 78010, Target strike is 78000 (diff = +$10 < $30 moat)
    dec = bot.evaluate(
        spot_price=78010.0,
        target_strike=78000.0,
        time_to_expiry_s=500.0,
        quolas_inference={"signal": "UP", "confidence": 0.85},
        kalshi_inference={"signal": "UP", "confidence": 0.80},
    )
    assert dec.call == "DONT"
    assert "Proximity trap" in dec.rationale
    assert dec.recommended_contracts == 0


def test_hmm_risk_off_veto():
    """When HMM detects RISK_OFF, all trading must be halted and resting orders cancelled."""
    hmm = MockHMMBrain(regime=MarketRegime.RISK_OFF)
    bot = MacroTrendDominionBot(hmm_brain=hmm, hmm_risk_off_veto=True)
    dec = bot.evaluate(
        spot_price=78100.0,
        target_strike=78000.0,
        time_to_expiry_s=500.0,
        quolas_inference={"signal": "UP", "confidence": 0.85},
    )
    assert dec.call == "DONT"
    assert "RISK_OFF" in dec.rationale
    assert dec.cancel_resting_orders is True


def test_bull_trend_consensus_yes_authorization():
    """Macro Bull + Spot UP + CLOB UP should authorize BUY YES at resting limit."""
    hmm = MockHMMBrain(regime=MarketRegime.VOL_EXPANSION)
    bot = MacroTrendDominionBot(
        limit_price_cents=52,
        min_confidence_pct=65.0,
        min_ev_dollars=Decimal("0.02"),
        volatility_moat_dollars=Decimal("20.00"),
        hmm_brain=hmm,
    )
    # Spot 78050, Target 78000 (diff = +$50 > $20 moat -> BULL)
    dec = bot.evaluate(
        spot_price=78050.0,
        target_strike=78000.0,
        time_to_expiry_s=600.0,
        quolas_inference={"signal": "UP", "confidence": 0.80},
        kalshi_inference={"signal": "UP", "confidence": 0.75},
    )
    assert dec.call == "YES"
    assert dec.side == "yes"
    assert dec.confidence_pct >= 65.0
    assert dec.limit_price == Decimal("0.52")
    assert dec.expected_value > Decimal("0.00")
    assert dec.recommended_contracts == 1
    assert dec.is_ev_positive is True


def test_bear_trend_consensus_no_authorization():
    """Macro Bear + Spot DOWN + CLOB DOWN should authorize BUY NO at resting limit."""
    bot = MacroTrendDominionBot(
        limit_price_cents=45,
        min_confidence_pct=60.0,
        volatility_moat_dollars=Decimal("20.00"),
    )
    # Spot 77920, Target 78000 (diff = -$80 -> BEAR)
    dec = bot.evaluate(
        spot_price=77920.0,
        target_strike=78000.0,
        time_to_expiry_s=600.0,
        quolas_inference={"signal": "DOWN", "confidence": 0.82},
        kalshi_inference={"signal": "DOWN", "confidence": 0.78},
    )
    assert dec.call == "NO"
    assert dec.side == "no"
    assert dec.confidence_pct >= 60.0
    assert dec.limit_price == Decimal("0.45")
    assert dec.recommended_contracts == 1


def test_ev_gate_negative_ev_rejection():
    """If limit price is 85c but model confidence is only 70%, EV is negative and trade is rejected."""
    bot = MacroTrendDominionBot(
        limit_price_cents=85,
        min_confidence_pct=60.0,
        min_ev_dollars=Decimal("0.03"),
        volatility_moat_dollars=Decimal("20.00"),
    )
    # Spot 78060, Target 78000 (diff = +$60 -> BULL)
    # Raw prob ~ 70% -> EV = 0.70 - 0.85 - 0.01 = -0.16 < +0.03
    dec = bot.evaluate(
        spot_price=78060.0,
        target_strike=78000.0,
        time_to_expiry_s=600.0,
        quolas_inference={"signal": "UP", "confidence": 0.70},
        kalshi_inference={"signal": "UP", "confidence": 0.70},
    )
    assert dec.call == "DONT"
    assert "EV Gate Veto" in dec.rationale
    assert dec.recommended_contracts == 0


def test_learning_engine_shrinkage_and_decile_pruning():
    """Test that the Learning Engine shrinks overconfidence and prunes expensive price deciles upon losses."""
    engine = MacroDominionLearningEngine(min_samples_for_adaptation=3, adaptation_rate=0.40)

    # 1. Simulate 3 high-priced losses (bought at 70c, all lost)
    for i in range(3):
        engine.record_cycle_result(
            cycle_id=f"CYC-{i}",
            ticker="KXBTC15M",
            call="YES",
            predicted_prob=0.80,
            fill_price=Decimal("0.70"),
            outcome="loss",
            pnl=Decimal("-0.70"),
            spot_diff_at_entry=35.0,
            spot_diff_at_settle=-5.0,
            macro_trend="BULL",
            hmm_regime="VOL_EXPANSION",
            execution_mode="paper",
        )

    diag = engine.get_diagnostics()
    assert diag["losses"] == 3
    assert diag["win_rate_pct"] == 0.0
    # Shrinkage factor must be significantly less than 1.0 (damped overconfidence)
    assert diag["shrinkage_factor"] < 1.0
    # Active price cap must be pruned from 89c down to 55c
    assert diag["active_price_cap"] == 0.55
    assert diag["mistake_breakdown"]["NEGATIVE_EV_HIGH_PRICE"] == 3

    # Calibrating an 80% raw probability should yield a lower calibrated probability
    cal_prob, factor = engine.calibrate_probability(0.80)
    assert cal_prob < 0.80
    assert pytest.approx(factor, rel=1e-3) == diag["shrinkage_factor"]

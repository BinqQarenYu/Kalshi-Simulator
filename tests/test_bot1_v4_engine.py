"""Unit tests for Bot 1 Version 4 (Multi-Turnover Domination Engine)."""

from decimal import Decimal
import pytest
from kalshi_sim.ml.bot1_v4_engine import Bot1V4DominationEngine
from kalshi_sim.schemas import L2BookState


def test_bot1_v4_ev_coupling() -> None:
    engine = Bot1V4DominationEngine(
        min_ev_hurdle_dollars=Decimal("0.02"),
        discount_limit_price=Decimal("0.52"),
    )
    req_win = engine.compute_required_win_probability(Decimal("0.52"))
    assert abs(req_win - 0.54) < 1e-4


def test_bot1_v4_max_turnover_cap() -> None:
    engine = Bot1V4DominationEngine(max_turnover_per_event=3)
    l2 = L2BookState("KXBTC15M-TEST")
    
    # Record 3 turnovers
    cycle_id = "CYCLE_TEST_101"
    engine.reset_cycle_turnover(cycle_id)
    assert engine.get_completed_turnovers(cycle_id) == 0

    engine.record_completed_turnover(cycle_id)
    engine.record_completed_turnover(cycle_id)
    engine.record_completed_turnover(cycle_id)
    assert engine.get_completed_turnovers(cycle_id) == 3

    # Opportunity evaluation should hit max turnover cap
    decision = engine.evaluate_market_opportunity(
        spot_price=85000.0,
        target_strike=84900.0,
        time_to_expiry_s=300.0,
        l2_book=l2,
        cycle_id=cycle_id,
    )
    assert decision.recommended_side == "wait"
    assert "Max Turnover Cap Hit" in decision.rationale


class MockONNXEngine:
    """Mock ONNX engine for deterministic testing."""

    def __init__(
        self,
        signal: str = "LONG",
        prob_long: float = 0.85,
        prob_short: float = 0.05,
        prob_wait: float = 0.10,
        confidence: float = 0.85,
        vpin_score: float = 0.25,
        vpin_veto: bool = False,
        raise_exc: bool = False,
    ) -> None:
        self.signal = signal
        self.prob_long = prob_long
        self.prob_short = prob_short
        self.prob_wait = prob_wait
        self.confidence = confidence
        self.vpin_score = vpin_score
        self.vpin_veto = vpin_veto
        self.raise_exc = raise_exc

    def process_orderbook_tick(self, book: L2BookState) -> dict:
        if self.raise_exc:
            raise RuntimeError("Mock ONNX execution failure")
        return {
            "signal": self.signal,
            "prob_long": self.prob_long,
            "prob_short": self.prob_short,
            "prob_wait": self.prob_wait,
            "confidence": self.confidence,
            "vpin_score": self.vpin_score,
            "vpin_veto": self.vpin_veto,
        }


def test_bot1_v4_bayesian_onnx_fusion() -> None:
    mock_onnx = MockONNXEngine(signal="LONG", prob_long=0.90, prob_short=0.05, prob_wait=0.05)
    engine = Bot1V4DominationEngine(
        onnx_engine=mock_onnx,
        fusion_weight_micro=0.40,
        discount_limit_price=Decimal("0.55"),
    )
    l2 = L2BookState("KXBTC15M-TEST")

    # With spot_diff = 0.0 (macro erf gives 0.50), the ONNX bullish signal should lift p_up
    p_up, p_down, p_wait, telemetry = engine.compute_fused_probabilities(
        spot_diff=0.0,
        time_to_expiry_s=600.0,
        l2_book=l2,
    )
    assert p_up > 0.50
    assert p_down < 0.50
    assert telemetry is not None
    assert telemetry["signal"] == "LONG"

    # Evaluate opportunity
    decision = engine.evaluate_market_opportunity(
        spot_price=85000.0,
        target_strike=84950.0,  # +$50 moat
        time_to_expiry_s=600.0,
        l2_book=l2,
        cycle_id="FUSION_CYCLE_1",
    )
    assert decision.fused_source == "bayesian_fusion"
    assert decision.onnx_signal == "LONG"
    assert decision.onnx_confidence == 0.85
    assert decision.recommended_side == "yes"


def test_bot1_v4_onnx_graceful_fallback() -> None:
    # Test with exception raising ONNX engine
    broken_onnx = MockONNXEngine(raise_exc=True)
    engine = Bot1V4DominationEngine(onnx_engine=broken_onnx)
    l2 = L2BookState("KXBTC15M-TEST")

    p_up, p_down, p_wait, telemetry = engine.compute_fused_probabilities(
        spot_diff=30.0,
        time_to_expiry_s=300.0,
        l2_book=l2,
    )
    # Should cleanly fall back to macro erf calculation without crashing
    assert p_up > 0.50
    assert p_down < 0.50
    assert telemetry is None

    decision = engine.evaluate_market_opportunity(
        spot_price=85030.0,
        target_strike=85000.0,
        time_to_expiry_s=300.0,
        l2_book=l2,
        cycle_id="FALLBACK_CYCLE_1",
    )
    assert decision.fused_source == "macro_erf"


def test_bot1_v4_strict_55c_price_cap() -> None:
    # Even if win probability is 99.9%, limit price must never exceed $0.55
    engine = Bot1V4DominationEngine(max_entry_price=Decimal("0.85"))  # deliberately set high to test clamp
    clamped_price = engine.compute_dynamic_limit_price(win_prob=0.999)
    assert clamped_price <= Decimal("0.55")


def test_bot1_v4_opening_quarantine_veto() -> None:
    engine = Bot1V4DominationEngine(opening_quarantine_seconds=90.0)
    l2 = L2BookState("KXBTC15M-TEST")
    decision = engine.evaluate_market_opportunity(
        spot_price=85050.0,
        target_strike=85000.0,
        time_to_expiry_s=850.0,  # 50s into cycle (< 90s quarantine)
        l2_book=l2,
    )
    assert decision.recommended_side == "wait"
    assert "Opening Cycle Quarantine Active" in decision.rationale


def test_bot1_v4_dynamic_proximity_moat_veto() -> None:
    engine = Bot1V4DominationEngine(opening_quarantine_seconds=90.0)
    l2 = L2BookState("KXBTC15M-TEST")
    decision = engine.evaluate_market_opportunity(
        spot_price=85005.0,
        target_strike=85000.0,
        time_to_expiry_s=500.0,  # Outside quarantine, but diff ($5) < dynamic moat (~$28+)
        l2_book=l2,
    )
    assert decision.recommended_side == "wait"
    assert "Proximity Moat Veto" in decision.rationale


def test_bot1_v4_wide_clob_spread_veto() -> None:
    engine = Bot1V4DominationEngine(opening_quarantine_seconds=90.0, max_clob_spread_cents=0.05)
    l2 = L2BookState("KXBTC15M-TEST")
    l2.yes_book = {Decimal("0.50"): Decimal("100")}
    l2.no_book = {Decimal("0.40"): Decimal("100")}  # YES ask = 0.60, YES bid = 0.50 -> spread 0.10 > 0.05
    decision = engine.evaluate_market_opportunity(
        spot_price=85100.0,
        target_strike=85000.0,
        time_to_expiry_s=500.0,
        l2_book=l2,
    )
    assert decision.recommended_side == "wait"
    assert "Wide CLOB Spread Veto" in decision.rationale


def test_bot1_v4_onnx_vpin_veto() -> None:
    toxic_onnx = MockONNXEngine(vpin_score=0.85, vpin_veto=True)
    engine = Bot1V4DominationEngine(onnx_engine=toxic_onnx, vpin_toxic_threshold=0.60)
    l2 = L2BookState("KXBTC15M-TEST")

    decision = engine.evaluate_market_opportunity(
        spot_price=85100.0,
        target_strike=85000.0,
        time_to_expiry_s=300.0,
        l2_book=l2,
        cycle_id="TOXIC_CYCLE_1",
    )
    assert decision.recommended_side == "wait"
    assert decision.vpin_is_safe is False
    assert decision.active_playbook == "vpin_toxicity_veto"


def test_dataset_builder_turnover_sniper_mode() -> None:
    from kalshi_sim.ml.dataset_builder import DatasetBuilder, TickFrame
    import numpy as np

    builder = DatasetBuilder(
        horizon_steps=1,
        horizon_seconds=0.0,
        price_diff_threshold=0.02,
        labeling_mode="turnover_sniper",
        turnover_roi_target=0.40,  # requires diff >= 0.02 * 1.40 = 0.028
    )

    feat = np.zeros(28, dtype=np.float32)
    # Frame 1: mid = 0.55
    # Frame 2: mid = 0.57 (diff = +0.02, below 0.028 -> WAIT)
    # Frame 3: mid = 0.60 (diff = +0.03 relative to frame 2 -> UP)
    f1 = TickFrame(timestamp=1.0, ticker="KXBTC15M", features=feat, mid_price=0.55)
    f2 = TickFrame(timestamp=2.0, ticker="KXBTC15M", features=feat, mid_price=0.57)
    f3 = TickFrame(timestamp=3.0, ticker="KXBTC15M", features=feat, mid_price=0.60)

    X, y = builder.build_dataset_from_frames([f1, f2, f3], max_wait_ratio=None)
    assert len(y) == 2
    # Pair (f1, f2): diff = 0.02 < 0.028 -> WAIT (2)
    assert y[0] == 2
    # Pair (f2, f3): diff = 0.03 >= 0.028 -> UP (0)
    assert y[1] == 0


def test_bot1_v4_frozen_sensor_veto() -> None:
    """Verify Tier 1 Hard Veto triggers when order book sensor is frozen (np.var == 0.0)."""
    frozen_onnx = MockONNXEngine(
        signal="WAIT",
        prob_long=0.0005,
        prob_short=0.0005,
        prob_wait=0.999,
        confidence=0.999,
    )
    # Add veto_reason attribute simulation
    orig_process = frozen_onnx.process_orderbook_tick
    frozen_onnx.process_orderbook_tick = lambda book: {
        **orig_process(book),
        "veto_reason": "FROZEN_SENSOR_ZERO_VARIANCE",
    }

    engine = Bot1V4DominationEngine(onnx_engine=frozen_onnx)
    l2 = L2BookState("KXBTC15M-TEST")

    decision = engine.evaluate_market_opportunity(
        spot_price=85020.0,
        target_strike=85000.0,
        time_to_expiry_s=300.0,
        l2_book=l2,
    )
    assert decision.recommended_side == "wait"
    assert decision.active_playbook == "frozen_sensor_veto"
    assert "Frozen Sensor Veto" in decision.rationale


def test_bot1_v4_warrior2_chop_harvester_pricing() -> None:
    """Verify Warrior 2 (Chop Harvester) executes asymmetric deep discount ($0.38 - $0.42)."""
    engine = Bot1V4DominationEngine()
    l2 = L2BookState("KXBTC15M-TEST")

    # Feed 10 calm ticks (range = $2, std < $1) to establish calm state
    t0 = 1000.0
    for i in range(10):
        engine.detect_market_regime(
            spot_price=85000.0 + (i % 2),
            time_to_expiry_s=300.0,
            cycle_id="CHOP_CYCLE_1",
            spot_velocity_3s=0.5,
            now_mono=t0 + i,
        )

    # Allow 45s hysteresis calm duration to switch to CHOP
    regime, reason = engine.detect_market_regime(
        spot_price=85001.0,
        time_to_expiry_s=300.0,
        cycle_id="CHOP_CYCLE_1",
        spot_velocity_3s=0.5,
        now_mono=t0 + 60.0,
    )
    assert regime == "CHOP"

    # Evaluate inside sweet spot (T=300s, spot=$85008, strike=$85000)
    decision = engine.evaluate_market_opportunity(
        spot_price=85008.0,
        target_strike=85000.0,
        time_to_expiry_s=300.0,
        l2_book=l2,
        cycle_id="CHOP_CYCLE_1",
        spot_velocity_3s=0.5,
    )
    assert decision.regime == "CHOP"
    assert decision.active_playbook == "playbook4_chop_harvester"
    assert decision.recommended_side == "yes"
    # Price must be clamped between $0.38 and $0.42
    assert 0.38 <= decision.limit_price <= 0.42


def test_bot1_v4_warrior2_timing_gates() -> None:
    """Verify Warrior 2 timing sweet spot gates: 150s <= T <= 450s."""
    engine = Bot1V4DominationEngine()
    l2 = L2BookState("KXBTC15M-TEST")
    engine._current_regime = "CHOP"  # Force CHOP

    # 1. Early noise quarantine (T = 500s > 450s)
    d_early = engine.evaluate_market_opportunity(
        spot_price=85005.0,
        target_strike=85000.0,
        time_to_expiry_s=500.0,
        l2_book=l2,
        cycle_id="GATE_CYCLE_1",
    )
    assert d_early.recommended_side == "wait"
    assert d_early.active_playbook == "chop_early_noise_quarantine"

    # 2. Late cycle freeze (T = 100s < 150s)
    d_late = engine.evaluate_market_opportunity(
        spot_price=85005.0,
        target_strike=85000.0,
        time_to_expiry_s=100.0,
        l2_book=l2,
        cycle_id="GATE_CYCLE_1",
    )
    assert d_late.recommended_side == "wait"
    assert d_late.active_playbook == "chop_late_cycle_freeze"


def test_bot1_v4_storm_onnx_wait_consensus() -> None:
    """Verify Warrior 1 respects ONNX WAIT partner consensus unless massive macro edge."""
    mock_onnx = MockONNXEngine(signal="WAIT", confidence=0.75, prob_wait=0.75)
    engine = Bot1V4DominationEngine(onnx_engine=mock_onnx)
    l2 = L2BookState("KXBTC15M-TEST")
    engine._current_regime = "STORM"

    # With moderate spot diff ($30 < $45 threshold), ONNX WAIT veto must hold
    decision = engine.evaluate_market_opportunity(
        spot_price=85030.0,
        target_strike=85000.0,
        time_to_expiry_s=500.0,
        l2_book=l2,
        cycle_id="CONSENSUS_CYCLE_1",
    )
    assert decision.recommended_side == "wait"
    assert decision.active_playbook == "onnx_wait_veto"
    assert "ONNX Consensus Veto" in decision.rationale


def test_bot1_v4_phase_transition_volcano_and_cooldown() -> None:
    """Verify dynamic phase transitions between Chop and Storm with 45s hysteresis."""
    engine = Bot1V4DominationEngine(hysteresis_cooldown_seconds=45.0)

    # 1. Transition into CHOP after calm
    t = 2000.0
    for i in range(10):
        engine.detect_market_regime(
            spot_price=85000.0 + (i % 2),
            time_to_expiry_s=300.0,
            cycle_id="TRANS_CYCLE_1",
            spot_velocity_3s=0.2,
            now_mono=t + i,
        )
    regime, _ = engine.detect_market_regime(
        spot_price=85000.0,
        time_to_expiry_s=300.0,
        cycle_id="TRANS_CYCLE_1",
        spot_velocity_3s=0.2,
        now_mono=t + 55.0,
    )
    assert regime == "CHOP"

    # 2. Fast-Path Volcano Trigger (velocity spike >= 15 $/s)
    regime, reason = engine.detect_market_regime(
        spot_price=85025.0,
        time_to_expiry_s=300.0,
        cycle_id="TRANS_CYCLE_1",
        spot_velocity_3s=18.5,
        now_mono=t + 60.0,
    )
    assert regime == "STORM"
    assert "Volcano Breakout" in reason

    # 3. Feed calm ticks at 85025 past the 60s rolling vol window (t + 130.0)
    for i in range(5):
        engine.detect_market_regime(
            spot_price=85025.0,
            time_to_expiry_s=300.0,
            cycle_id="TRANS_CYCLE_1",
            spot_velocity_3s=0.1,
            now_mono=t + 125.0 + i,
        )

    # 4. At t + 150.0 (21s since calm established at t + 129), inside 45s hysteresis -> still STORM
    regime, reason = engine.detect_market_regime(
        spot_price=85025.0,
        time_to_expiry_s=300.0,
        cycle_id="TRANS_CYCLE_1",
        spot_velocity_3s=0.1,
        now_mono=t + 150.0,
    )
    assert regime == "STORM"
    assert "cooling down" in reason

    # 5. Sustained calm passes 45s (t + 180.0 is 51s of calm) -> transitions back to CHOP
    regime, reason = engine.detect_market_regime(
        spot_price=85025.0,
        time_to_expiry_s=300.0,
        cycle_id="TRANS_CYCLE_1",
        spot_velocity_3s=0.1,
        now_mono=t + 180.0,
    )
    assert regime == "CHOP"
    assert "Cooldown Hysteresis Passed" in reason




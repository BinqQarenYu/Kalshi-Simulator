import pytest
from decimal import Decimal
from kalshi_sim.ml.bot1_v4_engine import Bot1V4DominationEngine
from kalshi_sim.ml.experience_buffer import ContinuousExperienceBuffer, CycleExperience


def test_experience_buffer_wiring():
    buf = ContinuousExperienceBuffer()
    engine = Bot1V4DominationEngine(experience_buffer=buf)
    
    assert engine.experience_buffer is buf
    assert engine.lead_deer_brain.experience_buffer is buf

    # Record settled cycles to verify recalibration
    exp1 = CycleExperience(
        ticker="KXBTC15M-TEST-01",
        cycle_id="c1",
        timestamp_utc="2026-10-12T00:00:00Z",
        strike_price=65000.0,
        settlement_spot=65100.0,
        spot_diff=100.0,
        bot_side="yes",
        entry_price=0.48,
        contracts=1,
        predicted_prob=0.85,
        outcome="win",
        net_pnl=0.52,
        fees=0.01,
        execution_mode="live",
    )
    buf.record_settled_cycle(exp1)

    assert len(buf.experiences) >= 1
    assert buf.brier_score >= 0.0

    # Probability calibration check
    raw_prob = 0.80
    calibrated = buf.calibrate_probability(raw_prob)
    assert 0.0 < calibrated < 1.0

    p_up, p_down, _, _ = engine.compute_fused_probabilities(spot_diff=100.0, time_to_expiry_s=300.0)
    assert 0.0 < p_up < 1.0
    assert 0.0 < p_down < 1.0

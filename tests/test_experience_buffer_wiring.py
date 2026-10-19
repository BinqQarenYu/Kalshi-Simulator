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


def test_golden_quadrant_and_pinnacle_reinforcement(tmp_path):
    buf = ContinuousExperienceBuffer(history_file=tmp_path / "test_exp.json", asset="ETH")
    
    # Record 4 consecutive winning cycles in MID_WIDE quadrant at $0.42 entry price
    for i in range(4):
        exp = CycleExperience(
            ticker=f"KXETH15M-PINNACLE-{i}",
            cycle_id=f"pinnacle_{i}",
            timestamp_utc="2026-10-19T00:00:00Z",
            strike_price=2600.0,
            settlement_spot=2610.0,
            spot_diff=10.0,  # WIDE (>5.0 threshold)
            bot_side="yes",
            entry_price=0.42,
            contracts=1,
            predicted_prob=0.82,
            outcome="win",
            net_pnl=0.58,
            fees=0.0,
            execution_mode="live",
            time_to_expiry_s=420.0,  # MID (180-600s)
            macro_regime="STORM",
        )
        buf.record_settled_cycle(exp)

    # Verify Golden Quadrant is identified and reinforced
    assert "MID_WIDE" in buf.golden_regime_quadrants
    assert buf.is_quadrant_golden(time_to_expiry_s=420.0, spot_diff=10.0) is True
    assert 40 in buf.golden_price_corridors  # 0.42 decile bucket 4 -> 40c

    # Check summary representation
    summary = buf.get_recent_summary(n=5)
    assert "MID_WIDE" in summary["golden_quadrants"]
    assert len(summary["pinnacle_exemplars"]) >= 4
    assert summary["pinnacle_exemplars"][-1]["entry_cents"] == 42
    assert summary["pinnacle_exemplars"][-1]["gain_dollars"] == 0.58


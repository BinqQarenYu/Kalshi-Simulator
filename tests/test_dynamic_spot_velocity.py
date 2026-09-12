"""Unit tests for Dynamic Spot Velocity Front-Run & 4-Regime Fading Mathematics."""

import math
from decimal import Decimal
import pytest

from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
from kalshi_sim.schemas import CryptoAsset, L2BookState, OrderSide


def test_expiration_quarantine_locks_out_sells() -> None:
    """Regime 4: At T <= 15s, front-run sells are strictly quarantined to protect $1.00 settlement."""
    bot = ThreeStepDominationBot(
        enable_dynamic_spot_velocity=True,
        twap_fading_quarantine_seconds=15.0,
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.88"): Decimal("200")}
    book.no_book = {Decimal("0.11"): Decimal("100")}

    # Massive adverse drop (-$50 in 3s) at T=10s
    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.52"),
        size=1,
        book=book,
        time_to_expiry_s=10.0,
        spot_price=85020.0,
        target_strike=85000.0,
        twap_60s=85030.0,
        spot_velocity_3s=-50.0,
    )

    assert decision.should_exit is False
    assert decision.exit_reason == "HOLD"


def test_silas_twap_gravity_vetoes_false_orderbook_panic() -> None:
    """Regime 3: At T=20s with TWAP margin +$30, small spot drop (-$6) cannot move settlement TWAP.

    v_crit = (2 * 30 * 60) / (20^2) = 9.0 $/s.
    Observed drop is -$6 in 3s = 2.0 $/s < 9.0 $/s.
    Exit is strictly VETOED by Silas TWAP Gravity.
    """
    bot = ThreeStepDominationBot(
        enable_dynamic_spot_velocity=True,
        twap_fading_window_seconds=60.0,
        twap_fading_quarantine_seconds=15.0,
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.86"): Decimal("150")}
    book.no_book = {Decimal("0.12"): Decimal("100")}

    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.80"),
        size=1,
        book=book,
        time_to_expiry_s=20.0,
        spot_price=85015.0,
        target_strike=85000.0,
        twap_60s=85030.0,
        spot_velocity_3s=-6.0,
    )

    assert decision.should_exit is False
    assert decision.exit_reason == "HOLD"


def test_silas_twap_gravity_fires_on_catastrophic_breach() -> None:
    """Regime 3: At T=30s with TWAP margin +$20, a severe drop (-$24 in 3s = 8.0 $/s) exceeds v_crit (2.67 $/s).

    v_crit = (2 * 20 * 60) / (30^2) = 2.67 $/s.
    8.0 $/s >= 2.67 $/s -> Front-run fires to save capital.
    """
    bot = ThreeStepDominationBot(
        enable_dynamic_spot_velocity=True,
        twap_fading_window_seconds=60.0,
        twap_fading_quarantine_seconds=15.0,
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.88"): Decimal("150")}
    book.no_book = {Decimal("0.11"): Decimal("100")}

    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.50"),
        size=1,
        book=book,
        time_to_expiry_s=30.0,
        spot_price=85010.0,
        target_strike=85000.0,
        twap_60s=85020.0,
        spot_velocity_3s=-24.0,
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "SPOT_DELTA_FRONT_RUN"
    assert decision.exit_price == Decimal("0.88")
    assert "TWAP BREACH HAZARD" in decision.rationale


def test_deep_itm_immunity_blocks_pointless_dumps() -> None:
    """Moneyness Moat: At T=300s, position is +$400 ITM. A -$20 drop does not trigger panic exit."""
    bot = ThreeStepDominationBot(
        enable_dynamic_spot_velocity=True,
        moneyness_moat_multiplier=2.0,
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.90"): Decimal("150")}
    book.no_book = {Decimal("0.09"): Decimal("100")}

    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.52"),
        size=1,
        book=book,
        time_to_expiry_s=300.0,
        spot_price=85400.0,
        target_strike=85000.0,
        spot_velocity_3s=-20.0,
    )

    assert decision.should_exit is False
    assert decision.exit_reason == "HOLD"


def test_transition_zone_front_runs_tight_moneyness() -> None:
    """Regime 2: At T=120s with tight moneyness (+$8), a -$16 drop breaches adaptive threshold and front-runs."""
    bot = ThreeStepDominationBot(
        enable_dynamic_spot_velocity=True,
        spot_delta_front_run_threshold=15.0,
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.86"): Decimal("150")}
    book.no_book = {Decimal("0.12"): Decimal("100")}

    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.52"),
        size=1,
        book=book,
        time_to_expiry_s=120.0,
        spot_price=85008.0,
        target_strike=85000.0,
        spot_velocity_3s=-16.0,
        rolling_vol_1m=14.0,
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "SPOT_DELTA_FRONT_RUN"
    assert "TRANSITION DRIFT HAZARD" in decision.rationale


def test_macro_drift_zone_z_score_trigger() -> None:
    """Regime 1: At T=500s with tight moneyness, an extreme 4-sigma drop (-$25 in 3s) triggers exit."""
    bot = ThreeStepDominationBot(
        enable_dynamic_spot_velocity=True,
        velocity_z_score_threshold=2.50,
        moneyness_moat_multiplier=2.0,
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.87"): Decimal("150")}
    book.no_book = {Decimal("0.11"): Decimal("100")}

    decision = bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.52"),
        size=1,
        book=book,
        time_to_expiry_s=500.0,
        spot_price=85012.0,
        target_strike=85000.0,
        spot_velocity_3s=-25.0,
        rolling_vol_1m=14.0,
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "SPOT_DELTA_FRONT_RUN"
    assert "MACRO DRIFT SHIFT" in decision.rationale


def test_no_position_front_runs_on_adverse_upward_spike() -> None:
    """Short / NO position front-runs when spot spikes upwards adversely."""
    bot = ThreeStepDominationBot(
        enable_dynamic_spot_velocity=True,
        spot_delta_front_run_threshold=15.0,
    )

    book = L2BookState(market_ticker="KXBTC15M-T78650")
    book.yes_book = {Decimal("0.12"): Decimal("100")}
    book.no_book = {Decimal("0.87"): Decimal("150")}

    # Spot spikes up by +$18 in 3s against our NO position
    decision = bot.evaluate_exit(
        side=OrderSide.NO,
        entry_price=Decimal("0.51"),
        size=1,
        book=book,
        time_to_expiry_s=150.0,
        spot_price=84990.0,
        target_strike=85000.0,
        spot_velocity_3s=+18.0,
        rolling_vol_1m=14.0,
    )

    assert decision.should_exit is True
    assert decision.exit_reason == "SPOT_DELTA_FRONT_RUN"
    assert decision.exit_price == Decimal("0.87")


def test_standalone_engine_ols_regression_velocity() -> None:
    """Test StandaloneBotEngine OLS regression slope calculation and SNR noise rejection."""
    from kalshi_sim.standalone_bot import StandaloneBotEngine
    from collections import deque

    # 1. Linear downward drift of -$2.00 per second for 3 seconds (15 ticks at 0.2s spacing)
    btc_hist = deque(maxlen=300)
    t0 = 1000.0
    for i in range(15):
        t = t0 + i * 0.2
        # price drops by $2/s -> -$0.40 per 0.2s
        p = 85000.0 - 2.0 * (i * 0.2)
        btc_hist.append((t, p))

    vel_3s, realized_vol, snr = StandaloneBotEngine.calculate_ols_spot_velocity(btc_hist, target_window_s=3.0)
    # Expected slope is -2.0 $/s -> projected 3s move is -6.0 $
    assert math.isclose(vel_3s, -6.0, abs_tol=0.1)
    assert snr > 50.0  # Perfect line -> very high SNR

    # 2. Pure noise with zero slope: alternating +0.10, -0.10
    eth_hist = deque(maxlen=300)
    for i in range(15):
        t = t0 + i * 0.2
        p = 3000.0 + (0.10 if i % 2 == 0 else -0.10)
        eth_hist.append((t, p))

    vel_eth, _, snr_eth = StandaloneBotEngine.calculate_ols_spot_velocity(eth_hist, target_window_s=3.0)
    # Slope is close to 0
    assert abs(vel_eth) < 0.2

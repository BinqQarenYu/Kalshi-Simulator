"""Unit and Invariant Tests for Dynamic Trading Strategy (DRSA).

Verifies:
1. Zero float financial math invariants (Decimal precision on prices, EV, diffs).
2. Schmitt Trigger Hysteresis & Dwell Time mechanics (Whipsaw rejection).
3. Continuous parameter modulation surfaces ($0.51 price ceiling clamp).
4. Silas Settlement late-cycle freeze (T <= 120s).
5. Bleed Defender and toxic flow quarantine.
6. Micro-bankroll sizing invariant (max 1 contract).
7. PresetAuditor validation on dynamic_trading_strategy_v1.json.
"""

import json
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from kalshi_sim.ml.dynamic_regime_strategy import DynamicRegimeStrategy, DynamicRegimeDecision
from kalshi_sim.schemas import L2BookState
from kalshi_sim.preset_manager import PresetAuditor, PresetManager


def _mock_book(bid: str = "0.45", ask: str = "0.47") -> L2BookState:
    book = L2BookState("KXBTC15M-TEST")
    bid_dec = Decimal(bid)
    ask_dec = Decimal(ask)
    book.yes_book[bid_dec] = Decimal("100")
    # Binary CLOB pricing: yes_ask = 1 - best_no_bid
    no_bid = Decimal("1.00") - ask_dec
    book.no_book[no_bid] = Decimal("100")
    return book


def test_dynamic_regime_zero_float_invariants():
    """Verify that all financial and pricing attributes in decisions are strictly Decimal."""
    strategy = DynamicRegimeStrategy(asset="BTC")
    book = _mock_book("0.44", "0.46")

    decision = strategy.evaluate(
        ticker="KXBTC15M-TEST",
        book=book,
        spot_price=Decimal("80050.00"),
        strike_price=Decimal("80000.00"),
        expiration_time=datetime.now(timezone.utc) + timedelta(minutes=8),
        volatility_1m=Decimal("15.00"),
        vpin=Decimal("0.45"),
    )

    assert isinstance(decision.limit_price, Decimal), "limit_price must be Decimal"
    assert isinstance(decision.expected_value, Decimal), "expected_value must be Decimal"
    assert isinstance(decision.edge_pct, Decimal), "edge_pct must be Decimal"
    assert isinstance(decision.spot_diff, Decimal), "spot_diff must be Decimal"
    assert isinstance(decision.volatility_1m, Decimal), "volatility_1m must be Decimal"
    assert isinstance(decision.spread, Decimal), "spread must be Decimal"


def test_micro_bankroll_sizing_armor():
    """Verify that recommended contracts never exceed 1."""
    strategy = DynamicRegimeStrategy(asset="BTC")
    book = _mock_book("0.45", "0.47")

    # In trend expansion
    decision = strategy.evaluate(
        ticker="KXBTC15M-TEST",
        book=book,
        spot_price=Decimal("80150.00"),
        strike_price=Decimal("80000.00"),
        expiration_time=datetime.now(timezone.utc) + timedelta(minutes=8),
        volatility_1m=Decimal("40.00"),
        vpin=Decimal("0.40"),
    )
    assert decision.recommended_contracts in (0, 1), f"Contracts must be <= 1, got {decision.recommended_contracts}"


def test_parameter_surface_positive_ev_clamp():
    """Verify that dynamic limit price never breaches the $0.45 deep discount positive EV ceiling."""
    strategy = DynamicRegimeStrategy(asset="BTC")

    # Low vol
    p_low = strategy.compute_dynamic_limit_price(Decimal("10.00"))
    assert p_low == Decimal("0.38")

    # Normal vol
    p_norm = strategy.compute_dynamic_limit_price(Decimal("20.00"))
    assert p_norm == Decimal("0.39")

    # Extreme extreme vol (e.g. 500.00)
    p_extreme = strategy.compute_dynamic_limit_price(Decimal("500.00"))
    assert p_extreme <= Decimal("0.45"), f"Limit price must be clamped at $0.45, got {p_extreme}"
    assert p_extreme == Decimal("0.45")


def test_schmitt_trigger_hysteresis_and_dwell_time():
    """Verify that regime switching obeys the Schmitt Trigger and 30s dwell time."""
    strategy = DynamicRegimeStrategy(asset="BTC", dwell_time_seconds=30.0)
    assert strategy.current_regime == DynamicRegimeStrategy.REGIME_CHOP

    t0 = 1000.0
    strategy._regime_entered_time = t0

    # 1. Transient vol spike at t0+5s should NOT trigger immediate switch (< 3 ticks and < dwell time)
    regime = strategy.update_regime_state(
        volatility_1m=Decimal("35.00"),
        spread=Decimal("0.02"),
        vpin=Decimal("0.40"),
        time_to_expiry_s=500.0,
        now_ts=t0 + 5.0,
    )
    assert regime == DynamicRegimeStrategy.REGIME_CHOP, "Transient spike must be filtered out"

    # 2. Sustained vol spike >= 3 ticks after dwell time has passed
    strategy.update_regime_state(Decimal("35.00"), Decimal("0.02"), Decimal("0.40"), 500.0, now_ts=t0 + 31.0)
    strategy.update_regime_state(Decimal("35.00"), Decimal("0.02"), Decimal("0.40"), 500.0, now_ts=t0 + 32.0)
    regime_trend = strategy.update_regime_state(Decimal("35.00"), Decimal("0.02"), Decimal("0.40"), 500.0, now_ts=t0 + 33.0)
    assert regime_trend == DynamicRegimeStrategy.REGIME_TREND, "Sustained high vol must transition to TREND"

    # 3. Inside the Deadband (vol = 24.0, between 18.0 and 30.0): Must remain in TREND
    regime_deadband = strategy.update_regime_state(Decimal("24.00"), Decimal("0.02"), Decimal("0.40"), 500.0, now_ts=t0 + 70.0)
    assert regime_deadband == DynamicRegimeStrategy.REGIME_TREND, "Inside deadband must remain in current regime"

    # 4. Vol drops below 18.0 after dwell time: Reverts to CHOP
    regime_revert = strategy.update_regime_state(Decimal("15.00"), Decimal("0.02"), Decimal("0.40"), 500.0, now_ts=t0 + 110.0)
    assert regime_revert == DynamicRegimeStrategy.REGIME_CHOP, "Low vol must revert to CHOP"


def test_silas_settlement_late_cycle_override():
    """Verify that T <= 120s strictly overrides all other regimes into SILAS_SETTLEMENT."""
    strategy = DynamicRegimeStrategy(asset="BTC")
    book = _mock_book("0.44", "0.46")

    # High vol, but only 60s remaining
    decision = strategy.evaluate(
        ticker="KXBTC15M-TEST",
        book=book,
        spot_price=Decimal("80040.00"),
        strike_price=Decimal("80000.00"),
        expiration_time=datetime.now(timezone.utc) + timedelta(seconds=60),
        volatility_1m=Decimal("50.00"),
        vpin=Decimal("0.40"),
    )

    assert decision.regime == DynamicRegimeStrategy.REGIME_SILAS
    assert "Silas Settlement Parity" in decision.rationale


def test_bleed_defender_toxic_quarantine():
    """Verify that wide CLOB spreads or high VPIN force BLEED_QUARANTINE with 0 contracts."""
    strategy = DynamicRegimeStrategy(asset="BTC")
    book = _mock_book("0.40", "0.47")  # 7 cents spread (> 4c max)

    decision = strategy.evaluate(
        ticker="KXBTC15M-TEST",
        book=book,
        spot_price=Decimal("80050.00"),
        strike_price=Decimal("80000.00"),
        expiration_time=datetime.now(timezone.utc) + timedelta(minutes=8),
        volatility_1m=Decimal("20.00"),
        vpin=Decimal("0.40"),
    )

    assert decision.regime == DynamicRegimeStrategy.REGIME_BLEED
    assert decision.recommended_side == "wait"
    assert decision.recommended_contracts == 0


def test_preset_vault_certified_preset_integrity():
    """Verify that dynamic_trading_strategy_v1.json passes all Pre-Flight Invariant checks."""
    preset_path = Path("data/presets/dynamic_trading_strategy_v1.json")
    assert preset_path.exists(), "dynamic_trading_strategy_v1.json must exist in vault"

    with open(preset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    is_valid, violations = PresetAuditor.validate_preset_dict(data)
    assert is_valid, f"PresetAuditor rejected dynamic preset: {violations}"
    assert data.get("is_council_certified") is True
    assert data.get("max_contracts") == 1
    assert data.get("discount_limit_price") <= 0.51


def test_failover_hot_swap_flow(tmp_path):
    """Verify that PresetManager can load dynamic_trading_strategy_v1 atomically."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    presets_dir = data_dir / "presets"
    presets_dir.mkdir(parents=True, exist_ok=True)

    # Copy preset to isolated test directory
    source_preset = Path("data/presets/dynamic_trading_strategy_v1.json")
    target_preset = presets_dir / "dynamic_trading_strategy_v1.json"
    target_preset.write_text(source_preset.read_text(encoding="utf-8"), encoding="utf-8")

    pm = PresetManager(presets_dir=presets_dir, data_dir=data_dir)
    success, msg, loaded_data = pm.load_preset("dynamic_trading_strategy_v1")

    assert success is True
    assert pm.get_active_preset_id() == "dynamic_trading_strategy_v1"
    assert loaded_data.get("max_contracts") == 1


def test_harakiri_streak_triggers_dynamic_failover():
    """Verify that when the current strategy hits the consecutive loss limit,
    AgentGuardrails triggers failover to dynamic_trading_strategy_v1."""
    from kalshi_sim.agent_guardrails import AgentGuardrails

    pm = PresetManager()
    pm.load_preset("baseline_council_v3.2")
    assert pm.get_active_preset_id() == "baseline_council_v3.2"

    guard = AgentGuardrails()
    guard.harakiri_loss_limit = 3

    # First 2 losses
    guard.record_trade_settlement("KXBTC15M-1", Decimal("-0.45"), was_win=False, execution_mode="live")
    guard.record_trade_settlement("KXBTC15M-2", Decimal("-0.45"), was_win=False, execution_mode="live")
    assert guard._consecutive_losses == 2
    assert guard.is_bot_armed is True

    # 3rd consecutive loss: triggers failure and automated failover
    guard.record_trade_settlement("KXBTC15M-3", Decimal("-0.45"), was_win=False, execution_mode="live")

    # Failover must have activated dynamic_trading_strategy_v1 and kept bot armed
    assert pm.get_active_preset_id() == "dynamic_trading_strategy_v1"
    assert guard.is_bot_armed is True
    assert guard._consecutive_losses == 0

    # Clean up: restore baseline
    pm.load_preset("baseline_council_v3.2")


def test_chop_stand_down_directive_vetoes_chop_bets():
    """Verify that when in CHOP with enable_chop_trading=False (default),
    the bot strictly stands down (0 contracts, wait) to eliminate adverse selection drag."""
    strategy = DynamicRegimeStrategy(asset="BTC", enable_chop_trading=False)
    book = _mock_book("0.42", "0.44")

    # In CHOP regime (low vol = 14.0), spot diff is +$10 (would have triggered chop maker if enabled)
    decision = strategy.evaluate(
        ticker="KXBTC15M-TEST",
        book=book,
        spot_price=Decimal("80010.00"),
        strike_price=Decimal("80000.00"),
        expiration_time=datetime.now(timezone.utc) + timedelta(minutes=7),
        volatility_1m=Decimal("14.00"),
        vpin=Decimal("0.40"),
    )

    assert decision.regime == DynamicRegimeStrategy.REGIME_CHOP
    assert decision.recommended_side == "wait", "Must stand down in chop when enable_chop_trading is False"
    assert decision.recommended_contracts == 0, "Must size strictly 0 contracts in chop stand-down"
    assert "Chop Stand-Down Directive" in decision.rationale


def test_storm_hunter_fights_when_volatility_expands():
    """Verify that when market is in TREND/STORM, the bot enters with high conviction."""
    strategy = DynamicRegimeStrategy(asset="BTC", enable_chop_trading=False, dwell_time_seconds=0.0)
    book = _mock_book("0.46", "0.48")

    # Push into TREND regime via sustained vol
    strategy.update_regime_state(Decimal("45.00"), Decimal("0.02"), Decimal("0.40"), 500.0)
    strategy.update_regime_state(Decimal("45.00"), Decimal("0.02"), Decimal("0.40"), 500.0)
    regime = strategy.update_regime_state(Decimal("45.00"), Decimal("0.02"), Decimal("0.40"), 500.0)
    assert regime == DynamicRegimeStrategy.REGIME_TREND

    # Spot diff +$60 exceeds spot threshold ($55 * 1.5 = 82.5 or base 55)
    decision = strategy.evaluate(
        ticker="KXBTC15M-TEST",
        book=book,
        spot_price=Decimal("80150.00"),
        strike_price=Decimal("80000.00"),
        expiration_time=datetime.now(timezone.utc) + timedelta(minutes=7),
        volatility_1m=Decimal("45.00"),
        vpin=Decimal("0.40"),
    )

    assert decision.regime == DynamicRegimeStrategy.REGIME_TREND
    assert decision.recommended_side == "yes", "Must enter YES in bullish storm/trend"
    assert decision.recommended_contracts == 1, "Must size 1 contract"
    assert "Trend Expansion" in decision.rationale


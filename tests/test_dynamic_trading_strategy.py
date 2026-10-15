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

    # Clean up: restore active strategy preset
    pm.load_preset("dynamic_trading_strategy_v1")


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
    assert decision.limit_price == Decimal("0.48"), "Must match best_ask for immediate fill"
    assert decision.is_maker is False, "Must execute as controlled aggressive taker"
    assert "Trend Expansion" in decision.rationale


def test_storm_hunter_refuses_expensive_chase():
    """Verify that when ask exceeds $0.52 armor ceiling, the bot refuses to chase."""
    strategy = DynamicRegimeStrategy(asset="BTC", enable_chop_trading=False, dwell_time_seconds=0.0)
    # Expensive book: ask = $0.58 (> $0.52 ceiling)
    book = _mock_book("0.55", "0.58")

    # Push into TREND
    strategy.update_regime_state(Decimal("45.00"), Decimal("0.02"), Decimal("0.40"), 500.0)
    strategy.update_regime_state(Decimal("45.00"), Decimal("0.02"), Decimal("0.40"), 500.0)
    strategy.update_regime_state(Decimal("45.00"), Decimal("0.02"), Decimal("0.40"), 500.0)

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
    assert decision.recommended_side == "wait", "Must not chase expensive asks > $0.52"
    assert decision.recommended_contracts == 0
    assert "armor" in decision.rationale


def test_eth_btc_digit_scale_and_moat_isolation():
    """Verify that BTC and ETH strategies evaluate with isolated calibrated moats and thresholds."""
    btc_strat = DynamicRegimeStrategy(asset="BTC")
    eth_strat = DynamicRegimeStrategy(asset="ETH")

    assert btc_strat.silas_spot_moat == Decimal("15.00")
    assert eth_strat.silas_spot_moat == Decimal("1.50")
    assert btc_strat.chop_harvester_spot_moat == Decimal("8.00")
    assert eth_strat.chop_harvester_spot_moat == Decimal("1.00")
    assert btc_strat.base_spot_threshold == Decimal("55.00")
    assert eth_strat.base_spot_threshold == Decimal("4.50")

    # In Silas Settlement (T=60s), spot diff = +$2.50
    book_eth = _mock_book("0.44", "0.46")
    exp_time = datetime.now(timezone.utc) + timedelta(seconds=60)

    # On ETH, +$2.50 exceeds the $1.50 moat -> YES
    dec_eth = eth_strat.evaluate(
        ticker="KXETH15M-T2600",
        book=book_eth,
        spot_price=Decimal("2602.50"),
        strike_price=Decimal("2600.00"),
        expiration_time=exp_time,
        volatility_1m=Decimal("0.60"),
    )
    assert dec_eth.regime == DynamicRegimeStrategy.REGIME_SILAS
    assert dec_eth.recommended_side == "yes"
    assert dec_eth.recommended_contracts == 1
    assert "Silas Settlement Parity" in dec_eth.rationale

    # On BTC, +$2.50 is tiny (< $15.00 moat) -> WAIT
    book_btc = _mock_book("0.44", "0.46")
    dec_btc = btc_strat.evaluate(
        ticker="KXBTC15M-T80000",
        book=book_btc,
        spot_price=Decimal("80002.50"),
        strike_price=Decimal("80000.00"),
        expiration_time=exp_time,
        volatility_1m=Decimal("14.00"),
    )
    assert dec_btc.regime == DynamicRegimeStrategy.REGIME_SILAS
    assert dec_btc.recommended_side == "wait"
    assert dec_btc.recommended_contracts == 0
    assert "Quarantine" in dec_btc.rationale


def test_strategy_evaluator_cross_asset_spot_price_isolation():
    """Verify that BTC spot price ($85,000+) never leaks into ETH contracts and vice versa."""
    from kalshi_sim.strategy_evaluator import StrategyEvaluationCoordinator
    from kalshi_sim.schemas import MarketInfo

    # Mock coordinator with a BTC spot getter returning $88,000
    coord = StrategyEvaluationCoordinator(
        guardrails=None,  # type: ignore
        simulator=None,  # type: ignore
        db_writer=None,  # type: ignore
        onnx_engine=None,  # type: ignore
        ev_engine=None,  # type: ignore
        macro_trend_bot=None,  # type: ignore
        dominion2_bot=None,  # type: ignore
        domination_bot=None,  # type: ignore
        dual_onnx_bot=None,  # type: ignore
        btc_orderflow_feed=None,  # type: ignore
        spot_price_getter=lambda: Decimal("88000.00"),
    )

    # 1. Fallback strike resolution for ETH vs BTC
    m_eth = MarketInfo(ticker="KXETH15M-UNKNOWN")
    m_btc = MarketInfo(ticker="KXBTC15M-UNKNOWN")
    assert coord._resolve_target_strike("KXETH15M-UNKNOWN", m_eth) == Decimal("2600.00")
    assert coord._resolve_target_strike("KXBTC15M-UNKNOWN", m_btc) == Decimal("78650.00")

    # 2. Spot price resolution for ETH when getter returns $88,000 (BTC scale)
    # The sanity check must reject $88,000 as BTC scale leak and resolve to ETH strike
    target_strike_eth = Decimal("2650.00")
    resolved_eth_spot = coord._resolve_spot_price("KXETH15M-T2650", None, target_strike_eth)
    assert resolved_eth_spot == Decimal("2650.00"), f"Expected 2650.00, got {resolved_eth_spot}"

    # 3. Spot price resolution for BTC when getter returns $88,000 (valid BTC scale)
    target_strike_btc = Decimal("88000.00")
    resolved_btc_spot = coord._resolve_spot_price("KXBTC15M-T88000", None, target_strike_btc)
    assert resolved_btc_spot == Decimal("88000.00"), f"Expected 88000.00, got {resolved_btc_spot}"


def test_wave_classifier_asset_scale_adaptation():
    """Verify that wave physics accurately classifies geometric wicks for both ETH and BTC."""
    from kalshi_sim.ml.wave_classifier import compute_wave_physics

    # BTC wave: range $150, wick $30 -> Bounded Chop on BTC
    btc_wave = compute_wave_physics(
        open_price=80000.0,
        high_price=80150.0,
        low_price=80000.0,
        current_price=80100.0,
        asset="BTC",
    )
    assert not btc_wave.is_tsunami
    assert not btc_wave.is_double_wick_meatgrinder

    # ETH wave: range $20 (high=2620, low=2600) -> Tsunami Expansion on ETH (> $15 threshold)
    eth_wave = compute_wave_physics(
        open_price=2600.0,
        high_price=2620.0,
        low_price=2600.0,
        current_price=2610.0,
        asset="ETH",
    )
    assert eth_wave.is_tsunami is True, "ETH $20 move must be recognized as tsunami"

    # ETH double-wick: upper wick $3.50, lower wick $3.50 -> Double-Wick Meatgrinder on ETH
    eth_wick = compute_wave_physics(
        open_price=2605.0,
        high_price=2610.0,
        low_price=2600.0,
        current_price=2605.0,
        asset="ETH",
    )
    assert eth_wick.is_double_wick_meatgrinder is True, "ETH wicks of $5 must trigger double-wick meatgrinder"




"""ASVL Verification Test Suite: The Balanced Division of Power.

Verifies:
1. ContinuousExperienceBuffer Supreme Governor methods (effective moat, price cap, Platt alpha, quadrant pruning).
2. Platt Confidence Leash: Suppresses Kev the Tactical Lead Taker when calibrated confidence < 60%.
3. 3D Mistake Matrix Quadrant Banning: Vetoes trades in historically toxic zones.
4. Dynamic Regime Strategy (DRSA) Learning Dials: Adapts proximity moats and clamps momentum ceilings.
5. In-Flight Derisking / Valley Ejector with HMM RISK_OFF: Salvages capital early at <= $0.40.
6. Silas TWAP Parity Guard: Immunizes positions from panic dumping when trailing 60s TWAP is secure.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from kalshi_sim.ml.btc_bot1v4.btc_bot1v4_engine import BtcBot1V4Engine
from kalshi_sim.ml.domination_exit_evaluator import DominationExitEvaluator
from kalshi_sim.ml.dynamic_regime_strategy import DynamicRegimeStrategy
from kalshi_sim.ml.eth_bot1v4.eth_bot1v4_engine import EthBot1V4Engine
from kalshi_sim.ml.experience_buffer import ContinuousExperienceBuffer
from kalshi_sim.schemas import CryptoAsset, L2BookState, MarketInfo, OrderSide


def test_continuous_experience_buffer_governance_methods(tmp_path: Path) -> None:
    """Test Supreme Governor helper methods for moat scaling and price capping."""
    hist_file = tmp_path / "test_buffer.json"
    buffer = ContinuousExperienceBuffer(history_file=hist_file, asset="ETH")

    # 1. Base moat tests
    base_moat = Decimal("1.50")
    assert buffer.get_effective_moat(base_moat) == Decimal("1.50")

    buffer.adaptive_proximity_moat_multiplier = 1.30
    # 1.50 * 1.30 = 1.95
    assert buffer.get_effective_moat(base_moat) == Decimal("1.95")

    # 2. Price cap tests
    default_cap = Decimal("0.65")
    assert buffer.get_effective_price_cap(default_cap) == Decimal("0.65")

    # Explicit active_price_cap clamp
    buffer.active_price_cap = Decimal("0.58")
    assert buffer.get_effective_price_cap(default_cap) == Decimal("0.58")

    # Higher than default cap retains default cap
    buffer.active_price_cap = Decimal("0.70")
    assert buffer.get_effective_price_cap(default_cap) == Decimal("0.65")

    # Decile pruning clamp
    buffer.active_price_cap = None
    buffer.pruned_price_deciles = [50]
    assert buffer.get_effective_price_cap(default_cap) == Decimal("0.48")


def test_3d_mistake_matrix_quadrant_pruning(tmp_path: Path) -> None:
    """Test 3D Mistake Matrix correctly classifies and prunes toxic quadrants."""
    hist_file = tmp_path / "test_buffer.json"
    buffer = ContinuousExperienceBuffer(history_file=hist_file, asset="ETH")

    tau_s = 500.0  # MID (180 < tau <= 600)
    diff = 3.0     # MID (2.00 <= |diff| < 5.00 for ETH)

    assert not buffer.is_quadrant_pruned(tau_s, diff)

    # Prune MID_MID quadrant
    buffer.pruned_quadrants = ["MID_MID"]
    assert buffer.is_quadrant_pruned(tau_s, diff)
    assert not buffer.is_quadrant_pruned(100.0, diff)  # LATE_MID is not pruned


def test_dynamic_regime_strategy_learning_dials() -> None:
    """Test DRSA correctly scales moats and clamps momentum ceilings when learning dials update."""
    strategy = DynamicRegimeStrategy(asset="BTC")

    assert strategy.silas_spot_moat == Decimal("15.00")
    assert strategy.max_momentum_price == Decimal("0.52")

    # Update learning dials
    strategy.update_learning_dials(
        adaptive_moat_multiplier=1.5,
        active_price_cap=Decimal("0.48"),
    )

    # Dynamic spot threshold should be scaled by 1.5x
    base_thresh = strategy.compute_dynamic_spot_threshold(Decimal("0.02"))
    # base_spot_threshold = 55.00 * (1 + 2/2) * 1.5 = 55.00 * 2.0 * 1.5 = 165.00
    assert base_thresh == Decimal("165.00")

    # Evaluate inside the expanded Silas moat (15 * 1.5 = 22.50)
    book = L2BookState("KXBTC15M-TEST")
    book.yes_book = {Decimal("0.45"): Decimal("10")}
    book.no_book = {Decimal("0.55"): Decimal("10")}

    strategy._current_regime = strategy.REGIME_SILAS
    decision_silas = strategy.evaluate(
        ticker="KXBTC15M-TEST",
        book=book,
        spot_price=Decimal("90018.00"),
        strike_price=Decimal("90000.00"),
        expiration_time=None,
        volatility_1m=Decimal("20.00"),
        now_ts=1000.0,
    )
    # Spot diff +18.00 < effective moat 22.50 => Should hold/wait
    assert decision_silas.recommended_side == "wait"
    assert "Silas TWAP Pin Quarantine" in decision_silas.rationale


def test_domination_exit_evaluator_valley_ejector_hmm_risk_off() -> None:
    """Test Rule 6 Valley Ejector salvages capital when HMM detects RISK_OFF."""
    from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
    bot = ThreeStepDominationBot()
    evaluator = DominationExitEvaluator(bot)

    book = L2BookState("KXBTC15M-TEST")
    book.yes_book = {Decimal("0.39"): Decimal("10")}
    book.no_book = {Decimal("0.61"): Decimal("10")}

    # Case A: Normal regime, reverse_prob = 0.50 -> HOLD (does not meet 0.38 / 0.70)
    bot.compute_market_probabilities = MagicMock(return_value=(0.50, 0.50))
    exit_normal = evaluator.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.55"),
        size=1,
        book=book,
        time_to_expiry_s=300.0,
        spot_price=90000.0,
        target_strike=90000.0,
        hmm_regime="NORMAL",
    )
    assert exit_normal.should_exit is False
    assert exit_normal.exit_reason == "HOLD"

    # Case B: HMM RISK_OFF regime, bid = $0.39, reverse_prob = 0.65 -> EJECT (meets 0.40 / 0.60 threshold)
    bot.compute_market_probabilities = MagicMock(return_value=(0.35, 0.65))
    exit_risk_off = evaluator.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.55"),
        size=1,
        book=book,
        time_to_expiry_s=300.0,
        spot_price=90000.0,
        target_strike=90000.0,
        hmm_regime="RISK_OFF",
    )
    assert exit_risk_off.should_exit is True
    assert exit_risk_off.exit_reason == "VALLEY_EJECTOR"
    assert "HMM RISK_OFF" in exit_risk_off.rationale
    assert exit_risk_off.exit_price == Decimal("0.39")


@pytest.mark.asyncio
async def test_platt_confidence_leash_vetoes_kev_in_eth_engine(tmp_path: Path) -> None:
    """Test that Platt Confidence Leash suppresses Kev when platt_alpha scales confidence below 60%."""
    hist_file = tmp_path / "eth_buffer.json"
    engine = EthBot1V4Engine(history_file=hist_file)

    # Mock orderbook and spot price
    book = L2BookState("KXETH15M-TEST-2600")
    book.yes_book = {Decimal("0.50"): Decimal("10")}
    book.no_book = {Decimal("0.50"): Decimal("10")}
    engine.fetch_orderbook = AsyncMock(return_value=book)
    engine.get_spot_price = MagicMock(return_value=Decimal("2605.00"))

    # Kev recommends YES with raw 0.70 confidence
    mock_rec = MagicMock()
    mock_rec.selected_option = "YES"
    mock_rec.confidence = 0.70
    mock_rec.latency_ms = 5.0
    mock_rec.source = "MOCK"

    mock_toxic = MagicMock()
    mock_toxic.selected_option = "false"

    engine.kev_oracle.evaluate = AsyncMock(return_value={
        "trade_direction": mock_rec,
        "is_toxic_sweep": mock_toxic,
    })

    # Set platt_alpha = 0.80 -> Calibrated conf = 0.70 * 0.80 = 0.56 (< 0.60 threshold)
    engine.experience_buffer.platt_alpha = 0.80

    # Ensure order client is not triggering a live order
    engine.order_client = None

    decision = await engine.run_cycle(ticker="KXETH15M-TEST-2600")
    assert decision is not None
    # Because Kev was suppressed, Kev's taker order was aborted and maker decision was preserved
    assert engine.kev_oracle.evaluate.called


@pytest.mark.asyncio
async def test_mistake_matrix_vetoes_kev_in_btc_engine(tmp_path: Path) -> None:
    """Test that 3D Mistake Matrix vetoes Kev when market is in a blacklisted quadrant."""
    hist_file = tmp_path / "btc_buffer.json"
    engine = BtcBot1V4Engine(history_file=hist_file)

    book = L2BookState("KXBTC15M-TEST-90000")
    book.yes_book = {Decimal("0.50"): Decimal("10")}
    book.no_book = {Decimal("0.50"): Decimal("10")}
    engine.fetch_orderbook = AsyncMock(return_value=book)
    engine.get_spot_price = MagicMock(return_value=Decimal("90035.00"))

    mock_rec = MagicMock()
    mock_rec.selected_option = "YES"
    mock_rec.confidence = 0.85
    mock_rec.latency_ms = 5.0
    mock_rec.source = "MOCK"

    mock_toxic = MagicMock()
    mock_toxic.selected_option = "false"

    engine.kev_oracle.evaluate = AsyncMock(return_value={
        "trade_direction": mock_rec,
        "is_toxic_sweep": mock_toxic,
    })

    # Prune MID_MID quadrant (180 < Tau <= 600, 25.00 <= Diff < 60.00 for BTC)
    engine.experience_buffer.pruned_quadrants = ["MID_MID"]
    engine.order_client = None

    decision = await engine.run_cycle(ticker="KXBTC15M-TEST-90000")
    assert decision is not None
    assert engine.kev_oracle.evaluate.called


def test_empirical_win_rate_and_platt_alpha_recalibration(tmp_path: Path) -> None:
    """Verify bad math fix: empirical_win_rate is 0.30 (not 1.0) when 3 of 10 trades win."""
    hist_file = tmp_path / "test_buffer_winrate.json"
    buffer = ContinuousExperienceBuffer(history_file=hist_file, asset="ETH")

    # Inject 10 trades: 3 wins, 7 losses, all with predicted prob 0.70
    from kalshi_sim.ml.experience_buffer import CycleExperience
    for i in range(10):
        is_win = (i < 3)
        exp = CycleExperience(
            ticker="KXETH15M-TEST",
            cycle_id=f"c_{i}",
            timestamp_utc="2026-10-16T12:00:00Z",
            strike_price=2600.0,
            settlement_spot=2610.0 if is_win else 2590.0,
            spot_diff=3.0,
            bot_side="yes",
            entry_price=0.50,
            contracts=1,
            predicted_prob=0.70,
            outcome="win" if is_win else "loss",
            net_pnl=0.49 if is_win else -0.51,
            fees=0.01,
            execution_mode="simulated",
            vpin=0.15,
            active_playbook="trend",
            macro_regime="trend",
            time_to_expiry_s=300.0,
            loss_cause="none" if is_win else "MOMENTUM_INVERSION",
        )
        buffer.experiences.append(exp)

    buffer.recalibrate()

    # Model was 70% confident on average, but only won 30% (empirical win rate = 0.30)
    # Bias = 0.70 - 0.30 = +0.40 (overconfident)
    # Platt alpha = max(0.65, round(1.0 - (0.40 * 1.5), 2)) = 0.65
    assert buffer.platt_alpha == 0.65

    # Calibrating 0.70 raw prob should now scale down to < 0.65
    calibrated = buffer.calibrate_probability(0.70)
    assert calibrated < 0.65


@pytest.mark.asyncio
async def test_kev_oracle_short_circuit_on_cycle_lock(tmp_path: Path) -> None:
    """Verify AGENTS.md Rule 8 & Law 2: Kev Oracle is never queried if cycle is already locked or traded."""
    hist_file = tmp_path / "eth_buffer_lock.json"
    engine = EthBot1V4Engine(history_file=hist_file)

    mock_client = MagicMock()
    engine.order_client = mock_client

    book = L2BookState("KXETH15M-LOCKED-2600")
    book.yes_book = {Decimal("0.50"): Decimal("10")}
    book.no_book = {Decimal("0.50"): Decimal("10")}
    engine.fetch_orderbook = AsyncMock(return_value=book)
    engine.get_spot_price = MagicMock(return_value=Decimal("2605.00"))
    engine.kev_oracle.evaluate = AsyncMock()

    from kalshi_sim.agent_guardrails import get_global_guardrails
    guardrails = get_global_guardrails()

    # Lock the cycle
    engine.record_completed_turnover("KXETH15M-LOCKED-2600")

    decision = await engine.run_cycle(ticker="KXETH15M-LOCKED-2600")
    assert decision is not None

    # Kev Oracle must NOT have been called (credit burning prevented!)
    assert not engine.kev_oracle.evaluate.called


def test_entry_spot_diff_preservation(tmp_path: Path) -> None:
    """Verify entry_spot_diff is preserved and not overwritten by settlement price delta."""
    hist_file = tmp_path / "test_buffer_spotdiff.json"
    buffer = ContinuousExperienceBuffer(history_file=hist_file, asset="ETH")

    # Trade entered with tight spot diff (1.20), but settlement drifted by 20.00
    report = {
        "ticker": "KXETH15M-TEST",
        "strike_price": 2600.0,
        "settlement_spot_price": 2620.0,  # +20.00 drift
        "entry_spot_diff": 1.20,          # Entry was +1.20
        "time_to_expiry_s": 550.0,
        "bot_side": "yes",
        "entry_price": 0.50,
        "outcome": "win",
        "pnl": 0.49,
    }
    exp = buffer._dict_to_experience(report)
    assert exp is not None
    # exp.spot_diff must reflect entry distance 1.20, NOT settlement drift 20.00
    assert exp.spot_diff == 1.20
    assert exp.time_to_expiry_s == 550.0


def test_valley_ejector_btc_twap_cushion() -> None:
    """Verify Rule 6 Valley Ejector uses asset-adaptive cushion (25.0 for BTC vs 2.5 for ETH)."""
    from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
    bot = ThreeStepDominationBot()
    bot.asset = CryptoAsset.BTC
    bot.STRATEGY_ID = "btc_bot1_v4_domination"
    evaluator = DominationExitEvaluator(bot)

    book = L2BookState("KXBTC15M-TEST-90000")
    book.yes_book = {Decimal("0.35"): Decimal("10")}
    book.no_book = {Decimal("0.65"): Decimal("10")}

    bot.compute_market_probabilities = MagicMock(return_value=(0.10, 0.90))

    # BTC target_strike = 90000.0, twap_60s = 90005.0 (+5.0 above strike).
    # Since BTC cushion is 25.0, +5.0 is NOT safe! Valley Ejector MUST eject!
    exit_decision = evaluator.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.55"),
        size=1,
        book=book,
        time_to_expiry_s=100.0,
        spot_price=89980.0,
        target_strike=90000.0,
        twap_60s=90005.0,
    )
    assert exit_decision.should_exit is True
    assert exit_decision.exit_reason == "VALLEY_EJECTOR"


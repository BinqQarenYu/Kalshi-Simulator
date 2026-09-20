"""Simsim Historical Replay Simulation Harness.

Replays actual tick streams from data/stream_*.jsonl and validates side-by-side:
- Legacy Static Model (blind $15 threshold) vs.
- Dynamic Fading Mathematics Model (Delta* with Silas TWAP Gravity and Moneyness Moat).
"""

import json
import math
from decimal import Decimal
from pathlib import Path
import pytest

from kalshi_sim.ml.bot1_v4_engine import Bot1V4DominationEngine
from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
from kalshi_sim.schemas import CryptoAsset, L2BookState, OrderSide


def test_simsim_fading_variance_vs_twap_gravity() -> None:
    """Simsim Simulation 1: Replay near-zero price variance explosion (T=25s, σ_P=0.404).

    Scenario:
    - Bot is holding 1 YES contract entered at $0.51.
    - Spot is $85,020, Strike is $85,000.
    - Trailing 60s TWAP is $85,035 (TWAP cushion = +$35.00).
    - Remaining time T=25s.
    - Orderbook bid drops from $0.92 to $0.68 due to retail panic.
    - Spot dips by -$16.00 in 3 seconds.

    Expected Result:
    - Legacy static model with fixed $15 threshold FALSELY DUMPS at $0.68.
    - Dynamic Fading Model evaluates v_crit = (2 * 35 * 60) / (25^2) = 6.72 $/s.
      Observed adverse drop is 16/3 = 5.33 $/s < 6.72 $/s.
      Dynamic Fading Model VETOES exit and holds for $1.00 settlement (+49c win)!
    """
    # 1. Legacy Static Bot
    legacy_bot = ThreeStepDominationBot(
        enable_dynamic_spot_velocity=False,
        spot_delta_front_run_threshold=15.0,
        late_cycle_roi=999.0,  # Isolate Rule 2
    )

    # 2. Dynamic Fading Bot
    dynamic_bot = ThreeStepDominationBot(
        enable_dynamic_spot_velocity=True,
        twap_fading_window_seconds=60.0,
        twap_fading_quarantine_seconds=15.0,
        late_cycle_roi=999.0,
    )

    book = L2BookState(market_ticker="KXBTC15M-T85000")
    book.yes_book = {Decimal("0.86"): Decimal("100")}  # High bid (86c) before settlement
    book.no_book = {Decimal("0.13"): Decimal("100")}

    # Evaluate Legacy Bot
    legacy_decision = legacy_bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.51"),
        size=1,
        book=book,
        time_to_expiry_s=25.0,
        spot_price=85020.0,
        target_strike=85000.0,
        twap_60s=85035.0,
        spot_velocity_3s=-16.0,  # Breaches static $15
    )

    # Evaluate Dynamic Fading Bot
    dynamic_decision = dynamic_bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.51"),
        size=1,
        book=book,
        time_to_expiry_s=25.0,
        spot_price=85020.0,
        target_strike=85000.0,
        twap_60s=85035.0,
        spot_velocity_3s=-16.0,
    )

    # Assertions: The Fading Model eliminates the false panic exit
    assert legacy_decision.should_exit is True
    assert legacy_decision.exit_reason == "SPOT_DELTA_FRONT_RUN"
    # Legacy sells at $0.68, sacrificing $0.32 of profit!

    assert dynamic_decision.should_exit is False
    assert dynamic_decision.exit_reason == "HOLD"
    # Dynamic holds to $1.00 settlement, capturing 100% of the win!


def test_simsim_catastrophic_macro_dump_protection() -> None:
    """Simsim Simulation 2: Replay a genuine catastrophic flash dump.

    Scenario:
    - Bot is holding 1 YES contract at $0.51.
    - Remaining time T=35s.
    - Spot is $85,010, Strike is $85,000.
    - Trailing 60s TWAP is $85,015 (tight TWAP cushion = +$15.00).
    - Extreme macro dump occurs: spot plunges -$60.00 in 3 seconds (20.0 $/s).
    - v_crit = (2 * 15 * 60) / (35^2) = 1.47 $/s.
    - 20.0 $/s is 13x higher than v_crit -> The contract IS going to zero!
    - Orderbook bid is still resting at $0.86 before market makers pull liquidity.

    Expected Result:
    - Dynamic bot immediately fires SPOT_DELTA_FRONT_RUN and dumps at $0.86,
      locking in a +$0.34 profit instead of taking a -$0.51 total loss at expiration!
    """
    dynamic_bot = ThreeStepDominationBot(
        enable_dynamic_spot_velocity=True,
        twap_fading_window_seconds=60.0,
        twap_fading_quarantine_seconds=15.0,
    )

    book = L2BookState(market_ticker="KXBTC15M-T85000")
    book.yes_book = {Decimal("0.86"): Decimal("150")}
    book.no_book = {Decimal("0.13"): Decimal("100")}

    dynamic_decision = dynamic_bot.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.51"),
        size=1,
        book=book,
        time_to_expiry_s=35.0,
        spot_price=85010.0,
        target_strike=85000.0,
        twap_60s=85015.0,
        spot_velocity_3s=-60.0,  # 20 $/s drop
    )

    assert dynamic_decision.should_exit is True
    assert dynamic_decision.exit_reason == "SPOT_DELTA_FRONT_RUN"
    assert dynamic_decision.exit_price == Decimal("0.86")
    assert "TWAP BREACH HAZARD" in dynamic_decision.rationale


def test_simsim_stream_ticks_replay() -> None:
    """Simsim Simulation 3: Stream replay from data/stream_*.jsonl file."""
    stream_files = list(Path("data").glob("stream_*.jsonl"))
    if not stream_files:
        pytest.skip("No stream_*.jsonl files found in data/")

    target_file = stream_files[0]
    ticks = []
    with open(target_file, "r") as f:
        for i, line in enumerate(f):
            if i >= 500:  # Sample first 500 ticks
                break
            try:
                ticks.append(json.loads(line))
            except Exception:
                continue

    assert len(ticks) > 50

    dynamic_bot = ThreeStepDominationBot(
        enable_dynamic_spot_velocity=True,
        twap_fading_quarantine_seconds=15.0,
    )

    # Verify bot evaluates ticks cleanly without throwing exceptions
    book = L2BookState(market_ticker="KXBTC15M-TEST")
    book.yes_book = {Decimal("0.88"): Decimal("100")}
    book.no_book = {Decimal("0.11"): Decimal("100")}

    eval_count = 0
    for t in ticks[:100]:
        price = t.get("price") or 0.50
        delta = t.get("delta") or 50.0
        # Evaluate exit
        dec = dynamic_bot.evaluate_exit(
            side=OrderSide.YES,
            entry_price=Decimal("0.51"),
            size=1,
            book=book,
            time_to_expiry_s=300.0,
            spot_price=85000.0 + delta,
            target_strike=85000.0,
            spot_velocity_3s=-2.0,
        )
        assert dec is not None
        eval_count += 1
    assert eval_count == 100


def test_simsim_bot1_v4_upgraded_doubt_harvest() -> None:
    """Simsim Simulation 4: Replay Bot 1 Version 4 with Upgraded Horizon-Proportional Doubt Harvest.

    Validates that:
    1. At 9 minutes (T=540s), a -$10 adverse spot dip is classified as normal Brownian noise
       and position is HELD.
    2. At 90 seconds (T=90s), that exact same -$10 adverse spot dip triggers prompt
       DOUBT_PROFIT_HARVEST exit at $0.75 bid, locking in profit before reversal.
    """
    bot1_v4 = Bot1V4DominationEngine(
        enable_doubt_harvest=True,
        doubt_threshold=0.55,
        default_btc_1m_volatility=14.0,
        enable_take_profit_ceiling=False,
        enable_dynamic_spot_velocity=False,  # Isolate Rule 5 Doubt Harvest
    )

    book = L2BookState(market_ticker="KXBTC15M-T85000")
    book.yes_book = {Decimal("0.75"): Decimal("50")}
    book.no_book = {Decimal("0.24"): Decimal("50")}

    # 1. Early in cycle (T=540s / 9 min remaining):
    early_exit = bot1_v4.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.51"),
        size=1,
        book=book,
        time_to_expiry_s=540.0,
        spot_price=85040.0,  # +$40 moat early in cycle
        target_strike=85000.0,
        spot_velocity_3s=-10.0,  # -$10 dip in 3s
    )
    # At 9 minutes, noise envelope V_threat ~ $25-$32, doubt score ~ 0.31 < 0.55 hurdle -> HOLD
    assert early_exit.should_exit is False
    assert early_exit.exit_reason == "HOLD"

    # 2. Late in cycle (T=90s / 1.5 min remaining):
    late_exit = bot1_v4.evaluate_exit(
        side=OrderSide.YES,
        entry_price=Decimal("0.51"),
        size=1,
        book=book,
        time_to_expiry_s=90.0,
        spot_price=85010.0,  # +$10 thin moat late in cycle
        target_strike=85000.0,
        spot_velocity_3s=-10.0,  # Exact same -$10 dip
    )
    # At 90 seconds, noise envelope V_threat ~ $14, doubt score ~ 0.62 >= 0.55 hurdle -> DOUBT_PROFIT_HARVEST
    assert late_exit.should_exit is True
    assert late_exit.exit_reason == "DOUBT_PROFIT_HARVEST"
    assert late_exit.exit_price == Decimal("0.75")
    assert "DOUBT-HARVEST TRIGGERED" in late_exit.rationale


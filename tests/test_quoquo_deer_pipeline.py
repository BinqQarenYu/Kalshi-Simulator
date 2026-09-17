import pytest
from decimal import Decimal
from kalshi_sim.quoquo.schemas import CondensedCycleTelemetry, CycleOutcome, VetoCategory
from kalshi_sim.quoquo.vault import QuoquoVault
from kalshi_sim.deer.scrubber import DeerScrubber

def test_deer_veto_classification():
    scrubber = DeerScrubber()
    assert scrubber.classify_veto_reason('Toxic Queue Depth Veto (Whale Armor): 4015 contracts resting ahead') == VetoCategory.WHALE_QUEUE
    assert scrubber.classify_veto_reason('Razor-Tight Proximity Veto (Dynamic Volatility Moat): |Diff|=12.5 < 16.1') == VetoCategory.RAZOR_TIGHT_MOAT
    assert scrubber.classify_veto_reason('Flow toxicity safe (0.15 < 0.60)') == VetoCategory.NONE
    assert scrubber.classify_veto_reason('High Toxicity Flow Veto (0.65 >= 0.60)') == VetoCategory.VPIN_TOXIC

def test_deer_scrubber_condensation_and_tokens(tmp_path):
    vault = QuoquoVault(vault_dir=tmp_path)
    scrubber = DeerScrubber()
    scrubber.vault = vault

    # Simulate 1,000 raw 20Hz ticks
    raw_ticks = [
        {'rationale': 'Razor-Tight Proximity Veto: |Diff|=13.2 < 16.1', 'spot_diff': 13.2, 'vpin': 0.18, 'queue_ahead': 50}
        for _ in range(1000)
    ]

    digest = scrubber.process_cycle_telemetry(
        cycle_ticker='KXBTC15M-26SEP160115-15',
        strike_price='85450.00',
        cycle_time_et='1:15 AM - 1:30 AM ET',
        raw_tick_events=raw_ticks,
    )

    assert digest.dominant_veto == VetoCategory.RAZOR_TIGHT_MOAT
    assert digest.outcome == CycleOutcome.CYCLE_HELD_VETO
    assert digest.raw_tokens_eliminated > 10000
    assert digest.condensed_token_cost < 300
    assert (tmp_path / 'cycles.jsonl').exists()
    assert (tmp_path / 'daily_digest.md').exists()

    recent = vault.get_recent_digests(limit=5)
    assert len(recent) == 1
    assert recent[0].cycle_ticker == 'KXBTC15M-26SEP160115-15'

def test_deer_trade_outcome_processing(tmp_path):
    vault = QuoquoVault(vault_dir=tmp_path)
    scrubber = DeerScrubber()
    scrubber.vault = vault

    trade_report = {
        'outcome': 'WIN',
        'bot_side': 'yes',
        'entry_price': 0.51,
        'contracts': 1,
        'pnl': 0.49,
    }

    digest = scrubber.process_cycle_telemetry(
        cycle_ticker='KXBTC15M-26SEP160130-15',
        strike_price='85500.00',
        cycle_time_et='1:30 AM - 1:45 AM ET',
        raw_tick_events=[],
        trade_report=trade_report,
    )

    assert digest.outcome == CycleOutcome.TRADE_FIRED_WIN
    assert digest.pnl == '0.49'
    assert digest.contracts == 1
    assert 'WIN' in digest.deer_briefing or 'favorable' in digest.deer_briefing

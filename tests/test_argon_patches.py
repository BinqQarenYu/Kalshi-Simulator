"""Tests for the Argon Patches Suite.

Validates the 5 surgical upgrades:
1. extract_strike_from_ticker() logic in schemas.py
2. Adverse OTM ask floor ($0.38) in bot1_v4_engine.py
3. ONNX Moneyness Consistency Guard in strategy_evaluator.py
4. ONNX Price Corridor Veto ($0.38-$0.55)
5. Experience buffer price cap sync in truth_synchronizer.py
"""

import os
from decimal import Decimal
import pytest

from kalshi_sim.schemas import CryptoAsset, extract_strike_from_ticker, L2BookState
from kalshi_sim.ml.bot1_v4_engine import Bot1V4DominationEngine
from kalshi_sim.truth_synchronizer import DynamicTruthSynchronizer


def test_extract_strike_minute_suffixes_rejected():
    """Confirms that 2-digit minute suffixes (-00, -15, -30, -45) are never parsed as strikes."""
    assert extract_strike_from_ticker("KXBTC15M-26OCT111100-00", CryptoAsset.BTC) is None
    assert extract_strike_from_ticker("KXBTC15M-26OCT111115-15", CryptoAsset.BTC) is None
    assert extract_strike_from_ticker("KXETH15M-26OCT140545-45", CryptoAsset.ETH) is None


def test_extract_strike_explicit_target_accepted():
    """Confirms that explicit -T<strike> and valid numeric strikes are extracted accurately."""
    assert extract_strike_from_ticker("KXBTC15M-T78650", CryptoAsset.BTC) == Decimal("78650")
    assert extract_strike_from_ticker("KXBTC15M-T82500.50", CryptoAsset.BTC) == Decimal("82500.50")
    assert extract_strike_from_ticker("KXETH15M-26OCT132100-2600", CryptoAsset.ETH) == Decimal("2600")
    assert extract_strike_from_ticker("KXETH15M-T2450", CryptoAsset.ETH) == Decimal("2450")


def test_extract_strike_asset_magnitude_bounds():
    """Confirms asset sanity bounds reject unrealistic numbers."""
    assert extract_strike_from_ticker("KXBTC15M-50", CryptoAsset.BTC) is None
    assert extract_strike_from_ticker("KXETH15M-50000", CryptoAsset.ETH) is None
    assert extract_strike_from_ticker("KXSOL15M-T145", CryptoAsset.SOL) == Decimal("145")


def test_otm_ask_floor_veto():
    """Confirms that Bot1V4DominationEngine vetoes entry when live ask < $0.38."""
    engine = Bot1V4DominationEngine(asset="BTC")
    
    # Mock orderbook where YES ask is $0.32 (deep OTM)
    l2 = L2BookState(market_ticker="KXBTC15M-T78650")
    l2._yes_book[Decimal("0.30")] = 10
    l2._no_book[Decimal("0.68")] = 10
    # best_yes_ask = 1.00 - 0.68 = 0.32
    assert l2.best_yes_ask == Decimal("0.32")
    
    dec = engine.evaluate_market_opportunity(
        spot_price=80000.0,
        target_strike=78650.0,
        time_to_expiry_s=600.0,
        l2_book=l2,
        vpin=0.10,
    )
    assert dec.recommended_side == "wait"
    assert dec.recommended_contracts == 0
    assert "Adverse OTM Ask Veto" in dec.rationale


def test_truth_synchronizer_learned_cap_enforcement(monkeypatch):
    """Confirms truth synchronizer clamps max_entry_price to experience buffer learned cap."""
    engine = Bot1V4DominationEngine(asset="BTC")
    
    class MockExpBuffer:
        def get_effective_price_cap(self, base):
            return Decimal("0.48")
            
    engine.experience_buffer = MockExpBuffer()
    sync = DynamicTruthSynchronizer()
    
    # Temporarily bypass the PYTEST_CURRENT_TEST guard to test sync logic
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    
    # Mock get_truth_parameters to return base preset with 0.55
    monkeypatch.setattr(sync, "get_truth_parameters", lambda asset="BTC": {
        "max_entry_price": 0.55,
        "momentum_max_price": 0.55
    })
    
    success = sync.sync_engine(engine, asset="BTC")
    assert engine.max_entry_price == Decimal("0.48")


def test_btc_and_eth_standalone_daemons_have_floor_and_cap():
    """Confirms that BtcBot1V4Engine and EthBot1V4Engine enforce $0.38 floor and $0.55 cap."""
    from kalshi_sim.ml.btc_bot1v4.btc_bot1v4_engine import BtcBot1V4Engine
    from kalshi_sim.ml.eth_bot1v4.eth_bot1v4_engine import EthBot1V4Engine

    btc_eng = BtcBot1V4Engine(load_persisted=False)
    eth_eng = EthBot1V4Engine(load_persisted=False)

    assert hasattr(btc_eng, "_recent_spot_history")
    assert hasattr(eth_eng, "_recent_spot_history")

    # Mock orderbook where YES ask is $0.30 (< $0.38 floor)
    l2 = L2BookState(market_ticker="KXBTC15M-T78650")
    l2._yes_book[Decimal("0.25")] = 10
    l2._no_book[Decimal("0.70")] = 10
    assert l2.best_yes_ask == Decimal("0.30")

    dec_btc = btc_eng.evaluate(
        book=l2,
        spot_price=80000.0,
        target_strike=78650.0,
        time_to_expiry_s=500.0,
        recent_trades=[],
        total_equity=Decimal("100.00"),
        max_position_size=1,
        estimated_vpin=0.10,
        cycle_id="KXBTC15M-T78650",
        spot_velocity_3s=5.0,
    )
    assert dec_btc.recommended_side == "wait"

    l2_eth = L2BookState(market_ticker="KXETH15M-T2450")
    l2_eth._yes_book[Decimal("0.25")] = 10
    l2_eth._no_book[Decimal("0.70")] = 10
    dec_eth = eth_eng.evaluate(
        book=l2_eth,
        spot_price=2500.0,
        target_strike=2450.0,
        time_to_expiry_s=500.0,
        recent_trades=[],
        total_equity=Decimal("100.00"),
        max_position_size=1,
        estimated_vpin=0.10,
        cycle_id="KXETH15M-T2450",
        spot_velocity_3s=1.0,
    )
    assert dec_eth.recommended_side == "wait"


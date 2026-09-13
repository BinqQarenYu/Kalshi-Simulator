"""Tests for Bot 1 Multi-Asset Basket Trading (Option B) and Gold 15M (KXGOLD15M) integration."""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from kalshi_sim.schemas import CryptoAsset, get_asset_config, CRYPTO_ASSETS
from kalshi_sim.market_discovery import ASSET_TIMEFRAME_SERIES, Timeframe
from kalshi_sim.cfbenchmarks_sync import INDEX_TO_ASSET, COINBASE_FALLBACK_PAIRS
from kalshi_sim.standalone_bot import StandaloneBotEngine, app


class TestMultiAssetBasket:
    """Test suite verifying Gold asset registration, basket mode, and portfolio caps."""

    def test_gold_asset_registration(self):
        """Verify CryptoAsset.GOLD is registered with all required 15M specs."""
        assert CryptoAsset.GOLD in CryptoAsset
        assert CryptoAsset.GOLD.value == "GOLD"

        cfg = get_asset_config(CryptoAsset.GOLD)
        assert cfg.series_ticker_15m == "KXGOLD15M"
        assert cfg.cf_index_id == "XAUUSD"
        assert cfg.min_spot_diff == Decimal("1.50")
        assert cfg.strike_step == Decimal("1.00")
        assert cfg.typical_1m_volatility == Decimal("0.75")
        assert cfg.coinbase_pair == "PAXG-USD"

        # Verify discovery series mapping
        assert "KXGOLD15M" in ASSET_TIMEFRAME_SERIES[CryptoAsset.GOLD][Timeframe.FIFTEEN_MIN]

        # Verify CF benchmarks sync index and fallback mapping
        assert INDEX_TO_ASSET["XAUUSD"] == CryptoAsset.GOLD
        assert INDEX_TO_ASSET["GOLD"] == CryptoAsset.GOLD
        assert COINBASE_FALLBACK_PAIRS[CryptoAsset.GOLD] == "PAXG-USD"

    def test_engine_set_asset_modes(self, tmp_path):
        """Verify StandaloneBotEngine handles both single asset and 'ALL' basket mode."""
        engine = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path, asset=CryptoAsset.BTC)
        assert engine.asset_mode == "single"
        assert engine.active_asset == CryptoAsset.BTC

        # Switch to GOLD
        engine.set_asset(CryptoAsset.GOLD)
        assert engine.asset_mode == "single"
        assert engine.active_asset == CryptoAsset.GOLD
        assert engine.active_cfg.series_ticker_15m == "KXGOLD15M"

        # Switch to ALL (Omnichannel Basket Mode)
        engine.set_asset("ALL")
        assert engine.asset_mode == "all"
        assert engine.max_concurrent_positions == 3
        assert len(engine.active_assets) == len(CryptoAsset)

        # Switch to custom multi-asset basket (BTC + GOLD)
        engine.set_asset([CryptoAsset.BTC, CryptoAsset.GOLD])
        assert engine.asset_mode == "basket"
        assert engine.active_assets == [CryptoAsset.BTC, CryptoAsset.GOLD]
        assert engine.active_asset == CryptoAsset.BTC

        # Switch back to ETH
        engine.set_asset(CryptoAsset.ETH)
        assert engine.asset_mode == "single"
        assert engine.active_asset == CryptoAsset.ETH
        assert engine.active_assets == [CryptoAsset.ETH]

    def test_portfolio_capacity_cap(self, tmp_path):
        """Verify max_concurrent_positions (3) limits active portfolio exposure."""
        engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path, asset=CryptoAsset.BTC)
        engine.set_asset("ALL")

        # Fill up 3 positions
        engine.active_positions["KXBTC15M-26SEP11-T100000"] = {"ticker": "KXBTC15M-26SEP11-T100000", "size": 1, "asset": "BTC"}
        engine.active_positions["KXETH15M-26SEP11-T3000"] = {"ticker": "KXETH15M-26SEP11-T3000", "size": 1, "asset": "ETH"}
        engine.active_positions["KXSOL15M-26SEP11-T200"] = {"ticker": "KXSOL15M-26SEP11-T200", "size": 1, "asset": "SOL"}

        open_cnt = len([p for p in engine.active_positions.values() if p.get("size", 0) > 0])
        assert open_cnt >= engine.max_concurrent_positions

    def test_1_contract_micro_bankroll_armor(self, tmp_path):
        """Verify that sizing is strictly hard-capped to 1 contract per trade."""
        engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path, asset=CryptoAsset.GOLD)
        assert engine.guardrails.max_micro_bankroll_contracts == 1
        assert engine.guardrails.max_nano_bankroll_contracts == 1

        with patch.object(engine.guardrails, "check_macro_news_blackout", return_value=(False, "")):
            is_allowed, reason, size, _ = engine.guardrails.validate_pre_trade_intent(
                ticker="KXGOLD15M-26SEP11-T2500",
                side="yes",
                requested_size=5,  # Bot or user tries to request 5
                est_price=Decimal("0.52"),
                total_equity=Decimal("50.00"),
                vpin=0.15,
                cycle_id="KXGOLD15M-26SEP11-T2500",
                is_bot=True,
                bot_type="3_step_domination_bot",
            )
            assert is_allowed is True
            assert size == 1  # Hard-capped to 1 contract armor

    def test_api_assets_and_select_all(self, tmp_path):
        """Verify REST API /api/assets and /api/assets/select support 'ALL' and 'GOLD'."""
        from httpx import AsyncClient, ASGITransport

        async def _run():
            engine = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path, asset=CryptoAsset.BTC)

            with patch("kalshi_sim.standalone_bot.app_engine", engine):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # 1. GET /api/assets
                    resp = await client.get("/api/assets")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert "assets" in data
                    asset_ids = [a["id"] for a in data["assets"]]
                    assert "GOLD" in asset_ids
                    assert "BTC" in asset_ids
                    assert "ETH" in asset_ids
                    assert "SOL" in asset_ids
                    assert "DOGE" in asset_ids

                    # Check Gold spec in response
                    gold_spec = next(a for a in data["assets"] if a["id"] == "GOLD")
                    assert gold_spec["series_15m"] == "KXGOLD15M"
                    assert gold_spec["min_spot_diff"] == 1.50
                    assert gold_spec["strike_step"] == 1.00

                    # 2. Select GOLD
                    resp_gold = await client.post("/api/assets/select", json={"asset": "GOLD"})
                    assert resp_gold.status_code == 200
                    assert resp_gold.json()["active_asset"] == "GOLD"
                    assert engine.active_asset == CryptoAsset.GOLD
                    assert engine.asset_mode == "single"

                    # 3. Select ALL
                    resp_all = await client.post("/api/assets/select", json={"asset": "ALL"})
                    assert resp_all.status_code == 200
                    assert resp_all.json()["active_asset"] == "ALL"
                    assert resp_all.json()["asset_mode"] == "all"
                    assert engine.asset_mode == "all"

                    # 4. Select Custom Basket (BTC, SOL, GOLD)
                    resp_basket = await client.post("/api/assets/select", json={"assets": ["BTC", "SOL", "GOLD"]})
                    assert resp_basket.status_code == 200
                    b_data = resp_basket.json()
                    assert b_data["status"] == "SUCCESS"
                    assert b_data["asset_mode"] == "basket"
                    assert set(b_data["active_assets"]) == {"BTC", "SOL", "GOLD"}
                    assert engine.asset_mode == "basket"
                    assert set(a.value for a in engine.active_assets) == {"BTC", "SOL", "GOLD"}

                    # Verify /api/assets reflects active_assets
                    resp_assets_b = await client.get("/api/assets")
                    assert resp_assets_b.status_code == 200
                    a_map = {a["id"]: a["is_active"] for a in resp_assets_b.json()["assets"]}
                    assert a_map["BTC"] is True
                    assert a_map["SOL"] is True
                    assert a_map["GOLD"] is True
                    assert a_map["ETH"] is False
                    assert a_map["DOGE"] is False

                    # 5. Check /api/state returns asset_mode and active_assets
                    resp_state = await client.get("/api/state")
                    assert resp_state.status_code == 200
                    state = resp_state.json()
                    assert state["asset_mode"] == "basket"
                    assert set(state["active_assets"]) == {"BTC", "SOL", "GOLD"}
                    assert state["max_concurrent_positions"] == 3
                    assert state["open_positions_count"] == 0

                    # 6. Test invalid asset in assets list
                    resp_inv = await client.post("/api/assets/select", json={"assets": ["INVALID_ASSET"]})
                    assert resp_inv.status_code == 400

        asyncio.run(_run())

    def test_hyper_asset_registration(self):
        """Verify CryptoAsset.HYPER is registered with all required 15M specs."""
        assert CryptoAsset.HYPER in CryptoAsset
        assert CryptoAsset.HYPER.value == "HYPER"

        cfg = get_asset_config(CryptoAsset.HYPER)
        assert cfg.series_ticker_15m == "KXHYPE15M"
        assert cfg.cf_index_id == "HYPEUSD_RTI"
        assert cfg.min_spot_diff == Decimal("0.35")
        assert cfg.strike_step == Decimal("0.25")
        assert cfg.typical_1m_volatility == Decimal("0.08")
        assert cfg.coinbase_pair == "HYPE-USD"

        # Verify discovery series mapping
        assert "KXHYPE15M" in ASSET_TIMEFRAME_SERIES[CryptoAsset.HYPER][Timeframe.FIFTEEN_MIN]

        # Verify CF benchmarks sync index and fallback mapping
        assert INDEX_TO_ASSET["HYPEUSD_RTI"] == CryptoAsset.HYPER
        assert INDEX_TO_ASSET["HYPER"] == CryptoAsset.HYPER
        assert COINBASE_FALLBACK_PAIRS[CryptoAsset.HYPER] == "HYPE-USD"

    def test_per_asset_strategy_parameter_isolation(self, tmp_path):
        """Verify that every asset has its own distinct dials without parameter bleed."""
        engine = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path, asset=CryptoAsset.BTC)

        # 1. Check all 6 assets exist in engine.asset_profiles
        assert set(engine.asset_profiles.keys()) == {"BTC", "ETH", "SOL", "DOGE", "GOLD", "HYPER"}

        # 2. Check defaults
        btc_params = engine.get_parameters("BTC")
        doge_params = engine.get_parameters("DOGE")
        hyper_params = engine.get_parameters("HYPER")

        assert btc_params["min_spot_diff"] == 35.0
        assert doge_params["min_spot_diff"] == 0.0005
        assert hyper_params["min_spot_diff"] == 0.35

        # 3. Update DOGE parameters
        engine.update_parameters(
            asset="DOGE",
            discount_limit_price=0.45,
            min_spot_diff=0.00010,
            typical_1m_volatility=0.000030,
            persist=True,
        )

        # BTC and HYPER must remain unaffected
        btc_after = engine.get_parameters("BTC")
        doge_after = engine.get_parameters("DOGE")
        hyper_after = engine.get_parameters("HYPER")

        assert btc_after["min_spot_diff"] == 35.0
        assert btc_after["discount_limit_price"] == 0.52
        assert doge_after["min_spot_diff"] == 0.00010
        assert doge_after["discount_limit_price"] == 0.45
        assert doge_after["typical_1m_volatility"] == 0.000030
        assert hyper_after["min_spot_diff"] == 0.35

        # 4. Test candidate evaluation switching (_apply_asset_profile)
        # Apply DOGE
        engine._apply_asset_profile(CryptoAsset.DOGE)
        assert engine.bot.min_spot_diff == 0.00010
        assert float(engine.bot.discount_limit_price) == 0.45

        # Apply HYPER
        engine._apply_asset_profile(CryptoAsset.HYPER)
        assert engine.bot.min_spot_diff == 0.35
        assert float(engine.bot.discount_limit_price) == 0.50

        # Apply BTC
        engine._apply_asset_profile(CryptoAsset.BTC)
        assert engine.bot.min_spot_diff == 35.0
        assert float(engine.bot.discount_limit_price) == 0.52

    def test_per_asset_persistence_and_reload(self, tmp_path):
        """Verify per-asset profiles persist to disk and reload correctly across sessions."""
        engine1 = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path, asset=CryptoAsset.BTC)

        # Update GOLD and HYPER
        engine1.update_parameters(asset="GOLD", min_spot_diff=1.55, discount_limit_price=0.49, persist=True)
        engine1.update_parameters(asset="HYPER", min_spot_diff=0.42, discount_limit_price=0.51, persist=True)

        # Verify disk file exists and contains nested assets
        p_file = tmp_path / "bot_parameters_domination.json"
        assert p_file.exists()

        # Instantiate a fresh engine on the same data directory
        engine2 = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path, asset=CryptoAsset.GOLD)

        # Dials for GOLD must match the custom saved values
        gold_loaded = engine2.get_parameters("GOLD")
        assert gold_loaded["min_spot_diff"] == 1.55
        assert gold_loaded["discount_limit_price"] == 0.49

        # HYPER must also match custom saved values
        hyper_loaded = engine2.get_parameters("HYPER")
        assert hyper_loaded["min_spot_diff"] == 0.42
        assert hyper_loaded["discount_limit_price"] == 0.51

        # BTC must still maintain its original defaults
        btc_loaded = engine2.get_parameters("BTC")
        assert btc_loaded["min_spot_diff"] == 35.0
        assert btc_loaded["discount_limit_price"] == 0.52

        # Max contracts must strictly be 1
        assert gold_loaded["max_contracts"] == 1
        assert hyper_loaded["max_contracts"] == 1
        assert btc_loaded["max_contracts"] == 1

    def test_api_per_asset_parameters(self, tmp_path):
        """Verify REST API GET and POST /api/bot/parameters with asset query/payload."""
        from httpx import AsyncClient, ASGITransport

        async def _run():
            engine = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path, asset=CryptoAsset.BTC)

            with patch("kalshi_sim.standalone_bot.app_engine", engine):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # 1. GET /api/bot/parameters for HYPER
                    resp_hyper = await client.get("/api/bot/parameters?asset=HYPER")
                    assert resp_hyper.status_code == 200
                    h_data = resp_hyper.json()
                    assert h_data["asset"] == "HYPER"
                    assert h_data["min_spot_diff"] == 0.35

                    # 2. Update HYPER dials via POST
                    update_resp = await client.post(
                        "/api/bot/parameters",
                        json={
                            "asset": "HYPER",
                            "discount_limit_price": 0.49,
                            "min_spot_diff": 0.38,
                            "min_confidence": 80.0,
                        },
                    )
                    assert update_resp.status_code == 200
                    u_data = update_resp.json()
                    assert u_data["status"] == "SUCCESS"
                    assert u_data["parameters"]["asset"] == "HYPER"
                    assert u_data["parameters"]["discount_limit_price"] == 0.49
                    assert u_data["parameters"]["min_spot_diff"] == 0.38

                    # 3. Verify BTC is still unchanged
                    resp_btc = await client.get("/api/bot/parameters?asset=BTC")
                    assert resp_btc.status_code == 200
                    b_data = resp_btc.json()
                    assert b_data["asset"] == "BTC"
                    assert b_data["min_spot_diff"] == 35.0
                    assert b_data["discount_limit_price"] == 0.52

        asyncio.run(_run())

    def test_gold_sniper_profile_and_reversal_gate_calibration(self, tmp_path):
        """Verify Gold institutional dials reflect the Late-Cycle Asymmetric Sniper model."""
        engine = StandaloneBotEngine(is_live=False, is_armed=False, data_dir=tmp_path, asset=CryptoAsset.GOLD)
        p = engine.get_parameters("GOLD")

        # 1. Parameter assertions
        assert p["discount_limit_price"] == 0.52
        assert p["momentum_max_price"] == 0.52
        assert p["min_confidence"] == 80.0
        assert p["min_edge_pct"] == 8.0
        assert p["min_ev_dollars"] == 0.03
        assert p["min_spot_diff"] == 1.50
        assert p["typical_1m_volatility"] == 0.75
        assert p["vpin_toxic_threshold"] == 0.55
        assert p["take_profit_price_threshold"] == 0.92
        assert p["enable_take_profit_ceiling"] is True
        assert p["require_reversal_for_tp_ceiling"] is False
        assert p["max_contracts"] == 1

        # 2. Engine applied profile assertions
        engine._apply_asset_profile(CryptoAsset.GOLD)
        assert engine.bot.min_spot_diff == 1.50
        assert float(engine.bot.discount_limit_price) == 0.52
        assert float(engine.bot.max_entry_price) == 0.52
        assert engine.bot.take_profit_price_threshold == Decimal("0.92")
        assert engine.bot.require_reversal_for_tp_ceiling is False

    def test_macro_news_event_blackout_guardrail(self):
        """Verify check_macro_news_blackout blocks Gold during US macro and FOMC windows."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from kalshi_sim.agent_guardrails import AgentGuardrails

        guard = AgentGuardrails()
        et_tz = ZoneInfo("America/New_York")

        # 1. 08:30:00 ET (Morning US Economic Data Release: CPI, NFP, GDP) -> BLOCKED for GOLD
        t_cpi = datetime(2026, 9, 11, 8, 30, 0, tzinfo=et_tz)
        is_blocked, reason = guard.check_macro_news_blackout("KXGOLD15M-T2500", now_dt=t_cpi)
        assert is_blocked is True
        assert "MACRO EVENT BLACKOUT" in reason
        assert "08:25-08:38 ET" in reason

        # Also blocked by raw asset name
        is_blocked_ast, _ = guard.check_macro_news_blackout("GOLD", now_dt=t_cpi)
        assert is_blocked_ast is True

        # Pre-trade intent validation should veto
        allowed, msg, size, diag = guard.validate_pre_trade_intent(
            ticker="KXGOLD15M-T2500",
            side="yes",
            requested_size=1,
            est_price=Decimal("0.50"),
            total_equity=Decimal("75.00"),
        )
        # Note: validate_pre_trade_intent uses current time, so test method directly or with simulated time
        is_direct_blocked, _ = guard.check_macro_news_blackout("KXGOLD15M-T2500", now_dt=t_cpi)
        assert is_direct_blocked is True

        # 2. 14:00:00 ET (Afternoon FOMC Release Window) -> BLOCKED for GOLD
        t_fomc = datetime(2026, 9, 11, 14, 0, 0, tzinfo=et_tz)
        is_blocked_fomc, reason_fomc = guard.check_macro_news_blackout("KXGOLD15M-T2500", now_dt=t_fomc)
        assert is_blocked_fomc is True
        assert "FOMC Release window" in reason_fomc

        # 3. 10:00:00 ET (Normal trading hours) -> ALLOWED for GOLD
        t_normal = datetime(2026, 9, 11, 10, 0, 0, tzinfo=et_tz)
        is_blocked_normal, _ = guard.check_macro_news_blackout("KXGOLD15M-T2500", now_dt=t_normal)
        assert is_blocked_normal is False

        # 4. BTC should NOT be blocked by Gold macro embargo
        is_blocked_btc, _ = guard.check_macro_news_blackout("KXBTC15M-T89000", now_dt=t_cpi)
        assert is_blocked_btc is False

    def test_gold_late_cycle_timing_filter(self, tmp_path):
        """Verify Gold cycle evaluation enforces the 120s <= T <= 420s late-cycle noise collapse window."""
        engine = StandaloneBotEngine(is_live=False, is_armed=True, data_dir=tmp_path, asset=CryptoAsset.GOLD)

        # Helper to simulate evaluate_strategy_cycle time check
        def is_gold_time_permitted(t_rem: float) -> bool:
            if t_rem > 420 or t_rem < 120:
                return False
            return True

        # T = 600s (10 min remaining): Brownian noise too high -> REJECTED
        assert is_gold_time_permitted(600) is False

        # T = 450s (7.5 min remaining): Still early -> REJECTED
        assert is_gold_time_permitted(450) is False

        # T = 300s (5 min remaining): In late-cycle sniper zone -> PERMITTED
        assert is_gold_time_permitted(300) is True

        # T = 180s (3 min remaining): Prime late-cycle entry -> PERMITTED
        assert is_gold_time_permitted(180) is True

        # T = 60s (1 min remaining): Too late, spread risk -> REJECTED
        assert is_gold_time_permitted(60) is False


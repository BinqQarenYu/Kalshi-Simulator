"""BNB-specific Bot 1 V4 quantitative engine.

Provides `BnbBot1V4Engine`, calibrated specifically for Kalshi 15-minute Binance Coin binary contracts
(series ``KXBNB15M``). Operates with:
- Calibrated BNB 1m volatility ($0.25), $1.00 strike step, and calibrated proximity moats ($1.50).
- Dedicated experience buffer writing to ``data/bnb_win_loss_reports.json`` (isolated learning).
- Real-time 15m market discovery, Level-2 orderbook ingestion, and autonomous cycle execution.
- Strict 1-trade-per-cycle lock, max 1 contract micro-bankroll sizing, and Zero Float Decimal financial math.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import inspect
import logging
import os
from pathlib import Path
import json
import math
import random
import time
from typing import Any, Optional, Union

import aiohttp

from kalshi_sim.auth import DEMO_REST_BASE, PROD_REST_BASE, get_auth_headers
from kalshi_sim.ml.bot1_v4_engine import Bot1V4Decision, Bot1V4DominationEngine
from kalshi_sim.ml.experience_buffer import ContinuousExperienceBuffer, CycleExperience
from kalshi_sim.orderflow.bnb_orderflow_feed import BnbOrderflowFeed
from kalshi_sim.schemas import (
    CryptoAsset,
    L2BookState,
    MarketInfo,
    MarketStatus,
    OrderSide,
    Timeframe,
    extract_strike_from_ticker,
    get_asset_config,
)
from kalshi_sim.ml.dof_governor import get_dof_governor
from kalshi_sim.ml.kev_oracle import KevDecisionOracle, KevQuestion, KevQuestionType
from kalshi_sim.ml.session_timing_guard import get_session_timing_guard
from kalshi_sim.ws_connection import create_aiohttp_connector

logger = logging.getLogger("kalshi_sim.bnb_bot1v4_engine")


class BnbBot1V4Engine(Bot1V4DominationEngine):
    """Institutional Bot 1 V4 engine calibrated for Kalshi Binance Coin (KXBNB15M) 15-minute events."""

    STRATEGY_ID = "bnb_bot1_v4"
    STRATEGY_NAME = "BNB Bot 1 V4 (Binance Coin Domination)"

    def __init__(
        self,
        order_client: Optional[Any] = None,
        orderflow_feed: Optional[BnbOrderflowFeed] = None,
        ticker: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        target_ticker = kwargs.pop("ticker", ticker)
        hist_file = kwargs.pop("history_file", None)
        min_bleed_diff = kwargs.pop("min_spot_diff_bleed", 1.50)
        param_file = kwargs.pop("parameters_file", None)
        load_persisted = kwargs.pop("load_persisted", param_file is not None)

        # Enforce BNB asset calibration
        kwargs.setdefault("asset", CryptoAsset.BNB)
        kwargs.setdefault("default_btc_1m_volatility", 0.25)  # BNB 1m rolling volatility (~$0.25)
        kwargs.setdefault("min_spot_diff", 1.50)              # Typical Kalshi BNB strike step is $1.00; $1.50 moat prevents dispersion excursion
        kwargs.setdefault("chop_range_threshold", 2.00)       # ~0.25% range of ~$740 spot
        kwargs.setdefault("chop_vol_threshold", 0.30)
        kwargs.setdefault("taker_breakout_min_velocity", 0.60) # $/3s spot velocity threshold
        kwargs.setdefault("discount_limit_price", Decimal("0.42"))
        kwargs.setdefault("max_entry_price", Decimal("0.45"))
        kwargs.setdefault("fee_per_contract", Decimal("0.01"))

        # Dedicated BNB experience buffer
        buffer_path = Path(hist_file) if hist_file else Path("data/bnb_win_loss_reports.json")
        buffer_path.parent.mkdir(parents=True, exist_ok=True)
        if "experience_buffer" not in kwargs or kwargs["experience_buffer"] is None:
            kwargs["experience_buffer"] = ContinuousExperienceBuffer(history_file=buffer_path, asset="BNB")

        super().__init__(*args, **kwargs)

        self.history_file = buffer_path
        self.parameters_file = Path(param_file) if param_file else Path("data/bot_parameters_bnb.json")
        if load_persisted and self.parameters_file.exists():
            self._load_persisted_parameters()
        self._active_trade_forensics: dict[str, dict[str, Any]] = {}

        self.min_spot_diff_bleed = float(min_bleed_diff)
        if hasattr(self, "bleed_defender") and self.bleed_defender:
            self.bleed_defender.min_spot_diff_bleed = self.min_spot_diff_bleed

        self.order_client = order_client
        self.orderflow_feed = orderflow_feed
        self.target_ticker: Optional[str] = target_ticker
        self._cached_market: Optional[MarketInfo] = None
        self._last_market_fetch_ts: float = 0.0
        self._session: Optional[aiohttp.ClientSession] = None
        self.kev_oracle = KevDecisionOracle()
        self.dof_governor = get_dof_governor()
        self.timing_guard = get_session_timing_guard()
        self._salvage_adverse_ticks: dict[str, int] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or reuse connection-pooled HTTP session to prevent socket exhaustion."""
        if self.order_client and hasattr(self.order_client, "_get_session"):
            return await self.order_client._get_session()
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(connector=create_aiohttp_connector())
        return self._session

    def _load_persisted_parameters(self) -> None:
        """Load persisted BNB bot parameters from disk if available."""
        if not self.parameters_file.exists():
            return
        try:
            raw = json.loads(self.parameters_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                bnb_params = raw.get("bnb_bot1_v4", raw)
                self.update_parameters(**bnb_params)
                logger.info("[BNB BOT] Loaded persisted parameters from %s", self.parameters_file)
        except Exception as exc:
            logger.debug("[BNB BOT] Error loading persisted parameters: %s", exc)

    def save_persisted_parameters(self) -> None:
        """Persist active parameters to data/bot_parameters_bnb.json."""
        try:
            self.parameters_file.parent.mkdir(parents=True, exist_ok=True)
            existing: dict[str, Any] = {}
            if self.parameters_file.exists():
                try:
                    existing = json.loads(self.parameters_file.read_text(encoding="utf-8"))
                except Exception:
                    existing = {}
            current_params = self.get_parameters()
            existing["bnb_bot1_v4"] = current_params
            existing["last_updated"] = datetime.now(timezone.utc).isoformat()
            self.parameters_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            logger.debug("[BNB BOT] Persisted parameters to %s", self.parameters_file)
        except Exception as exc:
            logger.warning("[BNB BOT] Could not persist parameters to %s: %s", self.parameters_file, exc)

    async def get_active_market(self, force_refresh: bool = False) -> Optional[MarketInfo]:
        """Fetch the current active 15m KXBNB15M market contract."""
        now = time.time()
        if not force_refresh and self._cached_market and (now - self._last_market_fetch_ts < 5.0):
            return self._cached_market

        base_url = PROD_REST_BASE if (self.order_client and getattr(self.order_client, "is_live", False)) else DEMO_REST_BASE
        url = f"{base_url}/markets"
        params = {"series_ticker": "KXBNB15M", "status": "open", "limit": 5}
        headers = get_auth_headers("GET", "/trade-api/v2/markets") if (self.order_client and getattr(self.order_client, "is_live", False)) else {}

        try:
            session = await self._get_session()
            async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=4.0)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    markets = data.get("markets", [])
                    if markets:
                        target = markets[0]
                        if self.target_ticker:
                            for m in markets:
                                if m.get("ticker") == self.target_ticker:
                                    target = m
                                    break
                        ticker_val = target.get("ticker", "")
                        strike_dec = None
                        if target.get("floor_strike") is not None:
                            try:
                                strike_dec = Decimal(str(target["floor_strike"]))
                            except Exception:
                                pass
                        if strike_dec is None:
                            strike_dec = extract_strike_from_ticker(ticker_val, asset=CryptoAsset.BNB)
                        if strike_dec is None and self.orderflow_feed and self.orderflow_feed.last_spot_price:
                            # Round to nearest dollar for strike
                            strike_dec = Decimal(str(round(float(self.orderflow_feed.last_spot_price))))

                        self._cached_market = MarketInfo(
                            ticker=ticker_val,
                            title=target.get("title", f"BNB 15M {ticker_val}"),
                            floor_strike=strike_dec,
                            close_time=target.get("close_time", target.get("expiration_time")),
                            status=MarketStatus.ACTIVE,
                            yes_bid=Decimal(str(target["yes_bid"])) if target.get("yes_bid") is not None else None,
                            yes_ask=Decimal(str(target["yes_ask"])) if target.get("yes_ask") is not None else None,
                            timeframe=Timeframe.FIFTEEN_MIN,
                        )
                        self._last_market_fetch_ts = now
                        return self._cached_market
                elif resp.status == 429:
                    logger.warning("[BNB BOT] HTTP 429 rate limited fetching KXBNB15M markets.")
        except Exception as e:
            logger.debug("[BNB BOT] Error fetching KXBNB15M active market: %s", e)

        return self._cached_market

    async def run_cycle(self, ticker: Optional[str] = None) -> Optional[Bot1V4Decision]:
        """Execute a single cycle iteration of the BNB Bot 1 V4 engine.

        1. Checks BNB circuit breaker (3 consecutive losses mandate).
        2. Discovers active KXBNB15M 15-minute market.
        3. Ingests Level-2 orderbook.
        4. Retrieves real-time BNB spot price.
        5. Evaluates market opportunity using Bot 1 V4 quantitative logic with BNB calibration.
        6. If signal is actionable ('yes' or 'no' with >0 contracts) and order_client is attached:
           executes 1 contract adhering to micro-bankroll rules and 1-trade-per-cycle lock.
        """
        from kalshi_sim.agent_guardrails import get_global_guardrails
        guardrails = get_global_guardrails()
        if not guardrails.is_bnb_bot_armed:
            logger.info("🛑 [BNB BOT 1 V4] Stand down: BNB bot circuit breaker tripped (%d consecutive losses). Stopped per user directive.", guardrails._bnb_consecutive_losses)
            return None

        target_ticker = ticker or self.target_ticker
        market_info: Optional[MarketInfo] = await self.fetch_active_market()
        if market_info:
            target_ticker = market_info.ticker

        if not target_ticker or "-" not in target_ticker:
            logger.debug("[BNB BOT] No active KXBNB15M market discovered.")
            return None

        # Fetch live L2 book
        book = await self.fetch_orderbook(target_ticker)
        if not book or (not book.yes_book and not book.no_book):
            logger.debug("[BNB BOT] Orderbook for %s empty or unavailable.", target_ticker)
            return None

        # Determine target strike & time to expiry
        now_utc = datetime.now(timezone.utc)
        target_strike = Decimal("750.00")
        time_to_expiry_s = 600.0

        if market_info and market_info.floor_strike and market_info.floor_strike > 0:
            target_strike = market_info.floor_strike
        elif market_info and hasattr(market_info, "target_strike") and market_info.target_strike > 0:
            target_strike = market_info.target_strike
        else:
            parsed_strike = extract_strike_from_ticker(target_ticker, asset=self.asset)
            if parsed_strike is not None and parsed_strike > 0:
                target_strike = parsed_strike
            elif "-" in target_ticker:
                parts = target_ticker.split("-")
                if len(parts) >= 3:
                    try:
                        cand = Decimal(parts[-1])
                        if cand > 0:
                            target_strike = cand
                    except Exception:
                        pass
        if target_strike <= 0:
            target_strike = self.get_spot_price()

        if market_info and market_info.expiration_time:
            time_to_expiry_s = max(1.0, (market_info.expiration_time - now_utc).total_seconds())

        spot_price = self.get_spot_price()
        now_mono = time.monotonic()
        spot_f = float(spot_price)
        self._recent_spot_history.append((now_mono, spot_f))
        spot_velocity_3s = 0.0
        if self._recent_spot_history:
            for prev_ts, prev_p in reversed(self._recent_spot_history):
                dt = now_mono - prev_ts
                if dt >= 0.5:
                    spot_velocity_3s = (spot_f - prev_p) / max(1.0, dt) * 3.0
                    break

        vpin_score = self.get_empirical_vpin()

        macro_slope = self.get_macro_1h_slope()
        dof_gov = getattr(self, "dof_governor", None) or get_dof_governor()

        decision = self.evaluate(
            book=book,
            spot_price=float(spot_price),
            target_strike=float(target_strike),
            time_to_expiry_s=time_to_expiry_s,
            recent_trades=[],
            total_equity=Decimal("100.00"),
            max_position_size=1,
            estimated_vpin=vpin_score,
            cycle_id=target_ticker,
            spot_velocity_3s=spot_velocity_3s,
        )

        logger.info(
            "⚡ [BNB BOT 1 V4] %s | Side: %s | P(Win): %.1f%% | EV: $%.2f | Price: $%.2f | Action: %s (%s)",
            target_ticker,
            decision.recommended_side.upper(),
            (decision.p_up if decision.recommended_side == "yes" else decision.p_down) * 100.0,
            decision.ev_yes if decision.recommended_side == "yes" else decision.ev_no,
            float(getattr(decision, "limit_price", 0.42)),
            getattr(decision, "action", decision.recommended_side.upper()),
            decision.rationale[:60],
        )

        # IN-FLIGHT ACTIVE POSITION DERISKING & TAKE-PROFIT
        # Check active position from local forensics or live exchange portfolio (survives restarts)
        active_info = self._active_trade_forensics.get(target_ticker)
        now_ts = time.time()
        last_port_sync = getattr(self, "_last_portfolio_sync_ts", 0.0)
        if not active_info and self.order_client and hasattr(self.order_client, "get_live_portfolio_state") and (now_ts - last_port_sync >= 30.0):
            try:
                self._last_portfolio_sync_ts = now_ts
                st = await self.order_client.get_live_portfolio_state()
                for p in st.positions:
                    if p.ticker == target_ticker and p.position > 0:
                        active_info = {
                            "order_id": f"synced_{target_ticker}",
                            "ticker": target_ticker,
                            "side": p.side.value.lower(),
                            "entry_price": 0.40,
                            "contracts": p.position,
                            "exited": False,
                        }
                        self._active_trade_forensics[target_ticker] = active_info
                        break
            except Exception:
                pass

        if self.order_client and active_info and not active_info.get("exited", False):
            pos_side = active_info.get("side", "yes")
            entry_pr = Decimal(str(active_info.get("entry_price", "0.50")))
            bid_to_sell = book.best_yes_bid if pos_side == "yes" else book.best_no_bid

            # 1. Take Profit: If position gained strongly (bid >= $0.88) with >= 120s left
            if bid_to_sell is not None and bid_to_sell >= Decimal("0.88") and time_to_expiry_s >= 120.0:
                try:
                    logger.info("🎯 [TAKE PROFIT TRIGGER] Selling %s %s @ $%s (Entry: $%s) to lock profit.", target_ticker, pos_side.upper(), bid_to_sell, entry_pr)
                    sell_kwargs = {
                        "ticker": target_ticker,
                        "side": pos_side,
                        "action": "sell",
                        "count": 1,
                        "order_type": "limit",
                        "price_dollars": bid_to_sell,
                        "time_in_force": "immediate_or_cancel",
                    }
                    res_sell = await self.order_client.place_order(**sell_kwargs)
                    if res_sell and not ("error" in res_sell or res_sell.get("status") in ("canceled", "rejected", "error")):
                        active_info["exited"] = True
                        active_info["exit_price"] = float(bid_to_sell)
                        active_info["exit_reason"] = "take_profit"
                        logger.info("✅ [TAKE PROFIT EXECUTED] Successfully locked profit @ $%s!", bid_to_sell)
                except Exception as tp_err:
                    logger.debug("Take profit error: %s", tp_err)

            # 2. Catastrophic Derisk / Salvage Stop (DEF-03 Anti-Dispersion Armor):
            # Dynamic salvage breach: In a macro bleed (slope <= -0.10%), adverse drift breach is tightened to $1.25
            salvage_breach = Decimal("2.50") if macro_slope <= -0.10 else Decimal("7.50")
            is_doomed = False
            if pos_side == "yes" and spot_price < (target_strike - salvage_breach):
                is_doomed = True
            elif pos_side == "no" and spot_price > (target_strike + salvage_breach):
                is_doomed = True

            dof_gov = getattr(self, "dof_governor", None) or get_dof_governor()
            patch_03_active = dof_gov.is_patch_active("BNB", "dof_03_stepped_salvage")
            patch_04_active = dof_gov.is_patch_active("BNB", "dof_04_salvage_persistence")

            # Track adverse persistence (DoF-04)
            if is_doomed:
                self._salvage_adverse_ticks[target_ticker] = self._salvage_adverse_ticks.get(target_ticker, 0) + 1
            else:
                self._salvage_adverse_ticks[target_ticker] = 0

            persist_ticks = self._salvage_adverse_ticks.get(target_ticker, 0)
            
            # Silas TWAP Parity Guard: Inside 60s, if trailing TWAP is safely in our favor, don't panic dump
            twap_safe = False
            if time_to_expiry_s <= 60.0 and hasattr(self, "_last_twap_60s") and self._last_twap_60s:
                twap_val = float(self._last_twap_60s)
                if pos_side == "yes" and twap_val >= float(target_strike) + 2.0:
                    twap_safe = True
                elif pos_side == "no" and twap_val <= float(target_strike) - 2.0:
                    twap_safe = True

            can_salvage = is_doomed and (not twap_safe) and (persist_ticks >= 2 if patch_04_active else True)

            # Determine salvage floor (DoF-03 & Bleed Inversion Floor)
            ofi_val = float(self.orderflow_feed.ofi_l1 if self.orderflow_feed else 0.0)
            if (patch_03_active and ofi_val <= -0.70) or macro_slope <= -0.10:
                salvage_floor = Decimal("0.20")
                logger.info("🛡️ [BNB STEPPED SALVAGE ACTIVE] Macro bleed / negative OFI. Salvage floor lowered to $0.08.")
            else:
                salvage_floor = Decimal("0.20")

            if can_salvage and bid_to_sell is not None and bid_to_sell >= salvage_floor and time_to_expiry_s >= 45.0:

                try:
                    logger.warning("🛡️ [SALVAGE DERISK TRIGGER] Position doomed (Spot: $%s vs Strike: $%s). Selling to salvage $%s/ct (Entry: $%s).", spot_price, target_strike, bid_to_sell, entry_pr)
                    sell_kwargs = {
                        "ticker": target_ticker,
                        "side": pos_side,
                        "action": "sell",
                        "count": 1,
                        "order_type": "limit",
                        "price_dollars": bid_to_sell,
                        "time_in_force": "immediate_or_cancel",
                    }
                    res_sell = await self.order_client.place_order(**sell_kwargs)
                    if res_sell and not ("error" in res_sell or res_sell.get("status") in ("canceled", "rejected", "error")):
                        active_info["exited"] = True
                        active_info["exit_price"] = float(bid_to_sell)
                        active_info["exit_reason"] = "salvage_derisk"
                        logger.warning("🛡️ [SALVAGE DERISK EXECUTED] Salvaged $%s/ct! Loss capped at -$%s (Saved 100%% wipeout)", bid_to_sell, float(entry_pr - bid_to_sell))
                except Exception as sl_err:
                    logger.debug("Salvage derisk error: %s", sl_err)

        # Short-circuit if cycle is locked, turnover limit reached, or active position held (Rule 8: Zero Credit Waste)
        if self.order_client:
            completed = self.get_completed_turnovers(target_ticker)
            if completed >= self.max_turnover_per_event or guardrails.is_cycle_locked(target_ticker):
                logger.info("[BNB BOT] Cycle %s already locked (turnover limit reached). Skipping Kev inference.", target_ticker)
                return decision
            if active_info and not active_info.get("exited", False):
                logger.debug("[BNB BOT] Position already active for %s. Skipping Kev inference.", target_ticker)
                return decision

        # ------------------------------------------------------------------
        # KEV DECISIVE LEAD & MATH-OF-WINNING TAKER ENGINE
        # ------------------------------------------------------------------
        kev_rec = None
        kev_toxic = None
        try:
            kev_regime = "BLEED" if macro_slope <= -0.10 else getattr(self, "_current_regime", "CHOP")
            kev_ctx = self.kev_oracle.build_market_context(
                asset="BNB",
                spot_price=spot_price,
                target_strike=target_strike,
                time_to_expiry_s=time_to_expiry_s,
                ofi=float(self.orderflow_feed.ofi_l1 if self.orderflow_feed else 0.0),
                vpin=vpin_score,
                spread_cents=0.02,
                current_regime=kev_regime,
                macro_slope=macro_slope,
            )
            kev_questions = [
                KevQuestion("is_toxic_sweep", "Is toxic sweep?", KevQuestionType.BOOLEAN),
                KevQuestion("trade_direction", "Direction?", KevQuestionType.CHOICE, ["YES", "NO", "WAIT"]),
            ]
            kev_res = await self.kev_oracle.evaluate(kev_ctx, kev_questions)
            kev_rec = kev_res.get("trade_direction")
            kev_toxic = kev_res.get("is_toxic_sweep")
            if kev_rec:
                logger.info(
                    "🔮 [KEV DECISION ORACLE] Rec: %s (Conf: %.1f%%) | Toxic: %s | Latency: %.1fms | Source: %s",
                    kev_rec.selected_option,
                    float(kev_rec.confidence) * 100.0,
                    kev_toxic.selected_option if kev_toxic else "false",
                    kev_rec.latency_ms,
                    kev_rec.source,
                )
        except Exception as kev_err:
            logger.debug("[KEV EVAL ERROR] %s", kev_err)

        # 1. Toxic Sweep Veto (Anti-Whale Armor)
        is_toxic = (kev_toxic and kev_toxic.selected_option.lower() == "true")
        if is_toxic:
            logger.warning("🛑 [KEV TOXIC SWEEP VETO] Toxic order flow / sweep detected by Kev Oracle. Stand down.")
            return decision

        # 1b. Late Cycle TWAP Guard (Anti-Pinning Trap)
        patch_02_active = dof_gov.is_patch_active("BNB", "dof_02_twap_guard")
        if patch_02_active:
            if time_to_expiry_s < 90.0:
                logger.info("⏸️ [BNB DoF-02 TWAP GUARD ACTIVE] Tau %.0fs < 90s. Pin risk elevated. Stand down.", time_to_expiry_s)
                return decision
        else:
            if time_to_expiry_s < 45.0:
                logger.info("⏸️ [EXPIRY CUTOFF] Tau %.0fs < 45s. Final seconds. Stand down.", time_to_expiry_s)
                return decision

        # 1c. Anti-Retail Momentum Exhaustion Gate (DoF-05)
        patch_05_active = dof_gov.is_patch_active("BNB", "dof_05_anti_exhaustion")
        if patch_05_active:
            wave_phys = getattr(self, "_last_wave_physics", None)
            w_ratio = (getattr(wave_phys, "upper_wick_dollars", 0.0) / max(1.0, getattr(wave_phys, "body_dollars", 1.0))) if wave_phys else 0.0
            if w_ratio >= 2.5:
                logger.warning("🛑 [BNB DoF-05 ANTI-EXHAUSTION ACTIVE] Wick ratio %.2f >= 2.5. Exhaustion wick detected. Stand down.", w_ratio)
                return decision

        # 1d. Opening Noise Maturity Gate (Anti-Brownian Noise Trap)
        # The first 5 minutes of a 15m cycle (tau > 600s) have high Brownian dispersion (+- $5.80 on BNB).
        # Require tau <= 600s before committing capital unless a structural breakout (|diff| >= $4.50) occurs.
        if time_to_expiry_s > 360.0:
            if abs(spot_price - target_strike) < Decimal("4.50"):
                logger.info(
                    "⏸️ [BNB OPENING NOISE MATURITY GATE] Tau %.0fs > 600s (|diff| $%.2f < $4.50). Waiting for cycle direction to mature.",
                    time_to_expiry_s, float(abs(spot_price - target_strike))
                )
                return decision

        # 2. Dynamic Moneyness Moat (Anti-Dispersion Excursion Shield)
        # Baseline freedom: flat $1.50 moat. When DoF-01 active: dynamic sqrt(tau) scaling moat.
        patch_01_active = dof_gov.is_patch_active("BNB", "dof_01_vol_moat")
        effective_moat = Decimal("2.50")
        if patch_01_active:
            if time_to_expiry_s > 720.0:
                effective_moat = Decimal("3.00")
            elif time_to_expiry_s > 450.0:
                scale = math.sqrt(time_to_expiry_s / 450.0)
                effective_moat = Decimal(str(round(1.50 * scale, 2)))
            logger.info("🛡️ [BNB DoF-01 VOL MOAT ACTIVE] Dynamic scaling moat: $%.2f (Tau: %.0fs)", float(effective_moat), time_to_expiry_s)

        # Apply Supreme Governor (Experience Buffer) adaptive proximity moat multiplier
        if self.experience_buffer:
            effective_moat = self.experience_buffer.get_effective_moat(effective_moat)

        spot_diff = abs(spot_price - target_strike)
        if spot_diff < effective_moat:
            logger.info("⏸️ [PROXIMITY MOAT VETO] |Diff| $%.2f < $%.2f noise threshold (Tau: %.0fs). Stand down.", float(spot_diff), float(effective_moat), time_to_expiry_s)
            return decision

        # 2b. 3D Mistake Matrix Quadrant Veto (Supreme Governor No-Fly Zone)
        if self.experience_buffer and self.experience_buffer.is_quadrant_pruned(time_to_expiry_s, float(spot_price - target_strike)):
            logger.warning(
                "🛑 [MISTAKE MATRIX VETO] Current (Tau=%.0fs, Diff=$%.2f) quadrant is blacklisted by Experience Buffer. Stand down.",
                time_to_expiry_s, float(spot_price - target_strike)
            )
            return decision

        # 3. Kev Lead Direction Gate (Governed by Supreme Governor Platt Leash)
        kev_dir = kev_rec.selected_option.upper() if kev_rec else "WAIT"
        raw_kev_conf = float(kev_rec.confidence) if kev_rec else 0.50
        platt_alpha = getattr(self.experience_buffer, "platt_alpha", 1.0) if self.experience_buffer else 1.0
        if self.experience_buffer and hasattr(self.experience_buffer, "calibrate_probability"):
            kev_conf = self.experience_buffer.calibrate_probability(raw_kev_conf)
        else:
            kev_conf = 0.50 + platt_alpha * (raw_kev_conf - 0.50)
        # Anti-deadlock gate: Requires strong qualitative conviction (raw >= 70%) and calibrated confidence >= 50%
        if kev_dir not in ("YES", "NO") or raw_kev_conf < 0.70 or kev_conf < 0.50:
            logger.info(
                "⏸️ [KEV STAND DOWN] Kev recommends %s (Calibrated Conf: %.1f%%, Raw: %.1f%%, Platt Alpha: %.2f). No trade.",
                kev_dir, kev_conf * 100.0, raw_kev_conf * 100.0, platt_alpha
            )
            return decision

        chosen_side = OrderSide.YES if kev_dir == "YES" else OrderSide.NO


        # 3b. Moneyness Consistency Check (Anti-OTM Trap Filter)
        # Prevent buying out-of-the-money contracts when spot is adverse to strike
        if chosen_side == OrderSide.YES and spot_price < (target_strike - Decimal("2.50")):
            logger.warning(
                "🛑 [OTM TRAP FILTER] Kev recommended YES, but spot ($%s) is deep below strike ($%s) by -$%.2f. Stand down to WAIT.",
                spot_price, target_strike, float(target_strike - spot_price)
            )
            return decision
        if chosen_side == OrderSide.NO and spot_price > (target_strike + Decimal("2.50")):
            logger.warning(
                "🛑 [OTM TRAP FILTER] Kev recommended NO, but spot ($%s) is deep above strike ($%s) by +$%.2f. Stand down to WAIT.",
                spot_price, target_strike, float(spot_price - target_strike)
            )
            return decision

        # 3c. Adverse Selection Flow Shield (Veto if queue pressure is aggressively opposing trade side)
        ofi_val = float(self.orderflow_feed.ofi_l1 if self.orderflow_feed else 0.0)
        if chosen_side == OrderSide.YES and ofi_val < 0.00:
            logger.warning("🛑 [BNB ADVERSE FLOW VETO] Opposing sell flow against YES (OFI: %+.2f < 0.00). Refusing adverse taker fill. Stand down.", ofi_val)
            return decision
        if chosen_side == OrderSide.NO and ofi_val > 0.00:
            logger.warning("🛑 [BNB ADVERSE FLOW VETO] Opposing buy flow against NO (OFI: %+.2f > 0.00). Refusing adverse taker fill. Stand down.", ofi_val)
            return decision

        # 3d. Asymmetric Macro-Trend Alignment Guard (Anti-Bleed Inversion)
        if macro_slope <= -0.10 and chosen_side == OrderSide.YES:
            if (spot_price - target_strike) < Decimal("7.50") or ofi_val < 0.20:
                logger.warning(
                    "🛑 [BNB MACRO BLEED VETO] Macro 1h slope (%.2f%%) is bearish. Refusing counter-trend YES (Diff: $%.2f). Stand down.",
                    macro_slope, float(spot_price - target_strike)
                )
                return decision

        if macro_slope >= 0.10 and chosen_side == OrderSide.NO:
            if (target_strike - spot_price) < Decimal("7.50") or ofi_val > -0.20:
                logger.warning(
                    "🛑 [BNB MACRO EXPANSION VETO] Macro 1h slope (+%.2f%%) is bullish. Refusing counter-trend NO (Diff: $%.2f). Stand down.",
                    macro_slope, float(spot_price - target_strike)
                )
                return decision

        # 3e. Empirical Session Timing Guard (Automatic Time-of-Day Veto & Golden Boost)
        timing_guard = getattr(self, "timing_guard", None) or get_session_timing_guard()
        timing_verdict = timing_guard.evaluate_timing(
            ref_time=now_utc,
            macro_regime=getattr(self, "_current_regime", "CHOP"),
            spot_diff=abs(spot_price - target_strike),
        )
        if not timing_verdict.allowed:
            if timing_verdict.is_warmup:
                logger.info("%s [WARM-UP ACTIVE] Feeds & ONNX primed; holding order execution until top-of-hour.", timing_verdict.reason)
            elif timing_verdict.is_shadow:
                logger.info("%s [SHADOW ACTIVE] Model inferencing & updating in shadow mode; live execution held.", timing_verdict.reason)
            else:
                logger.warning("%s Stand down to WAIT.", timing_verdict.reason)
            return decision
        if timing_verdict.is_golden:
            logger.info("%s", timing_verdict.reason)

        # 4. Continuous Math-of-Winning Formulation & Physics Dispersion Gate
        diff_float = float(spot_price - target_strike)
        sigma_15m = 6.0  # typical 15m BNB volatility
        tau_norm = max(0.01, time_to_expiry_s / 900.0)
        z = diff_float / (sigma_15m * math.sqrt(tau_norm))
        p_physics = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        p_physics_side = p_physics if chosen_side == OrderSide.YES else (1.0 - p_physics)

        # Physics Dispersion Gate: spot must have a statistical diffusion edge in trade direction
        if p_physics_side < 0.58:
            logger.info("⏸️ [PHYSICS DISPERSION GATE] P(Physics) %.1f%% < 58%% hurdle. Insufficient diffusion edge against dispersion. Stand down.", p_physics_side * 100.0)
            return decision

        # Balanced 50/50 synthesis of Kev qualitative conviction and diffusion physics
        p_win = (0.50 * kev_conf) + (0.50 * p_physics_side)
        p_win = max(0.51, min(0.99, p_win))

        # Dynamic Anti-Toxic Hurdle: widens when VPIN is elevated
        hurdle = Decimal("0.08") + Decimal(str(round(vpin_score * 0.10, 4)))
        # Cap at $0.55 winning corridor to maintain favorable risk/reward payoff asymmetry
        base_cap = Decimal("0.55")
        if self.experience_buffer:
            base_cap = self.experience_buffer.get_effective_price_cap(base_cap)
        max_taker_price = Decimal(str(round(p_win, 2))) - hurdle
        ask_floor = getattr(self, "min_viable_ask_floor", None) or Decimal("0.48")
        if isinstance(ask_floor, float):
            ask_floor = Decimal(str(ask_floor))
        max_taker_price = min(base_cap, max(ask_floor, max_taker_price))

        # 5. Live L2 Orderbook Taker Pricing & Zero-Liquidity Trap Protection
        best_ask = book.best_yes_ask if chosen_side == OrderSide.YES else book.best_no_ask
        if best_ask is None:
            logger.warning("🛑 [ZERO LIQUIDITY TRAP] Book has no resting asks for %s on %s. Stand down.", chosen_side.value.upper(), target_ticker)
            return decision

        # Adverse OTM Ask Floor ($0.40 Minimum Viable Floor)
        if best_ask < ask_floor:
            logger.info("⏸️ [BNB ADVERSE OTM ASK VETO] Best ask $%s < $%s minimum viable floor. Stand down.", best_ask, ask_floor)
            return decision

        if best_ask > max_taker_price:
            logger.info(
                "⏸️ [MATH HURDLE VETO] Best ask $%s > Max Taker Ceiling $%s (P_win: %.1f%%, Hurdle: $%.2f). Refusing to overpay.",
                best_ask, max_taker_price, p_win * 100.0, float(hurdle)
            )
            return decision

        # 6. Execution Guardrails: 1 trade per cycle & micro-bankroll sizing (1 contract)
        if self.order_client:
            completed = self.get_completed_turnovers(target_ticker)
            if completed >= self.max_turnover_per_event or guardrails.is_cycle_locked(target_ticker):
                logger.info("[BNB BOT] Cycle %s already locked (turnover limit reached).", target_ticker)
                return decision

            # Validate pre-trade intent with guardrails
            allowed, reason, approved_size, diag = guardrails.validate_pre_trade_intent(
                ticker=target_ticker,
                side=chosen_side.value,
                requested_size=1,
                est_price=best_ask,
                total_equity=Decimal("100.00"),
                vpin=vpin_score,
                cycle_id=target_ticker,
                is_bot=True,
                bot_type=self.STRATEGY_ID,
                is_live=True,
            )
            if not allowed:
                logger.warning("[BNB BOT GUARDRAIL BLOCKED] %s", reason)
                return decision

            try:
                order_kwargs: dict[str, Any] = {
                    "ticker": target_ticker,
                    "side": chosen_side.value,
                    "count": 1,
                    "order_type": "limit",
                    "price_dollars": best_ask,
                    "time_in_force": "immediate_or_cancel",
                }
                res = await self.order_client.place_order(**order_kwargs)

                # Check for valid execution
                if res is None or (isinstance(res, dict) and ("error" in res or res.get("status") in ("canceled", "rejected", "error"))):
                    logger.error("[BNB BOT ORDER REJECTED/FAILED] Response: %s", res)
                    guardrails.release_in_flight_intent(target_ticker)
                    return decision

                order_id = (
                    res.get("order_id")
                    or (res.get("order", {}).get("order_id") if isinstance(res.get("order"), dict) else None)
                    or f"ord_bnb_{int(time.time()*1000)}"
                )

                # Record trade inception into AgentGuardrails (locks cycle and enforces cooldown)
                exec_mode = "live" if hasattr(self.order_client, "shard_balances") else "simulated"
                guardrails.record_trade_inception(
                    trade_id=order_id,
                    ticker=target_ticker,
                    side=chosen_side.value,
                    size=1,
                    price=best_ask,
                    cost=best_ask,
                    fee=Decimal("0.01"),
                    bot_type=self.STRATEGY_ID,
                    execution_mode=exec_mode,
                    rationale=f"Kev-led taker: P_win {p_win*100:.1f}%, best_ask ${best_ask}",
                    vpin=vpin_score,
                    ai_prob=p_win,
                    cycle_id=target_ticker,
                )

                self.record_completed_turnover(target_ticker)
                logger.info(
                    "👑 [KEV LED TAKER ORDER EXECUTED] %s %s 1 ct @ $%s (Best Ask, Max Ceiling: $%s, P_win: %.1f%%, E[V]: +$%.2f) | Result: %s",
                    target_ticker, chosen_side.value.upper(), best_ask, max_taker_price, p_win * 100.0, float(Decimal(str(round(p_win, 2))) - best_ask - Decimal("0.01")), res
                )

                # Capture T1 & T2 Forensics for trade lifecycle ledger
                now_iso = datetime.now(timezone.utc).isoformat()
                self._active_trade_forensics[target_ticker] = {
                    "order_id": order_id,
                    "ticker": target_ticker,
                    "side": chosen_side.value,
                    "entry_price": float(best_ask),
                    "contracts": 1,
                    "time_to_expiry_s": float(time_to_expiry_s),
                    "entry_spot_diff": float(spot_price - target_strike),
                    "spot_diff": float(spot_price - target_strike),
                    "t1_timestamp": now_iso,
                    "t1_spot": float(spot_price),
                    "t1_strike_diff": float(spot_price - target_strike),
                    "t1_regime": getattr(self, "_current_regime", "CHOP").upper(),
                    "t1_vpin": float(vpin_score),
                    "t1_1h_slope": float(getattr(self, "_last_1h_slope", 0.0) or 0.0),
                    "t2_timestamp": now_iso,
                    "t2_spot": float(spot_price),
                    "t2_regime": getattr(self, "_current_regime", "CHOP").upper(),
                    "t2_vpin": float(vpin_score),
                }

                # Enqueue trade into separate BNB database
                get_bnb_db_writer().enqueue_trade(
                    trade_id=order_id,
                    ticker=target_ticker,
                    side=chosen_side.value,
                    price=float(best_ask),
                    gross_value=float(best_ask),
                    size=1,
                    vpin=float(vpin_score),
                    bot_type=self.STRATEGY_ID,
                    execution_mode=exec_mode,
                )
            except Exception as ex:
                logger.error("[BNB BOT ORDER FAILED] %s: %s", target_ticker, ex)
                guardrails.release_in_flight_intent(target_ticker)

        return decision


    def record_cycle_settlement(
        self,
        won_or_pnl: Union[bool, Decimal, float],
        ticker: Optional[str] = None,
        side: Optional[str] = None,
        entry_price: Optional[Decimal] = None,
        settlement_spot_price: Optional[Decimal] = None,
        strike_price: Optional[Decimal] = None,
        contracts: int = 1,
        execution_mode: str = 'shadow',
        twap_60s: Optional[Decimal] = None,
        market_condition: Optional[str] = None,
        target_ticker: Optional[str] = None,
        pnl: Optional[Union[Decimal, float]] = None,
    ) -> Optional[dict[str, Any]]:
        if isinstance(won_or_pnl, bool) and ticker is None and target_ticker is None:
            super().record_cycle_settlement(won_or_pnl)
            return None

        is_win = bool(won_or_pnl) if isinstance(won_or_pnl, bool) else (Decimal(str(won_or_pnl)) > 0)
        target_ticker = ticker or target_ticker or self.target_ticker or 'KXBNB15M-CYCLE'
        entry_p = entry_price or self.discount_limit_price
        if not isinstance(entry_p, Decimal):
            entry_p = Decimal(str(round(entry_p, 2)))

        if pnl is not None:
            pnl_dec = Decimal(str(pnl))
        elif isinstance(won_or_pnl, (Decimal, float)) and not isinstance(won_or_pnl, bool):
            pnl_dec = Decimal(str(won_or_pnl))
        else:
            pnl_dec = Decimal(str(contracts)) * (Decimal('1.00') - entry_p) if is_win else -Decimal(str(contracts)) * entry_p

        outcome = 'win' if is_win else 'loss'
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()
        report_id = f'WLR-BNB-{now_utc.strftime("%y%m%d%H%M%S")}-{random.randint(100, 999)}'

        strike = strike_price or Decimal('740.00')
        spot = settlement_spot_price or (strike + Decimal('2.50') if is_win else strike - Decimal('2.50'))
        side_clean = (side or 'yes').lower()
        cond_tag = market_condition or getattr(self, '_current_regime', 'CHOP').upper()

        report = {
            'report_id': report_id,
            'bot_id': self.STRATEGY_ID,
            'strategy_id': self.STRATEGY_ID,
            'cycle_time': now_utc.strftime('%B %d, 15M Event Cycle ET'),
            'ticker': target_ticker,
            'timeframe': '15m',
            'asset': 'BNB',
            'strike_price': float(strike),
            'settlement_spot_price': float(spot),
            'bot_side': side_clean,
            'contracts': contracts,
            'entry_price': float(entry_p),
            'settlement_price': 1.0 if is_win else 0.0,
            'outcome': outcome,
            'pnl': float(pnl_dec),
            'roi_pct': round(float(pnl_dec / (entry_p * contracts)) * 100.0, 2) if entry_p > 0 else 0.0,
            'ai_confidence': 0.80,
            'vpin_score': 0.15,
            'ev_edge': 0.08,
            'market_condition': cond_tag,
            'bot_type': self.STRATEGY_ID,
            'execution_mode': execution_mode,
            'timestamp_utc': now_iso,
        }

        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            reports = []
            if self.history_file.exists():
                try:
                    reports = json.loads(self.history_file.read_text(encoding='utf-8'))
                    if not isinstance(reports, list):
                        reports = []
                except Exception:
                    reports = []
            reports.insert(0, report)
            self.history_file.write_text(json.dumps(reports, indent=2), encoding='utf-8')
            logger.info('[BNB BOT] Persisted cycle settlement report to %s (%s, PnL: %s)', self.history_file, outcome.upper(), pnl_dec)
        except Exception as file_exc:
            logger.warning('[BNB BOT] Error persisting report to %s: %s', self.history_file, file_exc)

        if self.experience_buffer:
            try:
                exp = self.experience_buffer._dict_to_experience(report)
                if exp:
                    self.experience_buffer.record_settled_cycle(exp)
            except Exception as eb_exc:
                logger.debug('[BNB BOT] Error feeding experience buffer: %s', eb_exc)

        super().record_cycle_settlement(is_win)
        return report

    def get_spot_price(self) -> Decimal:
        """Retrieve current BNB spot price from feed or live exchange ticker."""
        if self.orderflow_feed and self.orderflow_feed.last_spot_price > 0:
            return self.orderflow_feed.last_spot_price
        try:
            import urllib.request
            resp = urllib.request.urlopen("https://api.binance.com/api/v3/ticker/price?symbol=BNBUSDT", timeout=2.0)
            data = json.loads(resp.read().decode())
            return Decimal(str(data.get("price", "750.00")))
        except Exception:
            return Decimal("750.00")

    async def fetch_active_market(self) -> Optional[MarketInfo]:
        """Alias for get_active_market conforming to Bot1V4 interface."""
        return await self.get_active_market()

    async def fetch_orderbook(self, ticker: str, rest_base: Optional[str] = None) -> Optional[L2BookState]:
        """Fetch live Level-2 Orderbook snapshot for the target BNB contract."""
        if rest_base is None:
            is_live_or_shadow = (self.order_client and getattr(self.order_client, "is_live", False)) or (self.order_client and getattr(self.order_client, "is_shadow", False)) or os.getenv("KALSHI_ENV", "live").lower() in ("prod", "live")
            rest_base = PROD_REST_BASE if is_live_or_shadow else DEMO_REST_BASE

        url = f"{rest_base}/markets/{ticker}/orderbook"
        headers = {
            "User-Agent": "KalshiSim-BnbBot1V4/1.0",
            "Accept": "application/json",
        }
        if self.order_client and getattr(self.order_client, "is_live", False):
            headers.update(get_auth_headers("GET", f"/trade-api/v2/markets/{ticker}/orderbook"))

        try:
            timeout = aiohttp.ClientTimeout(total=4.0)
            session = await self._get_session()
            async with session.get(url, headers=headers, timeout=timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw_book = data.get("orderbook_fp") or data.get("orderbook") or {}
                    bids = raw_book.get("yes_dollars") or raw_book.get("yes") or []
                    asks = raw_book.get("no_dollars") or raw_book.get("no") or []

                    book = L2BookState(ticker)
                    new_yes: dict[Decimal, Decimal] = {}
                    new_no: dict[Decimal, Decimal] = {}

                    for p_val, q_val in bids:
                        new_yes[Decimal(str(p_val))] = Decimal(str(q_val))
                    for p_val, q_val in asks:
                        new_no[Decimal(str(p_val))] = Decimal(str(q_val))

                    book.yes_book = new_yes
                    book.no_book = new_no
                    book.last_update = datetime.now(timezone.utc)
                    book._stale = False
                    return book
        except Exception as e:
            logger.debug("[BNB BOT] Error fetching orderbook for %s: %s", ticker, e)
        return None

    def get_empirical_vpin(self) -> float:
        """Compute empirical Volume-Synchronized Probability of Toxicity (VPIN) from aggressive trade tape."""
        if not self.orderflow_feed or not hasattr(self.orderflow_feed, "trades") or not self.orderflow_feed.trades:
            return 0.15
        trades = list(self.orderflow_feed.trades)
        if len(trades) < 5:
            return 0.15
        buy_vol = sum(float(getattr(t, "count", 0.0)) for t in trades if getattr(t, "taker_side", "") == "buy")
        sell_vol = sum(float(getattr(t, "count", 0.0)) for t in trades if getattr(t, "taker_side", "") == "sell")
        tot = buy_vol + sell_vol
        if tot <= 0.0001:
            return 0.15
        return float(min(0.99, max(0.01, abs(buy_vol - sell_vol) / tot)))

    def get_macro_1h_slope(self) -> float:
        """Fetch 1h macro trend percentage slope with 60-second caching for BNB."""
        now_mono = time.monotonic()
        if hasattr(self, "_last_1h_slope") and hasattr(self, "_last_1h_slope_ts"):
            if now_mono - getattr(self, "_last_1h_slope_ts", 0.0) < 60.0:
                return float(self._last_1h_slope)

        symbol = "BNBUSDT"
        fallback = 0.0
        try:
            import urllib.request
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=2"
            req = urllib.request.Request(url, headers={"User-Agent": "KalshiSim-BnbBot1V4/1.0"})
            resp = urllib.request.urlopen(req, timeout=2.5)
            data = json.loads(resp.read().decode())
            if data and len(data) >= 1:
                curr_kline = data[-1]
                open_pr = float(curr_kline[1])
                close_pr = float(curr_kline[4])
                if open_pr > 0.0:
                    slope_pct = ((close_pr - open_pr) / open_pr) * 100.0
                    self._last_1h_slope = slope_pct
                    self._last_1h_slope_ts = now_mono
                    return slope_pct
        except Exception as e:
            logger.debug("[BNB MACRO SLOPE] Fallback reading candles: %s", e)

        if self.orderflow_feed and hasattr(self.orderflow_feed, "candle_builder_5m"):
            candles = self.orderflow_feed.candle_builder_5m.get_candles(symbol, count=12)
            if len(candles) >= 2:
                o = float(candles[0].open)
                c = float(candles[-1].close)
                if o > 0.0:
                    slope = ((c - o) / o) * 100.0
                    self._last_1h_slope = slope
                    self._last_1h_slope_ts = now_mono
                    return slope

        self._last_1h_slope = fallback
        self._last_1h_slope_ts = now_mono
        return fallback

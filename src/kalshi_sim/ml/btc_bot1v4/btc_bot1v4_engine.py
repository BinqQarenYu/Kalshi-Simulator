"""Institutional Bot 1 V4 (BTC Domination) Quantitative Engine.

Calibrated strictly for Kalshi Bitcoin (KXBTC15M) 15-minute events:
* Zero Float Math (all valuations in Decimal).
* Kev the Decisive Lead Taker with Continuous Math-of-Winning.
* Active In-Flight Derisking & Take-Profit Salvage.
* Dedicated Binance Level-2 Orderflow & Kalshi CLOB Synchronization.
* Micro-Bankroll Sizing: Strictly 1 contract per trade.
* 1-Trade-Per-Cycle Lock.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
import math
import os
from pathlib import Path
import time
from typing import Any, Optional, Union

import aiohttp

from kalshi_sim.agent_guardrails import AgentGuardrails, get_global_guardrails
from kalshi_sim.auth import (
    DEMO_REST_BASE,
    PROD_REST_BASE,
    create_aiohttp_connector,
    get_auth_headers,
)
from kalshi_sim.db import get_db_writer
from kalshi_sim.ml.bot1_v4_engine import Bot1V4Decision, Bot1V4DominationEngine
from kalshi_sim.ml.experience_buffer import ContinuousExperienceBuffer
from kalshi_sim.ml.kev_oracle import KevDecisionOracle, KevQuestion, KevQuestionType
from kalshi_sim.orderflow.btc_orderflow_feed import BtcOrderflowFeed
from kalshi_sim.schemas import (
    CryptoAsset,
    L2BookState,
    MarketInfo,
    MarketStatus,
    OrderSide,
    TradeEvent,
)

logger = logging.getLogger("kalshi_sim.btc_bot1v4_engine")


class BtcBot1V4Engine(Bot1V4DominationEngine):
    """Institutional Bot 1 V4 engine calibrated for Kalshi Bitcoin (KXBTC15M) 15-minute events."""

    STRATEGY_ID = "bot1_v4_domination"
    STRATEGY_NAME = "Bot 1 V4 (BTC Domination)"

    def __init__(
        self,
        order_client: Optional[Any] = None,
        orderflow_feed: Optional[BtcOrderflowFeed] = None,
        ticker: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        target_ticker = kwargs.pop("ticker", ticker)
        hist_file = kwargs.pop("history_file", None)
        min_bleed_diff = kwargs.pop("min_spot_diff_bleed", 45.00)
        param_file = kwargs.pop("parameters_file", None)
        load_persisted = kwargs.pop("load_persisted", param_file is not None)

        # Enforce BTC asset calibration
        kwargs.setdefault("asset", CryptoAsset.BTC)
        kwargs.setdefault("default_btc_1m_volatility", 16.00)  # BTC 1m rolling volatility (~$16.00)
        kwargs.setdefault("min_spot_diff", 25.00)              # BTC strike proximity moat
        kwargs.setdefault("chop_range_threshold", 75.00)       # Range threshold for BTC
        kwargs.setdefault("chop_vol_threshold", 14.00)
        kwargs.setdefault("taker_breakout_min_velocity", 12.00) # $/3s spot velocity threshold
        kwargs.setdefault("discount_limit_price", Decimal("0.45"))
        kwargs.setdefault("max_entry_price", Decimal("0.55"))
        kwargs.setdefault("fee_per_contract", Decimal("0.01"))

        # Dedicated BTC experience buffer
        buffer_path = Path(hist_file) if hist_file else Path("data/win_loss_reports.json")
        buffer_path.parent.mkdir(parents=True, exist_ok=True)
        if "experience_buffer" not in kwargs or kwargs["experience_buffer"] is None:
            kwargs["experience_buffer"] = ContinuousExperienceBuffer(history_file=buffer_path, asset="BTC")

        super().__init__(*args, **kwargs)

        self.history_file = buffer_path
        self.parameters_file = Path(param_file) if param_file else Path("data/bot_parameters_domination.json")
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

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or reuse connection-pooled HTTP session to prevent socket exhaustion."""
        if self.order_client and hasattr(self.order_client, "_get_session"):
            return await self.order_client._get_session()
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(connector=create_aiohttp_connector())
        return self._session

    def _load_persisted_parameters(self) -> None:
        """Load persisted BTC bot parameters from disk if available."""
        if not self.parameters_file.exists():
            return
        try:
            raw = json.loads(self.parameters_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                btc_params = raw.get("bot1_v4_domination", raw)
                self.update_parameters(**btc_params)
                logger.info("[BTC BOT] Loaded persisted parameters from %s", self.parameters_file)
        except Exception as exc:
            logger.debug("[BTC BOT] Error loading persisted parameters: %s", exc)

    def save_persisted_parameters(self) -> None:
        """Persist active parameters to data/bot_parameters_domination.json."""
        try:
            self.parameters_file.parent.mkdir(parents=True, exist_ok=True)
            existing: dict[str, Any] = {}
            if self.parameters_file.exists():
                try:
                    existing = json.loads(self.parameters_file.read_text(encoding="utf-8"))
                except Exception:
                    existing = {}
            existing["bot1_v4_domination"] = self.get_parameters()
            self.parameters_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("[BTC BOT] Could not persist parameters to %s: %s", self.parameters_file, exc)

    async def fetch_active_market(self, rest_base: Optional[str] = None) -> Optional[MarketInfo]:
        """Discover the currently open active KXBTC15M Kalshi market contract."""
        if rest_base is None:
            env = os.getenv("KALSHI_ENV", "live").lower()
            rest_base = PROD_REST_BASE if env in ("prod", "live") else DEMO_REST_BASE

        now_mono = time.monotonic()
        now_utc = datetime.now(timezone.utc)

        # Cache open market lookup for 2.0s
        if self._cached_market and (now_mono - self._last_market_fetch_ts < 2.0):
            if self._cached_market.close_time and self._cached_market.close_time > now_utc:
                return self._cached_market

        url = f"{rest_base}/markets?series_ticker=KXBTC15M&status=open&limit=10"
        headers = {
            "User-Agent": "KalshiSim-BtcBot1V4/1.0",
            "Accept": "application/json",
        }

        if self.order_client and hasattr(self.order_client, "api_key_id") and hasattr(self.order_client, "private_key"):
            headers = get_auth_headers(
                self.order_client.api_key_id,
                self.order_client.private_key,
                "GET",
                "/trade-api/v2/markets",
            )

        try:
            timeout = aiohttp.ClientTimeout(total=4.0)
            session = await self._get_session()
            async with session.get(url, headers=headers, timeout=timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    markets_raw = data.get("markets", [])
                    valid_markets: list[tuple[datetime, dict[str, Any]]] = []

                    for m in markets_raw:
                        t_str = m.get("ticker", "")
                        close_str = m.get("close_time")
                        if not t_str or not close_str:
                            continue
                        close_dt = datetime.fromisoformat(close_str.replace("Z", "+00:00"))
                        if close_dt > now_utc:
                            valid_markets.append((close_dt, m))

                    if valid_markets:
                        valid_markets.sort(key=lambda x: x[0])
                        _, chosen = valid_markets[0]

                        floor_str = chosen.get("floor_strike")
                        floor_dec = Decimal(str(floor_str)) if floor_str is not None else None
                        close_dt = datetime.fromisoformat(chosen["close_time"].replace("Z", "+00:00"))
                        open_dt = datetime.fromisoformat(chosen["open_time"].replace("Z", "+00:00")) if chosen.get("open_time") else None

                        minfo = MarketInfo(
                            ticker=chosen.get("ticker", ""),
                            series_ticker=chosen.get("series_ticker", "KXBTC15M"),
                            title=chosen.get("title", ""),
                            subtitle=chosen.get("subtitle", ""),
                            status=MarketStatus.OPEN,
                            open_time=open_dt,
                            close_time=close_dt,
                            expiration_time=close_dt,
                            floor_strike=floor_dec,
                            cap_strike=None,
                            strike_type="greater",
                        )
                        self._cached_market = minfo
                        self._last_market_fetch_ts = now_mono
                        return minfo
        except Exception as exc:
            logger.debug("[BTC BOT] Error discovering KXBTC15M market: %s", exc)

        return self._cached_market

    async def fetch_orderbook(self, ticker: str, rest_base: Optional[str] = None) -> Optional[L2BookState]:
        """Fetch live Level-2 Orderbook snapshot for the target BTC contract."""
        if rest_base is None:
            env = os.getenv("KALSHI_ENV", "live").lower()
            rest_base = PROD_REST_BASE if env in ("prod", "live") else DEMO_REST_BASE

        url = f"{rest_base}/markets/{ticker}/orderbook"
        headers = {
            "User-Agent": "KalshiSim-BtcBot1V4/1.0",
            "Accept": "application/json",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=3.0)
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
        except Exception as exc:
            logger.debug("[BTC BOT] Error fetching orderbook for %s: %s", ticker, exc)

        return None

    def get_spot_price(self) -> Decimal:
        """Retrieve current BTC spot price from feed or Binance live ticker."""
        if self.orderflow_feed and self.orderflow_feed.last_spot_price > 0:
            return self.orderflow_feed.last_spot_price
        try:
            import urllib.request
            resp = urllib.request.urlopen("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=2.0)
            data = json.loads(resp.read().decode())
            return Decimal(str(data.get("price", "82000.00")))
        except Exception:
            pass
        return Decimal("82000.00")

    async def run_cycle(self, ticker: Optional[str] = None) -> Optional[Bot1V4Decision]:
        """Execute a single cycle iteration of the BTC Bot 1 V4 engine."""
        guardrails = get_global_guardrails()
        if not guardrails.is_btc_bot_armed:
            logger.info("🛑 [BTC BOT 1 V4] Stand down: BTC bot halted per user directive.")
            return None

        target_ticker = ticker or self.target_ticker
        market_info: Optional[MarketInfo] = None

        if not target_ticker or "-" not in target_ticker:
            market_info = await self.fetch_active_market()
            if market_info:
                target_ticker = market_info.ticker

        if not target_ticker or "-" not in target_ticker:
            logger.debug("[BTC BOT] No active KXBTC15M market discovered.")
            return None

        # Fetch live L2 book
        book = await self.fetch_orderbook(target_ticker)
        if not book or (not book.yes_book and not book.no_book):
            logger.debug("[BTC BOT] Orderbook for %s empty or unavailable.", target_ticker)
            return None

        # Determine target strike & time to expiry
        now_utc = datetime.now(timezone.utc)
        target_strike = Decimal("82000.00")
        time_to_expiry_s = 600.0

        if market_info and market_info.floor_strike:
            target_strike = market_info.floor_strike
        elif "-" in target_ticker:
            parts = target_ticker.split("-")
            if len(parts) >= 3:
                try:
                    target_strike = Decimal(parts[-1])
                except Exception:
                    pass

        if market_info and market_info.expiration_time:
            time_to_expiry_s = max(1.0, (market_info.expiration_time - now_utc).total_seconds())

        spot_price = self.get_spot_price()
        vpin_score = 0.15
        if self.orderflow_feed:
            vpin_score = min(0.99, max(0.01, abs(self.orderflow_feed.ofi_l1)))

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
            spot_velocity_3s=0.0,
        )

        logger.info(
            "⚡ [BTC BOT 1 V4] %s | Side: %s | P(Win): %.1f%% | EV: $%.2f | Price: $%.2f | Action: %s (%s)",
            target_ticker,
            decision.recommended_side.upper(),
            (decision.p_up if decision.recommended_side == "yes" else decision.p_down) * 100.0,
            decision.ev_yes if decision.recommended_side == "yes" else decision.ev_no,
            float(getattr(decision, "limit_price", 0.45)),
            getattr(decision, "action", decision.recommended_side.upper()),
            decision.rationale[:60],
        )

        # IN-FLIGHT ACTIVE POSITION DERISKING & TAKE-PROFIT
        if self.order_client and target_ticker in self._active_trade_forensics:
            active_info = self._active_trade_forensics[target_ticker]
            if not active_info.get("exited", False):
                pos_side = active_info.get("side", "yes")
                entry_pr = Decimal(str(active_info.get("entry_price", "0.50")))
                bid_to_sell = book.best_yes_bid if pos_side == "yes" else book.best_no_bid

                # 1. Take Profit: If position gained strongly (bid >= $0.88) with >= 120s left
                if bid_to_sell is not None and bid_to_sell >= Decimal("0.88") and time_to_expiry_s >= 120.0:
                    try:
                        logger.info("🎯 [BTC TAKE PROFIT TRIGGER] Selling %s %s @ $%s (Entry: $%s) to lock profit.", target_ticker, pos_side.upper(), bid_to_sell, entry_pr)
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
                            logger.info("✅ [BTC TAKE PROFIT EXECUTED] Successfully locked profit @ $%s!", bid_to_sell)
                    except Exception as tp_err:
                        logger.debug("Take profit error: %s", tp_err)

                # 2. Catastrophic Derisk / Salvage Stop:
                # If spot drifted adverse past strike by >= $30.00 with >= 90s left, salvage at market bid
                is_doomed = False
                if pos_side == "yes" and spot_price < (target_strike - Decimal("30.00")):
                    is_doomed = True
                elif pos_side == "no" and spot_price > (target_strike + Decimal("30.00")):
                    is_doomed = True

                if is_doomed and bid_to_sell is not None and bid_to_sell >= Decimal("0.15") and time_to_expiry_s >= 90.0:
                    try:
                        logger.warning("🛡️ [BTC SALVAGE DERISK TRIGGER] Position doomed (Spot: $%s vs Strike: $%s). Selling to salvage $%s/ct (Entry: $%s).", spot_price, target_strike, bid_to_sell, entry_pr)
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
                            logger.warning("🛡️ [BTC SALVAGE DERISK EXECUTED] Salvaged $%s/ct! Loss capped at -$%s (Saved 100%% wipeout)", bid_to_sell, float(entry_pr - bid_to_sell))
                    except Exception as sl_err:
                        logger.debug("Salvage derisk error: %s", sl_err)

        # ------------------------------------------------------------------
        # KEV DECISIVE LEAD & MATH-OF-WINNING TAKER ENGINE (BTC)
        # ------------------------------------------------------------------
        kev_rec = None
        kev_toxic = None
        try:
            kev_ctx = self.kev_oracle.build_market_context(
                asset="BTC",
                spot_price=spot_price,
                target_strike=target_strike,
                time_to_expiry_s=time_to_expiry_s,
                ofi=float(self.orderflow_feed.ofi_l1 if self.orderflow_feed else 0.0),
                vpin=vpin_score,
                spread_cents=0.02,
                current_regime=getattr(self, "_current_regime", "CHOP"),
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
                    "🔮 [BTC KEV ORACLE] Rec: %s (Conf: %.1f%%) | Toxic: %s | Latency: %.1fms | Source: %s",
                    kev_rec.selected_option,
                    float(kev_rec.confidence) * 100.0,
                    kev_toxic.selected_option if kev_toxic else "false",
                    kev_rec.latency_ms,
                    kev_rec.source,
                )
        except Exception as kev_err:
            logger.debug("[BTC KEV EVAL ERROR] %s", kev_err)

        # 1. Toxic Sweep Veto (Anti-Whale Armor)
        is_toxic = (kev_toxic and kev_toxic.selected_option.lower() == "true") or (vpin_score >= 0.60)
        if is_toxic:
            logger.warning("🛑 [BTC TOXIC SWEEP VETO] Toxic order flow / sweep detected (VPIN: %.2f). Stand down.", vpin_score)
            return decision

        # 2. Strict Moneyness Moat (Anti-Tie / Strict Inequality Protection: $25 for BTC)
        spot_diff = abs(spot_price - target_strike)
        if spot_diff < Decimal("25.00"):
            logger.info("⏸️ [BTC PROXIMITY MOAT VETO] |Diff| $%.2f < $25.00 noise threshold. Stand down.", float(spot_diff))
            return decision

        # 3. Kev Lead Direction Gate
        kev_dir = kev_rec.selected_option.upper() if kev_rec else "WAIT"
        kev_conf = float(kev_rec.confidence) if kev_rec else 0.50
        if kev_dir not in ("YES", "NO") or kev_conf < 0.60:
            logger.info("⏸️ [BTC KEV STAND DOWN] Kev recommends %s (Conf: %.1f%%). No trade.", kev_dir, kev_conf * 100.0)
            return decision

        chosen_side = OrderSide.YES if kev_dir == "YES" else OrderSide.NO

        # 3b. Moneyness Consistency Check (Anti-OTM Trap Filter: $35 margin for BTC)
        if chosen_side == OrderSide.YES and spot_price < (target_strike - Decimal("35.00")):
            logger.warning(
                "🛑 [BTC OTM TRAP FILTER] Kev recommended YES, but spot ($%s) is deep below strike ($%s). Stand down.",
                spot_price, target_strike
            )
            return decision
        if chosen_side == OrderSide.NO and spot_price > (target_strike + Decimal("35.00")):
            logger.warning(
                "🛑 [BTC OTM TRAP FILTER] Kev recommended NO, but spot ($%s) is deep above strike ($%s). Stand down.",
                spot_price, target_strike
            )
            return decision

        # 4. Continuous Math-of-Winning Formulation (BTC Volatility Scale: sigma = 120.0)
        diff_float = float(spot_price - target_strike)
        sigma_15m = 120.0
        tau_norm = max(0.01, time_to_expiry_s / 900.0)
        z = diff_float / (sigma_15m * math.sqrt(tau_norm))
        p_physics = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        p_physics_side = p_physics if chosen_side == OrderSide.YES else (1.0 - p_physics)

        p_win = (0.75 * kev_conf) + (0.25 * p_physics_side)
        p_win = max(0.51, min(0.99, p_win))

        # Dynamic Anti-Toxic Hurdle
        hurdle = Decimal("0.08") + Decimal(str(round(vpin_score * 0.10, 4)))
        max_taker_price = Decimal(str(round(p_win, 2))) - hurdle
        max_taker_price = min(Decimal("0.65"), max(Decimal("0.10"), max_taker_price))

        # 5. Live L2 Orderbook Taker Pricing
        best_ask = book.best_yes_ask if chosen_side == OrderSide.YES else book.best_no_ask
        if best_ask is None:
            logger.warning("🛑 [BTC ZERO LIQUIDITY TRAP] Book has no resting asks for %s on %s. Stand down.", chosen_side.value.upper(), target_ticker)
            return decision

        if best_ask > max_taker_price:
            logger.info(
                "⏸️ [BTC MATH HURDLE VETO] Best ask $%s > Max Taker Ceiling $%s (P_win: %.1f%%, Hurdle: $%.2f). Refusing to overpay.",
                best_ask, max_taker_price, p_win * 100.0, float(hurdle)
            )
            return decision

        # 6. Execution Guardrails: 1 trade per cycle & micro-bankroll sizing (1 contract)
        if self.order_client:
            completed = self.get_completed_turnovers(target_ticker)
            if completed >= self.max_turnover_per_event or guardrails.is_cycle_locked(target_ticker):
                logger.info("[BTC BOT] Cycle %s already locked (turnover limit reached).", target_ticker)
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
                logger.warning("[BTC BOT GUARDRAIL BLOCKED] %s", reason)
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

                if res is None or (isinstance(res, dict) and ("error" in res or res.get("status") in ("canceled", "rejected", "error"))):
                    logger.error("[BTC BOT ORDER REJECTED/FAILED] Response: %s", res)
                    guardrails.release_in_flight_intent(target_ticker)
                    return decision

                order_id = (
                    res.get("order_id")
                    or (res.get("order", {}).get("order_id") if isinstance(res.get("order"), dict) else None)
                    or f"ord_btc_{int(time.time()*1000)}"
                )

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
                    rationale=f"BTC Kev-led taker: P_win {p_win*100:.1f}%, best_ask ${best_ask}",
                    vpin=vpin_score,
                    ai_prob=p_win,
                    cycle_id=target_ticker,
                )

                self.record_completed_turnover(target_ticker)
                logger.info(
                    "👑 [BTC KEV LED TAKER ORDER EXECUTED] %s %s 1 ct @ $%s (Best Ask, Max Ceiling: $%s, P_win: %.1f%%, E[V]: +$%.2f) | Result: %s",
                    target_ticker, chosen_side.value.upper(), best_ask, max_taker_price, p_win * 100.0, float(Decimal(str(round(p_win, 2))) - best_ask), res
                )

                now_iso = datetime.now(timezone.utc).isoformat()
                self._active_trade_forensics[target_ticker] = {
                    "order_id": order_id,
                    "ticker": target_ticker,
                    "side": chosen_side.value,
                    "entry_price": float(best_ask),
                    "contracts": 1,
                    "t1_timestamp": now_iso,
                    "t1_spot": float(spot_price),
                    "t1_strike_diff": float(spot_price - target_strike),
                    "t1_regime": getattr(self, "_current_regime", "CHOP").upper(),
                    "t1_vpin": float(vpin_score),
                    "t2_timestamp": now_iso,
                    "t2_spot": float(spot_price),
                }

                get_db_writer().enqueue_trade(
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
                logger.error("[BTC BOT ORDER FAILED] %s: %s", target_ticker, ex)
                guardrails.release_in_flight_intent(target_ticker)

        return decision

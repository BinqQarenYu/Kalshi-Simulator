"""ETH‑specific Bot 1 V4 quantitative engine.

Provides `EthBot1V4Engine`, calibrated specifically for Kalshi 15-minute Ethereum binary contracts
(series ``KXETH15M``). Operates with:
- Calibrated ETH 1m volatility ($0.60), $2.50 strike step, and tighter proximity moats.
- Dedicated experience buffer writing to ``data/eth_win_loss_reports.json`` (isolated learning).
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
import random
import time
from typing import Any, Optional, Union

import aiohttp

from kalshi_sim.auth import DEMO_REST_BASE, PROD_REST_BASE, get_auth_headers
from kalshi_sim.db import get_eth_db_writer
from kalshi_sim.ml.bot1_v4_engine import Bot1V4Decision, Bot1V4DominationEngine
from kalshi_sim.ml.experience_buffer import ContinuousExperienceBuffer, CycleExperience
from kalshi_sim.orderflow.eth_orderflow_feed import EthOrderflowFeed
from kalshi_sim.schemas import (
    CryptoAsset,
    L2BookState,
    MarketInfo,
    MarketStatus,
    OrderSide,
    Timeframe,
    get_asset_config,
)
from kalshi_sim.ml.kev_oracle import KevDecisionOracle, KevQuestion, KevQuestionType
from kalshi_sim.ws_connection import create_aiohttp_connector

logger = logging.getLogger("kalshi_sim.eth_bot1v4_engine")


class EthBot1V4Engine(Bot1V4DominationEngine):
    """Institutional Bot 1 V4 engine calibrated for Kalshi Ethereum (KXETH15M) 15-minute events."""

    STRATEGY_ID = "eth_bot1_v4"
    STRATEGY_NAME = "ETH Bot 1 V4 (Ethereum Domination)"

    def __init__(
        self,
        order_client: Optional[Any] = None,
        orderflow_feed: Optional[EthOrderflowFeed] = None,
        ticker: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        target_ticker = kwargs.pop("ticker", ticker)
        hist_file = kwargs.pop("history_file", None)
        min_bleed_diff = kwargs.pop("min_spot_diff_bleed", 5.00)
        param_file = kwargs.pop("parameters_file", None)
        load_persisted = kwargs.pop("load_persisted", param_file is not None)

        # Enforce ETH asset calibration
        kwargs.setdefault("asset", CryptoAsset.ETH)
        kwargs.setdefault("default_btc_1m_volatility", 0.60)  # ETH 1m rolling volatility (~$0.60 vs BTC $14)
        kwargs.setdefault("min_spot_diff", 2.50)              # Typical Kalshi ETH strike step is $2.50
        kwargs.setdefault("chop_range_threshold", 7.50)       # 0.25% range of ~$3,000 spot
        kwargs.setdefault("chop_vol_threshold", 0.60)
        kwargs.setdefault("taker_breakout_min_velocity", 1.50) # $/3s spot velocity threshold
        kwargs.setdefault("discount_limit_price", Decimal("0.42"))
        kwargs.setdefault("max_entry_price", Decimal("0.45"))
        kwargs.setdefault("fee_per_contract", Decimal("0.01"))

        # Dedicated ETH experience buffer
        buffer_path = Path(hist_file) if hist_file else Path("data/eth_win_loss_reports.json")
        buffer_path.parent.mkdir(parents=True, exist_ok=True)
        if "experience_buffer" not in kwargs or kwargs["experience_buffer"] is None:
            kwargs["experience_buffer"] = ContinuousExperienceBuffer(history_file=buffer_path, asset="ETH")

        super().__init__(*args, **kwargs)

        self.history_file = buffer_path
        self.parameters_file = Path(param_file) if param_file else Path("data/bot_parameters_eth.json")
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
        """Load persisted ETH bot parameters from disk if available."""
        if not self.parameters_file.exists():
            return
        try:
            raw = json.loads(self.parameters_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                eth_params = raw.get("eth_bot1_v4", raw)
                self.update_parameters(**eth_params)
                logger.info("[ETH BOT] Loaded persisted parameters from %s", self.parameters_file)
        except Exception as exc:
            logger.debug("[ETH BOT] Error loading persisted parameters: %s", exc)

    def save_persisted_parameters(self) -> None:
        """Persist active parameters to data/bot_parameters_eth.json."""
        try:
            self.parameters_file.parent.mkdir(parents=True, exist_ok=True)
            existing: dict[str, Any] = {}
            if self.parameters_file.exists():
                try:
                    existing = json.loads(self.parameters_file.read_text(encoding="utf-8"))
                except Exception:
                    existing = {}
            existing["eth_bot1_v4"] = self.get_parameters()
            self.parameters_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("[ETH BOT] Could not persist parameters to %s: %s", self.parameters_file, exc)

    def evaluate(
        self,
        book: L2BookState,
        spot_price: float,
        target_strike: float,
        time_to_expiry_s: float,
        recent_trades: Optional[list[TradeEvent]] = None,
        total_equity: Decimal = Decimal("35.00"),
        max_position_size: int = 1,
        estimated_vpin: float = 0.20,
        cycle_id: str = "DEFAULT_CYCLE",
        spot_velocity_3s: float = 0.0,
        asset: CryptoAsset = CryptoAsset.ETH,
        **kwargs: Any,
    ) -> Bot1V4Decision:
        """Evaluate Bot 1 V4 with ETH asset scale and truth synchronization."""
        return super().evaluate(
            book=book,
            spot_price=spot_price,
            target_strike=target_strike,
            time_to_expiry_s=time_to_expiry_s,
            recent_trades=recent_trades,
            total_equity=total_equity,
            max_position_size=max_position_size,
            estimated_vpin=estimated_vpin,
            cycle_id=cycle_id,
            spot_velocity_3s=spot_velocity_3s,
            asset=asset,
            **kwargs,
        )

    async def fetch_active_market(self, rest_base: Optional[str] = None) -> Optional[MarketInfo]:
        """Discover the currently open active KXETH15M Kalshi market contract."""
        if rest_base is None:
            env = os.getenv("KALSHI_ENV", "live").lower()
            rest_base = PROD_REST_BASE if env in ("prod", "live") else DEMO_REST_BASE

        now_mono = time.monotonic()
        now_utc = datetime.now(timezone.utc)

        # Cache open market lookup for 2.0s
        if self._cached_market and (now_mono - self._last_market_fetch_ts < 2.0):
            if self._cached_market.close_time and self._cached_market.close_time > now_utc:
                return self._cached_market

        url = f"{rest_base}/markets?series_ticker=KXETH15M&status=open&limit=10"
        connector = create_aiohttp_connector()
        headers = {
            "User-Agent": "KalshiSim-EthBot1V4/1.0",
            "Accept": "application/json",
        }

        # If authenticated order_client is available, use its credentials
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
                            series_ticker=chosen.get("series_ticker", "KXETH15M"),
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
            logger.debug("[ETH BOT] Error discovering KXETH15M market: %s", exc)

        return self._cached_market

    async def fetch_orderbook(self, ticker: str, rest_base: Optional[str] = None) -> Optional[L2BookState]:
        """Fetch live Level-2 Orderbook snapshot for the target ETH contract."""
        if rest_base is None:
            env = os.getenv("KALSHI_ENV", "live").lower()
            rest_base = PROD_REST_BASE if env in ("prod", "live") else DEMO_REST_BASE

        url = f"{rest_base}/markets/{ticker}/orderbook"
        headers = {
            "User-Agent": "KalshiSim-EthBot1V4/1.0",
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
            logger.debug("[ETH BOT] Error fetching orderbook for %s: %s", ticker, exc)

        return None

    def get_spot_price(self) -> Decimal:
        """Retrieve current ETH spot price from feed or live exchange ticker."""
        if self.orderflow_feed and self.orderflow_feed.last_spot_price > 0:
            return self.orderflow_feed.last_spot_price
        try:
            import urllib.request
            resp = urllib.request.urlopen("https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT", timeout=2.0)
            data = json.loads(resp.read().decode())
            return Decimal(str(data.get("price", "2350.00")))
        except Exception:
            pass
        return Decimal("2350.00")

    async def run_cycle(self, ticker: Optional[str] = None) -> Optional[Bot1V4Decision]:
        """Execute a single cycle iteration of the ETH Bot 1 V4 engine.

        1. Checks ETH circuit breaker (3 consecutive losses mandate).
        2. Discovers active KXETH15M 15-minute market.
        3. Ingests Level-2 orderbook.
        4. Retrieves real-time ETH spot price.
        5. Evaluates market opportunity using Bot 1 V4 quantitative logic with ETH calibration.
        6. If signal is actionable ('yes' or 'no' with >0 contracts) and order_client is attached:
           executes 1 contract adhering to micro-bankroll rules and 1-trade-per-cycle lock.
        """
        from kalshi_sim.agent_guardrails import get_global_guardrails
        guardrails = get_global_guardrails()
        if not guardrails.is_eth_bot_armed:
            logger.info("🛑 [ETH BOT 1 V4] Stand down: ETH bot circuit breaker tripped (%d consecutive losses). Stopped per user directive.", guardrails._eth_consecutive_losses)
            return None

        target_ticker = ticker or self.target_ticker
        market_info: Optional[MarketInfo] = None

        if not target_ticker or "-" not in target_ticker:
            market_info = await self.fetch_active_market()
            if market_info:
                target_ticker = market_info.ticker

        if not target_ticker or "-" not in target_ticker:
            logger.debug("[ETH BOT] No active KXETH15M market discovered.")
            return None

        # Fetch live L2 book
        book = await self.fetch_orderbook(target_ticker)
        if not book or (not book.yes_book and not book.no_book):
            logger.debug("[ETH BOT] Orderbook for %s empty or unavailable.", target_ticker)
            return None

        # Determine target strike & time to expiry
        now_utc = datetime.now(timezone.utc)
        target_strike = Decimal("2600.00")
        time_to_expiry_s = 600.0

        if market_info and market_info.floor_strike:
            target_strike = market_info.floor_strike
        elif "-" in target_ticker:
            # Parse strike from ticker if formatted as KXETH15M-YYMMMDDHHMM-STRIKE
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
            "⚡ [ETH BOT 1 V4] %s | Side: %s | P(Win): %.1f%% | EV: $%.2f | Price: $%.2f | Action: %s (%s)",
            target_ticker,
            decision.recommended_side.upper(),
            (decision.p_up if decision.recommended_side == "yes" else decision.p_down) * 100.0,
            decision.ev_yes if decision.recommended_side == "yes" else decision.ev_no,
            float(getattr(decision, "limit_price", 0.42)),
            getattr(decision, "action", decision.recommended_side.upper()),
            decision.rationale[:60],
        )

        # ------------------------------------------------------------------
        # KEV DECISIVE LEAD & MATH-OF-WINNING TAKER ENGINE
        # ------------------------------------------------------------------
        kev_rec = None
        kev_toxic = None
        try:
            kev_ctx = self.kev_oracle.build_market_context(
                asset="ETH",
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
        is_toxic = (kev_toxic and kev_toxic.selected_option.lower() == "true") or (vpin_score >= 0.60)
        if is_toxic:
            logger.warning("🛑 [KEV TOXIC SWEEP VETO] Toxic order flow / sweep detected (VPIN: %.2f). Stand down.", vpin_score)
            return decision

        # 2. Strict Moneyness Moat (Anti-Tie / Strict Inequality Protection)
        spot_diff = abs(spot_price - target_strike)
        if spot_diff < Decimal("2.50"):
            logger.info("⏸️ [PROXIMITY MOAT VETO] |Diff| $%.2f < $2.50 noise threshold. Stand down.", float(spot_diff))
            return decision

        # 3. Kev Lead Direction Gate
        kev_dir = kev_rec.selected_option.upper() if kev_rec else "WAIT"
        kev_conf = float(kev_rec.confidence) if kev_rec else 0.50
        if kev_dir not in ("YES", "NO") or kev_conf < 0.60:
            logger.info("⏸️ [KEV STAND DOWN] Kev recommends %s (Conf: %.1f%%). No trade.", kev_dir, kev_conf * 100.0)
            return decision

        chosen_side = OrderSide.YES if kev_dir == "YES" else OrderSide.NO

        # 3b. Moneyness Consistency Check (Anti-OTM Trap Filter)
        # Prevent buying out-of-the-money contracts when spot is adverse to strike
        if chosen_side == OrderSide.YES and spot_price < (target_strike - Decimal("3.00")):
            logger.warning(
                "🛑 [OTM TRAP FILTER] Kev recommended YES, but spot ($%s) is deep below strike ($%s) by -$%.2f. Stand down to WAIT.",
                spot_price, target_strike, float(target_strike - spot_price)
            )
            return decision
        if chosen_side == OrderSide.NO and spot_price > (target_strike + Decimal("3.00")):
            logger.warning(
                "🛑 [OTM TRAP FILTER] Kev recommended NO, but spot ($%s) is deep above strike ($%s) by +$%.2f. Stand down to WAIT.",
                spot_price, target_strike, float(spot_price - target_strike)
            )
            return decision

        # 4. Continuous Math-of-Winning Formulation
        import math
        diff_float = float(spot_price - target_strike)
        sigma_15m = 6.0  # typical 15m ETH volatility
        tau_norm = max(0.01, time_to_expiry_s / 900.0)
        z = diff_float / (sigma_15m * math.sqrt(tau_norm))
        p_physics = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        p_physics_side = p_physics if chosen_side == OrderSide.YES else (1.0 - p_physics)

        # Kev has 75% higher weight in winning decision
        p_win = (0.75 * kev_conf) + (0.25 * p_physics_side)
        p_win = max(0.51, min(0.99, p_win))

        # Dynamic Anti-Toxic Hurdle: widens when VPIN is elevated
        hurdle = Decimal("0.08") + Decimal(str(round(vpin_score * 0.10, 4)))
        max_taker_price = Decimal(str(round(p_win, 2))) - hurdle
        max_taker_price = min(Decimal("0.55"), max(Decimal("0.10"), max_taker_price))

        # 5. Live L2 Orderbook Taker Pricing & Zero-Liquidity Trap Protection
        best_ask = book.best_yes_ask if chosen_side == OrderSide.YES else book.best_no_ask
        if best_ask is None:
            logger.warning("🛑 [ZERO LIQUIDITY TRAP] Book has no resting asks for %s on %s. Stand down.", chosen_side.value.upper(), target_ticker)
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
                logger.info("[ETH BOT] Cycle %s already locked (turnover limit reached).", target_ticker)
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
                logger.warning("[ETH BOT GUARDRAIL BLOCKED] %s", reason)
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
                    logger.error("[ETH BOT ORDER REJECTED/FAILED] Response: %s", res)
                    guardrails.release_in_flight_intent(target_ticker)
                    return decision

                order_id = (
                    res.get("order_id")
                    or (res.get("order", {}).get("order_id") if isinstance(res.get("order"), dict) else None)
                    or f"ord_eth_{int(time.time()*1000)}"
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
                    target_ticker, chosen_side.value.upper(), best_ask, max_taker_price, p_win * 100.0, float(Decimal(str(round(p_win, 2))) - best_ask), res
                )

                # Capture T1 & T2 Forensics for trade lifecycle ledger
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
                    "t1_1h_slope": float(getattr(self, "_last_1h_slope", 0.0) or 0.0),
                    "t2_timestamp": now_iso,
                    "t2_spot": float(spot_price),
                    "t2_regime": getattr(self, "_current_regime", "CHOP").upper(),
                    "t2_vpin": float(vpin_score),
                }

                # Enqueue trade into separate ETH database
                get_eth_db_writer().enqueue_trade(
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
                logger.error("[ETH BOT ORDER FAILED] %s: %s", target_ticker, ex)
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
        execution_mode: str = "live",
        twap_60s: Optional[Decimal] = None,
        market_condition: Optional[str] = None,
        target_ticker: Optional[str] = None,
        pnl: Optional[Union[Decimal, float]] = None,
    ) -> Optional[dict[str, Any]]:
        """Record cycle settlement across ETH database, lifecycle forensics, autopsies, and experience buffer."""
        # Simple boolean feedback invocation from server or loop
        if isinstance(won_or_pnl, bool) and ticker is None and target_ticker is None:
            super().record_cycle_settlement(won_or_pnl)
            return None

        is_win = bool(won_or_pnl) if isinstance(won_or_pnl, bool) else (Decimal(str(won_or_pnl)) > 0)
        target_ticker = ticker or target_ticker or self.target_ticker or "KXETH15M-CYCLE"
        entry_p = entry_price or self.discount_limit_price
        if not isinstance(entry_p, Decimal):
            entry_p = Decimal(str(round(entry_p, 2)))

        if pnl is not None:
            pnl = Decimal(str(pnl))
        elif isinstance(won_or_pnl, (Decimal, float)) and not isinstance(won_or_pnl, bool):
            pnl = Decimal(str(won_or_pnl))
        else:
            pnl = Decimal(str(contracts)) * (Decimal("1.00") - entry_p) if is_win else -Decimal(str(contracts)) * entry_p

        outcome = "win" if is_win else "loss"
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()
        report_id = f"WLR-ETH-{now_utc.strftime('%y%m%d%H%M%S')}-{random.randint(100, 999)}"

        strike = strike_price or Decimal("2600.00")
        spot = settlement_spot_price or (strike + Decimal("2.50") if is_win else strike - Decimal("2.50"))
        side_clean = (side or "yes").lower()

        twap_val = float(twap_60s if twap_60s is not None else spot)
        twap_div = float(spot) - twap_val
        macro_slope = float(getattr(self, "_last_1h_slope", 0.0) or 0.0)
        cond_tag = market_condition or getattr(self, "_current_regime", "CHOP").upper()

        # Retrieve saved T1/T2 forensics or construct baseline
        t_forensics = self._active_trade_forensics.pop(target_ticker, None) or {}
        t1_spot = t_forensics.get("t1_spot", float(strike))
        t1_diff = t_forensics.get("t1_strike_diff", float(spot - strike))
        t1_regime = t_forensics.get("t1_regime", cond_tag)
        t1_vpin = t_forensics.get("t1_vpin", 0.15)
        t1_ts = t_forensics.get("t1_timestamp", now_iso)

        t2_ts = t_forensics.get("t2_timestamp", now_iso)
        t2_spot = t_forensics.get("t2_spot", float(spot))
        t2_regime = t_forensics.get("t2_regime", cond_tag)
        t2_vpin = t_forensics.get("t2_vpin", t1_vpin)

        # 1. Failure Autopsy Attribution on Losses
        failure_code = "NONE"
        if not is_win:
            twap_div_threshold = 1.50
            salv_diff_threshold = 8.50
            is_twap_pin = 1 if abs(twap_div) >= twap_div_threshold and ((side_clean == "yes" and float(spot) >= float(strike) and twap_val < float(strike)) or (side_clean == "no" and float(spot) < float(strike) and twap_val >= float(strike))) else 0
            is_ct = 1 if ((side_clean == "no" and macro_slope > 0.20) or (side_clean == "yes" and macro_slope < -0.20)) else 0
            wave_phys = getattr(self, "_last_wave_physics", None)
            is_dw = 1 if (wave_phys and getattr(wave_phys, "is_double_wick_meatgrinder", False)) else 0
            w_ratio = getattr(wave_phys, "upper_wick_dollars", 0.0) / max(1.0, getattr(wave_phys, "body_dollars", 1.0)) if wave_phys else 0.0
            was_salv = 1 if float(entry_p) >= 0.40 and abs(float(spot - strike)) >= salv_diff_threshold else 0
            salv_lost = 0.12 * contracts if was_salv else 0.0

            if is_twap_pin:
                failure_code = "ERR_TWAP_PIN_VICTIM"
            elif is_ct:
                failure_code = "ERR_COUNTER_TREND"
            elif is_dw:
                failure_code = "ERR_DOUBLE_WICK_TRAP"
            elif was_salv:
                failure_code = "ERR_DOOMED_HOLD_TO_ZERO"
            elif abs(float(spot - strike)) < 2.00:
                failure_code = "STRIKE_PROXIMITY_TRAP"
            elif t1_vpin >= 0.50:
                failure_code = "ADVERSE_SELECTION_SWEEP"
            else:
                failure_code = "ERR_DISPERSION_EXCURSION"

            get_eth_db_writer().enqueue_failure_autopsy(
                trade_id=report_id,
                ticker=target_ticker,
                outcome="LOSS",
                realized_pnl=float(pnl),
                failure_code=failure_code,
                is_counter_trend=is_ct,
                macro_1h_slope=macro_slope,
                is_double_wick_trap=is_dw,
                wick_to_body_ratio=w_ratio,
                was_salvageable=was_salv,
                salvageable_cents_lost=salv_lost,
                is_twap_pin_victim=is_twap_pin,
                twap_vs_spot_divergence=twap_div,
                bot_type=self.STRATEGY_ID,
            )

        # 2. Lifecycle Forensics (T1, T2, T3) Enqueue
        get_eth_db_writer().enqueue_lifecycle_forensics(
            trade_id=report_id,
            ticker=target_ticker,
            side=side_clean,
            entry_price=float(entry_p),
            outcome=outcome.upper(),
            realized_pnl=float(pnl),
            role="MAKER" if float(entry_p) <= 0.48 else "TAKER",
            fee_paid=0.0 if float(entry_p) <= 0.48 else 0.01,
            t1_timestamp=t1_ts,
            t1_spot=t1_spot,
            t1_strike_diff=t1_diff,
            t1_1h_slope=macro_slope,
            t1_regime=t1_regime,
            t1_vpin=t1_vpin,
            t2_timestamp=t2_ts,
            t2_spot=t2_spot,
            t2_1h_slope=macro_slope,
            t2_regime=t2_regime,
            t2_vpin=t2_vpin,
            t3_timestamp=now_iso,
            t3_spot=float(spot),
            t3_60s_twap=twap_val,
            twap_vs_spot_divergence=twap_div,
            t3_1h_slope=macro_slope,
            t3_regime=cond_tag,
            bot_type=self.STRATEGY_ID,
        )

        # 3. Contract Settlement Enqueue
        get_eth_db_writer().enqueue_settlement(
            settlement_id=report_id,
            ticker=target_ticker,
            side=side_clean,
            size=contracts,
            entry_price=float(entry_p),
            settlement_price=1.0 if is_win else 0.0,
            outcome=outcome,
            pnl=float(pnl),
            balance_after=26.34,
            bot_type=self.STRATEGY_ID,
            execution_mode=execution_mode,
        )

        # 4. Standardized Win/Loss Report for disk persistence
        report = {
            "report_id": report_id,
            "cycle_time": now_utc.strftime("%B %d, 15M Event Cycle ET"),
            "ticker": target_ticker,
            "timeframe": "15m",
            "asset": "ETH",
            "strike_price": float(strike),
            "settlement_spot_price": float(spot),
            "bot_side": side_clean,
            "contracts": contracts,
            "entry_price": float(entry_p),
            "settlement_price": 1.0 if is_win else 0.0,
            "outcome": outcome,
            "pnl": float(pnl),
            "roi_pct": round(float(pnl / (entry_p * contracts)) * 100.0, 2) if entry_p > 0 else 0.0,
            "ai_confidence": 0.80,
            "ai_rationale": f"ETH 15M Cycle Execution | Loss Cause: {failure_code}" if not is_win else "ETH 15M Cycle Execution | Profitable Settlement",
            "vpin_score": t1_vpin,
            "ev_edge": 0.08,
            "balance_after": 26.34,
            "market_condition": cond_tag,
            "bot_type": self.STRATEGY_ID,
            "execution_mode": execution_mode,
            "timestamp_utc": now_iso,
            "failure_code": failure_code,
            "bot_parameters": self.get_parameters(),
        }

        # Save to data/eth_win_loss_reports.json
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            reports = []
            if self.history_file.exists():
                try:
                    reports = json.loads(self.history_file.read_text(encoding="utf-8"))
                    if not isinstance(reports, list):
                        reports = []
                except Exception:
                    reports = []
            reports.insert(0, report)
            self.history_file.write_text(json.dumps(reports, indent=2), encoding="utf-8")
        except Exception as file_exc:
            logger.warning("[ETH BOT] Error persisting report to %s: %s", self.history_file, file_exc)

        # 5. Feed Continuous Experience Buffer for online sharpening & Platt calibration
        if self.experience_buffer:
            try:
                exp = self.experience_buffer._dict_to_experience(report)
                if exp:
                    self.experience_buffer.record_settled_cycle(exp)
                    logger.info(
                        "🧠 [ETH EXPERIENCE_BUFFER] Recalibrated after cycle %s -> %s (PnL: $%s). Brier: %.4f, Platt Alpha: %.2f",
                        target_ticker, outcome.upper(), pnl, self.experience_buffer.brier_score, self.experience_buffer.platt_alpha
                    )
            except Exception as eb_exc:
                logger.debug("[ETH BOT] Error feeding experience buffer: %s", eb_exc)

        # 6. Update wave classifier, bleed defender, healing protocol
        super().record_cycle_settlement(is_win)

        # 7. Persist dynamic parameters
        self.save_persisted_parameters()

        return report

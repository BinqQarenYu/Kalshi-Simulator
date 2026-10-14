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
import time
from typing import Any, Optional

import aiohttp

from kalshi_sim.auth import DEMO_REST_BASE, PROD_REST_BASE, get_auth_headers
from kalshi_sim.ml.bot1_v4_engine import Bot1V4Decision, Bot1V4DominationEngine
from kalshi_sim.ml.experience_buffer import ContinuousExperienceBuffer
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
        if "experience_buffer" not in kwargs or kwargs["experience_buffer"] is None:
            buffer_path = Path(hist_file) if hist_file else Path("data/eth_win_loss_reports.json")
            buffer_path.parent.mkdir(parents=True, exist_ok=True)
            kwargs["experience_buffer"] = ContinuousExperienceBuffer(history_file=buffer_path)

        super().__init__(*args, **kwargs)

        self.min_spot_diff_bleed = float(min_bleed_diff)
        if hasattr(self, "bleed_defender") and self.bleed_defender:
            self.bleed_defender.min_spot_diff_bleed = self.min_spot_diff_bleed

        self.order_client = order_client
        self.orderflow_feed = orderflow_feed
        self.target_ticker: Optional[str] = target_ticker
        self._cached_market: Optional[MarketInfo] = None
        self._last_market_fetch_ts: float = 0.0

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
            async with aiohttp.ClientSession(connector=connector, headers=headers, timeout=timeout) as session:
                async with session.get(url) as resp:
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
        connector = create_aiohttp_connector()
        headers = {
            "User-Agent": "KalshiSim-EthBot1V4/1.0",
            "Accept": "application/json",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=3.0)
            async with aiohttp.ClientSession(connector=connector, headers=headers, timeout=timeout) as session:
                async with session.get(url) as resp:
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
        """Retrieve current ETH spot price from feed or fallback."""
        if self.orderflow_feed and self.orderflow_feed.last_spot_price > 0:
            return self.orderflow_feed.last_spot_price
        return Decimal("2600.00")

    async def run_cycle(self, ticker: Optional[str] = None) -> Optional[Bot1V4Decision]:
        """Execute a single cycle iteration of the ETH Bot 1 V4 engine.

        1. Discovers active KXETH15M 15-minute market.
        2. Ingests Level-2 orderbook.
        3. Retrieves real-time ETH spot price.
        4. Evaluates market opportunity using Bot 1 V4 quantitative logic with ETH calibration.
        5. If signal is actionable ('yes' or 'no' with >0 contracts) and order_client is attached:
           executes 1 contract adhering to micro-bankroll rules and 1-trade-per-cycle lock.
        """
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

        # Execution guardrails: 1 trade per cycle & micro-bankroll sizing (1 contract)
        if decision.recommended_side in ("yes", "no") and decision.recommended_contracts > 0:
            if self.order_client:
                # 1-trade-per-cycle lock check
                completed = self.get_completed_turnovers(target_ticker)
                if completed >= self.max_turnover_per_event:
                    logger.info("[ETH BOT] Cycle %s already locked (turnover limit reached).", target_ticker)
                    return decision

                order_side = OrderSide.YES if decision.recommended_side == "yes" else OrderSide.NO
                limit_p = getattr(decision, "limit_price", Decimal("0.42"))
                if not isinstance(limit_p, Decimal):
                    limit_p = Decimal(str(round(limit_p, 2)))

                try:
                    order_kwargs: dict[str, Any] = {
                        "ticker": target_ticker,
                        "side": order_side.value,
                        "count": 1,
                        "order_type": getattr(decision, "order_type", "limit"),
                    }
                    try:
                        sig = inspect.signature(self.order_client.place_order)
                        if "price_dollars" in sig.parameters:
                            order_kwargs["price_dollars"] = limit_p
                        else:
                            order_kwargs["price"] = limit_p
                    except Exception:
                        order_kwargs["price_dollars"] = limit_p

                    res = await self.order_client.place_order(**order_kwargs)
                    self.record_completed_turnover(target_ticker)
                    logger.info("🚀 [ETH BOT ORDER EXECUTED] %s %s 1 ct @ $%s | Result: %s", target_ticker, order_side.value, limit_p, res)
                except Exception as ex:
                    logger.error("[ETH BOT ORDER FAILED] %s: %s", target_ticker, ex)

        return decision

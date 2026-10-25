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
                            strike_price=strike_dec,
                            expiration_time=target.get("close_time", target.get("expiration_time")),
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

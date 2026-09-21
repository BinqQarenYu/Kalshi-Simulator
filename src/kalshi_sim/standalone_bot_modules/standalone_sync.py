"""Standalone Bot Account Sync & Settlement Reconciliation Module."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
import ctypes
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
import logging
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Union
from zoneinfo import ZoneInfo

import aiohttp
from kalshi_sim.agent_guardrails import AgentGuardrails
from kalshi_sim.auth import (
    DEMO_REST_BASE,
    DEMO_WS_URL,
    PROD_REST_BASE,
    PROD_WS_URL,
    create_aiohttp_connector,
    load_private_key,
)
from kalshi_sim.bot_deployment_auditor import BotDeploymentAuditor
from kalshi_sim.cfbenchmarks_sync import CFBenchmarksSync
from kalshi_sim.clock_sync import clock_sync
from kalshi_sim.db import get_db_writer, DatabaseWriter
import kalshi_sim.standalone_bot as sb
from kalshi_sim.incubator_manager import get_incubator_manager
from kalshi_sim.live_coordinator import LiveCoordinator
from kalshi_sim.ml.domination_bot import DominationDecision, ThreeStepDominationBot
from kalshi_sim.ml.macro_trend_dominion_bot import MacroTrendDominionBot
from kalshi_sim.ml.onnx_engine import KalshiONNXEngine
from kalshi_sim.order_client import KalshiDemoOrderClient, KalshiLiveOrderClient
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.poe_flight_recorder import POEFlightRecorder, POEDecisionRecord
from kalshi_sim.rate_limiter import kalshi_rate_limiter
from kalshi_sim.schemas import (
    CRYPTO_ASSETS,
    CryptoAsset,
    get_asset_config,
    L2BookState,
    MarketInfo,
    MarketStatus,
    OrderSide,
    OrderType,
    Timeframe,
    TradeEvent,
)
from kalshi_sim.standalone_bot_modules.config import DEFAULT_ASSET_PROFILES, ET_ZONE
from kalshi_sim.standalone_bot_modules.power import format_cycle_time_from_iso

logger = logging.getLogger("StandaloneBot")


class _BaseCoordinator:
    """Base proxy coordinator forwarding attribute lookup and mutation to the parent engine."""
    def __init__(self, engine: Any) -> None:
        object.__setattr__(self, "engine", engine)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "engine"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "engine":
            object.__setattr__(self, "engine", value)
        else:
            setattr(object.__getattribute__(self, "engine"), name, value)


class StandaloneSyncCoordinator(_BaseCoordinator):
    """Handles balance polling, position sync, watchdog loops, and settlement reconciliation."""

    def sync_pnl_reports(self) -> None:
        """Sync realized PnL and settled cycles from persisted win_loss_reports.json."""
        reports_file = self.data_dir / "win_loss_reports.json"
        if not reports_file.exists():
            return
        try:
            content = reports_file.read_text(encoding="utf-8")
            all_reports = json.loads(content)
            now_utc = datetime.now(timezone.utc)
            today_prefix = now_utc.strftime("%y%b%d").upper()
            today_iso = now_utc.strftime("%Y-%m-%d")

            today_reports = [
                r for r in all_reports
                if (r.get("execution_mode") == "live" or r.get("bot_type") == "live" or not self.is_live)
                and (today_prefix in r.get("ticker", "") or today_iso in str(r.get("timestamp_utc", "")))
            ]
            self.settled_cycles = len(today_reports)
            pnl_sum = sum(float(r.get("pnl", 0.0)) for r in today_reports)
            self.today_pnl = Decimal(str(round(pnl_sum, 2)))

            wins = sum(1 for r in today_reports if r.get("outcome") == "win")
            self.today_wins = wins
            self.today_losses = self.settled_cycles - wins
            self.today_win_rate = (wins / self.settled_cycles * 100.0) if self.settled_cycles > 0 else 0.0

            # Store recent 5 settlements for display
            self.recent_reports = [
                {
                    "ticker": r.get("ticker", ""),
                    "side": r.get("bot_side", "").upper(),
                    "outcome": r.get("outcome", "").upper(),
                    "pnl": float(r.get("pnl", 0.0)),
                    "strike": float(r.get("strike_price", 0.0)),
                    "settle_price": float(r.get("settlement_btc_price", 0.0)),
                    "contracts": r.get("contracts", 1),
                    "time": r.get("timestamp_utc", "")[:19].replace("T", " "),
                }
                for r in today_reports[:5]
            ]
        except Exception as exc:
            logger.debug("Error syncing PnL reports: %s", exc)

    async def sync_balance(self) -> None:
        """Sync live account balance from Kalshi portfolio and Polymarket.
        
        When budget partitioning is active (--budget flag), balance_dollars is
        clamped to min(real_balance, budget_cap).
        """
        try:
            self.polymarket_balance_dollars = await asyncio.wait_for(
                asyncio.to_thread(pm_client.get_usdc_balance), timeout=3.0
            )
        except Exception as e:
            logger.debug("Polymarket balance sync error: %s", e)

        if self.order_client:
            try:
                data = await self.order_client.get_balance()
                b_all = data.get("balance_dollars")
                if b_all is not None:
                    self.total_balance_dollars = Decimal(str(b_all))
                b2 = self.order_client.shard_balances.get(2)
                if b2 is not None:
                    self.shard2_balance_dollars = b2
                else:
                    self.shard2_balance_dollars = self.total_balance_dollars
                if self.budget_dollars is not None:
                    self.balance_dollars = min(self.total_balance_dollars, self.budget_dollars)
                else:
                    self.balance_dollars = self.total_balance_dollars
            except Exception as e:
                logger.debug("Balance sync error: %s", e)

    async def sync_positions(self) -> None:
        """Sync live open positions from Kalshi exchange to track for take-profit ceiling."""
        if self.order_client:
            try:
                positions = await self.order_client.get_positions()
                open_tickers = set()
                for p in positions:
                    ticker = p.get("ticker") or p.get("market_ticker")
                    if not ticker:
                        continue
                    pos_raw = p.get("position", p.get("position_fp", 0))
                    try:
                        pos_cnt = int(float(str(pos_raw)))
                    except (ValueError, TypeError):
                        pos_cnt = 0
                    if pos_cnt > 0:
                        open_tickers.add(ticker)
                        side_raw = p.get("side", "yes")
                        side = OrderSide.YES if str(side_raw).lower() == "yes" else OrderSide.NO
                        entry_p = self.bot.discount_limit_price
                        if ticker in self.active_positions and self.active_positions[ticker].get("entry_price"):
                            entry_p = self.active_positions[ticker]["entry_price"]
                        elif self.active_position and self.active_position.get("ticker") == ticker and self.active_position.get("entry_price"):
                            entry_p = self.active_position["entry_price"]

                        existing_p = self.active_positions.get(ticker, {})
                        pos_dict = {
                            "ticker": ticker,
                            "side": side,
                            "size": pos_cnt,
                            "entry_price": entry_p,
                            "entry_time": existing_p.get("entry_time", time.time()),
                            "peak_bid": existing_p.get("peak_bid", entry_p),
                            "asset": existing_p.get("asset", self.active_asset.value),
                            "target_strike": existing_p.get("target_strike"),
                            "close_dt": existing_p.get("close_dt"),
                        }
                        self.active_positions[ticker] = pos_dict
                        if ticker == self.active_ticker:
                            self.active_position = pos_dict

                # Prune closed positions
                for t in list(self.active_positions.keys()):
                    if t not in open_tickers:
                        self.active_positions.pop(t, None)
                        if self.active_position and self.active_position.get("ticker") == t:
                            self.active_position = None
            except Exception as pe:
                logger.debug("Error syncing positions from Kalshi: %s", pe)

    def _record_exit_report(
        self,
        ticker: str,
        side: str,
        size: int,
        entry_price: float,
        exit_price: float,
        net_pnl: float,
        exit_reason: str,
    ) -> None:
        """Persist early take-profit exit report to win_loss_reports.json."""
        reports_file = self.data_dir / "win_loss_reports.json"
        all_reports: List[Dict[str, Any]] = []
        if reports_file.exists():
            try:
                all_reports = json.loads(reports_file.read_text(encoding="utf-8"))
            except Exception:
                all_reports = []

        report_id = f"WLR-TP-{ticker}-{int(time.time())}"
        now_iso = datetime.now(timezone.utc).isoformat()
        report = {
            "report_id": report_id,
            "ticker": ticker,
            "bot_side": side.upper(),
            "outcome": "win" if net_pnl >= 0.0 else "loss",
            "pnl": round(net_pnl, 2),
            "roi_pct": round(((exit_price - entry_price) / max(0.01, entry_price)) * 100.0, 2),
            "contracts": size,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "settlement_price": exit_price,
            "timestamp_utc": now_iso,
            "execution_mode": "live" if self.order_client else "paper",
            "bot_type": self.bot_id,
            "exit_reason": exit_reason,
            "bot_parameters": self.bot.get_parameters() if hasattr(self.bot, "get_parameters") else None,
        }
        all_reports.insert(0, report)
        # Cap to latest 100 entries to prevent file and token bloat
        all_reports = all_reports[:100]
        try:
            reports_file.write_text(json.dumps(all_reports, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Error writing exit win_loss_report: %s", e)

    def _finalize_take_profit_exit(
        self,
        pos_ticker: str,
        pos: Dict[str, Any],
        exit_dec: Any,
    ) -> None:
        """Finalize early take-profit exit: record in SQLite trades, update PnL, and purge position."""
        self.db_writer.enqueue_trade(
            trade_id=f"tp_{int(time.time()*1000)}",
            ticker=pos["ticker"],
            side=str(pos["side"]).lower(),
            size=pos["size"],
            price=float(exit_dec.exit_price),
            gross_value=float(exit_dec.exit_price * Decimal(str(pos["size"]))),
            fees=float(self.bot.fee_per_contract * Decimal(str(pos["size"]))),
            vpin=0.15,
            timeframe=self.get_current_timeframe(),
            bot_type=self.bot_id,
            execution_mode="live" if (self.is_live and self.order_client) else "paper",
            status="take_profit_exit",
        )
        self.today_pnl += exit_dec.unrealized_pnl
        is_win = exit_dec.unrealized_pnl >= Decimal("0.00")
        if is_win:
            self.today_wins += 1
            self.consecutive_losses = 0
        else:
            self.today_losses += 1
            self.consecutive_losses += 1
        self.settled_cycles += 1
        self.today_win_rate = (self.today_wins / self.settled_cycles * 100.0) if self.settled_cycles > 0 else 0.0
        self._record_exit_report(
            ticker=pos["ticker"],
            side=str(pos["side"]).lower(),
            size=pos["size"],
            entry_price=float(pos["entry_price"]),
            exit_price=float(exit_dec.exit_price),
            net_pnl=float(exit_dec.unrealized_pnl),
            exit_reason=exit_dec.exit_reason,
        )
        self.active_positions.pop(pos_ticker, None)
        if self.active_position and self.active_position.get("ticker") == pos_ticker:
            self.active_position = None
        self.sync_pnl_reports()
        logger.info(
            "✅ [TAKE PROFIT EXECUTED] Position closed at $%s ceiling! Banked +$%s on %s.",
            exit_dec.exit_price, exit_dec.unrealized_pnl, pos_ticker,
        )

    async def _balance_polling_loop(self) -> None:
        """Poll balance, positions, and PnL settlements every 5 seconds."""
        while self._running:
            await self.sync_balance()
            await self.sync_positions()
            self.sync_pnl_reports()
            await asyncio.sleep(5.0)


    async def _resting_order_watchdog_loop(self) -> None:
        """Watch resting limit orders and auto-cancel prior to expiration (t_rem <= 45s or <= 0s) or once event is finished."""
        while self._running:
            try:
                t_rem = self.get_time_to_expiry()
                if self.order_client:
                    # 1. Pre-Expiry & Expired Cleanup for active contract (t_rem <= 45s, including <= 0)
                    if t_rem <= 45.0:
                        if self.active_resting_orders:
                            for oid, o_info in list(self.active_resting_orders.items()):
                                if o_info.get("ticker") == self.active_ticker:
                                    try:
                                        await self.order_client.cancel_order(oid, ticker=self.active_ticker)
                                        self.active_resting_orders.pop(oid, None)
                                        logger.warning(
                                            "🛑 [PRE-EXPIRY CLEANUP] Auto-cancelled unfilled resting order %s on %s at T=%.0fs.",
                                            oid, self.active_ticker, t_rem
                                        )
                                    except Exception as c_err:
                                        logger.debug("Error cancelling resting order %s: %s", oid, c_err)

                        # Check exchange open orders for expiring active ticker
                        try:
                            open_orders = await self.order_client.get_open_orders()
                            for o in open_orders:
                                if o.get("ticker") == self.active_ticker:
                                    oid = o.get("order_id")
                                    if oid:
                                        await self.order_client.cancel_order(oid, ticker=self.active_ticker)
                                        logger.warning(
                                            "🛑 [PRE-EXPIRY CLEANUP] Auto-cancelled exchange open order %s on %s at T=%.0fs.",
                                            oid, self.active_ticker, t_rem
                                        )
                        except Exception as o_err:
                            logger.debug("Error querying open orders in watchdog: %s", o_err)

                    # 1.2 Velocity Panic-Cancel (Non-Live Only)
                    if not self.is_live and self.active_resting_orders:
                        try:
                            vel_3s = self.get_spot_velocity_3s(self.active_asset)
                            thresh = getattr(self.bot, 'spot_delta_front_run_threshold', 28.0)
                            if abs(vel_3s) >= thresh:
                                for oid, o_info in list(self.active_resting_orders.items()):
                                    if o_info.get("action") == "buy":  # Only cancel entry limit orders
                                        try:
                                            await self.order_client.cancel_order(oid, ticker=self.active_ticker)
                                            self.active_resting_orders.pop(oid, None)
                                            logger.warning(
                                                "⚠️ [VELOCITY PANIC-CANCEL] Auto-cancelled resting %s entry order %s. Spot Velocity (%.2f $/3s) exceeded threshold (%.2f).",
                                                o_info.get("side"), oid, vel_3s, thresh
                                            )
                                        except Exception as c_err:
                                            logger.debug("Error cancelling order on velocity spike: %s", c_err)
                        except Exception as vel_err:
                            logger.debug("Error in velocity panic-cancel: %s", vel_err)

                    # 1.5 Detect fills on active resting orders
                    if self.active_resting_orders:
                        try:
                            open_orders = await self.order_client.get_open_orders()
                            open_oids = {o.get("order_id") for o in open_orders}
                            for oid, o_info in list(self.active_resting_orders.items()):
                                if oid not in open_oids:
                                    t_tkr = o_info.get("ticker")
                                    if o_info.get("action") == "sell":
                                        # Resting Take-Profit Exit order filled!
                                        exit_dec = o_info.get("exit_dec")
                                        pos = o_info.get("pos")
                                        if exit_dec and pos and t_tkr:
                                            self._finalize_take_profit_exit(t_tkr, pos, exit_dec)
                                        self.active_resting_orders.pop(oid, None)
                                        logger.info(
                                            "🎉 [TAKE PROFIT FILLED] Resting exit order %s on %s FILLED! Position closed.",
                                            oid, t_tkr,
                                        )
                                        await self.sync_balance()
                                    else:
                                        # Resting Entry Buy order filled!
                                        entry_asset = self.active_asset
                                        for a in CryptoAsset:
                                            cfg_a = get_asset_config(a)
                                            if t_tkr and (t_tkr.startswith(cfg_a.series_ticker_15m) or (a.value in t_tkr)):
                                                entry_asset = a
                                                break
                                        pos_dict = {
                                            "ticker": t_tkr,
                                            "side": o_info.get("side", "yes"),
                                            "size": o_info.get("size", 1),
                                            "entry_price": o_info.get("price", Decimal("0.52")),
                                            "entry_time": time.time(),
                                            "order_id": oid,
                                            "asset": entry_asset.value,
                                        }
                                        if t_tkr:
                                            self.active_positions[t_tkr] = pos_dict
                                            p_price = o_info.get("price", Decimal("0.52"))
                                            self.poe_recorder.record_fill(
                                                cycle_id=t_tkr,
                                                order_side=o_info.get("side", "yes"),
                                                order_type="LIMIT",
                                                order_price=p_price,
                                                fill_price=p_price,
                                                fill_slippage=Decimal("0.00"),
                                                queue_depth_ahead=0,
                                                taker_fee_paid=Decimal("0.00"),
                                            )
                                        if t_tkr == self.active_ticker:
                                            self.active_position = pos_dict
                                        self.active_resting_orders.pop(oid, None)
                                        logger.info(
                                            "🎉 [ORDER FILLED] Resting order %s on %s FILLED! Position active for Take Profit monitoring.",
                                            oid, t_tkr,
                                        )
                        except Exception as f_err:
                            logger.debug("Error checking resting order fills: %s", f_err)

                    # 2. Continuous Finished Event Sweep: Cancel resting orders on truly finished/past contracts
                    try:
                        # Build protected tickers set: any ticker with open positions, active resting orders, or active unexpired cycles
                        protected_tickers = set()
                        for p_tkr in self.active_positions.keys():
                            protected_tickers.add(p_tkr)
                        for r_info in self.active_resting_orders.values():
                            r_tkr = r_info.get("ticker")
                            if r_tkr:
                                protected_tickers.add(r_tkr)
                        for m in self.asset_markets.values():
                            m_tkr = m.get("ticker")
                            c_dt = m.get("close_dt")
                            if m_tkr and self.get_time_to_expiry(c_dt) > 45.0:
                                protected_tickers.add(m_tkr)
                        if self.active_ticker and self.get_time_to_expiry(self.active_market_close_dt) > 45.0:
                            protected_tickers.add(self.active_ticker)

                        open_orders = await self.order_client.get_open_orders()
                        for o in open_orders:
                            t = o.get("ticker")
                            oid = o.get("order_id")
                            if oid and t and t not in protected_tickers:
                                try:
                                    await self.order_client.cancel_order(oid, ticker=t)
                                    logger.warning(
                                        "🧹 [FINISHED EVENT SWEEP] Auto-cancelled resting order %s on finished event %s (protected: %s).",
                                        oid, t, list(protected_tickers),
                                    )
                                except Exception as c_err:
                                    logger.debug("Error cancelling finished event order %s: %s", oid, c_err)
                    except Exception as sweep_err:
                        logger.debug("Error sweeping non-active ticker orders: %s", sweep_err)

                    # 3. Entry Window Close Sweep (Option C)
                    # Wipe and auto-cancel all resting entry BUY orders once remaining cycle time breaches entry_window_close_minutes
                    if self.active_resting_orders:
                        for oid, o_info in list(self.active_resting_orders.items()):
                            if o_info.get("action") == "sell":
                                continue
                            o_ast_key = o_info.get("asset", self.active_asset.value)
                            o_profile = self.asset_profiles.get(o_ast_key, DEFAULT_ASSET_PROFILES.get(o_ast_key, {}))
                            close_min = float(o_profile.get("entry_window_close_minutes", 4.5))
                            close_sec = close_min * 60.0
                            o_tkr = o_info.get("ticker", self.active_ticker)
                            m_info = self.asset_markets.get(o_ast_key, {})
                            c_dt = m_info.get("close_dt", self.active_market_close_dt)
                            t_rem_order = self.get_time_to_expiry(c_dt)
                            if t_rem_order <= close_sec:
                                try:
                                    await self.order_client.cancel_order(oid, ticker=o_tkr)
                                    self.active_resting_orders.pop(oid, None)
                                    logger.warning(
                                        "🛑 [WINDOW CLOSE SWEEP] Auto-cancelled resting entry order %s on %s at T=%.0fs (Cutoff: %.1fm).",
                                        oid, o_tkr, t_rem_order, close_min
                                    )
                                except Exception as c_err:
                                    logger.debug("Error cancelling window-breached order %s: %s", oid, c_err)
                else:
                    # Simulated / Paper mode watchdog sweeps
                    if self.active_resting_orders:
                        for oid, o_info in list(self.active_resting_orders.items()):
                            if o_info.get("action") == "sell":
                                continue
                            o_ast_key = o_info.get("asset", self.active_asset.value)
                            o_profile = self.asset_profiles.get(o_ast_key, DEFAULT_ASSET_PROFILES.get(o_ast_key, {}))
                            close_min = float(o_profile.get("entry_window_close_minutes", 4.5))
                            close_sec = close_min * 60.0
                            m_info = self.asset_markets.get(o_ast_key, {})
                            c_dt = m_info.get("close_dt", self.active_market_close_dt)
                            t_rem_order = self.get_time_to_expiry(c_dt)
                            if t_rem_order <= close_sec:
                                self.active_resting_orders.pop(oid, None)
                                logger.warning(
                                    "🛑 [WINDOW CLOSE SWEEP] Auto-cancelled simulated resting entry order %s at T=%.0fs (Cutoff: %.1fm).",
                                    oid, t_rem_order, close_min
                                )

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("Watchdog loop error: %s", exc)

            await asyncio.sleep(2.0)

    async def _settlement_reconciliation_loop(self) -> None:
        """Autonomous 24/7 Kalshi portfolio settlement reconciliation loop."""
        while self._running:
            try:
                if self.order_client:
                    settlements = await self.order_client.get_settlements(limit=20)
                    if settlements:
                        reports_file = self.data_dir / "win_loss_reports.json"
                        all_reports: List[Dict[str, Any]] = []
                        if reports_file.exists():
                            try:
                                all_reports = json.loads(reports_file.read_text(encoding="utf-8"))
                            except Exception:
                                all_reports = []

                        existing_ids = {r.get("report_id") for r in all_reports}
                        existing_tickers = {r.get("ticker") for r in all_reports if r.get("execution_mode") == "live"}

                        # Query local SQLite trades for accurate price/size attribution
                        local_trades: Dict[str, Dict[str, Any]] = {}
                        try:
                            async with sb.get_db(self.data_dir / "kalshi_history.db").get_connection() as conn:
                                async with conn.execute(
                                    "SELECT trade_id, ticker, side, size, price, gross_value, timestamp_utc, bot_type FROM trades WHERE execution_mode = 'live'"
                                ) as cursor:
                                    for row in await cursor.fetchall():
                                        local_trades[row[1]] = {
                                            "trade_id": row[0],
                                            "ticker": row[1],
                                            "side": row[2],
                                            "size": row[3],
                                            "price": Decimal(str(row[4])),
                                            "gross_value": Decimal(str(row[5])),
                                            "timestamp_utc": row[6],
                                            "bot_type": row[7] or self.bot_id,
                                        }
                        except Exception as db_exc:
                            logger.debug("Failed reading trades table in standalone settlement loop: %s", db_exc)

                        new_reconciled = 0
                        for s in settlements:
                            ticker = s.get("ticker", "")
                            report_id = f"WLR-LIVE-{ticker}"
                            if not ticker or report_id in existing_ids or ticker in existing_tickers:
                                if ticker:
                                    self.guardrails.unlock_cycle(ticker)
                                continue

                            market_result = (s.get("market_result") or "").lower()
                            if not market_result:
                                continue

                            t_info = local_trades.get(ticker)
                            if t_info:
                                trade_side = t_info["side"].lower()
                                size = t_info["size"]
                                cost = t_info["gross_value"]
                                entry_price = t_info["price"]
                                bot_type = t_info["bot_type"]
                            else:
                                raw_cnt = int(s.get("count", 0))
                                if raw_cnt == 0:
                                    continue
                                raw_rev = s.get("revenue", 0)
                                size = raw_cnt
                                trade_side = market_result if raw_rev > 0 else ("no" if market_result == "yes" else "yes")
                                entry_price = Decimal("0.50")
                                cost = Decimal(str(size)) * entry_price
                                bot_type = self.bot_id

                            won = (trade_side == market_result)
                            outcome = "win" if won else "loss"
                            revenue = Decimal(str(size)) * Decimal("1.00") if won else Decimal("0.00")
                            raw_rev = s.get("revenue")
                            if raw_rev is not None:
                                rev_dec = Decimal(str(raw_rev)) / Decimal("100") if isinstance(raw_rev, int) else Decimal(str(raw_rev))
                                if rev_dec > Decimal("0") and won:
                                    revenue = rev_dec

                            pnl = revenue - cost
                            roi_pct = (pnl / cost * Decimal("100.0")) if cost > Decimal("0") else Decimal("0.0")

                            raw_settled_time = s.get("settled_time")
                            is_historical = False
                            if self.is_live and raw_settled_time:
                                try:
                                    dt = datetime.fromisoformat(str(raw_settled_time).replace("Z", "+00:00"))
                                    if dt < self.engine_start_time:
                                        is_historical = True
                                except Exception:
                                    pass

                            settled_ts = raw_settled_time or datetime.now(timezone.utc).isoformat()
                            cycle_time = format_cycle_time_from_iso(settled_ts)

                            # Resolve strike price
                            strike_price = Decimal("0.0")
                            if ticker == self.active_ticker:
                                strike_price = self.target_strike
                            if strike_price <= Decimal("0.0"):
                                if self.current_btc_spot > Decimal("0.0"):
                                    strike_price = self.current_btc_spot
                                else:
                                    fallback_strikes = {
                                        CryptoAsset.BTC: Decimal("80000.00"),
                                        CryptoAsset.ETH: Decimal("2500.00"),
                                        CryptoAsset.SOL: Decimal("150.00"),
                                        CryptoAsset.DOGE: Decimal("0.2000"),
                                    }
                                    strike_price = fallback_strikes.get(self.active_asset, Decimal("80000.00"))

                            step = self.active_cfg.strike_step
                            # Use real spot price at reconciliation time; fabricated strike±step as fallback
                            if self.current_btc_spot > Decimal("0.0"):
                                settlement_spot_price = self.current_btc_spot
                            else:
                                settlement_spot_price = strike_price + (step if market_result == "yes" else -step)
                            balance_after = self.total_balance_dollars if self.total_balance_dollars > 0 else self.balance_dollars

                            rep_tf = "5m" if ("5M" in ticker.upper() or "5MIN" in ticker.upper()) else "15m"
                            rep_asset = self.active_asset.value

                            rep = {
                                "report_id": report_id,
                                "cycle_time": cycle_time,
                                "ticker": ticker,
                                "timeframe": rep_tf,
                                "asset": rep_asset,
                                "strike_price": float(strike_price),
                                "settlement_btc_price": float(settlement_spot_price),
                                "settlement_spot_price": float(settlement_spot_price),
                                "bot_side": trade_side,
                                "contracts": size,
                                "entry_price": float(entry_price),
                                "settlement_price": 1.00 if won else 0.00,
                                "outcome": outcome,
                                "pnl": float(pnl),
                                "roi_pct": float(round(roi_pct, 2)),
                                "ai_confidence": 0.85,
                                "ai_rationale": f"24/7 Standalone Settlement | Result: {market_result.upper()} | Revenue: ${float(revenue):.2f}",
                                "vpin_score": 0.15,
                                "ev_edge": 0.10,
                                "balance_after": float(balance_after),
                                "bot_type": bot_type,
                                "bot_id": self.bot_id,
                                "strategy_id": self.bot_id,
                                "execution_mode": "live",
                                "lane": "LANE 1 (LIVE)",
                                "timestamp_utc": settled_ts,
                                "bot_parameters": self.bot.get_parameters() if hasattr(self.bot, "get_parameters") else None,
                            }

                            all_reports.insert(0, rep)
                            existing_ids.add(report_id)
                            existing_tickers.add(ticker)
                            new_reconciled += 1

                            # Enqueue settlement to SQLite
                            self.db_writer.enqueue_settlement(
                                settlement_id=report_id,
                                ticker=ticker,
                                side=trade_side,
                                size=size,
                                entry_price=float(entry_price),
                                settlement_price=1.00 if won else 0.00,
                                outcome=outcome,
                                pnl=float(pnl),
                                balance_after=float(balance_after),
                                bot_type=bot_type,
                                execution_mode="live",
                            )

                            # Release cycle lock in Guardrails
                            self.guardrails.record_cycle_settlement(
                                ticker=ticker,
                                outcome=outcome,
                                pnl=pnl,
                                balance_after=balance_after,
                                cycle_id=ticker,
                            )

                            # POE Flight Recorder: Link live settlement (Cluster 3)
                            self.poe_recorder.record_settlement(
                                cycle_id=ticker,
                                settlement_spot=float(settlement_spot_price),
                                contract_winning_side="YES" if market_result == "yes" else "NO",
                                settled_payout=Decimal("1.00") if won else Decimal("0.00"),
                                realized_pnl=pnl,
                            )

                            # Consecutive Loss Streak Breaker — auto-disarm after N consecutive losses
                            # Only evaluate for new live settlements that occurred during this running session.
                            if not is_historical:
                                if outcome == "loss":
                                    self.consecutive_losses += 1
                                    if self.consecutive_losses >= self.max_consecutive_losses and self.is_armed:
                                        self.is_armed = False
                                        logger.warning(
                                            "🛑 [STREAK BREAKER] %d consecutive losses reached (max=%d). "
                                            "Bot AUTO-DISARMED to prevent further hemorrhaging. "
                                            "Manual re-arm required via /api/bot/arm.",
                                            self.consecutive_losses, self.max_consecutive_losses,
                                        )
                                else:
                                    if self.consecutive_losses > 0:
                                        logger.info(
                                            "✅ [STREAK RESET] Win breaks %d-loss streak. Counter reset to 0.",
                                            self.consecutive_losses,
                                        )
                                    self.consecutive_losses = 0

                            logger.info(
                                "🏆 [SETTLEMENT RECONCILED] %s: %s | Result: %s | PnL: %+.2f | Streak: %d",
                                ticker, outcome.upper(), market_result.upper(), float(pnl), self.consecutive_losses
                            )

                        if new_reconciled > 0:
                            # Cap to latest 100 entries to prevent token bloat
                            all_reports = all_reports[:100]
                            # Atomic disk persist
                            tmp_file = self.data_dir / "win_loss_reports.tmp"
                            with open(tmp_file, "w", encoding="utf-8") as f:
                                json.dump(all_reports, f, indent=2)
                            tmp_file.replace(reports_file)

                            self.sync_pnl_reports()
                            await self.sync_balance()

                    # Reconcile un-settled vetoed cycles via Kalshi market outcome API
                    unsettled_records = self.poe_recorder.get_unsettled_records()
                    if unsettled_records and self.order_client:
                        connector = create_aiohttp_connector()
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                            "Accept": "application/json",
                        }
                        async with aiohttp.ClientSession(connector=connector, headers=headers) as u_session:
                            for u_rec in unsettled_records:
                                u_ticker = u_rec.cycle_id
                                try:
                                    url = f"{self.rest_base}/markets/{u_ticker}"
                                    async with u_session.get(url, timeout=aiohttp.ClientTimeout(total=2.5)) as m_resp:
                                        if m_resp.status == 200:
                                            m_data = await m_resp.json()
                                            mkt = m_data.get("market", {})
                                            m_status = str(mkt.get("status", "")).lower()
                                            m_res = str(mkt.get("result", "")).lower()
                                            if m_status in ("finalized", "closed", "settled") and m_res in ("yes", "no"):
                                                self.poe_recorder.record_settlement(
                                                    cycle_id=u_ticker,
                                                    settlement_spot=float(u_rec.target_strike),
                                                    contract_winning_side=m_res.upper(),
                                                    settled_payout=Decimal("1.00") if m_res == "yes" else Decimal("0.00"),
                                                    realized_pnl=None,
                                                )
                                                logger.info("📋 [POE VETO SETTLED] %s settled %s -> %s", u_ticker, m_res.upper(), u_rec.quadrant)
                                except Exception as u_err:
                                    logger.debug("Failed querying settlement for vetoed cycle %s: %s", u_ticker, u_err)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("Settlement reconciliation loop error: %s", exc)

            await asyncio.sleep(15.0)


# ---------------------------------------------------------------------------
# FastAPI Pocket Cockpit Server


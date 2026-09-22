"""Standalone Bot Strategy Evaluation & Order Execution Module."""

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
from kalshi_sim.db import get_db, get_db_writer, DatabaseWriter
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


class StandaloneEvaluationCoordinator(_BaseCoordinator):
    """Handles 3-step decision evaluation, VPIN toxicity checks, live order routing, and sweeping."""

    def get_time_to_expiry(self, close_dt: Optional[Union[datetime, str]] = None) -> float:
        """Return time to contract expiry in seconds (calibrated to Kalshi exchange clock)."""
        target_dt = close_dt or self.active_market_close_dt
        if not target_dt:
            return 0.0
        if isinstance(target_dt, str):
            try:
                target_dt = datetime.fromisoformat(target_dt.replace("Z", "+00:00"))
            except Exception:
                return 0.0
        now_utc = clock_sync.web_now()
        
        if target_dt.tzinfo is None:
            target_dt = target_dt.replace(tzinfo=timezone.utc)
        return max(0.0, (target_dt - now_utc).total_seconds())

    def _flush_cycle_veto(self, ticker: str) -> None:
        """Flush un-traded cycle veto candidate to POE flight recorder ledger."""
        cand = self._cycle_veto_candidates.pop(ticker, None)
        if cand and ticker not in self.poe_recorder._records:
            self.poe_recorder.record_decision(**cand)
            logger.info("📋 [POE VETO RECORDED] %s vetoed by %s", ticker, cand.get("primary_blocking_parameter"))

    async def evaluate_and_execute(self) -> None:
        """Evaluate 3-step domination logic and route live orders through guardrails."""
        if self._eval_lock.locked():
            return
        async with self._eval_lock:
            now_mono = time.monotonic()
            if now_mono - self.last_eval_time < 0.25:
                return
            self.last_eval_time = now_mono

            # 0. Early Exit & Take Profit Price Ceiling Evaluation across open positions
            positions_to_eval = list(self.active_positions.values())
            if not positions_to_eval and self.active_position and self.active_position.get("size", 0) > 0:
                positions_to_eval = [self.active_position]

            for pos in positions_to_eval:
                pos_ticker = pos.get("ticker", "")
                if not pos_ticker or pos.get("size", 0) <= 0:
                    continue
                pos_book = self.orderbook.get_book(pos_ticker)
                if not pos_book or (not pos_book.yes_book and not pos_book.no_book):
                    continue

                side_is_yes = (pos["side"] == OrderSide.YES) if isinstance(pos["side"], OrderSide) else (str(pos["side"]).lower() == "yes")
                cur_bid = pos_book.best_yes_bid if side_is_yes else pos_book.best_no_bid

                # Check if a sell exit order is already resting on Kalshi
                resting_exit = next(
                    (o for o in self.active_resting_orders.values() if o.get("ticker") == pos_ticker and o.get("action") == "sell"),
                    None,
                )
                if resting_exit:
                    placed_at = resting_exit.get("placed_at", time.time())
                    resting_p = resting_exit.get("price", Decimal("0.90"))
                    # If market bid dropped below resting limit price OR order rested for > 3.0s, cancel and re-evaluate
                    is_valid_bid = isinstance(cur_bid, (Decimal, float, int))
                    if (is_valid_bid and cur_bid < resting_p) or (time.time() - placed_at > 3.0):
                        logger.warning(
                            "⚠️ [RESTING EXIT STALENESS] Auto-cancelling stale resting sell %s @ $%s on %s (Cur Bid: $%s, Age: %.1fs).",
                            resting_exit.get("order_id"), resting_p, pos_ticker, cur_bid, time.time() - placed_at,
                        )
                        if self.is_live and self.order_client:
                            try:
                                await self.order_client.cancel_order(resting_exit.get("order_id", ""), ticker=pos_ticker)
                            except Exception as cx_err:
                                logger.debug("Error cancelling stale exit order: %s", cx_err)
                        self.active_resting_orders.pop(resting_exit.get("order_id", ""), None)
                    else:
                        # Order is still competitively resting at current bid; do not duplicate
                        continue

                pos_asset = self.active_asset
                for a in CryptoAsset:
                    cfg_a = get_asset_config(a)
                    if pos_ticker.startswith(cfg_a.series_ticker_15m) or (a.value in pos_ticker):
                        pos_asset = a
                        break

                pos_market = self.asset_markets.get(pos_asset.value, {})
                pos_strike = pos.get("target_strike") or pos_market.get("target_strike", self.target_strike if pos_asset == self.active_asset else Decimal("0.00"))
                pos_spot = self.cf_sync.get_price(pos_asset) if self.cf_sync else Decimal("0.00")
                if pos_spot <= Decimal("0.00"):
                    pos_spot = pos_market.get("spot_price", Decimal("0.00"))
                if pos_spot <= Decimal("0.00") and pos_asset == self.active_asset:
                    pos_spot = self.current_btc_spot
                if pos_spot is None:
                    pos_spot = Decimal("0.00")
                if pos_strike is None:
                    pos_strike = Decimal("0.00")

                pos_close = pos.get("close_dt") or pos_market.get("close_dt", self.active_market_close_dt if pos_asset == self.active_asset else None)
                t_rem = self.get_time_to_expiry(pos_close)
                if t_rem <= 0:
                    continue

                self._apply_asset_profile(pos_asset)
                # Track peak bid for high-water mark trailing ratchet
                side_is_yes = (pos["side"] == OrderSide.YES) if isinstance(pos["side"], OrderSide) else (str(pos["side"]).lower() == "yes")
                cur_bid = pos_book.best_yes_bid if side_is_yes else pos_book.best_no_bid
                if cur_bid is not None and cur_bid > Decimal("0.00"):
                    pos["peak_bid"] = max(pos.get("peak_bid", pos["entry_price"]), cur_bid)

                spot_vel_3s, rolling_vol, snr = self.get_spot_velocity_stats(pos_asset)
                pos_twap = pos_market.get("twap") or (self.twap_60s_price if pos_asset == self.active_asset else None)
                exit_dec = self.bot.evaluate_exit(
                    side=pos["side"],
                    entry_price=pos["entry_price"],
                    size=pos["size"],
                    book=pos_book,
                    time_to_expiry_s=t_rem,
                    spot_price=float(pos_spot),
                    target_strike=float(pos_strike),
                    peak_bid=pos.get("peak_bid"),
                    spot_velocity_3s=spot_vel_3s,
                    twap_60s=float(pos_twap) if pos_twap is not None else None,
                    rolling_vol_1m=rolling_vol,
                )
                if exit_dec.should_exit:
                    logger.info(
                        "🎯 [TAKE PROFIT TRIGGERED] %s: %s | Net PnL: +$%s | Exit price: $%s on %s",
                        exit_dec.exit_reason,
                        exit_dec.rationale,
                        exit_dec.unrealized_pnl,
                        exit_dec.exit_price,
                        pos_ticker,
                    )
                    sold_ok = True
                    is_immediate_fill = True
                    sell_oid = f"tp_exit_{int(time.time()*1000)}"
                    if self.is_live and self.order_client:
                        try:
                            sell_res = await self.order_client.place_order(
                                ticker=pos["ticker"],
                                side=pos["side"],
                                count=pos["size"],
                                action="sell",
                                order_type="limit",
                                price_dollars=exit_dec.exit_price,
                                exchange_index=2,
                            )
                            if not sell_res:
                                sold_ok = False
                                logger.error("Failed to execute sell order on Kalshi for %s", pos["ticker"])
                            else:
                                sell_oid = sell_res.get("order_id", sell_oid)
                                fill_cnt = 0
                                try:
                                    fill_cnt = int(float(str(sell_res.get("fill_count", 0))))
                                except Exception:
                                    fill_cnt = 0
                                st = str(sell_res.get("status", "")).lower()
                                is_immediate_fill = fill_cnt > 0 or st in ("executed", "filled")
                        except Exception as se:
                            sold_ok = False
                            logger.error("Error dispatching sell order: %s", se)

                    if sold_ok:
                        if is_immediate_fill:
                            self._finalize_take_profit_exit(pos_ticker, pos, exit_dec)
                            await self.sync_balance()
                        else:
                            self.active_resting_orders[sell_oid] = {
                                "order_id": sell_oid,
                                "ticker": pos_ticker,
                                "side": pos["side"],
                                "size": pos["size"],
                                "price": exit_dec.exit_price,
                                "action": "sell",
                                "exit_dec": exit_dec,
                                "pos": pos,
                                "placed_at": time.time(),
                            }
                            logger.info(
                                "⏳ [TAKE PROFIT RESTING] Limit exit order %s placed @ $%s on %s. Awaiting exchange fill...",
                                sell_oid, exit_dec.exit_price, pos_ticker,
                            )

            # 1. Strategy Entry Evaluation
            candidate_assets = self.active_assets
            open_pos_count = len([p for p in self.active_positions.values() if p.get("size", 0) > 0])
            if open_pos_count >= self.max_concurrent_positions:
                self._apply_asset_profile(self.active_asset)
                return

            for cand_asset in candidate_assets:
                if open_pos_count >= self.max_concurrent_positions:
                    break

                ast_key = cand_asset.value
                m_info = self.asset_markets.get(ast_key, {})
                cand_ticker = m_info.get("ticker")
                if not cand_ticker and cand_asset == self.active_asset:
                    cand_ticker = self.active_ticker
                if not cand_ticker:
                    continue

                # In-flight / open position check: strictly 1 trade per cycle per asset
                if cand_ticker in self.active_positions and self.active_positions[cand_ticker].get("size", 0) > 0:
                    continue
                if self.active_position and self.active_position.get("ticker") == cand_ticker and self.active_position.get("size", 0) > 0:
                    continue
                if any(o.get("ticker") == cand_ticker for o in self.active_resting_orders.values()):
                    continue

                cand_strike = m_info.get("target_strike", self.target_strike if cand_asset == self.active_asset else Decimal("0.00"))
                cand_spot = self.cf_sync.get_price(cand_asset) if self.cf_sync else Decimal("0.00")
                if cand_spot <= Decimal("0.00"):
                    cand_spot = m_info.get("spot_price", Decimal("0.00"))
                if cand_spot <= Decimal("0.00") and cand_asset == self.active_asset:
                    cand_spot = self.current_btc_spot
                if cand_spot <= 0 or cand_strike <= 0:
                    continue

                cand_book = self.orderbook.get_book(cand_ticker)
                if not cand_book or (not cand_book.yes_book and not cand_book.no_book):
                    continue

                cand_close = m_info.get("close_dt", self.active_market_close_dt if cand_asset == self.active_asset else None)
                t_rem = self.get_time_to_expiry(cand_close)
                if t_rem <= 0:
                    continue

                # Macro news event blackout guardrail (e.g. GOLD during US economic releases)
                is_blackout, blackout_reason = self.guardrails.check_macro_news_blackout(cand_asset.value)
                if is_blackout:
                    logger.warning("[GUARDRAIL] %s", blackout_reason)
                    continue

                # Dynamic Entry Timing Envelope per Asset Profile (Option C)
                cand_profile = self.asset_profiles.get(ast_key, DEFAULT_ASSET_PROFILES.get(ast_key, {}))
                open_sec = float(cand_profile.get("entry_window_open_minutes", 12.0)) * 60.0
                close_sec = float(cand_profile.get("entry_window_close_minutes", 4.5)) * 60.0

                if t_rem > open_sec:
                    # Early cycle noise blackout (e.g. T_rem > 12.0m for BTC, > 7.0m for Gold)
                    continue
                if t_rem < close_sec:
                    # Allow late-cycle entry ONLY if within Silas TWAP Immutability Sniper window [15s, 45s]
                    if not (15.0 <= t_rem <= 45.0):
                        continue

                # Calibrate strategy for candidate asset using its dedicated profile
                self._apply_asset_profile(cand_asset)
                try:
                    decision = self.bot.evaluate(
                        book=cand_book,
                        spot_price=float(cand_spot),
                        target_strike=float(cand_strike),
                        time_to_expiry_s=t_rem,
                        twap_60s=float(self.twap_60s_price) if self.twap_60s_price else None,
                        total_equity=self.balance_dollars,
                        max_position_size=1,
                        estimated_vpin=0.15,
                    )
                    if cand_asset == self.active_asset:
                        self.last_decision = decision
                except Exception as eval_err:
                    logger.exception("❌ [EVALUATION ERROR] Error evaluating %s: %s", ast_key, eval_err)
                    continue

                # Execution Gating: Check Arming
                if not self.is_armed:
                    continue

                spot_vel_3s, _, _ = self.get_spot_velocity_stats(cand_asset)

                # Check Signal Recommendation
                if decision.recommended_side not in ("yes", "no") or decision.recommended_contracts <= 0:
                    # Strategy Veto: determine primary blocking parameter from rationale
                    veto_param = "EV_EDGE_FLOOR"
                    if "AI Conviction Veto" in decision.rationale:
                        veto_param = "AI_CONVICTION_FLOOR"
                    elif "Toxic Queue Depth Veto" in decision.rationale:
                        veto_param = "QUEUE_DEPTH_SHIELD"
                    elif "TWAP Sniper Cap Veto" in decision.rationale:
                        veto_param = "TWAP_SNIPER_CEILING"
                    elif "Price Cap Veto" in decision.rationale:
                        veto_param = "PRICE_CAP_CEILING"
                    elif "Momentum Alignment Veto" in decision.rationale:
                        veto_param = "MOMENTUM_ALIGNMENT_FILTER"
                    elif "Marginal Zone Veto" in decision.rationale:
                        veto_param = "MARGINAL_ZONE_BOOST"
                    elif "Awaiting Cycle Window" in decision.rationale:
                        veto_param = "TIMING_ENVELOPE"

                    p_side = "YES" if decision.p_up >= decision.p_down else "NO"
                    ev_val = Decimal(str(decision.ev_yes if p_side == "YES" else decision.ev_no))
                    self._cycle_veto_candidates[cand_ticker] = {
                        "cycle_id": cand_ticker,
                        "tau_seconds_remaining": t_rem,
                        "spot_price": float(cand_spot),
                        "target_strike": float(cand_strike),
                        "moneyness_diff": float(cand_spot - cand_strike),
                        "spot_velocity_10s": float(spot_vel_3s),
                        "vpin_score": float(decision.vpin),
                        "ai_predicted_side": p_side,
                        "ai_confidence": float(max(decision.p_up, decision.p_down)),
                        "ev_gross": ev_val,
                        "ev_net": ev_val,
                        "decision": "VETO",
                        "primary_blocking_parameter": veto_param,
                        "param_actual": None,
                        "param_threshold": None,
                        "co_veto_matrix": {"strategy_rationale": decision.rationale[:60]},
                    }
                    continue

                # Institutional Pre-Trade Guardrail Check
                rec_side = decision.recommended_side
                rec_size = min(decision.recommended_contracts, 1)  # Micro-Bankroll Sizing Armor: Strictly 1 contract
                est_price = Decimal(str(getattr(decision, 'limit_price', None) or getattr(decision, 'entry_discount_depth', None) or "0.52"))
                target_ticker = cand_ticker

                is_allowed, g_reason, approved_size, _ = self.guardrails.validate_pre_trade_intent(
                    ticker=target_ticker,
                    side=rec_side,
                    requested_size=rec_size,
                    est_price=est_price,
                    total_equity=self.balance_dollars,
                    vpin=decision.vpin,
                    cycle_id=target_ticker,
                    is_bot=True,
                    bot_type=self.bot_id,
                )

                if not is_allowed or approved_size <= 0:
                    logger.info("🛡️ [GUARDRAIL BLOCK] %s on %s (%s): %s", rec_side.upper(), target_ticker, ast_key, g_reason)
                    g_param = "GUARDRAIL_VPIN_TOXIC" if "vpin" in g_reason.lower() else (
                        "GUARDRAIL_COOLDOWN" if "cooldown" in g_reason.lower() else (
                            "GUARDRAIL_CYCLE_LOCK" if "cycle" in g_reason.lower() else "GUARDRAIL_PRE_TRADE_VETO"
                        )
                    )
                    self._cycle_veto_candidates[target_ticker] = {
                        "cycle_id": target_ticker,
                        "tau_seconds_remaining": t_rem,
                        "spot_price": float(cand_spot),
                        "target_strike": float(cand_strike),
                        "moneyness_diff": float(cand_spot - cand_strike),
                        "spot_velocity_10s": float(spot_vel_3s),
                        "vpin_score": float(decision.vpin),
                        "ai_predicted_side": rec_side.upper(),
                        "ai_confidence": float(max(decision.p_up, decision.p_down)),
                        "ev_gross": Decimal(str(decision.ev_yes if rec_side == "yes" else decision.ev_no)),
                        "ev_net": Decimal(str(decision.ev_yes if rec_side == "yes" else decision.ev_no)),
                        "decision": "VETO",
                        "primary_blocking_parameter": g_param,
                        "param_actual": float(decision.vpin) if "vpin" in g_reason.lower() else None,
                        "param_threshold": 0.60 if "vpin" in g_reason.lower() else None,
                        "co_veto_matrix": {"guardrails": "FAIL", "reason": g_reason[:60]},
                    }
                    continue

                # Anti-Burst Pre-Flight Check on Kalshi Open Orders
                if self.order_client:
                    try:
                        open_orders = await self.order_client.get_open_orders()
                        existing_for_ticker = [o for o in open_orders if o.get("ticker") == target_ticker]
                        if existing_for_ticker:
                            logger.warning("⚠️ [ANTI-BURST] Resting order already active on Kalshi for %s. Suppressing duplicate.", target_ticker)
                            self.guardrails.record_resting_order(
                                order_id=existing_for_ticker[0].get("order_id", "ext_rest"),
                                ticker=target_ticker,
                                side=rec_side,
                                size=approved_size,
                                price=est_price,
                                cycle_id=target_ticker,
                                bot_type=self.bot_id,
                            )
                            continue
                    except Exception as e:
                        logger.debug("Failed open order anti-burst check: %s", e)

                    # Seal of Excellence Pre-Flight Live Authorization Gate
                    if not self.auditor.has_seal_of_excellence(self.bot_id):
                        logger.error("🛡️ [SEAL OF EXCELLENCE VETO] 3-Step Dominion lacks active live seal authorization.")
                        self.guardrails.release_in_flight_intent(target_ticker)
                        continue

                    # Cross-Bot CFTC Anti-Wash Trading Coordinator Check
                    is_permitted, coord_reason = self.coordinator.check_trade_permission(
                        ticker=target_ticker,
                        proposed_side=rec_side,
                        bot_id=self.bot_id,
                        requested_contracts=approved_size,
                        is_live=self.is_live,
                    )
                    if not is_permitted:
                        logger.warning("🛡️ [COORDINATOR VETO] %s on %s: %s", rec_side.upper(), target_ticker, coord_reason)
                        self._cycle_veto_candidates[target_ticker] = {
                            "cycle_id": target_ticker,
                            "tau_seconds_remaining": t_rem,
                            "spot_price": float(cand_spot),
                            "target_strike": float(cand_strike),
                            "moneyness_diff": float(cand_spot - cand_strike),
                            "spot_velocity_10s": float(spot_vel_3s),
                            "vpin_score": float(decision.vpin),
                            "ai_predicted_side": rec_side.upper(),
                            "ai_confidence": float(max(decision.p_up, decision.p_down)),
                            "ev_gross": Decimal(str(decision.ev_yes if rec_side == "yes" else decision.ev_no)),
                            "ev_net": Decimal(str(decision.ev_yes if rec_side == "yes" else decision.ev_no)),
                            "decision": "VETO",
                            "primary_blocking_parameter": "COORDINATOR_ANTI_WASH",
                            "co_veto_matrix": {"coordinator": "FAIL", "reason": coord_reason[:60]},
                        }
                        self.guardrails.release_in_flight_intent(target_ticker)
                        continue

                    # Dispatch Live Order
                    logger.info(
                        "🚀 [LIVE ORDER INCEPTION] %s %d contracts @ $%s on %s (%s) (Playbook: %s, Edge: +%.1f%%)",
                        rec_side.upper(), approved_size, est_price, target_ticker, ast_key, decision.active_playbook, decision.edge_pct * 100
                    )
                    try:
                        order_res = await self.order_client.place_order(
                            ticker=target_ticker,
                            side=rec_side,
                            count=approved_size,
                            action="buy",
                            order_type="limit",
                            price_dollars=est_price,
                            exchange_index=2,
                        )
                    except Exception as exc:
                        self.guardrails.release_in_flight_intent(target_ticker)
                        logger.error("Failed to dispatch live order to Kalshi: %s", exc)
                        continue

                    if order_res:
                        order_id = order_res.get("order_id", "live_ord")
                        logger.info("✅ [ORDER PLACED] Order ID: %s", order_id)

                        # POE Flight Recorder: Record live TRADE decision immediately
                        ev_val = Decimal(str(decision.ev_yes if rec_side == "yes" else decision.ev_no))
                        self.poe_recorder.record_decision(
                            cycle_id=target_ticker,
                            tau_seconds_remaining=t_rem,
                            spot_price=float(cand_spot),
                            target_strike=float(cand_strike),
                            moneyness_diff=float(cand_spot - cand_strike),
                            spot_velocity_10s=float(spot_vel_3s),
                            vpin_score=float(decision.vpin),
                            ai_predicted_side=rec_side.upper(),
                            ai_confidence=float(max(decision.p_up, decision.p_down)),
                            ev_gross=ev_val,
                            ev_net=ev_val,
                            decision="TRADE",
                            primary_blocking_parameter=None,
                            param_actual=None,
                            param_threshold=None,
                            co_veto_matrix={"strategy": "PASS", "guardrails": "PASS", "coordinator": "PASS"},
                        )
                        self._cycle_veto_candidates.pop(target_ticker, None)

                        self.guardrails.record_resting_order(
                            order_id=order_id,
                            ticker=target_ticker,
                            side=rec_side,
                            size=approved_size,
                            price=est_price,
                            cycle_id=target_ticker,
                            bot_type=self.bot_id,
                        )
                        fill_cnt = 0
                        try:
                            fill_cnt = int(float(str(order_res.get("fill_count", 0))))
                        except Exception:
                            fill_cnt = 0
                        if fill_cnt > 0 or str(order_res.get("status", "")).lower() in ("executed", "filled"):
                            # Record immediate fill in POE
                            self.poe_recorder.record_fill(
                                cycle_id=target_ticker,
                                order_side=rec_side,
                                order_type="LIMIT",
                                order_price=est_price,
                                fill_price=est_price,
                                fill_slippage=Decimal("0.00"),
                                queue_depth_ahead=0,
                                taker_fee_paid=Decimal("0.00"),
                            )
                            pos_item = {
                                "ticker": target_ticker,
                                "side": rec_side,
                                "size": approved_size,
                                "entry_price": est_price,
                                "entry_time": time.time(),
                                "order_id": order_id,
                                "asset": ast_key,
                            }
                            self.active_positions[target_ticker] = pos_item
                            if target_ticker == self.active_ticker or self.asset_mode != "all":
                                self.active_position = pos_item
                            open_pos_count += 1
                            logger.info("⚡ [IMMEDIATE FILL] %s %d contracts @ $%s on %s (%s)", rec_side.upper(), approved_size, est_price, target_ticker, ast_key)
                        else:
                            self.active_resting_orders[order_id] = {
                                "ticker": target_ticker,
                                "side": rec_side,
                                "size": approved_size,
                                "price": est_price,
                                "placed_at": time.time(),
                                "asset": ast_key,
                            }
                        expiry_ts = cand_close.timestamp() if cand_close else None
                        self.coordinator.record_trade(
                            ticker=target_ticker,
                            side=rec_side,
                            contracts=approved_size,
                            price=float(est_price),
                            bot_id=self.bot_id,
                            expiry_ts=expiry_ts,
                        )
                        self.db_writer.enqueue_trade(
                            trade_id=f"live_{order_id}",
                            ticker=target_ticker,
                            side=rec_side,
                            size=approved_size,
                            price=float(est_price),
                            gross_value=float(est_price * Decimal(str(approved_size))),
                            fees=0.0,
                            vpin=decision.vpin,
                            timeframe=self.get_current_timeframe(),
                            bot_type=self.bot_id,
                            execution_mode="live",
                            status="resting",
                        )
                        await self.sync_balance()
                    else:
                        self.guardrails.release_in_flight_intent(target_ticker)

            self._apply_asset_profile(self.active_asset)

    async def panic_cancel_all(self) -> int:
        """Cancel all open resting orders on Kalshi exchange and disarm bot."""
        self.is_armed = False
        self._persist_parameters()
        cancelled_count = 0
        if self.order_client:
            try:
                open_orders = await self.order_client.get_open_orders()
                for o in open_orders:
                    oid = o.get("order_id")
                    if oid:
                        await self.order_client.cancel_order(oid)
                        cancelled_count += 1
                        logger.warning("🛑 [PANIC CANCELLED] Order %s on %s", oid, o.get("ticker"))
                self.active_resting_orders.clear()
            except Exception as e:
                logger.error("Error during panic cancel: %s", e)
        return cancelled_count

    async def sweep_old_orders(self, keep_ticker: Optional[str] = None, force_all: bool = False) -> int:
        """Cancel all open resting orders on Kalshi exchange for finished, expired, or non-active contracts."""
        cancelled = 0
        t_rem = self.get_time_to_expiry()
        is_active_expired = (self.active_market_close_dt is not None and t_rem <= 45.0)

        keep_set = set()
        if not force_all:
            if keep_ticker:
                keep_set.add(keep_ticker)
            # Protect open positions across all assets
            for p_tkr in self.active_positions.keys():
                keep_set.add(p_tkr)
            # Protect unexpired asset markets across all assets
            for m in self.asset_markets.values():
                tkr = m.get("ticker")
                c_dt = m.get("close_dt")
                t_rem_m = self.get_time_to_expiry(c_dt)
                if tkr and t_rem_m > 45.0:
                    keep_set.add(tkr)
            if self.active_ticker and not is_active_expired:
                keep_set.add(self.active_ticker)

        if self.order_client:
            try:
                open_orders = await self.order_client.get_open_orders()
                for o in open_orders:
                    t = o.get("ticker")
                    oid = o.get("order_id")
                    if oid and (not keep_set or t not in keep_set):
                        try:
                            success = await self.order_client.cancel_order(oid, ticker=t)
                            if success:
                                cancelled += 1
                                logger.warning("🧹 [EXPIRED ORDER SWEEP] Cancelled resting order %s on finished/expired event %s", oid, t)
                        except Exception as ce:
                            logger.error("Error cancelling old order %s on %s: %s", oid, t, ce)
            except Exception as e:
                logger.error("Error fetching open orders during sweep: %s", e)

        if self.active_resting_orders:
            for oid, o_info in list(self.active_resting_orders.items()):
                t = o_info.get("ticker")
                if not keep_set or t not in keep_set:
                    self.active_resting_orders.pop(oid, None)
                    if not self.order_client:
                        cancelled += 1
                        logger.warning("🧹 [EXPIRED ORDER SWEEP] Cleared virtual resting order %s on finished event %s", oid, t)

        # Flush any expired or non-active cycle veto candidates to POE ledger
        for cand_tkr in list(self._cycle_veto_candidates.keys()):
            if not keep_set or cand_tkr not in keep_set:
                self._flush_cycle_veto(cand_tkr)

        logger.info("🧹 [SWEEP SUMMARY] Cancelled %d resting order(s). Active keep_set: %s", cancelled, list(keep_set))
        return cancelled



"""Agent_Guardrails — Autonomous Quantitative Risk & Self-Preservation Guardian.

Enforces pre-trade execution guardrails, anti-kamikaze bankroll protection,
1-trade-per-cycle locks, execution cooldown throttles, and instant trade inception telemetry.
"""

from __future__ import annotations

from datetime import datetime, timezone, time as dt_time
from decimal import Decimal
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger("kalshi_sim.guardrails")
ET_ZONE = ZoneInfo("America/New_York")


class AgentGuardrails:
    """Quantitative Execution Guardrail & Self-Preservation Guardian."""

    def __init__(
        self,
        min_order_interval_seconds: float = 45.0,
        max_risk_pct_per_trade: Decimal = Decimal("0.08"),  # Max 8% of equity per trade
        max_micro_bankroll_contracts: int = 1,  # Hard cap: Strictly 1 contract per trade for each asset
        max_nano_bankroll_contracts: int = 1,   # Strictly 1 contract max
        max_other_bots_contracts: int = 0,      # Rule: Only 3-Step Dominion is authorized to trade (other bots 0)
        consecutive_loss_taper_threshold: int = 2,
        drawdown_taper_threshold: Decimal = Decimal("0.15"),  # 15% drawdown activates taper
        emergency_drawdown_limit: Decimal = Decimal("0.25"),  # 25% drawdown halts all trading
        vpin_toxic_threshold: float = 0.65,
    ) -> None:
        self.min_order_interval_seconds = min_order_interval_seconds
        self.max_risk_pct_per_trade = max_risk_pct_per_trade
        self.max_micro_bankroll_contracts = max_micro_bankroll_contracts
        self.max_nano_bankroll_contracts = max_nano_bankroll_contracts
        self.max_other_bots_contracts = max_other_bots_contracts
        self.consecutive_loss_taper_threshold = consecutive_loss_taper_threshold
        self.drawdown_taper_threshold = drawdown_taper_threshold
        self.emergency_drawdown_limit = emergency_drawdown_limit
        self.vpin_toxic_threshold = vpin_toxic_threshold

        # State tracking
        self._last_order_ts: float = 0.0
        self._last_order_ts_by_ticker: dict[str, float] = {}
        self._cycle_locks: dict[str, str] = {}  # cycle_key -> trade_id
        self._in_flight_locks: set[str] = set()  # In-flight order dispatch locks (anti-burst)
        self._in_flight_lock_ts: dict[str, float] = {}  # cycle_key -> monotonic lock reservation timestamp
        self._cycle_contracts_count: dict[str, int] = {}  # cycle_key -> total contracts placed (hard cap: 2)
        self._consecutive_losses: int = 0
        self._peak_equity: Optional[Decimal] = None
        self._circuit_breaker_tripped: bool = False
        self.is_bot_armed: bool = True
        self.harakiri_loss_limit: int = 3

        # Certified Live Strategies
        self.authorized_live_bots: set[str] = {
            "3_step_domination_bot",
            "3_step_domination",
            "domination",
            "3step_dominion",
            "three_step_domination",
        }

        # Telemetry & Audit
        self._total_validations: int = 0
        self._total_rejections: int = 0
        self._rejection_reasons: dict[str, int] = {}
        self._recent_inceptions: list[dict[str, Any]] = []
        self._recent_rejections: list[dict[str, Any]] = []
        self._last_log_rejection_ts: dict[str, float] = {}

    def authorize_live_bot(self, bot_type: str) -> None:
        """Promote and authorize a certified strategy for Live Mode."""
        self.authorized_live_bots.add(bot_type)
        if bot_type in ("the_onnx_strategy", "dual_onnx", "dual_onnx_bot"):
            self.authorized_live_bots.update({
                "the_onnx_strategy",
                "dual_onnx",
                "dual_onnx_bot",
                "dual_onnx_arbitrage",
                "dual_onnx_arbitrage_bot",
                "onnx_macro_v2",
            })
        if bot_type in ("macro_trend_dominion", "macro_onnx", "macro_trend_dominion_bot", "macro_trend"):
            self.authorized_live_bots.update({
                "macro_trend_dominion",
                "macro_onnx",
                "macro_trend_dominion_bot",
                "macro_trend",
            })

    # -------------------------------------------------------------------------
    # 1. Pre-Trade Intent Validation
    # -------------------------------------------------------------------------

    def check_macro_news_blackout(
        self,
        ticker_or_asset: str,
        now_dt: Optional[datetime] = None,
    ) -> Tuple[bool, str]:
        """Verify whether high-impact US macroeconomic release embargo is active.

        Embargos:
          1. 08:25:00 - 08:38:00 Eastern Time (US CPI, PPI, NFP, GDP, Retail Sales).
          2. 13:55:00 - 14:10:00 Eastern Time (FOMC Rate Decisions & Statements).

        Applies to physical macro assets: GOLD (KXGOLD15M).
        """
        asset_str = ticker_or_asset.upper()
        if "GOLD" not in asset_str and "XAU" not in asset_str:
            return False, ""

        if now_dt is None:
            now_dt = datetime.now(timezone.utc)
        elif now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)

        et_now = now_dt.astimezone(ET_ZONE)
        t_time = et_now.time()

        # Window 1: Morning 8:25 AM - 8:38 AM ET
        w1_start = dt_time(8, 25, 0)
        w1_end = dt_time(8, 38, 0)
        if w1_start <= t_time <= w1_end:
            msg = (
                f"[GUARDRAIL VETO] MACRO EVENT BLACKOUT: Current time {et_now.strftime('%H:%M:%S ET')} "
                f"is inside the US Economic Data Release window (08:25-08:38 ET). Trading for {ticker_or_asset} embargoed."
            )
            return True, msg

        # Window 2: Afternoon 1:55 PM - 2:10 PM ET
        w2_start = dt_time(13, 55, 0)
        w2_end = dt_time(14, 10, 0)
        if w2_start <= t_time <= w2_end:
            msg = (
                f"[GUARDRAIL VETO] MACRO EVENT BLACKOUT: Current time {et_now.strftime('%H:%M:%S ET')} "
                f"is inside the FOMC Release window (13:55-14:10 ET). Trading for {ticker_or_asset} embargoed."
            )
            return True, msg

        return False, ""

    def verify_macro_event_embargo(
        self,
        ticker_or_asset: str,
        now_dt: Optional[datetime] = None,
    ) -> Tuple[bool, str]:
        """Alias for check_macro_news_blackout."""
        return self.check_macro_news_blackout(ticker_or_asset, now_dt)

    def verify_incubator_lock(
        self,
        ticker_or_asset: str,
        is_live: bool = True,
    ) -> Tuple[bool, str]:
        """Verify whether an asset is quarantined in Lane 2 Incubator and locked from Live trading."""
        if not is_live:
            return False, ""
        from kalshi_sim.incubator_manager import get_incubator_manager

        inc_mgr = get_incubator_manager()
        asset_str = ticker_or_asset.upper()

        for key in inc_mgr.get_status().keys():
            if key in asset_str:
                if inc_mgr.is_locked(key):
                    reason = inc_mgr.get_lock_reason(key)
                    return True, f"[INCUBATOR LOCK VETO] {key} is quarantined in Lane 2 Incubator: {reason}"

        if inc_mgr.is_locked(asset_str):
            reason = inc_mgr.get_lock_reason(asset_str)
            return True, f"[INCUBATOR LOCK VETO] {asset_str} is quarantined in Lane 2 Incubator: {reason}"

        return False, ""

    def validate_pre_trade_intent(
        self,
        ticker: str,
        side: str,
        requested_size: int,
        est_price: Decimal,
        total_equity: Decimal,
        vpin: float = 0.0,
        cycle_id: Optional[str] = None,
        is_bot: bool = True,
        bot_type: Optional[str] = None,
        is_live: bool = False,
    ) -> Tuple[bool, str, int, Dict[str, Any]]:
        """Validate an order against all safety guardrails before placement.

        Returns:
            (is_allowed, reason, approved_size, diagnostic_metrics)
        """
        self._total_validations += 1
        now_mono = time.monotonic()
        now_utc = datetime.now(timezone.utc).isoformat()
        cycle_key = cycle_id or ticker

        # 0. 5M Expansion Live Prohibition Veto
        # 5-minute event contracts (KXBTC5M or 5m cycle) are strictly exclusive to Mother Dash Paper Live.
        # Live real-money trading is permanently prohibited under all conditions.
        # Ensure "15M" is not falsely matched when testing for "5M" substring!
        is_5m_contract = (
            ("5M" in ticker.upper() and "15M" not in ticker.upper())
            or "5MIN" in ticker.upper()
            or (cycle_id is not None and "5M" in cycle_id.upper() and "15M" not in cycle_id.upper())
            or (cycle_id is not None and "_5m" in cycle_id.lower())
        )
        if is_live and is_5m_contract:
            msg = (
                f"5M LIVE TRADING PROHIBITED: Contract '{ticker}' is part of the 5-Minute Expansion series. "
                f"5M events are strictly exclusive to Mother Dash Paper Live. Live real-money trading is permanently prohibited."
            )
            self._record_rejection("5m_live_prohibited", msg, ticker, now_utc)
            return False, msg, 0, {"veto": "5m_live_prohibited", "ticker": ticker, "is_live": True}

        # 0b. Macro Event News Blackout Veto (e.g. GOLD during high-impact US economic releases)
        is_macro_blackout, macro_reason = self.check_macro_news_blackout(ticker)
        if is_macro_blackout:
            self._record_rejection("macro_event_blackout", macro_reason, ticker, now_utc)
            return False, macro_reason, 0, {"veto": "macro_event_blackout", "ticker": ticker}

        # 0c. Lane 2 Incubator Live Lock Veto
        if is_live:
            is_locked, lock_reason = self.verify_incubator_lock(ticker, is_live=True)
            if is_locked:
                self._record_rejection("incubator_locked", lock_reason, ticker, now_utc)
                return False, lock_reason, 0, {"veto": "incubator_locked", "ticker": ticker}

        # 0d. Harakiri Streak Breaker Veto (Auto-Disarm after consecutive losses)
        if is_bot and not self.is_bot_armed:
            msg = f"HARAKIRI STREAK BREAKER VETO: Bot is DISARMED after reaching {self._consecutive_losses} consecutive losses. Manual re-arming required."
            self._record_rejection("bot_disarmed", msg, ticker, now_utc)
            return False, msg, 0, {"veto": "harakiri_disarmed", "consecutive_losses": self._consecutive_losses}

        # Update peak equity
        if self._peak_equity is None or total_equity > self._peak_equity:
            self._peak_equity = total_equity

        # Compute drawdown
        drawdown = max(Decimal("0"), self._peak_equity - total_equity)
        drawdown_pct = (drawdown / self._peak_equity) if (self._peak_equity and self._peak_equity > 0) else Decimal("0")

        # 1. Emergency Circuit Breaker Check
        if self._circuit_breaker_tripped or drawdown_pct >= self.emergency_drawdown_limit:
            self._circuit_breaker_tripped = True
            msg = f"EMERGENCY CIRCUIT BREAKER TRIPPED: Drawdown {drawdown_pct*100:.1f}% >= {self.emergency_drawdown_limit*100:.0f}%. All trading halted."
            self._record_rejection("circuit_breaker", msg, ticker, now_utc)
            return False, msg, 0, {"drawdown_pct": float(drawdown_pct)}

        # 2. VPIN Toxicity Veto
        if vpin >= self.vpin_toxic_threshold:
            msg = f"VPIN TOXICITY VETO: VPIN score {vpin:.2f} >= {self.vpin_toxic_threshold:.2f}. Adverse selection protection active."
            self._record_rejection("vpin_toxicity", msg, ticker, now_utc)
            return False, msg, 0, {"vpin": vpin}

        # 2b. In-Flight Order Lockout (Anti-Burst Concurrency Protection with 15s Invariant TTL)
        if is_bot and cycle_key in self._in_flight_locks:
            lock_time = self._in_flight_lock_ts.get(cycle_key, 0.0)
            if now_mono - lock_time >= 15.0:
                logger.warning(
                    "⏱️ [IN-FLIGHT TIMEOUT] Lock for cycle '%s' expired after %.1fs TTL (15s limit). Auto-releasing.",
                    cycle_key, now_mono - lock_time
                )
                self._in_flight_locks.discard(cycle_key)
                self._in_flight_lock_ts.pop(cycle_key, None)
            else:
                msg = f"IN-FLIGHT ORDER LOCKOUT: Order dispatch currently in flight for cycle '{cycle_key}'. Concurrent order placement blocked."
                self._record_rejection("order_in_flight", msg, ticker, now_utc)
                return False, msg, 0, {"cycle_key": cycle_key}

        # 3. 1-Trade-Per-Cycle & Max-2-Contracts Exposure Lockout Check (Automated bots only)
        already_allocated = self._cycle_contracts_count.get(cycle_key, 0)
        if is_bot and (cycle_key in self._cycle_locks or already_allocated >= 2):
            locked_trade = self._cycle_locks.get(cycle_key, f"{already_allocated}_contracts")
            msg = f"1-TRADE-PER-CYCLE LOCKOUT: Cycle '{cycle_key}' already has active trade '{locked_trade}'. Further entries blocked until expiration."
            self._record_rejection("cycle_locked", msg, ticker, now_utc)
            return False, msg, 0, {"locked_trade": locked_trade, "already_allocated": already_allocated}

        # 4. Mandatory Execution Cooldown Throttle (Automated bots only)
        if is_bot:
            elapsed_global = now_mono - self._last_order_ts
            if self._last_order_ts > 0 and elapsed_global < self.min_order_interval_seconds:
                rem = self.min_order_interval_seconds - elapsed_global
                msg = f"COOLDOWN THROTTLE: Next bot order permitted in {rem:.1f}s (cooldown={self.min_order_interval_seconds:.0f}s)."
                self._record_rejection("cooldown_throttle", msg, ticker, now_utc)
                return False, msg, 0, {"remaining_cooldown_s": rem}

        # 5. Price Corridor Guardrail Check (Avoid 98c tail blowups and <6c fee drag for automated bots)
        if is_bot:
            if est_price > Decimal("0.90"):
                msg = f"PRICE CORRIDOR VETO: Estimated price ${est_price:.2f} > $0.90 ceiling. Asymmetric tail risk veto active."
                self._record_rejection("price_ceiling_veto", msg, ticker, now_utc)
                return False, msg, 0, {"price": float(est_price)}

            if est_price < Decimal("0.06"):
                msg = f"PRICE CORRIDOR VETO: Estimated price ${est_price:.2f} < $0.06 floor. Negative-EV fee drag lottery veto active."
                self._record_rejection("price_floor_veto", msg, ticker, now_utc)
                return False, msg, 0, {"price": float(est_price)}

        # 6. Anti-Kamikaze Bankroll Sizing & Risk Caps
        max_risk_dollars = total_equity * self.max_risk_pct_per_trade
        unit_cost = max(Decimal("0.05"), min(Decimal("0.99"), est_price))
        
        # Max affordable under risk budget
        budget_contracts = int(max_risk_dollars / unit_cost) if unit_cost > 0 else 0
        
        # Tiered Bankroll Caps
        if total_equity <= Decimal("25.00"):
            bankroll_cap = self.max_nano_bankroll_contracts
        elif total_equity <= Decimal("100.00"):
            bankroll_cap = self.max_micro_bankroll_contracts
        else:
            bankroll_cap = max(self.max_micro_bankroll_contracts, int(total_equity / Decimal("25.00")))

        # Rule: Strictly 1 contract per trade, max 2 shares total per cycle.
        # Certified Live Strategies: Bots in self.authorized_live_bots are permitted for live order routing.
        # Lane 2 Shadow Paper Trading: Certified bots authorized for paper trading.
        is_primary_domination = (
            bot_type in ("3_step_domination_bot", "3_step_domination", "domination", "3step_dominion", "three_step_domination")
            or bot_type is None
        )
        is_authorized_live_bot = (
            bot_type in self.authorized_live_bots
            or bot_type is None
        )
        # Automatic promotion: any bot with an active Seal of Excellence on disk is authorized for live
        if is_bot and is_live and not is_authorized_live_bot and bot_type:
            from kalshi_sim.bot_deployment_auditor import BotDeploymentAuditor
            res = BotDeploymentAuditor.check_live_authorization_on_disk(bot_type)
            auth_ok = res[0] if isinstance(res, (tuple, list)) else bool(res)
            if auth_ok:
                self.authorized_live_bots.add(bot_type)
                is_authorized_live_bot = True

        is_authorized_paper_bot = (
            is_authorized_live_bot
            or bot_type in (
                "onnx_macro_v2",
                "dual_onnx",
                "the_onnx_strategy",
                "dual_onnx_bot",
                "dual_onnx_arbitrage",
                "dual_onnx_arbitrage_bot",
                "macro_trend_dominion",
                "macro_onnx",
                "macro_trend",
                "macro_trend_dominion_bot",
                "bot1_ver_4",
                "3_step_domination_bot_v4",
            )
        )
        if is_bot:
            if is_live and not is_authorized_live_bot:
                msg = f"LIVE BOT TRADING PROHIBITED: Bot '{bot_type}' is not authorized to route live orders."
                self._record_rejection("bot_prohibited", msg, ticker, now_utc)
                return False, msg, 0, {"bot_type": bot_type}
            elif not is_live and not (is_primary_domination or is_authorized_paper_bot):
                msg = f"BOT TRADING PROHIBITED: Bot '{bot_type}' is deactivated and not authorized for paper trading."
                self._record_rejection("bot_prohibited", msg, ticker, now_utc)
                return False, msg, 0, {"bot_type": bot_type}
            else:
                # Strictly 1 contract per trade; cycle capacity max 2 shares total
                remaining_cycle_capacity = max(0, 2 - already_allocated)
                bankroll_cap = min(1, remaining_cycle_capacity)

        approved_size = min(requested_size, budget_contracts, bankroll_cap)

        # 7. Loss Streak & Drawdown Defense Taper
        is_tapered = False
        if self._consecutive_losses >= self.consecutive_loss_taper_threshold or drawdown_pct >= self.drawdown_taper_threshold:
            is_tapered = True
            approved_size = min(approved_size, 1)  # Strict self-preservation: minimum size

        if approved_size <= 0:
            if already_allocated >= 2:
                msg = f"CYCLE EXPOSURE CAP: Cycle '{cycle_key}' reached max 2 contracts exposure ({already_allocated}/2 active)."
                self._record_rejection("max_cycle_exposure", msg, ticker, now_utc)
            else:
                msg = f"INSUFFICIENT RISK BUDGET: Equity ${total_equity:.2f} (Max Risk ${max_risk_dollars:.2f}) cannot afford 1 contract @ ${unit_cost:.2f}."
                self._record_rejection("insufficient_budget", msg, ticker, now_utc)
            return False, msg, 0, {"max_risk_dollars": float(max_risk_dollars)}

        # CRITICAL CONCURRENCY RESERVATION: Immediately reserve in-flight lock and advance cooldown
        # to prevent any concurrent ticks/coroutines from firing another order before this one finishes.
        if is_bot:
            self._in_flight_locks.add(cycle_key)
            self._in_flight_lock_ts[cycle_key] = now_mono
            self._last_order_ts = now_mono
            self._last_order_ts_by_ticker[ticker] = now_mono

        approved_cost = unit_cost * Decimal(str(approved_size))
        diag = {
            "approved_size": approved_size,
            "approved_cost": float(approved_cost),
            "max_risk_dollars": float(max_risk_dollars),
            "is_tapered": is_tapered,
            "consecutive_losses": self._consecutive_losses,
            "drawdown_pct": float(drawdown_pct),
        }
        return True, "PASSED_GUARDRAILS", approved_size, diag

    # -------------------------------------------------------------------------
    # 2. Trade Inception Recording & Immediate Telemetry
    # -------------------------------------------------------------------------

    def record_trade_inception(
        self,
        trade_id: str,
        ticker: str,
        side: str,
        size: int,
        price: Decimal,
        cost: Decimal,
        fee: Decimal,
        bot_type: str,
        execution_mode: str,
        rationale: str,
        vpin: float,
        ai_prob: float,
        cycle_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record trade entry, lock the cycle, set cooldowns, and emit instant telemetry."""
        now_mono = time.monotonic()
        now_utc = datetime.now(timezone.utc).isoformat()
        cycle_key = cycle_id or ticker

        # Lock the cycle and record cooldown
        self._in_flight_locks.discard(cycle_key)
        self._cycle_contracts_count[cycle_key] = self._cycle_contracts_count.get(cycle_key, 0) + size
        self._cycle_locks[cycle_key] = trade_id
        self._last_order_ts = now_mono
        self._last_order_ts_by_ticker[ticker] = now_mono

        report = {
            "event_type": "TRADE_INCEPTION",
            "trade_id": trade_id,
            "ticker": ticker,
            "side": side.lower(),
            "size": size,
            "price": float(price),
            "cost": float(cost),
            "fee": float(fee),
            "bot_type": bot_type,
            "execution_mode": execution_mode,
            "rationale": rationale,
            "vpin": round(vpin, 3),
            "ai_prob": round(ai_prob, 3),
            "cycle_key": cycle_key,
            "timestamp_utc": now_utc,
        }

        self._recent_inceptions.insert(0, report)
        if len(self._recent_inceptions) > 50:
            self._recent_inceptions.pop()

        logger.info(
            "🛡️ [GUARDRAIL INCEPTION] Locked cycle '%s' for trade %s (%s %d cts @ $%.2f). Total in cycle: %d/2",
            cycle_key, trade_id, side.upper(), size, float(price), self._cycle_contracts_count[cycle_key]
        )
        return report

    def record_resting_order(
        self,
        order_id: str,
        ticker: str,
        side: str,
        size: int,
        price: Decimal,
        cycle_id: Optional[str] = None,
        bot_type: str = "3_step_domination_bot",
    ) -> None:
        """Lock the cycle immediately upon submitting a resting limit order to prevent duplicate orders."""
        now_mono = time.monotonic()
        now_utc = datetime.now(timezone.utc).isoformat()
        cycle_key = cycle_id or ticker
        self._in_flight_locks.discard(cycle_key)
        self._cycle_contracts_count[cycle_key] = self._cycle_contracts_count.get(cycle_key, 0) + size
        self._cycle_locks[cycle_key] = order_id
        self._last_order_ts = now_mono
        self._last_order_ts_by_ticker[ticker] = now_mono
        
        report = {
            "event_type": "RESTING_ORDER_SUBMISSION",
            "trade_id": order_id,
            "ticker": ticker,
            "side": side.lower(),
            "size": size,
            "price": float(price),
            "cost": float(price * Decimal(str(size))),
            "fee": 0.0,
            "bot_type": bot_type,
            "execution_mode": "live",
            "rationale": f"Resting maker limit order submitted; cycle locked to max 2 entries (allocated: {self._cycle_contracts_count[cycle_key]}/2).",
            "vpin": 0.15,
            "ai_prob": 0.50,
            "cycle_key": cycle_key,
            "timestamp_utc": now_utc,
        }
        self._recent_inceptions.insert(0, report)
        if len(self._recent_inceptions) > 50:
            self._recent_inceptions.pop()

        logger.info(
            "🛡️ [GUARDRAIL RESTING LOCK] Locked cycle '%s' for resting order %s (%s %d cts @ $%.2f). Total in cycle: %d/2",
            cycle_key, order_id, side.upper(), size, float(price), self._cycle_contracts_count[cycle_key]
        )

    def release_in_flight_intent(self, cycle_key: str) -> None:
        """Release in-flight reservation if order placement failed, was rejected, or was cancelled."""
        self._in_flight_locks.discard(cycle_key)
        self._in_flight_lock_ts.pop(cycle_key, None)

    def record_order_attempt(self, ticker: str, cooldown_seconds: Optional[float] = None) -> None:
        """Record an order attempt (fill, 0-fill, or rejection) to enforce execution cooldown."""
        now_mono = time.monotonic()
        self._last_order_ts = now_mono
        self._last_order_ts_by_ticker[ticker] = now_mono

    # -------------------------------------------------------------------------
    # 3. Settlement & Cycle Unlocking
    # -------------------------------------------------------------------------

    def record_cycle_settlement(
        self,
        ticker: str,
        outcome: str,
        pnl: Decimal,
        balance_after: Decimal,
        cycle_id: Optional[str] = None,
    ) -> None:
        """Release the cycle lock upon official contract expiration and update loss streaks."""
        cycle_key = cycle_id or ticker
        self._cycle_locks.pop(cycle_key, None)
        self._cycle_contracts_count.pop(cycle_key, None)
        self._in_flight_locks.discard(cycle_key)
        self._in_flight_lock_ts.pop(cycle_key, None)

        if outcome.lower() == "loss":
            self._consecutive_losses += 1
            logger.info("🛡️ [GUARDRAIL SETTLEMENT] Loss recorded. Consecutive losses = %d", self._consecutive_losses)
            if self._consecutive_losses >= self.harakiri_loss_limit:
                self.is_bot_armed = False
                logger.warning(
                    "🚨 [GUARDRAIL HARAKIRI] Consecutive losses (%d) reached limit (%d)! Bot automatically DISARMED.",
                    self._consecutive_losses, self.harakiri_loss_limit
                )
        elif outcome.lower() == "win":
            self._consecutive_losses = 0
            logger.info("🛡️ [GUARDRAIL SETTLEMENT] Win recorded. Consecutive losses reset to 0.")

        # Update peak equity and circuit breaker
        if self._peak_equity is None or balance_after > self._peak_equity:
            self._peak_equity = balance_after

        drawdown = max(Decimal("0"), self._peak_equity - balance_after)
        drawdown_pct = (drawdown / self._peak_equity) if (self._peak_equity and self._peak_equity > 0) else Decimal("0")
        if drawdown_pct >= self.emergency_drawdown_limit:
            self._circuit_breaker_tripped = True
            logger.warning(
                "🚨 [GUARDRAIL EMERGENCY] Circuit breaker tripped on settlement! Drawdown %.1f%% >= %.0f%%",
                float(drawdown_pct * 100), float(self.emergency_drawdown_limit * 100)
            )

    def record_trade_settlement(
        self,
        ticker: str,
        pnl: Decimal,
        was_win: bool,
        balance_after: Optional[Decimal] = None,
        cycle_id: Optional[str] = None,
    ) -> None:
        """Convenience method to record trade settlement with boolean outcome."""
        outcome = "win" if was_win else "loss"
        curr_balance = balance_after if balance_after is not None else (self._peak_equity or Decimal("100.00")) + pnl
        self.record_cycle_settlement(ticker, outcome=outcome, pnl=pnl, balance_after=curr_balance, cycle_id=cycle_id)

    def arm_bot(self) -> None:
        """Manually re-arm the bot and reset consecutive loss streak."""
        self.is_bot_armed = True
        self._consecutive_losses = 0
        logger.info("🛡️ [GUARDRAIL ARM] Bot manually RE-ARMED. Consecutive loss counter reset.")

    def disarm_bot(self) -> None:
        """Manually disarm the bot (emergency manual shutdown)."""
        self.is_bot_armed = False
        logger.warning("🛡️ [GUARDRAIL DISARM] Bot manually DISARMED.")

    def unlock_cycle(self, cycle_key: str) -> None:
        """Manually unlock a cycle if needed."""
        self._cycle_locks.pop(cycle_key, None)
        self._cycle_contracts_count.pop(cycle_key, None)
        self._in_flight_locks.discard(cycle_key)

    def is_cycle_locked(self, cycle_key: str) -> bool:
        """Check whether a cycle currently has an active trade lockout."""
        return cycle_key in self._cycle_locks

    def reset_circuit_breaker(self, current_balance: Decimal) -> None:
        """Reset emergency circuit breaker and re-anchor peak equity."""
        self._circuit_breaker_tripped = False
        self._peak_equity = current_balance
        self._consecutive_losses = 0
        logger.info("🛡️ [GUARDRAIL RESET] Circuit breaker reset. Peak equity re-anchored to $%.2f", float(current_balance))

    # -------------------------------------------------------------------------
    # 4. Status & Diagnostics
    # -------------------------------------------------------------------------

    def _record_rejection(self, category: str, msg: str, ticker: str, timestamp_utc: str) -> None:
        self._total_rejections += 1
        self._rejection_reasons[category] = self._rejection_reasons.get(category, 0) + 1
        entry = {
            "category": category,
            "message": msg,
            "ticker": ticker,
            "timestamp_utc": timestamp_utc,
        }
        self._recent_rejections.insert(0, entry)
        if len(self._recent_rejections) > 30:
            self._recent_rejections.pop()
        now_mono = time.monotonic()
        key = f"{ticker}_{category}"
        if now_mono - self._last_log_rejection_ts.get(key, 0.0) >= 5.0:
            self._last_log_rejection_ts[key] = now_mono
            logger.warning("🛡️ [GUARDRAIL BLOCKED] %s", msg)

    def get_status(self) -> Dict[str, Any]:
        """Return real-time guardrail telemetry for UI and diagnostics."""
        now_mono = time.monotonic()
        elapsed_global = now_mono - self._last_order_ts if self._last_order_ts > 0 else 999.0
        remaining_cooldown = max(0.0, self.min_order_interval_seconds - elapsed_global)

        return {
            "circuit_breaker_tripped": self._circuit_breaker_tripped,
            "consecutive_losses": self._consecutive_losses,
            "active_cycle_locks": list(self._cycle_locks.keys()),
            "locked_cycles_count": len(self._cycle_locks),
            "remaining_cooldown_seconds": round(remaining_cooldown, 1),
            "is_in_cooldown": remaining_cooldown > 0,
            "min_order_interval_seconds": self.min_order_interval_seconds,
            "max_risk_pct_per_trade": float(self.max_risk_pct_per_trade * 100),
            "total_validations": self._total_validations,
            "total_rejections": self._total_rejections,
            "rejection_reasons": dict(self._rejection_reasons),
            "recent_inceptions": list(self._recent_inceptions[:10]),
            "recent_rejections": list(self._recent_rejections[:10]),
        }

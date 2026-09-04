"""Agent_Guardrails — Autonomous Quantitative Risk & Self-Preservation Guardian.

Enforces pre-trade execution guardrails, anti-kamikaze bankroll protection,
1-trade-per-cycle locks, execution cooldown throttles, and instant trade inception telemetry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("kalshi_sim.guardrails")


class AgentGuardrails:
    """Quantitative Execution Guardrail & Self-Preservation Guardian."""

    def __init__(
        self,
        min_order_interval_seconds: float = 45.0,
        max_risk_pct_per_trade: Decimal = Decimal("0.08"),  # Max 8% of equity per trade
        max_micro_bankroll_contracts: int = 4,  # Max contracts for equity <= $100
        max_nano_bankroll_contracts: int = 2,   # Max contracts for equity <= $25
        consecutive_loss_taper_threshold: int = 2,
        drawdown_taper_threshold: Decimal = Decimal("0.15"),  # 15% drawdown activates taper
        emergency_drawdown_limit: Decimal = Decimal("0.25"),  # 25% drawdown halts all trading
        vpin_toxic_threshold: float = 0.65,
    ) -> None:
        self.min_order_interval_seconds = min_order_interval_seconds
        self.max_risk_pct_per_trade = max_risk_pct_per_trade
        self.max_micro_bankroll_contracts = max_micro_bankroll_contracts
        self.max_nano_bankroll_contracts = max_nano_bankroll_contracts
        self.consecutive_loss_taper_threshold = consecutive_loss_taper_threshold
        self.drawdown_taper_threshold = drawdown_taper_threshold
        self.emergency_drawdown_limit = emergency_drawdown_limit
        self.vpin_toxic_threshold = vpin_toxic_threshold

        # State tracking
        self._last_order_ts: float = 0.0
        self._last_order_ts_by_ticker: dict[str, float] = {}
        self._cycle_locks: dict[str, str] = {}  # cycle_key -> trade_id
        self._consecutive_losses: int = 0
        self._peak_equity: Optional[Decimal] = None
        self._circuit_breaker_tripped: bool = False

        # Telemetry & Audit
        self._total_validations: int = 0
        self._total_rejections: int = 0
        self._rejection_reasons: dict[str, int] = {}
        self._recent_inceptions: list[dict[str, Any]] = []
        self._recent_rejections: list[dict[str, Any]] = []
        self._last_log_rejection_ts: dict[str, float] = {}

    # -------------------------------------------------------------------------
    # 1. Pre-Trade Intent Validation
    # -------------------------------------------------------------------------

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
    ) -> Tuple[bool, str, int, Dict[str, Any]]:
        """Validate an order against all safety guardrails before placement.

        Returns:
            (is_allowed, reason, approved_size, diagnostic_metrics)
        """
        self._total_validations += 1
        now_mono = time.monotonic()
        now_utc = datetime.now(timezone.utc).isoformat()
        cycle_key = cycle_id or ticker

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

        # 3. 1-Trade-Per-Cycle Lockout Check (Automated bots only)
        if is_bot and cycle_key in self._cycle_locks:
            locked_trade = self._cycle_locks[cycle_key]
            msg = f"1-TRADE-PER-CYCLE LOCKOUT: Cycle '{cycle_key}' already has active trade '{locked_trade}'. Further entries blocked until expiration."
            self._record_rejection("cycle_locked", msg, ticker, now_utc)
            return False, msg, 0, {"locked_trade": locked_trade}

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

        approved_size = min(requested_size, budget_contracts, bankroll_cap)

        # 6. Loss Streak & Drawdown Defense Taper
        is_tapered = False
        if self._consecutive_losses >= self.consecutive_loss_taper_threshold or drawdown_pct >= self.drawdown_taper_threshold:
            is_tapered = True
            approved_size = min(approved_size, 1)  # Strict self-preservation: minimum size

        if approved_size <= 0:
            msg = f"INSUFFICIENT RISK BUDGET: Equity ${total_equity:.2f} (Max Risk ${max_risk_dollars:.2f}) cannot afford 1 contract @ ${unit_cost:.2f}."
            self._record_rejection("insufficient_budget", msg, ticker, now_utc)
            return False, msg, 0, {"max_risk_dollars": float(max_risk_dollars)}

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
            "🛡️ [GUARDRAIL INCEPTION] Locked cycle '%s' for trade %s (%s %d cts @ $%.2f)",
            cycle_key, trade_id, side.upper(), size, float(price)
        )
        return report

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

        if outcome.lower() == "loss":
            self._consecutive_losses += 1
            logger.info("🛡️ [GUARDRAIL SETTLEMENT] Loss recorded. Consecutive losses = %d", self._consecutive_losses)
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

    def unlock_cycle(self, cycle_key: str) -> None:
        """Manually unlock a cycle if needed."""
        self._cycle_locks.pop(cycle_key, None)

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

"""Incubator Agent: Lane 2 Shadow Strategy Supervisor & Pre-Flight Certification Engine.

Autonomous supervisor monitoring shadow trading bots in Lane 2 (operating on live
Kalshi WebSocket ticks & CME CF BRTI 5Hz data with zero real capital risk).

Key Responsibilities:
1. Warm-Path Cycle Post-Mortems: Diagnostic reviews after every 15M/5M cycle settlement.
2. Quantitative Scorecard: Tracks multi-cycle Win Rate, Profit Factor, Max Drawdown,
   Adverse Selection Drift, and VPIN Toxicity Resilience with strict Decimal arithmetic.
3. 4-Pillar Promotion Gatekeeper: Evaluates shadow bots against BotDeploymentAuditor
   and empirical statistical thresholds before authorizing promotion to Live Trading (Lane 1).
4. Mobile-Optimized Telemetry: Generates concise digests formatted for mobile screens,
   Telegram, and Discord webhooks.

CRITICAL INVARIANT: The Incubator Agent operates exclusively on the Warm Path (asynchronous
post-cycle events and REST queries) and NEVER intercepts or adds latency to the 5Hz tick hot path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import logging
import math
from pathlib import Path
import time
from typing import Any, Dict, List, Literal, Optional, Tuple

from app_3_autonomous_chef.bot_deployment_auditor import BotDeploymentAuditor, BotAuditReport
from shared.schemas import OrderSide

logger = logging.getLogger("kalshi_sim.incubator_agent")

DEFAULT_INCUBATOR_STATE_FILE = Path("data") / "incubator_state.json"


def calc_taker_fee(count: int, price: Decimal) -> Decimal:
    """Calculate official Kalshi taker fee per contract with strict Decimal arithmetic."""
    c = Decimal(str(count))
    p = price
    p_comp = Decimal("1.00") - p
    var_fee = Decimal("0.07") * c * p * p_comp
    cents = math.ceil(float(var_fee) * 100)
    fee = Decimal(str(cents)) / Decimal("100")
    floor_fee = Decimal("0.01") * c
    cap_fee = Decimal("0.02") * c
    return max(floor_fee, min(cap_fee, fee))


class ShadowTradeRecord:
    """Record of an individual shadow paper trade placed by a candidate bot."""

    def __init__(
        self,
        trade_id: str,
        bot_id: str,
        bot_name: str,
        ticker: str,
        side: Literal["yes", "no"],
        count: int,
        entry_price: Decimal,
        target_strike: Decimal,
        entry_spot: Decimal,
        vpin_at_entry: float = 0.0,
        entry_time: Optional[str] = None,
        cycle_id: Optional[str] = None,
    ) -> None:
        self.trade_id = trade_id
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.ticker = ticker
        self.side = side.lower()
        self.count = count
        self.entry_price = entry_price
        self.target_strike = target_strike
        self.entry_spot = entry_spot
        self.vpin_at_entry = vpin_at_entry
        self.entry_time = entry_time or datetime.now(timezone.utc).isoformat()
        self.cycle_id = cycle_id or ticker
        self.settled: bool = False
        self.settlement_twap: Optional[Decimal] = None
        self.outcome: Optional[str] = None
        self.won: Optional[bool] = None
        self.realized_pnl: Optional[Decimal] = None
        self.fee: Optional[Decimal] = None
        self.adverse_drift: bool = False

    def settle(self, final_twap: Decimal, target_strike: Decimal) -> Decimal:
        """Settle trade against official final settlement TWAP and strike."""
        self.settlement_twap = final_twap
        self.target_strike = target_strike
        self.settled = True

        # Binary settlement: YES wins if final_twap >= target_strike
        yes_won = final_twap >= target_strike
        self.outcome = "YES_WIN" if yes_won else "NO_WIN"

        self.won = (self.side == "yes" and yes_won) or (self.side == "no" and not yes_won)

        self.fee = calc_taker_fee(self.count, self.entry_price)
        total_cost = Decimal(str(self.count)) * self.entry_price

        if self.won:
            gross_payout = Decimal(str(self.count)) * Decimal("1.00")
            self.realized_pnl = gross_payout - total_cost - self.fee
        else:
            self.realized_pnl = -total_cost - self.fee

        # Adverse drift check: Spot moved > $15 against trade direction between entry and settlement
        spot_diff = final_twap - self.entry_spot
        if self.side == "yes" and spot_diff < Decimal("-15.00"):
            self.adverse_drift = True
        elif self.side == "no" and spot_diff > Decimal("15.00"):
            self.adverse_drift = True
        else:
            self.adverse_drift = False

        return self.realized_pnl

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "bot_id": self.bot_id,
            "bot_name": self.bot_name,
            "ticker": self.ticker,
            "cycle_id": self.cycle_id,
            "side": self.side,
            "count": self.count,
            "entry_price": str(self.entry_price),
            "target_strike": str(self.target_strike),
            "entry_spot": str(self.entry_spot),
            "vpin_at_entry": self.vpin_at_entry,
            "entry_time": self.entry_time,
            "settled": self.settled,
            "settlement_twap": str(self.settlement_twap) if self.settlement_twap is not None else None,
            "outcome": self.outcome,
            "won": self.won,
            "realized_pnl": str(self.realized_pnl) if self.realized_pnl is not None else None,
            "fee": str(self.fee) if self.fee is not None else None,
            "adverse_drift": self.adverse_drift,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ShadowTradeRecord:
        rec = cls(
            trade_id=data["trade_id"],
            bot_id=data["bot_id"],
            bot_name=data.get("bot_name", data["bot_id"]),
            ticker=data["ticker"],
            side=data["side"],
            count=data["count"],
            entry_price=Decimal(str(data["entry_price"])),
            target_strike=Decimal(str(data["target_strike"])),
            entry_spot=Decimal(str(data["entry_spot"])),
            vpin_at_entry=float(data.get("vpin_at_entry", 0.0)),
            entry_time=data.get("entry_time"),
            cycle_id=data.get("cycle_id"),
        )
        rec.settled = data.get("settled", False)
        if data.get("settlement_twap") is not None:
            rec.settlement_twap = Decimal(str(data["settlement_twap"]))
        rec.outcome = data.get("outcome")
        rec.won = data.get("won")
        if data.get("realized_pnl") is not None:
            rec.realized_pnl = Decimal(str(data["realized_pnl"]))
        if data.get("fee") is not None:
            rec.fee = Decimal(str(data["fee"]))
        rec.adverse_drift = data.get("adverse_drift", False)
        return rec


class CyclePostMortem:
    """Diagnostic post-mortem for a completed contract cycle across all active shadow bots."""

    def __init__(
        self,
        cycle_id: str,
        ticker: str,
        settlement_twap: Decimal,
        target_strike: Decimal,
        outcome: str,
        trades: List[Dict[str, Any]],
        total_pnl: Decimal,
        diagnosis: str,
        timestamp: Optional[str] = None,
    ) -> None:
        self.cycle_id = cycle_id
        self.ticker = ticker
        self.settlement_twap = settlement_twap
        self.target_strike = target_strike
        self.outcome = outcome
        self.trades = trades
        self.total_pnl = total_pnl
        self.diagnosis = diagnosis
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "ticker": self.ticker,
            "settlement_twap": str(self.settlement_twap),
            "target_strike": str(self.target_strike),
            "outcome": self.outcome,
            "trades": self.trades,
            "total_pnl": str(self.total_pnl),
            "diagnosis": self.diagnosis,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CyclePostMortem:
        return cls(
            cycle_id=data["cycle_id"],
            ticker=data["ticker"],
            settlement_twap=Decimal(str(data["settlement_twap"])),
            target_strike=Decimal(str(data["target_strike"])),
            outcome=data["outcome"],
            trades=data.get("trades", []),
            total_pnl=Decimal(str(data.get("total_pnl", "0.00"))),
            diagnosis=data.get("diagnosis", ""),
            timestamp=data.get("timestamp"),
        )


class BotScorecard:
    """Comprehensive multi-cycle quantitative scorecard for a shadow bot candidate."""

    def __init__(
        self,
        bot_id: str,
        bot_name: str,
        total_trades: int = 0,
        wins: int = 0,
        losses: int = 0,
        total_pnl: Decimal = Decimal("0.00"),
        profit_factor: Decimal = Decimal("0.00"),
        max_drawdown_pct: Decimal = Decimal("0.00"),
        adverse_selection_count: int = 0,
        toxic_vpin_trades_count: int = 0,
        promotion_status: Literal["COOKING", "AUDITING", "READY_FOR_PROMOTION", "PROMOTED", "BLOCKED"] = "COOKING",
        readiness_score_pct: int = 0,
        last_audit: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.total_trades = total_trades
        self.wins = wins
        self.losses = losses
        self.total_pnl = total_pnl
        self.profit_factor = profit_factor
        self.max_drawdown_pct = max_drawdown_pct
        self.adverse_selection_count = adverse_selection_count
        self.toxic_vpin_trades_count = toxic_vpin_trades_count
        self.promotion_status = promotion_status
        self.readiness_score_pct = readiness_score_pct
        self.last_audit = last_audit

    @property
    def win_rate_pct(self) -> Decimal:
        if self.total_trades == 0:
            return Decimal("0.00")
        return (Decimal(str(self.wins)) / Decimal(str(self.total_trades)) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def academic_standing(self) -> str:
        """Quant University academic standing tier based on settled cycle count."""
        if self.total_trades < 10:
            return "Freshman (Incubator Sandbox)"
        elif self.total_trades < 20:
            return "Sophomore (Lab Trials)"
        elif self.total_trades < 30:
            return "Junior (Stress Arena)"
        else:
            return "Senior (Graduation Candidate)"

    @property
    def curriculum_progress_pct(self) -> int:
        """Progress towards 30-cycle graduation requirement (0-100%)."""
        return min(100, int((self.total_trades / 30) * 100))

    @property
    def graduation_eligible(self) -> bool:
        """Whether the candidate bot has satisfied minimum cycles and performance criteria."""
        return (
            self.total_trades >= 30
            and self.win_rate_pct >= Decimal("52.00")
            and self.profit_factor >= Decimal("1.10")
            and self.max_drawdown_pct <= Decimal("15.00")
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bot_id": self.bot_id,
            "bot_name": self.bot_name,
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate_pct": str(self.win_rate_pct),
            "total_pnl": str(self.total_pnl),
            "profit_factor": str(self.profit_factor),
            "max_drawdown_pct": str(self.max_drawdown_pct),
            "adverse_selection_count": self.adverse_selection_count,
            "toxic_vpin_trades_count": self.toxic_vpin_trades_count,
            "promotion_status": self.promotion_status,
            "readiness_score_pct": self.readiness_score_pct,
            "academic_standing": self.academic_standing,
            "curriculum_progress_pct": self.curriculum_progress_pct,
            "graduation_eligible": self.graduation_eligible,
            "last_audit": self.last_audit,
        }


class IncubatorAgent:
    """Autonomous Lane 2 Supervisor and Pre-Flight Certification Gatekeeper."""

    def __init__(
        self,
        auditor: Optional[BotDeploymentAuditor] = None,
        state_path: Path = DEFAULT_INCUBATOR_STATE_FILE,
    ) -> None:
        self.auditor = auditor or BotDeploymentAuditor()
        self.state_path = state_path
        self._trades: List[ShadowTradeRecord] = []
        self._post_mortems: List[CyclePostMortem] = []
        self._load_state()

    def _load_state(self) -> None:
        """Load persistent incubator history from disk."""
        if not self.state_path.exists():
            return
        try:
            content = self.state_path.read_text(encoding="utf-8").strip()
            if not content:
                return
            data = json.loads(content)
            self._trades = [ShadowTradeRecord.from_dict(t) for t in data.get("trades", [])]
            self._post_mortems = [CyclePostMortem.from_dict(pm) for pm in data.get("post_mortems", [])]
        except Exception as exc:
            logger.error("Failed to load incubator state from %s: %s", self.state_path, exc)

    def _save_state(self) -> None:
        """Persist incubator state atomically to disk."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.state_path.with_suffix(".tmp")
            payload = {
                "trades": [t.to_dict() for t in self._trades[-500:]],  # Ring buffer of recent 500 shadow trades
                "post_mortems": [pm.to_dict() for pm in self._post_mortems[-100:]],  # Recent 100 cycle post-mortems
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
            temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temp_path.replace(self.state_path)
        except Exception as exc:
            logger.error("Failed to save incubator state: %s", exc)

    def record_shadow_order(
        self,
        trade_id: str,
        bot_id: str,
        bot_name: str,
        ticker: str,
        side: Literal["yes", "no"],
        count: int,
        entry_price: Decimal,
        target_strike: Decimal,
        entry_spot: Decimal,
        vpin_at_entry: float = 0.0,
        cycle_id: Optional[str] = None,
    ) -> ShadowTradeRecord:
        """Record a shadow paper execution in Lane 2."""
        record = ShadowTradeRecord(
            trade_id=trade_id,
            bot_id=bot_id,
            bot_name=bot_name,
            ticker=ticker,
            side=side,
            count=count,
            entry_price=entry_price,
            target_strike=target_strike,
            entry_spot=entry_spot,
            vpin_at_entry=vpin_at_entry,
            cycle_id=cycle_id or ticker,
        )
        self._trades.append(record)
        self._save_state()
        logger.info(
            "🧪 [INCUBATOR RECORD] Bot '%s' placed %s x%d on %s @ $%s (Strike: $%s, Spot: $%s, VPIN: %.2f)",
            bot_name,
            side.upper(),
            count,
            ticker,
            entry_price,
            target_strike,
            entry_spot,
            vpin_at_entry,
        )
        return record

    def on_cycle_settled(
        self,
        ticker: str,
        final_twap: Decimal,
        target_strike: Decimal,
        cycle_id: Optional[str] = None,
    ) -> CyclePostMortem:
        """Perform autonomous warm-path post-mortem when a 15M/5M contract cycle settles."""
        active_cycle_id = cycle_id or ticker
        unsettled_trades = [t for t in self._trades if (t.ticker == ticker or t.cycle_id == active_cycle_id) and not t.settled]

        total_cycle_pnl = Decimal("0.00")
        settled_trade_dicts: List[Dict[str, Any]] = []
        diagnoses: List[str] = []

        yes_won = final_twap >= target_strike
        outcome_str = "YES_WIN" if yes_won else "NO_WIN"

        for trade in unsettled_trades:
            pnl = trade.settle(final_twap, target_strike)
            total_cycle_pnl += pnl
            settled_trade_dicts.append(trade.to_dict())

            # Formulate clinical diagnosis
            if trade.won:
                diagnoses.append(f"Bot '{trade.bot_name}' won +${pnl:.2f} with {trade.side.upper()} @ ${trade.entry_price}.")
            else:
                reason = "Predicted wrong direction"
                if trade.adverse_drift:
                    reason = "Adverse selection price drift (Spot shifted >$15 against trade)"
                elif trade.vpin_at_entry >= 0.65:
                    reason = f"Toxic flow entry (VPIN={trade.vpin_at_entry:.2f} >= 0.65)"
                diagnoses.append(f"Bot '{trade.bot_name}' lost -${abs(pnl):.2f} on {trade.side.upper()}: {reason}.")

        diff = final_twap - target_strike
        summary_diag = (
            f"Cycle {active_cycle_id} settled {outcome_str} (TWAP ${final_twap:.2f} vs Strike ${target_strike:.2f}, Diff: ${diff:+.2f}). "
            + (" ".join(diagnoses) if diagnoses else "No active shadow bots entered this cycle.")
        )

        post_mortem = CyclePostMortem(
            cycle_id=active_cycle_id,
            ticker=ticker,
            settlement_twap=final_twap,
            target_strike=target_strike,
            outcome=outcome_str,
            trades=settled_trade_dicts,
            total_pnl=total_cycle_pnl,
            diagnosis=summary_diag,
        )

        self._post_mortems.append(post_mortem)
        self._save_state()

        logger.info("🧪 [INCUBATOR POST-MORTEM] %s", summary_diag)
        return post_mortem

    def get_bot_scorecard(self, bot_id: str, bot_name: Optional[str] = None) -> BotScorecard:
        """Compute live quantitative scorecard and readiness score for a specific bot."""
        bot_trades = [t for t in self._trades if t.bot_id == bot_id and t.settled]
        name = bot_name or (bot_trades[0].bot_name if bot_trades else bot_id)

        if not bot_trades:
            return BotScorecard(bot_id=bot_id, bot_name=name, promotion_status="COOKING", readiness_score_pct=0)

        total_trades = len(bot_trades)
        wins = sum(1 for t in bot_trades if t.won)
        losses = total_trades - wins

        total_gains = Decimal("0.00")
        total_losses = Decimal("0.00")
        running_equity = Decimal("100.00")
        peak_equity = Decimal("100.00")
        max_drawdown = Decimal("0.00")
        total_pnl = Decimal("0.00")
        adverse_drift_count = 0
        toxic_vpin_count = 0

        for t in bot_trades:
            pnl = t.realized_pnl or Decimal("0.00")
            total_pnl += pnl
            if pnl > Decimal("0.00"):
                total_gains += pnl
            else:
                total_losses += abs(pnl)

            running_equity += pnl
            if running_equity > peak_equity:
                peak_equity = running_equity
            
            dd = (peak_equity - running_equity) / peak_equity * Decimal("100")
            if dd > max_drawdown:
                max_drawdown = dd

            if t.adverse_drift:
                adverse_drift_count += 1
            if t.vpin_at_entry >= 0.65:
                toxic_vpin_count += 1

        profit_factor = Decimal("99.99") if total_losses == Decimal("0.00") and total_gains > Decimal("0.00") else (
            (total_gains / total_losses).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if total_losses > Decimal("0.00") else Decimal("0.00")
        )

        win_rate = (Decimal(str(wins)) / Decimal(str(total_trades)) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Compute Readiness Score (0 to 100%)
        sample_score = min(30, int(total_trades / 20 * 30))
        win_score = min(30, int(float(win_rate) / 60.0 * 30))
        pf_score = min(25, int(float(profit_factor) / 1.30 * 25))
        dd_score = 15 if max_drawdown <= Decimal("15.00") else max(0, 15 - int(float(max_drawdown - Decimal("15.00"))))
        readiness_pct = min(100, max(0, sample_score + win_score + pf_score + dd_score))

        status: Literal["COOKING", "AUDITING", "READY_FOR_PROMOTION", "PROMOTED", "BLOCKED"] = "COOKING"
        if total_trades < 10:
            status = "COOKING"
        elif readiness_pct >= 85 and total_trades >= 20:
            status = "READY_FOR_PROMOTION"
        elif total_trades >= 10:
            status = "AUDITING"

        return BotScorecard(
            bot_id=bot_id,
            bot_name=name,
            total_trades=total_trades,
            wins=wins,
            losses=losses,
            total_pnl=total_pnl.quantize(Decimal("0.01")),
            profit_factor=profit_factor,
            max_drawdown_pct=max_drawdown.quantize(Decimal("0.01")),
            adverse_selection_count=adverse_drift_count,
            toxic_vpin_trades_count=toxic_vpin_count,
            promotion_status=status,
            readiness_score_pct=readiness_pct,
        )

    def get_all_scorecards(self) -> List[Dict[str, Any]]:
        """Get scorecards for all distinct bots that have traded in the incubator."""
        bot_ids = sorted(list(set(t.bot_id for t in self._trades)))
        if not bot_ids:
            bot_ids = ["3_step_domination_bot", "macro_trend_dominion", "the_onnx_strategy"]
        return [self.get_bot_scorecard(bid).to_dict() for bid in bot_ids]

    def get_recent_post_mortems(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent post-mortems."""
        return [pm.to_dict() for pm in reversed(self._post_mortems[-limit:])]

    def audit_for_promotion(self, bot_id: str, bot_instance: Optional[Any] = None) -> Dict[str, Any]:
        """Perform comprehensive 4-Pillar pre-flight audit and quantitative performance gate."""
        scorecard = self.get_bot_scorecard(bot_id)

        # 1. Performance Gate Verification
        perf_failures: List[str] = []
        if scorecard.total_trades < 20:
            perf_failures.append(f"Insufficient shadow sample size: {scorecard.total_trades}/20 minimum trades.")
        if scorecard.win_rate_pct < Decimal("60.00"):
            perf_failures.append(f"Win rate {scorecard.win_rate_pct}% < 60.00% minimum threshold.")
        if scorecard.profit_factor < Decimal("1.30"):
            perf_failures.append(f"Profit factor {scorecard.profit_factor} < 1.30 minimum threshold.")
        if scorecard.max_drawdown_pct > Decimal("15.00"):
            perf_failures.append(f"Max drawdown {scorecard.max_drawdown_pct}% exceeds 15.00% limit.")

        perf_status = "PASS" if not perf_failures else "FAIL"

        # 2. 4-Pillar Pre-Flight Certification Gate
        target_instance = bot_instance if bot_instance is not None else object()
        pillar_report = self.auditor.audit_bot(bot_id=bot_id, bot_instance=target_instance, mode="live")

        is_eligible = (perf_status == "PASS") and pillar_report.is_certified

        return {
            "bot_id": bot_id,
            "bot_name": scorecard.bot_name,
            "is_eligible_for_live_promotion": is_eligible,
            "performance_gate": {
                "status": perf_status,
                "metrics": {
                    "total_trades": scorecard.total_trades,
                    "win_rate_pct": str(scorecard.win_rate_pct),
                    "profit_factor": str(scorecard.profit_factor),
                    "max_drawdown_pct": str(scorecard.max_drawdown_pct),
                },
                "failures": perf_failures,
            },
            "four_pillar_audit": pillar_report.to_dict(),
            "audited_at": datetime.now(timezone.utc).isoformat(),
        }

    def generate_mobile_digest(self) -> str:
        """Generate mobile-screen-optimized markdown summary for remote monitoring."""
        scorecards = [self.get_bot_scorecard(bid) for bid in sorted(list(set(t.bot_id for t in self._trades)))]
        recent_pm = self._post_mortems[-1] if self._post_mortems else None

        lines = [
            "🧪 **INCUBATOR AGENT: SHADOW TELEMETRY**",
            f"📅 *{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*",
            "",
            "📊 **Candidate Bots Cooking (Lane 2):**",
        ]

        if not scorecards:
            lines.append("*(No shadow trades recorded yet. Waiting for cycle trigger)*")
        else:
            for sc in scorecards:
                status_icon = "🟢" if sc.promotion_status == "READY_FOR_PROMOTION" else "🟡" if sc.promotion_status == "AUDITING" else "⚪"
                pnl_prefix = "+" if sc.total_pnl >= Decimal("0.00") else ""
                lines.append(
                    f"{status_icon} **{sc.bot_name}** (`{sc.promotion_status}`)\n"
                    f"   • Win Rate: **{sc.win_rate_pct}%** ({sc.wins}W / {sc.losses}L)\n"
                    f"   • PnL: **{pnl_prefix}${sc.total_pnl}** | PF: **{sc.profit_factor}** | MaxDD: **{sc.max_drawdown_pct}%**\n"
                    f"   • Readiness: **{sc.readiness_score_pct}%** / 100%"
                )

        if recent_pm:
            lines.extend([
                "",
                "🔍 **Latest Cycle Post-Mortem:**",
                f"• Cycle: `{recent_pm.cycle_id}` ({recent_pm.outcome})",
                f"• TWAP: `${recent_pm.settlement_twap}` vs Strike `${recent_pm.target_strike}`",
                f"• Diagnosis: {recent_pm.diagnosis}",
            ])

        return "\n".join(lines)

    def take_certification_exam(self, bot_id: str, bot_instance: Optional[Any] = None) -> Dict[str, Any]:
        """Administer the Quant University final certification exam and Seal of Excellence audit."""
        scorecard = self.get_bot_scorecard(bot_id)
        reasons: List[str] = []

        # 1. Sample size check (Senior Standing)
        if scorecard.total_trades < 30:
            reasons.append(f"Insufficient shadow sample size: completed {scorecard.total_trades}/30 required settled cycles.")

        # 2. Minimum statistical hurdle check
        if scorecard.win_rate_pct < Decimal("52.00"):
            reasons.append(f"Win rate {scorecard.win_rate_pct}% below 52.00% graduation threshold.")

        if scorecard.profit_factor < Decimal("1.10"):
            reasons.append(f"Profit factor {scorecard.profit_factor} below 1.10 minimum graduation threshold.")

        # 3. 5-Pillar Audit Gauntlet
        target_inst = bot_instance if bot_instance is not None else object()
        audit_report = self.auditor.audit_bot(bot_id=bot_id, bot_instance=target_inst, mode="live")

        if not audit_report.is_certified:
            reasons.extend(audit_report.failure_reasons)

        graduated = len(reasons) == 0 and audit_report.is_certified

        return {
            "bot_id": bot_id,
            "bot_name": scorecard.bot_name,
            "academic_standing": scorecard.academic_standing,
            "graduated": graduated,
            "reasons": reasons,
            "scorecard": scorecard.to_dict(),
            "audit_report": audit_report.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Singleton factory
_incubator_agent_instance: Optional[IncubatorAgent] = None


def get_incubator_agent() -> IncubatorAgent:
    """Get or create singleton IncubatorAgent instance."""
    global _incubator_agent_instance
    if _incubator_agent_instance is None:
        _incubator_agent_instance = IncubatorAgent()
    return _incubator_agent_instance

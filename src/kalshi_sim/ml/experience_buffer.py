"""Continuous Experience Learning Buffer for Kalshi 15M Trading Bots.

Maintains rolling historical memory of settled cycles, calculates calibration
metrics (Brier score, reliability curve), identifies repeating loss patterns
(mistake clustering), and dynamically prunes -EV entry price deciles.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kalshi_sim.experience_buffer")


@dataclass
class CycleExperience:
    """Standardized representation of an individual settled 15M cycle."""
    ticker: str
    cycle_id: str
    timestamp_utc: str
    strike_price: float
    settlement_spot: float
    spot_diff: float
    bot_side: str  # 'yes' | 'no' | 'wait'
    entry_price: float
    contracts: int
    predicted_prob: float
    outcome: str  # 'win' | 'loss' | 'wait'
    net_pnl: float
    fees: float
    execution_mode: str  # 'live' | 'simulated'
    vpin: float = 0.0
    active_playbook: str = "none"
    macro_regime: str = "neutral"


class ContinuousExperienceBuffer:
    """Rolling experience memory bank with online Brier calibration and mistake pruning."""

    def __init__(
        self,
        max_buffer_size: int = 500,
        history_file: Optional[Path] = None,
    ):
        self.max_buffer_size = max_buffer_size
        self.history_file = history_file or Path("data/win_loss_reports.json")
        self.experiences: List[CycleExperience] = []
        self.brier_score: float = 0.25  # Uninformative baseline
        self.pruned_price_deciles: List[int] = []
        self._load_initial_history()

    def _load_initial_history(self) -> None:
        """Load and parse past settled cycles from disk."""
        if not self.history_file.exists():
            logger.info("No prior win_loss_reports.json found. Starting empty buffer.")
            return

        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            for item in raw_data[-self.max_buffer_size:]:
                exp = self._dict_to_experience(item)
                if exp:
                    self.experiences.append(exp)

            self.recalibrate()
            logger.info("Loaded %d cycle experiences into buffer. Brier Score: %.4f", len(self.experiences), self.brier_score)
        except Exception as exc:
            logger.warning("Error loading initial experience history: %s", exc)

    def _dict_to_experience(self, d: Dict[str, Any]) -> Optional[CycleExperience]:
        """Convert raw report dictionary into structured CycleExperience."""
        try:
            strike = float(d.get("strike_price", 0.0))
            settle = float(d.get("settlement_btc_price", d.get("settlement_price", 0.0)))
            side = str(d.get("bot_side", d.get("side", "wait"))).lower()
            entry = float(d.get("entry_price", 0.50))
            contracts = int(d.get("contracts", d.get("size", 1)))
            outcome = str(d.get("outcome", "unknown")).lower()
            pnl = float(d.get("net_pnl", d.get("pnl", 0.0)))
            mode = str(d.get("execution_mode", d.get("mode", "simulated"))).lower()
            prob = float(d.get("predicted_prob", d.get("confidence", 0.65)))

            return CycleExperience(
                ticker=d.get("ticker", "KXBTC15M-UNKNOWN"),
                cycle_id=d.get("report_id", d.get("cycle_id", "")),
                timestamp_utc=d.get("timestamp_utc", ""),
                strike_price=strike,
                settlement_spot=settle,
                spot_diff=settle - strike,
                bot_side=side,
                entry_price=entry,
                contracts=contracts,
                predicted_prob=prob,
                outcome=outcome,
                net_pnl=pnl,
                fees=float(d.get("fees", 0.01)),
                execution_mode=mode,
                vpin=float(d.get("vpin", 0.15)),
                active_playbook=d.get("active_playbook", "none"),
                macro_regime=d.get("macro_regime", "neutral"),
            )
        except Exception:
            return None

    def record_settled_cycle(self, exp: CycleExperience) -> None:
        """Add a newly settled cycle to the buffer and trigger online recalibration."""
        self.experiences.append(exp)
        if len(self.experiences) > self.max_buffer_size:
            self.experiences.pop(0)
        self.recalibrate()

    def recalibrate(self) -> None:
        """Compute rolling Brier score and identify systematically unprofitable price bands."""
        settled_trades = [e for e in self.experiences if e.outcome in ("win", "loss")]
        if not settled_trades:
            self.brier_score = 0.25
            self.pruned_price_deciles = []
            return

        total_sq_err = 0.0
        decile_pnl: Dict[int, List[float]] = {d: [] for d in range(1, 10)}

        for e in settled_trades:
            actual = 1.0 if e.outcome == "win" else 0.0
            prob = max(0.01, min(0.99, e.predicted_prob))
            total_sq_err += (prob - actual) ** 2

            decile_bucket = int(e.entry_price * 10)
            if decile_bucket in decile_pnl:
                decile_pnl[decile_bucket].append(e.net_pnl)

        self.brier_score = round(total_sq_err / len(settled_trades), 4)

        pruned = []
        for decile, pnls in decile_pnl.items():
            if len(pnls) >= 5 and sum(pnls) < 0.0:
                pruned.append(decile * 10)
        self.pruned_price_deciles = sorted(pruned)

    def get_recent_summary(self, n: int = 20) -> Dict[str, Any]:
        """Summarize the last N settled cycles for LLM context ingestion."""
        recent = [e for e in self.experiences if e.outcome in ("win", "loss")][-n:]
        if not recent:
            return {
                "total_recent": 0,
                "win_rate": 0.0,
                "net_pnl": 0.0,
                "brier_score": self.brier_score,
                "pruned_deciles": self.pruned_price_deciles,
                "recent_mistakes": [],
            }

        wins = sum(1 for e in recent if e.outcome == "win")
        total_pnl = sum(e.net_pnl for e in recent)
        win_rate = round((wins / len(recent)) * 100, 1)

        mistakes = []
        for e in recent:
            if e.outcome == "loss":
                mistakes.append({
                    "ticker": e.ticker,
                    "side": e.bot_side.upper(),
                    "entry_cents": int(e.entry_price * 100),
                    "spot_diff": round(e.spot_diff, 2),
                    "loss_dollars": round(abs(e.net_pnl), 2),
                    "playbook": e.active_playbook,
                })

        return {
            "total_recent": len(recent),
            "wins": wins,
            "losses": len(recent) - wins,
            "win_rate": win_rate,
            "net_pnl": round(total_pnl, 2),
            "brier_score": self.brier_score,
            "pruned_deciles": [f"{d}Â¢" for d in self.pruned_price_deciles],
            "recent_mistakes": mistakes[-5:],
        }



"""
Trial Registry — the anti-self-deception layer for deer_quant.

THE PROBLEM THIS EXISTS TO SOLVE
--------------------------------
"Keep revising the bot until it hits 75% win rate" is a loop that ALWAYS
terminates successfully and almost always produces a worthless bot.

Two independent reasons, both verified numerically:

1) MULTIPLE TESTING. A bot with zero edge (true 52% WR) tested over 30
   settled cycles will, by chance alone, show a 75%+ backtest roughly 1 time
   in 100. Search 1000 variants and ~6 will clear 75%. Search 5000 and you
   get a variant showing 86.7%. None of them have any edge. The search found
   noise and labelled it a discovery. This is why the number of trials is
   the single most important number in any backtest, and why a backtest that
   doesn't report it is uninterpretable. (Bailey & Lopez de Prado, 2014)

2) WIN RATE IS THE WRONG TARGET. On a binary contract, profit depends on
   the price paid. With Kalshi's taker fee of ceil(0.07*C*P*(1-P)):
       75% WR at price 0.70 -> EV +0.030/contract
       75% WR at price 0.80 -> EV -0.070/contract
       75% WR at price 0.90 -> EV -0.160/contract
   An optimizer rewarded on win rate learns to buy 0.90 favourites, scores
   ~90% WR, reports triumph, and loses money on every trade.

So this module does three things:
   - registers EVERY trial, so metrics can be deflated by search intensity
   - seals a holdout set that can be opened exactly once, by a human
   - scores on expected value, treating win rate as a diagnostic
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any


# =============================================================================
# Kalshi contract economics
# =============================================================================

def taker_fee(price: Decimal, contracts: int = 1) -> Decimal:
    """
    Kalshi taker fee: ceil(0.07 * C * P * (1-P)) rounded up to the cent.
    Decimal throughout — float money in a trading system is a defect.
    """
    raw = Decimal("0.07") * Decimal(contracts) * price * (Decimal(1) - price)
    return raw.quantize(Decimal("0.01"), rounding=ROUND_CEILING)


def expected_value(win_prob: Decimal, price: Decimal,
                   contracts: int = 1) -> Decimal:
    """
    EV per position, net of fees.

    THIS is the objective. Not win rate.
        win  -> gain (1 - price) per contract
        lose -> lose price per contract
    """
    fee = taker_fee(price, contracts)
    gain = (Decimal(1) - price) * contracts
    loss = price * contracts
    return win_prob * gain - (Decimal(1) - win_prob) * loss - fee


def breakeven_win_rate(price: Decimal, contracts: int = 1) -> Decimal:
    """The WR you must EXCEED at this price just to break even."""
    fee_per = taker_fee(price, contracts) / contracts
    return price + fee_per


# =============================================================================
# Statistics
# =============================================================================

def deflated_win_rate(observed_wr: float, n_cycles: int, n_trials: int,
                      null_wr: float = 0.50) -> dict[str, float]:
    """
    Haircut an observed win rate for the intensity of the search that found it.

    Intuition: the expected MAXIMUM of N random draws rises with N. If you
    tried 500 variants, the best one looks good even when all are worthless,
    so the bar it must clear rises with the number of trials.

    Uses the standard expected-maximum-of-N-normals approximation. This is a
    screening heuristic, not a formal test — it is deliberately conservative.
    """
    if n_cycles <= 1 or n_trials < 1:
        return {"deflated_wr": 0.0, "threshold": 1.0, "passes": False}

    se = math.sqrt(null_wr * (1 - null_wr) / n_cycles)

    # E[max of n_trials standard normals]
    if n_trials == 1:
        e_max = 0.0
    else:
        euler = 0.5772156649
        ln_n = math.log(n_trials)
        e_max = ((1 - euler) * _z(1 - 1 / n_trials)
                 + euler * _z(1 - 1 / (n_trials * math.e)))

    threshold = null_wr + e_max * se
    observed_z = (observed_wr - null_wr) / se if se > 0 else 0.0
    deflated = observed_z - e_max

    return {
        "observed_wr": observed_wr,
        "null_wr": null_wr,
        "std_error": se,
        "n_cycles": n_cycles,
        "n_trials": n_trials,
        "expected_max_z_from_noise": e_max,
        "wr_threshold_to_beat_noise": threshold,
        "deflated_z": deflated,
        "passes": bool(deflated > 0 and observed_wr > threshold),
    }


def _z(p: float) -> float:
    """Inverse normal CDF (Acklam approximation)."""
    if p <= 0 or p >= 1:
        return 0.0
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


# =============================================================================
# Trial record
# =============================================================================

@dataclass
class Trial:
    trial_id: str
    parent_bot: str
    hypothesis: str              # WHY this variant should work — required
    params_hash: str
    params: dict[str, Any]
    n_cycles: int
    win_rate: float              # diagnostic only
    avg_entry_price: float
    ev_per_contract: float       # the real objective
    profit_factor: float
    fold_evs: list[float]
    created: str
    verdict: str = "PENDING"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TrialRegistry:
    """
    Every backtest ever run, recorded. Nothing can be un-tried.

    The registry is append-only by design: if a variant could be deleted,
    the trial count could be laundered and the deflation defeated.
    """

    def __init__(self, db: Path) -> None:
        db.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db), check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS trials (
                trial_id TEXT PRIMARY KEY,
                parent_bot TEXT, hypothesis TEXT,
                params_hash TEXT UNIQUE, params TEXT,
                n_cycles INT, win_rate REAL, avg_entry_price REAL,
                ev_per_contract REAL, profit_factor REAL,
                fold_evs TEXT, created TEXT, verdict TEXT, notes TEXT
            )""")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS holdout_seal (
                dataset TEXT PRIMARY KEY, sealed_at TEXT,
                checksum TEXT, opened_at TEXT, opened_by TEXT
            )""")
        self.conn.commit()

    # -- trial accounting --------------------------------------------------
    def count(self, parent_bot: str | None = None) -> int:
        if parent_bot:
            cur = self.conn.execute(
                "SELECT COUNT(*) FROM trials WHERE parent_bot=?", (parent_bot,))
        else:
            cur = self.conn.execute("SELECT COUNT(*) FROM trials")
        return int(cur.fetchone()[0])

    def already_tried(self, params: dict[str, Any]) -> str | None:
        h = self._hash(params)
        cur = self.conn.execute(
            "SELECT trial_id FROM trials WHERE params_hash=?", (h,))
        row = cur.fetchone()
        return row[0] if row else None

    def register(self, t: Trial) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO trials VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (t.trial_id, t.parent_bot, t.hypothesis, t.params_hash,
             json.dumps(t.params), t.n_cycles, t.win_rate, t.avg_entry_price,
             t.ev_per_contract, t.profit_factor, json.dumps(t.fold_evs),
             t.created, t.verdict, t.notes))
        self.conn.commit()

    @staticmethod
    def _hash(params: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(params, sort_keys=True).encode()).hexdigest()[:16]

    # -- the holdout seal --------------------------------------------------
    def seal_holdout(self, dataset: str, checksum: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO holdout_seal VALUES (?,?,?,NULL,NULL)",
            (dataset, datetime.now(timezone.utc).isoformat(), checksum))
        self.conn.commit()

    def holdout_is_sealed(self, dataset: str) -> bool:
        cur = self.conn.execute(
            "SELECT opened_at FROM holdout_seal WHERE dataset=?", (dataset,))
        row = cur.fetchone()
        return bool(row) and row[0] is None

    def open_holdout(self, dataset: str, human: str) -> bool:
        """
        One shot, ever. A holdout you peek at twice is a training set.

        If the first look fails, you do NOT get to tune and re-test — that
        is exactly the loop that manufactures false discoveries. You go back
        to a new hypothesis and a fresh holdout.
        """
        if not self.holdout_is_sealed(dataset):
            return False
        self.conn.execute(
            "UPDATE holdout_seal SET opened_at=?, opened_by=? WHERE dataset=?",
            (datetime.now(timezone.utc).isoformat(), human, dataset))
        self.conn.commit()
        return True


# =============================================================================
# The gate
# =============================================================================

@dataclass
class Verdict:
    passed: bool
    reasons: list[str]
    metrics: dict[str, Any]


def evaluate_candidate(trial: Trial, registry: TrialRegistry,
                       min_cycles: int = 30,
                       min_profit_factor: float = 1.10) -> Verdict:
    """
    Judge a candidate honestly. Deliberately hard to pass.

    Note what is NOT here: any win-rate target. A candidate with a 62% win
    rate and positive EV passes; one with 88% win rate and negative EV fails.
    """
    reasons: list[str] = []
    n_trials = registry.count(trial.parent_bot)

    # 1. sample size
    if trial.n_cycles < min_cycles:
        reasons.append(
            f"only {trial.n_cycles} settled cycles; need >= {min_cycles}. "
            f"Below this, the confidence interval is wider than any edge.")

    # 2. THE objective
    if trial.ev_per_contract <= 0:
        reasons.append(
            f"EV per contract is {trial.ev_per_contract:+.4f} — not profitable "
            f"after fees, regardless of its {trial.win_rate:.1%} win rate.")

    # 3. the reward-hacking check
    be = float(breakeven_win_rate(Decimal(str(trial.avg_entry_price))))
    if trial.win_rate >= 0.70 and trial.win_rate < be:
        reasons.append(
            f"REWARD HACK: {trial.win_rate:.1%} win rate looks impressive but "
            f"average entry price {trial.avg_entry_price:.2f} requires "
            f"{be:.1%} to break even. This bot buys favourites and loses money.")

    # 4. profit factor
    if trial.profit_factor < min_profit_factor:
        reasons.append(
            f"profit factor {trial.profit_factor:.2f} < {min_profit_factor}")

    # 5. stability across folds
    if trial.fold_evs:
        neg = sum(1 for e in trial.fold_evs if e <= 0)
        if neg:
            reasons.append(
                f"EV is negative in {neg}/{len(trial.fold_evs)} walk-forward "
                f"folds — the edge is regime-dependent, not real.")

    # 6. search-intensity deflation
    d = deflated_win_rate(trial.win_rate, trial.n_cycles, n_trials)
    if not d["passes"]:
        reasons.append(
            f"after {n_trials} trials, noise alone would produce "
            f"{d['wr_threshold_to_beat_noise']:.1%}; observed "
            f"{trial.win_rate:.1%} does not clear that bar.")

    # 7. hypothesis discipline
    if len(trial.hypothesis.strip()) < 30:
        reasons.append(
            "no stated hypothesis. A parameter found by search with no "
            "explanation for WHY it should work is a curve fit.")

    return Verdict(
        passed=not reasons,
        reasons=reasons,
        metrics={**d, "ev_per_contract": trial.ev_per_contract,
                 "profit_factor": trial.profit_factor,
                 "breakeven_wr_at_avg_price": be,
                 "trials_so_far": n_trials},
    )

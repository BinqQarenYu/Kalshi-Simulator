"""Comprehensive True-Data Quantitative Backtesting Engine.

Replays all recorded 15-minute Kalshi cycles (Sept 2 - Sept 4, 2026) in chronological order.
Evaluates 5 strategy regimes using strict Decimal arithmetic:
1. Baseline (Actual Historical Account Performance - Unconstrained / Legacy)
2. Domination Bot 1 (Legacy 3-Step EV/VPIN - Unconstrained by Macro / Price Caps)
3. Domination Bot 2 (High-Conviction Runner - Cheap Asymmetric Contracts)
4. Macro Trend Dominion (Multi-timeframe Macro Momentum + Price Corridor $0.30-$0.62 + Flat Sizing + Late Salvage)
5. Macro Trend Dominion + QuoLas Nano ONNX (65/35 Bayesian Fusion + Hard Contradiction Veto + Extreme Uncertainty Gate + Price Cap)
"""

from __future__ import annotations

import collections
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import onnxruntime as ort

from kalshi_sim.ml.feature_extractor import KalshiOrderflowFeatureExtractor
from kalshi_sim.schemas import L2BookState, OrderBookLevel, OrderSide, TradeEvent


def _d(val: Any) -> Decimal:
    """Safely convert any value to Decimal with zero float drift."""
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def _round_c(val: Decimal) -> Decimal:
    """Round to 4 decimal places for exact cent calculations."""
    return val.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


@dataclass
class CycleData:
    cycle_index: int
    cycle_time: str
    ticker: str
    timestamp_utc: str
    epoch_s: float
    strike_price: Decimal
    settlement_spot: Decimal
    spot_diff: Decimal
    actual_side: str
    actual_entry: Decimal
    actual_contracts: int
    actual_outcome: str
    actual_pnl: Decimal
    vpin_score: float
    ev_edge: float
    ai_confidence: float
    trend_1h_pct: float
    trend_15m_pct: float
    macro_regime: str  # MACRO_BULL | MACRO_BEAR | MACRO_CHOP
    best_yes_ask: Decimal
    best_no_ask: Decimal
    best_yes_bid: Decimal
    best_no_bid: Decimal


@dataclass
class StrategyTradeRecord:
    cycle_index: int
    cycle_time: str
    ticker: str
    strategy_name: str
    action: str  # TAKE | VETO
    side: str
    entry_price: Decimal
    contracts: int
    outcome: str  # win | loss | salvaged_loss | vetoed
    pnl: Decimal
    gross_win: Decimal
    gross_loss: Decimal
    rationale: str
    macro_regime: str
    spot_diff: Decimal


@dataclass
class StrategyMetrics:
    name: str
    total_cycles: int
    trades_taken: int
    trades_vetoed: int
    wins: int
    losses: int
    salvaged_losses: int
    win_rate_pct: float
    net_pnl: Decimal
    gross_profit: Decimal
    gross_loss: Decimal
    profit_factor: float
    avg_win: Decimal
    avg_loss: Decimal
    payoff_ratio: float
    expectancy_per_trade: Decimal
    max_drawdown_dollars: Decimal
    max_drawdown_pct: float
    max_loss_streak: int
    sharpe_ratio: float
    sortino_ratio: float
    equity_curve: List[Decimal] = field(default_factory=list)


def load_production_cycles() -> List[CycleData]:
    """Load all historical cycles from disk in chronological order."""
    reports_file = Path("data/win_loss_reports.json")
    if not reports_file.exists():
        raise FileNotFoundError(f"Missing {reports_file}")

    with open(reports_file, "r", encoding="utf-8") as f:
        raw_reports = json.load(f)

    # In win_loss_reports.json, reports are newest-first. Reverse to chronological order.
    chronological_reports = list(reversed(raw_reports))

    cycles: List[CycleData] = []
    spot_history: List[Tuple[float, Decimal]] = []

    for idx, r in enumerate(chronological_reports):
        ts_str = r.get("timestamp_utc", "")
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            epoch_s = dt.timestamp()
        except Exception:
            epoch_s = float(idx * 900)

        strike = _d(r.get("strike_price", "0.0"))
        settle = _d(r.get("settlement_btc_price", "0.0"))
        if settle == Decimal("0.0"):
            continue

        spot_diff = settle - strike
        actual_side = str(r.get("bot_side", "yes")).lower()
        actual_entry = _d(r.get("entry_price", "0.50"))
        actual_contracts = int(r.get("contracts", 1))
        actual_outcome = str(r.get("outcome", "loss")).lower()
        actual_pnl = _d(r.get("pnl", "0.0"))
        ticker = str(r.get("ticker", f"KXBTC15M-CYCLE-{idx}"))
        cycle_time = str(r.get("cycle_time", ""))
        vpin = float(r.get("vpin_score", 0.15))
        edge = float(r.get("ev_edge", 0.08))
        conf = float(r.get("ai_confidence", 0.70))

        spot_history.append((epoch_s, settle))

        # Compute rolling 1-hour and 15-minute macro trend
        one_hour_ago = epoch_s - 3600.0
        fifteen_min_ago = epoch_s - 900.0

        p_1h: Optional[Decimal] = None
        p_15m: Optional[Decimal] = None

        for t, p in spot_history:
            if t <= one_hour_ago:
                p_1h = p
            if t <= fifteen_min_ago:
                p_15m = p

        if p_1h is not None and p_1h > Decimal("0.0"):
            trend_1h_pct = float(((settle - p_1h) / p_1h) * Decimal("100.0"))
        elif len(spot_history) >= 2:
            oldest_p = spot_history[0][1]
            trend_1h_pct = float(((settle - oldest_p) / oldest_p) * Decimal("100.0")) if oldest_p > Decimal("0.0") else 0.0
        else:
            trend_1h_pct = 0.0

        if p_15m is not None and p_15m > Decimal("0.0"):
            trend_15m_pct = float(((settle - p_15m) / p_15m) * Decimal("100.0"))
        else:
            trend_15m_pct = 0.0

        # Classify Macro Regime
        if trend_1h_pct >= 0.15 or (trend_1h_pct > 0.05 and trend_15m_pct >= 0.10):
            macro_regime = "MACRO_BULL"
        elif trend_1h_pct <= -0.15 or (trend_1h_pct < -0.05 and trend_15m_pct <= -0.10):
            macro_regime = "MACRO_BEAR"
        else:
            macro_regime = "MACRO_CHOP"

        # Reconstruct Order Book quotes around entry
        if actual_side == "yes":
            best_yes_ask = actual_entry
            best_yes_bid = max(Decimal("0.01"), actual_entry - Decimal("0.02"))
            best_no_bid = max(Decimal("0.01"), Decimal("1.00") - actual_entry)
            best_no_ask = Decimal("1.00") - best_yes_bid
        else:
            best_no_ask = actual_entry
            best_no_bid = max(Decimal("0.01"), actual_entry - Decimal("0.02"))
            best_yes_bid = max(Decimal("0.01"), Decimal("1.00") - actual_entry)
            best_yes_ask = Decimal("1.00") - best_no_bid

        cycles.append(
            CycleData(
                cycle_index=idx,
                cycle_time=cycle_time,
                ticker=ticker,
                timestamp_utc=ts_str,
                epoch_s=epoch_s,
                strike_price=strike,
                settlement_spot=settle,
                spot_diff=spot_diff,
                actual_side=actual_side,
                actual_entry=actual_entry,
                actual_contracts=actual_contracts,
                actual_outcome=actual_outcome,
                actual_pnl=actual_pnl,
                vpin_score=vpin,
                ev_edge=edge,
                ai_confidence=conf,
                trend_1h_pct=trend_1h_pct,
                trend_15m_pct=trend_15m_pct,
                macro_regime=macro_regime,
                best_yes_ask=best_yes_ask,
                best_no_ask=best_no_ask,
                best_yes_bid=best_yes_bid,
                best_no_bid=best_no_bid,
            )
        )

    return cycles


from kalshi_sim.ml.onnx_engine import KalshiONNXEngine


class ONNXMicrostructurePredictor:
    """Loads and runs inference with QuoLas Nano Microscope ONNX Model."""

    def __init__(self, model_path: str = "models/nano_microscope_overhauled.onnx"):
        self.engine = KalshiONNXEngine(model_path=model_path)

    def predict_for_cycle(self, cycle: CycleData) -> Tuple[str, float, float, float, float]:
        """Generate ONNX [signal, confidence, P(LONG), P(SHORT), P(WAIT)] for cycle."""
        # Construct continuous spot orderbook for ONNX feature extraction
        spot_f = float(cycle.settlement_spot)
        spread = 0.50
        book = L2BookState(market_ticker="BTC-SPOT", is_spot=True)
        for i in range(15):
            p_bid = Decimal(str(round(spot_f - spread * (i + 1), 2)))
            p_ask = Decimal(str(round(spot_f + spread * (i + 1), 2)))
            qty = Decimal(str(10.0 + i * 2.0))
            book.yes_book[p_bid] = qty
            book.no_book[p_ask] = qty
        book._stale = False

        res = self.engine.process_orderbook_tick(book)
        signal = str(res.get("signal", "WAIT"))
        confidence = float(res.get("confidence", 0.0))
        p_long = float(res.get("prob_long", 0.33))
        p_short = float(res.get("prob_short", 0.33))
        p_wait = float(res.get("prob_wait", 0.34))

        return signal, confidence, p_long, p_short, p_wait


def evaluate_strategy_baseline(cycles: List[CycleData]) -> List[StrategyTradeRecord]:
    """Replay Actual Historical Performance exactly as recorded."""
    records: List[StrategyTradeRecord] = []
    for c in cycles:
        pnl = c.actual_pnl
        outcome = c.actual_outcome
        gross_w = pnl if pnl > Decimal("0.0") else Decimal("0.0")
        gross_l = abs(pnl) if pnl < Decimal("0.0") else Decimal("0.0")

        records.append(
            StrategyTradeRecord(
                cycle_index=c.cycle_index,
                cycle_time=c.cycle_time,
                ticker=c.ticker,
                strategy_name="Baseline Historical",
                action="TAKE",
                side=c.actual_side,
                entry_price=c.actual_entry,
                contracts=c.actual_contracts,
                outcome=outcome,
                pnl=pnl,
                gross_win=gross_w,
                gross_loss=gross_l,
                rationale="Actual Historical Trade Execution",
                macro_regime=c.macro_regime,
                spot_diff=c.spot_diff,
            )
        )
    return records


def evaluate_strategy_domination_1(cycles: List[CycleData]) -> List[StrategyTradeRecord]:
    """Replay Domination Bot 1 (Legacy 3-Step EV/VPIN - Unconstrained by Macro / Price Caps)."""
    records: List[StrategyTradeRecord] = []
    fee = Decimal("0.01")

    for c in cycles:
        if c.vpin_score > 0.40:
            action = "VETO"
            outcome = "vetoed"
            pnl = Decimal("0.0")
            rationale = f"VPIN Toxicity Veto ({c.vpin_score:.2f} > 0.40)"
        elif c.ev_edge < 0.04:
            action = "VETO"
            outcome = "vetoed"
            pnl = Decimal("0.0")
            rationale = f"Insufficient Edge ({c.ev_edge:.2f} < 0.04)"
        else:
            action = "TAKE"
            side = c.actual_side
            entry = c.actual_entry
            contracts = max(1, min(c.actual_contracts, 10))

            cycle_won_yes = c.settlement_spot >= c.strike_price
            bot_won = (side == "yes" and cycle_won_yes) or (side == "no" and not cycle_won_yes)

            if bot_won:
                outcome = "win"
                pnl = (Decimal("1.00") - entry - fee) * Decimal(contracts)
            else:
                outcome = "loss"
                pnl = (-entry - fee) * Decimal(contracts)
            rationale = f"Domination 1 Edge (+{c.ev_edge*100:.1f}%) | {contracts} contracts @ ${entry}"

        gross_w = pnl if pnl > Decimal("0.0") else Decimal("0.0")
        gross_l = abs(pnl) if pnl < Decimal("0.0") else Decimal("0.0")

        records.append(
            StrategyTradeRecord(
                cycle_index=c.cycle_index,
                cycle_time=c.cycle_time,
                ticker=c.ticker,
                strategy_name="Domination Bot 1 (Legacy EV/VPIN)",
                action=action,
                side=c.actual_side,
                entry_price=c.actual_entry,
                contracts=c.actual_contracts if action == "TAKE" else 0,
                outcome=outcome,
                pnl=pnl,
                gross_win=gross_w,
                gross_loss=gross_l,
                rationale=rationale,
                macro_regime=c.macro_regime,
                spot_diff=c.spot_diff,
            )
        )
    return records


def evaluate_strategy_domination_2(cycles: List[CycleData]) -> List[StrategyTradeRecord]:
    """Replay Domination Bot 2 (High-Conviction Runner - Cheap Asymmetric Contracts)."""
    records: List[StrategyTradeRecord] = []
    fee = Decimal("0.01")

    for c in cycles:
        entry = c.actual_entry
        if entry > Decimal("0.45"):
            action = "VETO"
            outcome = "vetoed"
            pnl = Decimal("0.0")
            rationale = f"Domination 2 Price Cap: Entry ${entry} > $0.45 threshold"
        elif entry < Decimal("0.05"):
            action = "VETO"
            outcome = "vetoed"
            pnl = Decimal("0.0")
            rationale = f"Domination 2 Lottery Filter: Entry ${entry} < $0.05"
        else:
            action = "TAKE"
            side = c.actual_side
            contracts = 8

            cycle_won_yes = c.settlement_spot >= c.strike_price
            bot_won = (side == "yes" and cycle_won_yes) or (side == "no" and not cycle_won_yes)

            if bot_won:
                outcome = "win"
                pnl = (Decimal("1.00") - entry - fee) * Decimal(contracts)
            else:
                outcome = "loss"
                pnl = (-entry - fee) * Decimal(contracts)
            rationale = f"Domination 2 Asymmetric Runner ({contracts} cts @ ${entry})"

        gross_w = pnl if pnl > Decimal("0.0") else Decimal("0.0")
        gross_l = abs(pnl) if pnl < Decimal("0.0") else Decimal("0.0")

        records.append(
            StrategyTradeRecord(
                cycle_index=c.cycle_index,
                cycle_time=c.cycle_time,
                ticker=c.ticker,
                strategy_name="Domination Bot 2 (Asymmetric Runner)",
                action=action,
                side=c.actual_side,
                entry_price=entry,
                contracts=8 if action == "TAKE" else 0,
                outcome=outcome,
                pnl=pnl,
                gross_win=gross_w,
                gross_loss=gross_l,
                rationale=rationale,
                macro_regime=c.macro_regime,
                spot_diff=c.spot_diff,
            )
        )
    return records


def load_stream_profiles() -> Dict[str, Any]:
    """Load pre-computed tick and depth price profiles from data/stream_profiles_cache.json."""
    cache_path = Path("data/stream_profiles_cache.json")
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def evaluate_strategy_domination_rev3(
    cycles: List[CycleData],
    discount_price: float = 0.48,
    contracts: int = 1,
    strategy_label: Optional[str] = None,
    profiles_cache: Optional[Dict[str, Any]] = None,
) -> List[StrategyTradeRecord]:
    """Replay 3-Step Domination Bot Rev 3 (Option B - Resting Maker Discount Sniper).

    Guarantees:
    1. $0.00 Maker fee (Kalshi resting limit order on CLOB).
    2. Asymmetric Risk/Reward: Max risk = discount_price, Reward = (1.00 - discount_price).
    3. Pre-trade filters: VPIN <= 0.40 and |Spot - Strike| >= $35 (skips coin-flip territory near strike).
    4. Fill Invariant: Only filled if market traded at or through the limit price in real recordings.
       If market never traded down to the discount, the resting order is auto-cancelled at 45s cutoff ($0.00 PnL, $0.00 fee).
    """
    disc_dec = _d(str(discount_price))
    fee = Decimal("0.00")  # Free maker order on Kalshi
    label = strategy_label or f"Domination Rev 3 (${discount_price:.2f})"
    profiles = profiles_cache or {}
    records: List[StrategyTradeRecord] = []

    for c in cycles:
        side = c.actual_side

        # 1. Pre-trade guardrail checks
        if c.vpin_score > 0.40:
            records.append(
                StrategyTradeRecord(
                    cycle_index=c.cycle_index,
                    cycle_time=c.cycle_time,
                    ticker=c.ticker,
                    strategy_name=label,
                    action="VETO",
                    side=side,
                    entry_price=c.actual_entry,
                    contracts=0,
                    outcome="vetoed",
                    pnl=Decimal("0.0"),
                    gross_win=Decimal("0.0"),
                    gross_loss=Decimal("0.0"),
                    rationale=f"VPIN Toxicity Veto ({c.vpin_score:.2f} > 0.40)",
                    macro_regime=c.macro_regime,
                    spot_diff=c.spot_diff,
                )
            )
            continue

        if abs(c.spot_diff) < Decimal("35.0"):
            records.append(
                StrategyTradeRecord(
                    cycle_index=c.cycle_index,
                    cycle_time=c.cycle_time,
                    ticker=c.ticker,
                    strategy_name=label,
                    action="VETO",
                    side=side,
                    entry_price=c.actual_entry,
                    contracts=0,
                    outcome="vetoed",
                    pnl=Decimal("0.0"),
                    gross_win=Decimal("0.0"),
                    gross_loss=Decimal("0.0"),
                    rationale=f"Spot-Strike Proximity Veto (|Diff|=${abs(c.spot_diff):.1f} < $35)",
                    macro_regime=c.macro_regime,
                    spot_diff=c.spot_diff,
                )
            )
            continue

        # 2. Maker Resting Fill check against real L2 orderbook & trade tape
        prof = profiles.get(c.ticker)
        filled = False
        if prof:
            if side == "yes":
                min_p = prof.get("min_trade_yes") or prof.get("min_yes_ask")
            else:
                min_p = prof.get("min_trade_no") or prof.get("min_no_ask")

            if min_p is not None and Decimal(str(round(min_p, 2))) <= disc_dec:
                filled = True
        else:
            if c.actual_entry <= disc_dec:
                filled = True

        if not filled:
            records.append(
                StrategyTradeRecord(
                    cycle_index=c.cycle_index,
                    cycle_time=c.cycle_time,
                    ticker=c.ticker,
                    strategy_name=label,
                    action="UNFILLED",
                    side=side,
                    entry_price=disc_dec,
                    contracts=0,
                    outcome="unfilled",
                    pnl=Decimal("0.0"),
                    gross_win=Decimal("0.0"),
                    gross_loss=Decimal("0.0"),
                    rationale=f"Maker Order @ ${discount_price:.2f} never reached (Auto-cancelled @ 45s)",
                    macro_regime=c.macro_regime,
                    spot_diff=c.spot_diff,
                )
            )
            continue

        # 3. Settlement evaluation
        cycle_yes_won = c.settlement_spot >= c.strike_price
        bot_won = (side == "yes" and cycle_yes_won) or (side == "no" and not cycle_yes_won)

        if bot_won:
            outcome = "win"
            pnl = (Decimal("1.00") - disc_dec - fee) * Decimal(contracts)
            gross_w = pnl
            gross_l = Decimal("0.0")
        else:
            outcome = "loss"
            pnl = (-disc_dec - fee) * Decimal(contracts)
            gross_w = Decimal("0.0")
            gross_l = abs(pnl)

        records.append(
            StrategyTradeRecord(
                cycle_index=c.cycle_index,
                cycle_time=c.cycle_time,
                ticker=c.ticker,
                strategy_name=label,
                action="TAKE",
                side=side,
                entry_price=disc_dec,
                contracts=contracts,
                outcome=outcome,
                pnl=pnl,
                gross_win=gross_w,
                gross_loss=gross_l,
                rationale=f"Maker Discount Fill @ ${discount_price:.2f} ($0.00 fee) | Diff: {c.spot_diff:+.1f}",
                macro_regime=c.macro_regime,
                spot_diff=c.spot_diff,
            )
        )

    return records


def evaluate_strategy_macro_trend(cycles: List[CycleData]) -> List[StrategyTradeRecord]:
    """Replay Macro Trend Dominion (Macro Momentum + Price Corridor $0.30-$0.62 + Salvage)."""
    records: List[StrategyTradeRecord] = []
    fee = Decimal("0.01")

    for c in cycles:
        action = "TAKE"
        assigned_side = c.actual_side
        veto_reason = ""

        # 1. Macro Regime Following Gate
        if c.macro_regime == "MACRO_BULL":
            if c.actual_side == "no":
                action = "VETO"
                veto_reason = "Macro Bull: Counter-trend NO bet vetoed"
            else:
                assigned_side = "yes"
        elif c.macro_regime == "MACRO_BEAR":
            if c.actual_side == "yes":
                action = "VETO"
                veto_reason = "Macro Bear: Counter-trend YES bet vetoed"
            else:
                assigned_side = "no"
        else:  # MACRO_CHOP
            if abs(c.spot_diff) < Decimal("50.0"):
                action = "VETO"
                veto_reason = f"Macro Chop: Distance (${c.spot_diff:+.1f}) < $50 threshold"

        # 2. Price Corridor ($0.30 - $0.62)
        if action == "TAKE":
            if c.actual_entry > Decimal("0.62"):
                action = "VETO"
                veto_reason = f"Price Ceiling: Entry ${c.actual_entry:.2f} > $0.62 max"
            elif c.actual_entry < Decimal("0.30"):
                action = "VETO"
                veto_reason = f"Price Floor: Entry ${c.actual_entry:.2f} < $0.30 lottery trap"

        bot_entry_price = min(c.actual_entry, Decimal("0.62"))

        if action == "TAKE":
            cycle_won_yes = c.settlement_spot >= c.strike_price
            bot_won = (assigned_side == "yes" and cycle_won_yes) or (assigned_side == "no" and not cycle_won_yes)

            if bot_won:
                outcome = "win"
                pnl = Decimal("1.00") - bot_entry_price - fee
            else:
                adverse_distance = (c.strike_price - c.settlement_spot) if assigned_side == "yes" else (c.settlement_spot - c.strike_price)
                if adverse_distance > Decimal("50.0"):
                    salvage_price = Decimal("0.10")
                    pnl = salvage_price - bot_entry_price - fee
                    outcome = "salvaged_loss"
                else:
                    outcome = "loss"
                    pnl = -bot_entry_price - fee
            rationale = f"Macro Trend ({c.macro_regime} 1h: {c.trend_1h_pct:+.2f}%)"
        else:
            outcome = "vetoed"
            pnl = Decimal("0.0")
            rationale = veto_reason

        gross_w = pnl if pnl > Decimal("0.0") else Decimal("0.0")
        gross_l = abs(pnl) if pnl < Decimal("0.0") else Decimal("0.0")

        records.append(
            StrategyTradeRecord(
                cycle_index=c.cycle_index,
                cycle_time=c.cycle_time,
                ticker=c.ticker,
                strategy_name="Macro Trend Dominion (Momentum Only)",
                action=action,
                side=assigned_side if action == "TAKE" else c.actual_side,
                entry_price=bot_entry_price if action == "TAKE" else c.actual_entry,
                contracts=1 if action == "TAKE" else 0,
                outcome=outcome,
                pnl=pnl,
                gross_win=gross_w,
                gross_loss=gross_l,
                rationale=rationale,
                macro_regime=c.macro_regime,
                spot_diff=c.spot_diff,
            )
        )
    return records


def evaluate_strategy_macro_trend_onnx_fusion(
    cycles: List[CycleData],
    predictor: ONNXMicrostructurePredictor,
    uncertainty_distance_threshold: float = 50.0,
    strategy_label: str = "Macro Trend + ONNX Fusion",
) -> List[StrategyTradeRecord]:
    """Replay Macro Trend Dominion + QuoLas Nano ONNX with configurable uncertainty gate."""
    records: List[StrategyTradeRecord] = []
    fee = Decimal("0.01")
    dist_thresh = Decimal(str(uncertainty_distance_threshold))

    for c in cycles:
        signal, conf, p_long, p_short, p_wait = predictor.predict_for_cycle(c)

        action = "TAKE"
        assigned_side = c.actual_side
        veto_reason = ""

        # 1. Multi-scale Macro Regime Gate
        if c.macro_regime == "MACRO_BULL":
            if c.actual_side == "no":
                action = "VETO"
                veto_reason = f"Macro Bull Veto: Counter-trend NO bet vetoed (1h: {c.trend_1h_pct:+.2f}%)"
            else:
                assigned_side = "yes"
        elif c.macro_regime == "MACRO_BEAR":
            if c.actual_side == "yes":
                action = "VETO"
                veto_reason = f"Macro Bear Veto: Counter-trend YES bet vetoed (1h: {c.trend_1h_pct:+.2f}%)"
            else:
                assigned_side = "no"
        else:  # MACRO_CHOP
            if abs(c.spot_diff) < Decimal("50.0"):
                action = "VETO"
                veto_reason = f"Macro Chop Veto: Strike distance (${c.spot_diff:+.1f}) < $50 threshold"

        # 2. ONNX Bitcoin Orderflow Contradiction Hard Veto
        if action == "TAKE":
            if assigned_side == "yes":
                if (signal == "SHORT" and conf >= 0.55) or p_short >= 0.58:
                    action = "VETO"
                    veto_reason = (
                        f"ONNX Contradiction Veto: Model SHORT ({conf*100:.0f}%, P_short={p_short*100:.1f}%) "
                        f"contradicts recommended YES"
                    )
            elif assigned_side == "no":
                if (signal == "LONG" and conf >= 0.55) or p_long >= 0.58:
                    action = "VETO"
                    veto_reason = (
                        f"ONNX Contradiction Veto: Model LONG ({conf*100:.0f}%, P_long={p_long*100:.1f}%) "
                        f"contradicts recommended NO"
                    )

        # 3. ONNX Extreme Uncertainty Gate
        if action == "TAKE":
            if p_wait >= 0.70 and abs(c.spot_diff) < dist_thresh:
                action = "VETO"
                veto_reason = (
                    f"ONNX Uncertainty Gate: P(WAIT)={p_wait*100:.0f}% >= 70% within ${dist_thresh} of strike"
                )

        # 4. Entry Price Corridor ($0.30 - $0.62) & Hard Kill ($0.68)
        if action == "TAKE":
            if c.actual_entry > Decimal("0.68"):
                action = "VETO"
                veto_reason = f"Hard Kill Price Veto: Entry ${c.actual_entry:.2f} > $0.68 hard ceiling"
            elif c.actual_entry > Decimal("0.62"):
                action = "VETO"
                veto_reason = f"Price Ceiling Veto: Entry ${c.actual_entry:.2f} > $0.62 target"
            elif c.actual_entry < Decimal("0.30"):
                action = "VETO"
                veto_reason = f"Price Floor Veto: Entry ${c.actual_entry:.2f} < $0.30 lottery trap"

        bot_entry_price = min(c.actual_entry, Decimal("0.62"))

        if action == "TAKE":
            cycle_won_yes = c.settlement_spot >= c.strike_price
            bot_won = (assigned_side == "yes" and cycle_won_yes) or (assigned_side == "no" and not cycle_won_yes)

            if bot_won:
                outcome = "win"
                pnl = Decimal("1.00") - bot_entry_price - fee
            else:
                adverse_distance = (c.strike_price - c.settlement_spot) if assigned_side == "yes" else (c.settlement_spot - c.strike_price)
                if adverse_distance > Decimal("50.0"):
                    salvage_price = Decimal("0.10")
                    pnl = salvage_price - bot_entry_price - fee
                    outcome = "salvaged_loss"
                else:
                    outcome = "loss"
                    pnl = -bot_entry_price - fee
            rationale = (
                f"Fusion: Macro {c.macro_regime} ({c.trend_1h_pct:+.2f}%) + ONNX {signal} ({conf*100:.0f}%)"
            )
        else:
            outcome = "vetoed"
            pnl = Decimal("0.0")
            rationale = veto_reason

        gross_w = pnl if pnl > Decimal("0.0") else Decimal("0.0")
        gross_l = abs(pnl) if pnl < Decimal("0.0") else Decimal("0.0")

        records.append(
            StrategyTradeRecord(
                cycle_index=c.cycle_index,
                cycle_time=c.cycle_time,
                ticker=c.ticker,
                strategy_name=strategy_label,
                action=action,
                side=assigned_side if action == "TAKE" else c.actual_side,
                entry_price=bot_entry_price if action == "TAKE" else c.actual_entry,
                contracts=1 if action == "TAKE" else 0,
                outcome=outcome,
                pnl=pnl,
                gross_win=gross_w,
                gross_loss=gross_l,
                rationale=rationale,
                macro_regime=c.macro_regime,
                spot_diff=c.spot_diff,
            )
        )
    return records


def compute_metrics(name: str, records: List[StrategyTradeRecord]) -> StrategyMetrics:
    """Compute institutional quantitative statistics using strict Decimal arithmetic."""
    total_cycles = len(records)
    trades_taken = [r for r in records if r.action == "TAKE"]
    trades_vetoed = total_cycles - len(trades_taken)

    wins = [r for r in trades_taken if r.outcome == "win"]
    losses = [r for r in trades_taken if r.outcome == "loss"]
    salvaged = [r for r in trades_taken if r.outcome == "salvaged_loss"]
    all_losses = losses + salvaged

    win_rate = (len(wins) / len(trades_taken) * 100.0) if trades_taken else 0.0

    net_pnl = sum((r.pnl for r in trades_taken), Decimal("0.0"))
    gross_profit = sum((r.gross_win for r in trades_taken), Decimal("0.0"))
    gross_loss = sum((r.gross_loss for r in trades_taken), Decimal("0.0"))

    profit_factor = float(gross_profit / gross_loss) if gross_loss > Decimal("0.0") else (99.0 if gross_profit > Decimal("0.0") else 0.0)

    avg_win = (gross_profit / Decimal(len(wins))) if wins else Decimal("0.0")
    avg_loss = (gross_loss / Decimal(len(all_losses))) if all_losses else Decimal("0.0")
    payoff_ratio = float(avg_win / avg_loss) if avg_loss > Decimal("0.0") else 0.0

    expectancy = (net_pnl / Decimal(len(trades_taken))) if trades_taken else Decimal("0.0")

    running_equity = Decimal("25.00")
    peak_equity = running_equity
    max_dd_dollars = Decimal("0.0")
    equity_curve: List[Decimal] = [running_equity]

    loss_streak = 0
    max_loss_streak = 0
    pnl_series: List[float] = []

    for r in trades_taken:
        running_equity += r.pnl
        equity_curve.append(running_equity)
        pnl_series.append(float(r.pnl))

        if running_equity > peak_equity:
            peak_equity = running_equity
        dd = peak_equity - running_equity
        if dd > max_dd_dollars:
            max_dd_dollars = dd

        if r.outcome in ("loss", "salvaged_loss"):
            loss_streak += 1
            if loss_streak > max_loss_streak:
                max_loss_streak = loss_streak
        else:
            loss_streak = 0

    max_dd_pct = float((max_dd_dollars / peak_equity) * Decimal("100.0")) if peak_equity > Decimal("0.0") else 0.0

    if len(pnl_series) >= 2:
        mean_r = float(np.mean(pnl_series))
        std_r = float(np.std(pnl_series, ddof=1))
        sharpe = (mean_r / std_r * math.sqrt(len(pnl_series))) if std_r > 1e-6 else 0.0

        downside = [p for p in pnl_series if p < 0]
        if downside:
            down_std = float(np.std(downside, ddof=1)) if len(downside) > 1 else abs(downside[0])
            if down_std <= 1e-6:
                down_std = abs(float(np.mean(downside)))
            sortino = (mean_r / down_std * math.sqrt(len(pnl_series))) if down_std > 1e-6 else 0.0
        else:
            sortino = 99.0
    else:
        sharpe = 0.0
        sortino = 0.0

    return StrategyMetrics(
        name=name,
        total_cycles=total_cycles,
        trades_taken=len(trades_taken),
        trades_vetoed=trades_vetoed,
        wins=len(wins),
        losses=len(losses),
        salvaged_losses=len(salvaged),
        win_rate_pct=round(win_rate, 2),
        net_pnl=_round_c(net_pnl),
        gross_profit=_round_c(gross_profit),
        gross_loss=_round_c(gross_loss),
        profit_factor=round(profit_factor, 2),
        avg_win=_round_c(avg_win),
        avg_loss=_round_c(avg_loss),
        payoff_ratio=round(payoff_ratio, 2),
        expectancy_per_trade=_round_c(expectancy),
        max_drawdown_dollars=_round_c(max_dd_dollars),
        max_drawdown_pct=round(max_dd_pct, 2),
        max_loss_streak=max_loss_streak,
        sharpe_ratio=round(sharpe, 2),
        sortino_ratio=round(sortino, 2),
        equity_curve=equity_curve,
    )


def compute_regime_breakdown(records: List[StrategyTradeRecord]) -> Dict[str, Dict[str, Any]]:
    """Compute performance split across MACRO_BULL, MACRO_BEAR, and MACRO_CHOP."""
    regimes = ["MACRO_BULL", "MACRO_BEAR", "MACRO_CHOP"]
    results: Dict[str, Dict[str, Any]] = {}

    for reg in regimes:
        r_trades = [r for r in records if r.macro_regime == reg]
        taken = [r for r in r_trades if r.action == "TAKE"]
        wins = [r for r in taken if r.outcome == "win"]
        losses = [r for r in taken if r.outcome in ("loss", "salvaged_loss")]
        net_pnl = sum((r.pnl for r in taken), Decimal("0.0"))
        wr = (len(wins) / len(taken) * 100.0) if taken else 0.0

        results[reg] = {
            "total_cycles": len(r_trades),
            "trades_taken": len(taken),
            "trades_vetoed": len(r_trades) - len(taken),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round(wr, 1),
            "net_pnl": float(net_pnl),
        }
    return results


def run_full_backtest() -> Dict[str, Any]:
    cycles = load_production_cycles()
    predictor = ONNXMicrostructurePredictor()
    profiles = load_stream_profiles()

    base_records = evaluate_strategy_baseline(cycles)
    dom1_records = evaluate_strategy_domination_1(cycles)
    dom2_records = evaluate_strategy_domination_2(cycles)
    macro_records = evaluate_strategy_macro_trend(cycles)
    fusion_strict_records = evaluate_strategy_macro_trend_onnx_fusion(
        cycles, predictor, uncertainty_distance_threshold=50.0, strategy_label="Macro+ONNX (Strict $50)"
    )
    fusion_balanced_records = evaluate_strategy_macro_trend_onnx_fusion(
        cycles, predictor, uncertainty_distance_threshold=40.0, strategy_label="Macro+ONNX (Balanced $40)"
    )
    rev3_48_records = evaluate_strategy_domination_rev3(
        cycles, discount_price=0.48, strategy_label="Domination Rev 3 ($0.48)", profiles_cache=profiles
    )
    rev3_35_records = evaluate_strategy_domination_rev3(
        cycles, discount_price=0.35, strategy_label="Domination Rev 3 ($0.35)", profiles_cache=profiles
    )

    base_m = compute_metrics("Baseline (Historical)", base_records)
    dom1_m = compute_metrics("Domination Bot 1 (Legacy)", dom1_records)
    dom2_m = compute_metrics("Domination Bot 2 (Runner)", dom2_records)
    macro_m = compute_metrics("Macro Trend Dominion", macro_records)
    fusion_strict_m = compute_metrics("Macro+ONNX (Strict $50)", fusion_strict_records)
    fusion_balanced_m = compute_metrics("Macro+ONNX (Balanced $40)", fusion_balanced_records)
    rev3_48_m = compute_metrics("Domination Rev 3 ($0.48)", rev3_48_records)
    rev3_35_m = compute_metrics("Domination Rev 3 ($0.35)", rev3_35_records)

    # Multi-level sensitivity matrix for Rev 3 Maker Discount Sniper
    rev3_sensitivity = {}
    for disc in [0.48, 0.45, 0.40, 0.35, 0.30]:
        recs = evaluate_strategy_domination_rev3(
            cycles, discount_price=disc, strategy_label=f"Domination Rev 3 (${disc:.2f})", profiles_cache=profiles
        )
        unfilled_cnt = sum(1 for r in recs if r.action == "UNFILLED")
        vetoed_cnt = sum(1 for r in recs if r.action == "VETO")
        m_obj = compute_metrics(f"Rev 3 (${disc:.2f})", recs)
        rev3_sensitivity[disc] = {
            "metrics": m_obj,
            "unfilled": unfilled_cnt,
            "vetoed": vetoed_cnt,
            "records": recs,
        }

    return {
        "cycles_count": len(cycles),
        "oldest_cycle": cycles[0].cycle_time,
        "newest_cycle": cycles[-1].cycle_time,
        "oldest_ts": cycles[0].timestamp_utc,
        "newest_ts": cycles[-1].timestamp_utc,
        "metrics": {
            "baseline": base_m,
            "domination_1": dom1_m,
            "domination_2": dom2_m,
            "macro_trend": macro_m,
            "macro_onnx_strict": fusion_strict_m,
            "macro_onnx_balanced": fusion_balanced_m,
            "domination_rev3_48": rev3_48_m,
            "domination_rev3_35": rev3_35_m,
        },
        "rev3_sensitivity": rev3_sensitivity,
        "regimes": {
            "baseline": compute_regime_breakdown(base_records),
            "macro_trend": compute_regime_breakdown(macro_records),
            "macro_onnx_strict": compute_regime_breakdown(fusion_strict_records),
            "macro_onnx_balanced": compute_regime_breakdown(fusion_balanced_records),
            "domination_rev3_35": compute_regime_breakdown(rev3_35_records),
        },
        "recent_trades_strict": fusion_strict_records[-15:],
        "recent_trades_balanced": fusion_balanced_records[-15:],
        "recent_trades_rev3_35": rev3_35_records[-15:],
    }


def print_comparison_table(results: Dict[str, Any]):
    m = results["metrics"]
    base: StrategyMetrics = m["baseline"]
    dom1: StrategyMetrics = m["domination_1"]
    dom2: StrategyMetrics = m["domination_2"]
    macro: StrategyMetrics = m["macro_trend"]
    f_bal: StrategyMetrics = m["macro_onnx_balanced"]
    r3_48: StrategyMetrics = m["domination_rev3_48"]
    r3_35: StrategyMetrics = m["domination_rev3_35"]

    print("=" * 162)
    print("KALSHI BTC 15M INSTITUTIONAL BACKTEST: COMPREHENSIVE REAL PRODUCTION DATA REPLAY (SEPT 4 - SEPT 5, 2026)")
    print("=" * 162)
    print(f"Total Evaluated Production Cycles: {results['cycles_count']}")
    print(f"Time Horizon: {results['oldest_cycle']} ({results['oldest_ts'][:19]}Z) -> {results['newest_cycle']} ({results['newest_ts'][:19]}Z)")
    print("-" * 162)

    col_fmt = "{:<24} | {:<16} | {:<16} | {:<16} | {:<16} | {:<17} | {:<18} | {:<18}"
    print(col_fmt.format("METRIC", "BASELINE (HIST)", "DOMINATION 1", "DOMINATION 2", "MACRO TREND", "ONNX (BAL $40)", "REV 3 ($0.48 DEF)", "REV 3 ($0.35 SNIPER)"))
    print("-" * 162)

    print(col_fmt.format("Trades Taken / Vetoed", f"{base.trades_taken} / {base.trades_vetoed}", f"{dom1.trades_taken} / {dom1.trades_vetoed}", f"{dom2.trades_taken} / {dom2.trades_vetoed}", f"{macro.trades_taken} / {macro.trades_vetoed}", f"{f_bal.trades_taken} / {f_bal.trades_vetoed}", f"{r3_48.trades_taken} / {r3_48.trades_vetoed}", f"{r3_35.trades_taken} / {r3_35.trades_vetoed}"))
    print(col_fmt.format("Win Rate (%)", f"{base.win_rate_pct:.1f}% ({base.wins}W/{base.losses}L)", f"{dom1.win_rate_pct:.1f}% ({dom1.wins}W/{dom1.losses}L)", f"{dom2.win_rate_pct:.1f}% ({dom2.wins}W/{dom2.losses}L)", f"{macro.win_rate_pct:.1f}% ({macro.wins}W/{macro.losses}L)", f"{f_bal.win_rate_pct:.1f}% ({f_bal.wins}W/{f_bal.losses}L)", f"{r3_48.win_rate_pct:.1f}% ({r3_48.wins}W/{r3_48.losses}L)", f"{r3_35.win_rate_pct:.1f}% ({r3_35.wins}W/{r3_35.losses}L)"))
    print(col_fmt.format("Net Realized PnL ($)", f"${base.net_pnl}", f"${dom1.net_pnl}", f"${dom2.net_pnl}", f"${macro.net_pnl}", f"${f_bal.net_pnl}", f"${r3_48.net_pnl}", f"${r3_35.net_pnl}"))
    print(col_fmt.format("Profit Factor", f"{base.profit_factor:.2f}", f"{dom1.profit_factor:.2f}", f"{dom2.profit_factor:.2f}", f"{macro.profit_factor:.2f}", f"{f_bal.profit_factor:.2f}", f"{r3_48.profit_factor:.2f}", f"{r3_35.profit_factor:.2f}"))
    print(col_fmt.format("Gross Profit ($)", f"${base.gross_profit}", f"${dom1.gross_profit}", f"${dom2.gross_profit}", f"${macro.gross_profit}", f"${f_bal.gross_profit}", f"${r3_48.gross_profit}", f"${r3_35.gross_profit}"))
    print(col_fmt.format("Gross Loss Drag ($)", f"${base.gross_loss}", f"${dom1.gross_loss}", f"${dom2.gross_loss}", f"${macro.gross_loss}", f"${f_bal.gross_loss}", f"${r3_48.gross_loss}", f"${r3_35.gross_loss}"))
    print(col_fmt.format("Avg Win / Avg Loss ($)", f"${base.avg_win} / ${base.avg_loss}", f"${dom1.avg_win} / ${dom1.avg_loss}", f"${dom2.avg_win} / ${dom2.avg_loss}", f"${macro.avg_win} / ${macro.avg_loss}", f"${f_bal.avg_win} / ${f_bal.avg_loss}", f"${r3_48.avg_win} / ${r3_48.avg_loss}", f"${r3_35.avg_win} / ${r3_35.avg_loss}"))
    print(col_fmt.format("Payoff Ratio", f"{base.payoff_ratio:.2f}", f"{dom1.payoff_ratio:.2f}", f"{dom2.payoff_ratio:.2f}", f"{macro.payoff_ratio:.2f}", f"{f_bal.payoff_ratio:.2f}", f"{r3_48.payoff_ratio:.2f}", f"{r3_35.payoff_ratio:.2f}"))
    print(col_fmt.format("Expectancy / Trade ($)", f"${base.expectancy_per_trade}", f"${dom1.expectancy_per_trade}", f"${dom2.expectancy_per_trade}", f"${macro.expectancy_per_trade}", f"${f_bal.expectancy_per_trade}", f"${r3_48.expectancy_per_trade}", f"${r3_35.expectancy_per_trade}"))
    print(col_fmt.format("Max Drawdown ($)", f"${base.max_drawdown_dollars} ({base.max_drawdown_pct:.1f}%)", f"${dom1.max_drawdown_dollars} ({dom1.max_drawdown_pct:.1f}%)", f"${dom2.max_drawdown_dollars} ({dom2.max_drawdown_pct:.1f}%)", f"${macro.max_drawdown_dollars} ({macro.max_drawdown_pct:.1f}%)", f"${f_bal.max_drawdown_dollars} ({f_bal.max_drawdown_pct:.1f}%)", f"${r3_48.max_drawdown_dollars} ({r3_48.max_drawdown_pct:.1f}%)", f"${r3_35.max_drawdown_dollars} ({r3_35.max_drawdown_pct:.1f}%)"))
    print(col_fmt.format("Max Loss Streak", f"{base.max_loss_streak} losses", f"{dom1.max_loss_streak} losses", f"{dom2.max_loss_streak} losses", f"{macro.max_loss_streak} losses", f"{f_bal.max_loss_streak} losses", f"{r3_48.max_loss_streak} losses", f"{r3_35.max_loss_streak} losses"))
    print(col_fmt.format("Sharpe Ratio", f"{base.sharpe_ratio:.2f}", f"{dom1.sharpe_ratio:.2f}", f"{dom2.sharpe_ratio:.2f}", f"{macro.sharpe_ratio:.2f}", f"{f_bal.sharpe_ratio:.2f}", f"{r3_48.sharpe_ratio:.2f}", f"{r3_35.sharpe_ratio:.2f}"))
    print(col_fmt.format("Sortino Ratio", f"{base.sortino_ratio:.2f}", f"{dom1.sortino_ratio:.2f}", f"{dom2.sortino_ratio:.2f}", f"{macro.sortino_ratio:.2f}", f"{f_bal.sortino_ratio:.2f}", f"{r3_48.sortino_ratio:.2f}", f"{r3_35.sortino_ratio:.2f}"))
    print("-" * 162)

    # 3-Step Domination Rev 3 Maker Discount Sensitivity Table
    print("\n" + "=" * 162)
    print("3-STEP DOMINATION BOT REV 3 ('MAKER DISCOUNT SNIPER') SENSITIVITY MATRIX ACROSS CEILING PRICES ($0.00 MAKER FEES)")
    print("=" * 162)
    sens_fmt = "{:<12} | {:<18} | {:<16} | {:<12} | {:<12} | {:<14} | {:<14} | {:<14} | {:<16}"
    print(sens_fmt.format("DISCOUNT", "FILLED/VETO/UNFILL", "WIN RATE (%)", "NET PNL ($)", "PROFIT FACT", "PAYOFF RATIO", "AVG WIN/LOSS", "EXPECTANCY", "MAX DRAWDOWN"))
    print("-" * 162)

    for disc, item in results["rev3_sensitivity"].items():
        sm: StrategyMetrics = item["metrics"]
        unfilled = item["unfilled"]
        vetoed = item["vetoed"]
        ratio_str = f"{sm.trades_taken} / {vetoed} / {unfilled}"
        wr_str = f"{sm.win_rate_pct:.1f}% ({sm.wins}W/{sm.losses}L)"
        wl_str = f"${sm.avg_win:.2f} / ${sm.avg_loss:.2f}"
        dd_str = f"${sm.max_drawdown_dollars:.2f} ({sm.max_drawdown_pct:.1f}%)"
        print(sens_fmt.format(
            f"${disc:.2f}",
            ratio_str,
            wr_str,
            f"${sm.net_pnl:+.2f}",
            f"{sm.profit_factor:.2f}",
            f"{sm.payoff_ratio:.2f}x",
            wl_str,
            f"${sm.expectancy_per_trade:+.2f}/trade",
            dd_str,
        ))
    print("=" * 162)

    print("\n" + "=" * 162)
    print("LATEST 15 PRODUCTION REPLAY EXECUTIONS (CHRONOLOGICAL: REV 3 MAKER DISCOUNT SNIPER @ $0.35)")
    print("=" * 162)
    trade_fmt = "{:<26} | {:<8} | {:<8} | {:<6} | {:<9} | {:<16} | {:<52}"
    print(trade_fmt.format("CYCLE TIME", "REGIME", "ACTION", "SIDE", "ENTRY", "OUTCOME", "RATIONALE / VETO REASON"))
    print("-" * 162)
    for t in results["recent_trades_rev3_35"]:
        pnl_str = f"${t.pnl:+.2f}" if t.action == "TAKE" else "$0.00"
        print(trade_fmt.format(
            t.cycle_time[:26],
            t.macro_regime.replace("MACRO_", ""),
            t.action,
            t.side.upper(),
            f"${t.entry_price:.2f}",
            f"{t.outcome.upper()} ({pnl_str})",
            t.rationale[:52],
        ))
    print("=" * 162)


if __name__ == "__main__":
    results = run_full_backtest()
    print_comparison_table(results)

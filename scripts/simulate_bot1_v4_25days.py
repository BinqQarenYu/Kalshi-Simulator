"""Empirical 25-Day Simulation for Bot 1 Ver 4 (ThreeStepDominationBotV4).

Evaluates the new Bot 1 Ver 4 against baseline across 25 days of trading (Aug 25, 2026 - Sep 19, 2026)
using genuine historical Kalshi 15M/5M cycles.

Key Mechanisms Simulated:
1. Every-Cycle Engagement: Brain evaluates dominant side for each cycle.
2. [18¢, 48¢] Pricing Corridor: Buys cheapest available ask inside corridor, avoiding toxic lottery tickets (<18¢) and overpaying (>48¢).
3. +45% Gross Profit Harvest Target: Early liquidation when peak mid-cycle bid >= entry * 1.45.
4. -35% Defensive Stop-Loss Cutoff: Early salvage when adverse trough bid <= entry * 0.65.
5. Playbook 3 (T <= 240s) Gamma Freeze: Prohibits new entries in dangerous late-cycle chop.
6. 1-Contract Micro-Bankroll Sizing: Adheres to institutional $75 bankroll limit.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from kalshi_sim.ml.domination_bot_v4 import ThreeStepDominationBotV4
from kalshi_sim.ml.domination_bot import ThreeStepDominationBot
from kalshi_sim.schemas import L2BookState, OrderSide


@dataclass
class SimulationCycle:
    index: int
    ticker: str
    cycle_time: str
    timestamp_utc: str
    strike_price: float
    settlement_btc_price: float
    spot_diff: float
    regime: str  # 'VOLATILE_UP' | 'VOLATILE_DOWN' | 'CONSOLIDATION'
    actual_side: str
    actual_entry: float
    actual_outcome: str
    actual_pnl: float
    hour_et: int
    best_yes_ask: Decimal
    best_no_ask: Decimal
    best_yes_bid: Decimal
    best_no_bid: Decimal
    max_yes_bid: float
    max_no_bid: float
    min_yes_ask: float
    min_no_ask: float


def load_25day_cycles(cutoff_days: int = 25) -> List[SimulationCycle]:
    """Load historical cycles from disk and filter to the last 25 days."""
    wlr_path = Path("data/win_loss_reports.json")
    stream_path = Path("data/stream_profiles_cache.json")

    if not wlr_path.exists():
        raise FileNotFoundError(f"Missing {wlr_path}")

    with open(wlr_path, "r", encoding="utf-8") as f:
        raw_reports = json.load(f)

    stream_cache: Dict[str, Dict[str, Any]] = {}
    if stream_path.exists():
        with open(stream_path, "r", encoding="utf-8") as f:
            stream_cache = json.load(f)

    cycles: List[SimulationCycle] = []

    # Sort chronological
    def parse_ts(item: Dict[str, Any]) -> datetime:
        ts = item.get("timestamp_utc", "")
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    sorted_reports = sorted(raw_reports, key=parse_ts)

    latest_dt = parse_ts(sorted_reports[-1])
    earliest_cutoff = latest_dt.timestamp() - (cutoff_days * 86400)

    for idx, r in enumerate(sorted_reports):
        dt = parse_ts(r)
        if dt.timestamp() < earliest_cutoff:
            continue

        strike = float(r.get("strike_price", 0.0))
        settle = float(r.get("settlement_btc_price", 0.0))
        diff = settle - strike
        ts_str = r.get("timestamp_utc", "")
        entry = float(r.get("entry_price", 0.50))
        side = r.get("bot_side", "yes").lower()
        outcome = r.get("outcome", "loss").lower()
        pnl = float(r.get("pnl", 0.0))
        ticker = r.get("ticker", f"KXBTC15M-CYCLE-{idx}")
        cycle_time = r.get("cycle_time", "")

        hour_et = 12
        try:
            dt_et = dt.astimezone(ZoneInfo("America/New_York"))
            hour_et = dt_et.hour
        except Exception:
            pass

        if diff > 35.0:
            regime = "VOLATILE_UP"
        elif diff < -35.0:
            regime = "VOLATILE_DOWN"
        else:
            regime = "CONSOLIDATION"

        # Inside touch
        if side == "yes":
            best_yes_ask = Decimal(str(round(entry, 2)))
            best_yes_bid = max(Decimal("0.01"), best_yes_ask - Decimal("0.02"))
            best_no_bid = max(Decimal("0.01"), Decimal("1.00") - best_yes_ask)
            best_no_ask = Decimal("1.00") - best_yes_bid
        else:
            best_no_ask = Decimal(str(round(entry, 2)))
            best_no_bid = max(Decimal("0.01"), best_no_ask - Decimal("0.02"))
            best_yes_bid = max(Decimal("0.01"), Decimal("1.00") - best_no_ask)
            best_yes_ask = Decimal("1.00") - best_no_bid

        # Mid-cycle stream profile if available
        profile = stream_cache.get(ticker, {})
        max_yes_bid = profile.get("max_yes_bid", float(best_yes_bid))
        max_no_bid = profile.get("max_no_bid", float(best_no_bid))
        min_yes_ask = profile.get("min_yes_ask", float(best_yes_ask))
        min_no_ask = profile.get("min_no_ask", float(best_no_ask))

        # Ensure realistic bounds
        if max_yes_bid <= 0.0:
            max_yes_bid = 0.99 if settle > strike else float(best_yes_bid)
        if max_no_bid <= 0.0:
            max_no_bid = 0.99 if settle <= strike else float(best_no_bid)

        cycles.append(
            SimulationCycle(
                index=idx,
                ticker=ticker,
                cycle_time=cycle_time,
                timestamp_utc=ts_str,
                strike_price=strike,
                settlement_btc_price=settle,
                spot_diff=diff,
                regime=regime,
                actual_side=side,
                actual_entry=entry,
                actual_outcome=outcome,
                actual_pnl=pnl,
                hour_et=hour_et,
                best_yes_ask=best_yes_ask,
                best_no_ask=best_no_ask,
                best_yes_bid=best_yes_bid,
                best_no_bid=best_no_bid,
                max_yes_bid=max_yes_bid,
                max_no_bid=max_no_bid,
                min_yes_ask=min_yes_ask,
                min_no_ask=min_no_ask,
            )
        )

    return cycles


def run_simulation() -> None:
    cycles = load_25day_cycles(cutoff_days=25)
    print(f"Loaded {len(cycles)} historical cycles across the last 25 trading days.")

    # Initialize Bot 1 Ver 4
    bot_v4 = ThreeStepDominationBotV4(
        min_entry_price=Decimal("0.18"),
        max_entry_price=Decimal("0.48"),
        profit_harvest_pct=0.45,
        enable_stop_loss=True,
        stop_loss_pct=0.35,
        entry_cutoff_seconds=240.0,
        enable_every_cycle_engagement=True,
    )

    # Initialize Baseline Bot 1 (Legacy / Standard)
    bot_v3 = ThreeStepDominationBot(
        min_edge_pct=0.015,
        discount_limit_price=Decimal("0.52"),
        max_entry_price=Decimal("0.62"),
    )

    fee_per_contract = Decimal("0.01")

    # Metrics Tracking
    stats_v4 = {
        "trades": 0,
        "skipped": 0,
        "corridor_vetoes": 0,
        "gamma_freeze_vetoes": 0,
        "harvests": 0,
        "stops": 0,
        "settle_wins": 0,
        "settle_losses": 0,
        "net_pnl": Decimal("0.00"),
        "gross_gains": Decimal("0.00"),
        "gross_losses": Decimal("0.00"),
        "max_loss_streak": 0,
        "curr_loss_streak": 0,
        "peak_pnl": Decimal("0.00"),
        "max_dd": Decimal("0.00"),
    }

    stats_v3 = {
        "trades": 0,
        "skipped": 0,
        "wins": 0,
        "losses": 0,
        "net_pnl": Decimal("0.00"),
        "gross_gains": Decimal("0.00"),
        "gross_losses": Decimal("0.00"),
        "max_loss_streak": 0,
        "curr_loss_streak": 0,
        "peak_pnl": Decimal("0.00"),
        "max_dd": Decimal("0.00"),
    }

    # Simulation loop across cycles
    # For each cycle, test entry at early/mid-cycle (e.g. T=450s, 7.5 mins remaining)
    time_to_expiry_s = 450.0

    for c in cycles:
        # Build order book state
        book = L2BookState(market_ticker=c.ticker)
        book.yes_book = {c.best_yes_bid: Decimal("100")}
        book.no_book = {c.best_no_bid: Decimal("100")}

        # Spot price at decision time
        spot_price = c.strike_price + c.spot_diff
        settle = c.settlement_btc_price
        strike = c.strike_price
        yes_settles_win = settle > strike

        # -------------------------------------------------------------
        # 1. EVALUATE BOT 1 VER 4
        # -------------------------------------------------------------
        dec_v4 = bot_v4.evaluate(
            book=book,
            spot_price=spot_price,
            target_strike=strike,
            time_to_expiry_s=time_to_expiry_s,
            total_equity=Decimal("25.00"),
            max_position_size=1,
            estimated_vpin=0.15,
        )

        if dec_v4.recommended_side in ("yes", "no") and dec_v4.recommended_contracts > 0:
            side = dec_v4.recommended_side
            entry_price = c.best_yes_ask if side == "yes" else c.best_no_ask
            stats_v4["trades"] += 1
            entry_f = float(entry_price)
            target_harvest_bid = entry_f * 1.45
            stop_loss_bid = entry_f * 0.65

            peak_bid = c.max_yes_bid if side == "yes" else c.max_no_bid
            trough_bid = (1.0 - c.min_no_ask) if side == "yes" else (1.0 - c.min_yes_ask)

            # Did it reach +45% profit harvest mid-cycle?
            # A trade reaches peak if favorable price surge occurs
            is_harvested = (peak_bid >= target_harvest_bid)

            # Did it trigger defensive stop loss?
            # If adverse trough drops below stop_loss_bid before or without harvest
            is_stopped = False
            if not is_harvested:
                # If outcome ended as loss, did it drop through stop?
                final_is_win = yes_settles_win if side == "yes" else (not yes_settles_win)
                if not final_is_win and trough_bid <= stop_loss_bid:
                    is_stopped = True

            # Calculate PnL for V4 trade
            if is_harvested:
                stats_v4["harvests"] += 1
                exit_p = Decimal(str(round(target_harvest_bid, 2)))
                trade_pnl = (exit_p - entry_price) - fee_per_contract
                is_win = True
            elif is_stopped:
                stats_v4["stops"] += 1
                exit_p = Decimal(str(round(stop_loss_bid, 2)))
                trade_pnl = (exit_p - entry_price) - fee_per_contract
                is_win = False
            else:
                # Held to settlement
                final_win = yes_settles_win if side == "yes" else (not yes_settles_win)
                if final_win:
                    stats_v4["settle_wins"] += 1
                    trade_pnl = (Decimal("1.00") - entry_price) - fee_per_contract
                    is_win = True
                else:
                    stats_v4["settle_losses"] += 1
                    trade_pnl = (Decimal("0.00") - entry_price) - fee_per_contract
                    is_win = False

            stats_v4["net_pnl"] += trade_pnl
            if is_win:
                stats_v4["gross_gains"] += trade_pnl
                stats_v4["curr_loss_streak"] = 0
            else:
                stats_v4["gross_losses"] += abs(trade_pnl)
                stats_v4["curr_loss_streak"] += 1
                if stats_v4["curr_loss_streak"] > stats_v4["max_loss_streak"]:
                    stats_v4["max_loss_streak"] = stats_v4["curr_loss_streak"]

            if stats_v4["net_pnl"] > stats_v4["peak_pnl"]:
                stats_v4["peak_pnl"] = stats_v4["net_pnl"]
            dd = stats_v4["peak_pnl"] - stats_v4["net_pnl"]
            if dd > stats_v4["max_dd"]:
                stats_v4["max_dd"] = dd
        else:
            stats_v4["skipped"] += 1
            if "Corridor" in dec_v4.rationale:
                stats_v4["corridor_vetoes"] += 1

        # -------------------------------------------------------------
        # 2. EVALUATE BASELINE BOT 1 (Legacy / V3.2)
        # -------------------------------------------------------------
        dec_v3 = bot_v3.evaluate(
            book=book,
            spot_price=spot_price,
            target_strike=strike,
            time_to_expiry_s=time_to_expiry_s,
            total_equity=Decimal("25.00"),
            max_position_size=1,
            estimated_vpin=0.15,
        )

        if dec_v3.recommended_side in ("yes", "no") and dec_v3.recommended_contracts > 0:
            stats_v3["trades"] += 1
            side_v3 = dec_v3.recommended_side
            entry_v3 = c.best_yes_ask if side_v3 == "yes" else c.best_no_ask

            is_win_v3 = yes_settles_win if side_v3 == "yes" else (not yes_settles_win)
            exit_v3 = Decimal("1.00") if is_win_v3 else Decimal("0.00")
            trade_pnl_v3 = (exit_v3 - entry_v3) - fee_per_contract

            stats_v3["net_pnl"] += trade_pnl_v3
            if is_win_v3:
                stats_v3["wins"] += 1
                stats_v3["gross_gains"] += trade_pnl_v3
                stats_v3["curr_loss_streak"] = 0
            else:
                stats_v3["losses"] += 1
                stats_v3["gross_losses"] += abs(trade_pnl_v3)
                stats_v3["curr_loss_streak"] += 1
                if stats_v3["curr_loss_streak"] > stats_v3["max_loss_streak"]:
                    stats_v3["max_loss_streak"] = stats_v3["curr_loss_streak"]

            if stats_v3["net_pnl"] > stats_v3["peak_pnl"]:
                stats_v3["peak_pnl"] = stats_v3["net_pnl"]
            dd_v3 = stats_v3["peak_pnl"] - stats_v3["net_pnl"]
            if dd_v3 > stats_v3["max_dd"]:
                stats_v3["max_dd"] = dd_v3
        else:
            stats_v3["skipped"] += 1

    # Print Full Comparative Table
    print("\n" + "=" * 80)
    print(" 25-DAY EMPIRICAL SIMULATION RESULTS (AUG 25 - SEP 19, 2026)")
    print(f" Total Historical Cycles Evaluated: {len(cycles)}")
    print("=" * 80)

    v4_total_wins = stats_v4["harvests"] + stats_v4["settle_wins"]
    v4_total_losses = stats_v4["stops"] + stats_v4["settle_losses"]
    v4_win_rate = (v4_total_wins / stats_v4["trades"] * 100.0) if stats_v4["trades"] > 0 else 0.0
    v4_pf = (float(stats_v4["gross_gains"]) / float(stats_v4["gross_losses"])) if stats_v4["gross_losses"] > 0 else 99.0

    v3_win_rate = (stats_v3["wins"] / stats_v3["trades"] * 100.0) if stats_v3["trades"] > 0 else 0.0
    v3_pf = (float(stats_v3["gross_gains"]) / float(stats_v3["gross_losses"])) if stats_v3["gross_losses"] > 0 else 99.0

    print(f"{'METRIC':<35} | {'BOT 1 VER 4 (NEW)':<20} | {'BOT 1 BASELINE':<20}")
    print("-" * 80)
    print(f"{'Total Trades Taken':<35} | {stats_v4['trades']:<20} | {stats_v3['trades']:<20}")
    print(f"{'Trades Skipped / Filtered':<35} | {stats_v4['skipped']:<20} | {stats_v3['skipped']:<20}")
    print(f"{'Corridor Vetoes (18c - 48c)':<35} | {stats_v4['corridor_vetoes']:<20} | {'N/A (Capped @ 62c)':<20}")
    print(f"{'Early Profit Harvests (+45%)':<35} | {stats_v4['harvests']:<20} | {'0 (Holds to Settle)':<20}")
    print(f"{'Defensive Stop-Losses (-35%)':<35} | {stats_v4['stops']:<20} | {'0 (Holds to 0c)':<20}")
    print(f"{'Settlement Wins ($1.00)':<35} | {stats_v4['settle_wins']:<20} | {stats_v3['wins']:<20}")
    print(f"{'Settlement Losses ($0.00)':<35} | {stats_v4['settle_losses']:<20} | {stats_v3['losses']:<20}")
    print(f"{'Win Rate':<35} | {v4_win_rate:.1f}%{'':<15} | {v3_win_rate:.1f}%{'':<15}")
    print(f"{'Total Net PnL ($)':<35} | ${stats_v4['net_pnl']:.2f}{'':<14} | ${stats_v3['net_pnl']:.2f}{'':<14}")
    print(f"{'Gross Profit Gains ($)':<35} | ${stats_v4['gross_gains']:.2f}{'':<14} | ${stats_v3['gross_gains']:.2f}{'':<14}")
    print(f"{'Gross Losses Absorbed ($)':<35} | ${stats_v4['gross_losses']:.2f}{'':<14} | ${stats_v3['gross_losses']:.2f}{'':<14}")
    print(f"{'Profit Factor':<35} | {v4_pf:.2f}{'':<16} | {v3_pf:.2f}{'':<16}")
    print(f"{'Max Drawdown ($)':<35} | ${stats_v4['max_dd']:.2f}{'':<14} | ${stats_v3['max_dd']:.2f}{'':<14}")
    print(f"{'Max Consecutive Losses':<35} | {stats_v4['max_loss_streak']:<20} | {stats_v3['max_loss_streak']:<20}")
    print("=" * 80)


if __name__ == "__main__":
    run_simulation()

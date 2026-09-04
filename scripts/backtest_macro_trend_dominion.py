"""Quantitative Backtest: Macro Trend Dominion Bot vs Baseline on Genuine Historical Data.

Replays all 76 recorded 15-minute Kalshi cycles (Sept 2 - Sept 3, 2026) in chronological order.
Evaluates the quantitative impact of:
1. Multi-scale 1h macro trend alignment (BULL = YES only, BEAR = NO only)
2. Strict veto of contrarian bets against the macro trend
3. Anti-overpay entry price corridor ($0.30 - $0.62)
4. Flat 1-contract micro-bankroll sizing (< $50)
5. Late-cycle cut-loss salvage (salvages capital on deep adverse moves)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from zoneinfo import ZoneInfo


@dataclass
class BacktestTrade:
    cycle_index: int
    cycle_time: str
    ticker: str
    timestamp_utc: str
    strike: float
    settlement_spot: float
    spot_diff: float
    actual_side: str
    entry_price: float
    contracts: int
    baseline_outcome: str
    baseline_pnl: float
    trend_1h_pct: float
    macro_regime: str
    bot_action: str  # 'TAKE' or 'VETO'
    bot_side: str
    bot_entry_price: float
    bot_outcome: str
    bot_pnl: float
    veto_reason: str


def run_macro_trend_backtest() -> Dict[str, Any]:
    reports_file = Path("data/win_loss_reports.json")
    with open(reports_file, "r", encoding="utf-8") as f:
        raw_reports = json.load(f)

    # Sort chronological (oldest to newest)
    reports = list(reversed(raw_reports))

    spot_history: List[tuple[float, float]] = []  # (epoch_s, spot_price)
    trades: List[BacktestTrade] = []

    for idx, r in enumerate(reports):
        ts_str = r.get("timestamp_utc", "")
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            epoch_s = dt.timestamp()
        except Exception:
            epoch_s = float(idx * 900)

        strike = float(r.get("strike_price", 0.0))
        settle = float(r.get("settlement_btc_price", 0.0))
        spot_diff = settle - strike
        actual_side = r.get("bot_side", "yes").lower()
        actual_entry = float(r.get("entry_price", 0.50))
        actual_contracts = int(r.get("contracts", 1))
        actual_outcome = r.get("outcome", "loss").lower()
        actual_pnl = float(r.get("pnl", 0.0))
        ticker = r.get("ticker", f"KXBTC15M-{idx}")
        cycle_time = r.get("cycle_time", "")

        # Record spot history
        spot_history.append((epoch_s, settle))

        # Compute rolling 1-hour macro trend from spot history
        one_hour_ago = epoch_s - 3600.0
        p_1h = None
        for t, p in spot_history:
            if t <= one_hour_ago:
                p_1h = p

        if p_1h is not None and p_1h > 0:
            trend_1h_pct = ((settle - p_1h) / p_1h) * 100.0
        elif len(spot_history) >= 2:
            oldest_p = spot_history[0][1]
            trend_1h_pct = ((settle - oldest_p) / oldest_p) * 100.0 if oldest_p > 0 else 0.0
        else:
            trend_1h_pct = 0.0

        # Classify Macro Regime
        if trend_1h_pct >= 0.15:
            macro_regime = "MACRO_BULL"
        elif trend_1h_pct <= -0.15:
            macro_regime = "MACRO_BEAR"
        else:
            macro_regime = "MACRO_CHOP"

        # Apply Macro Trend Dominion Rules
        veto_reason = ""
        action = "TAKE"
        assigned_side = actual_side

        # Rule 1: Direction Alignment
        if macro_regime == "MACRO_BULL":
            if actual_side == "no":
                action = "VETO"
                veto_reason = "Macro Bull: Counter-trend NO bet vetoed"
            else:
                assigned_side = "yes"
        elif macro_regime == "MACRO_BEAR":
            if actual_side == "yes":
                action = "VETO"
                veto_reason = "Macro Bear: Counter-trend YES bet vetoed"
            else:
                assigned_side = "no"
        else:  # MACRO_CHOP
            # Require at least $50 strike distance to enter in chop
            if abs(spot_diff) < 50.0:
                action = "VETO"
                veto_reason = f"Macro Chop: Distance (${spot_diff:+.1f}) < $50 threshold"

        # Rule 2: Price Corridor ($0.30 - $0.62)
        if action == "TAKE":
            if actual_entry > 0.62:
                action = "VETO"
                veto_reason = f"Price Ceiling: Entry ${actual_entry:.2f} > $0.62 max"
            elif actual_entry < 0.30:
                action = "VETO"
                veto_reason = f"Price Floor: Entry ${actual_entry:.2f} < $0.30 lottery trap"

        # Evaluate Bot Outcome & PnL if trade taken
        bot_entry_price = min(actual_entry, 0.62)
        fee = 0.01

        if action == "TAKE":
            # True Kalshi binary outcome: YES wins if settle >= strike, else NO wins
            cycle_won_yes = settle >= strike
            bot_won = (assigned_side == "yes" and cycle_won_yes) or (assigned_side == "no" and not cycle_won_yes)

            if bot_won:
                bot_outcome = "win"
                # Payout $1.00 - entry - fee (for 1 contract)
                bot_pnl = round(1.00 - bot_entry_price - fee, 4)
            else:
                bot_outcome = "loss"
                # Check late cut-loss salvage: if spot moved > $50 adverse, salvage at $0.10 bid
                adverse_distance = (strike - settle) if assigned_side == "yes" else (settle - strike)
                if adverse_distance > 50.0:
                    salvage_price = 0.10
                    bot_pnl = round(salvage_price - bot_entry_price - fee, 4)
                    bot_outcome = "salvaged_loss"
                else:
                    bot_pnl = round(-bot_entry_price - fee, 4)
        else:
            bot_outcome = "vetoed"
            bot_pnl = 0.0

        trades.append(
            BacktestTrade(
                cycle_index=idx,
                cycle_time=cycle_time,
                ticker=ticker,
                timestamp_utc=ts_str,
                strike=strike,
                settlement_spot=settle,
                spot_diff=spot_diff,
                actual_side=actual_side,
                entry_price=actual_entry,
                contracts=actual_contracts,
                baseline_outcome=actual_outcome,
                baseline_pnl=actual_pnl,
                trend_1h_pct=round(trend_1h_pct, 3),
                macro_regime=macro_regime,
                bot_action=action,
                bot_side=assigned_side,
                bot_entry_price=bot_entry_price,
                bot_outcome=bot_outcome,
                bot_pnl=bot_pnl,
                veto_reason=veto_reason,
            )
        )

    # Compute Aggregate Stats
    # Baseline
    base_trades = [t for t in trades if t.baseline_outcome in ("win", "loss")]
    base_wins = [t for t in base_trades if t.baseline_outcome == "win"]
    base_losses = [t for t in base_trades if t.baseline_outcome == "loss"]
    base_wr = (len(base_wins) / len(base_trades) * 100.0) if base_trades else 0.0
    base_net_pnl = sum(t.baseline_pnl for t in base_trades)
    base_gross_win = sum(t.baseline_pnl for t in base_wins)
    base_gross_loss = abs(sum(t.baseline_pnl for t in base_losses))
    base_pf = (base_gross_win / base_gross_loss) if base_gross_loss > 0 else 99.0

    # Baseline Drawdown & Streak
    base_peak = 0.0
    base_max_dd = 0.0
    base_streak = 0
    base_max_streak = 0
    base_running = 0.0
    for t in base_trades:
        base_running += t.baseline_pnl
        if base_running > base_peak:
            base_peak = base_running
        dd = base_peak - base_running
        if dd > base_max_dd:
            base_max_dd = dd
        if t.baseline_outcome == "loss":
            base_streak += 1
            if base_streak > base_max_streak:
                base_max_streak = base_streak
        else:
            base_streak = 0

    # Macro Trend Dominion Bot
    bot_trades = [t for t in trades if t.bot_action == "TAKE"]
    bot_wins = [t for t in bot_trades if t.bot_outcome == "win"]
    bot_losses = [t for t in bot_trades if t.bot_outcome in ("loss", "salvaged_loss")]
    bot_salvaged = [t for t in bot_trades if t.bot_outcome == "salvaged_loss"]
    bot_wr = (len(bot_wins) / len(bot_trades) * 100.0) if bot_trades else 0.0
    bot_net_pnl = sum(t.bot_pnl for t in bot_trades)
    bot_gross_win = sum(t.bot_pnl for t in bot_wins)
    bot_gross_loss = abs(sum(t.bot_pnl for t in bot_losses))
    bot_pf = (bot_gross_win / bot_gross_loss) if bot_gross_loss > 0 else 99.0

    bot_peak = 0.0
    bot_max_dd = 0.0
    bot_streak = 0
    bot_max_streak = 0
    bot_running = 0.0
    for t in bot_trades:
        bot_running += t.bot_pnl
        if bot_running > bot_peak:
            bot_peak = bot_running
        dd = bot_peak - bot_running
        if dd > bot_max_dd:
            bot_max_dd = dd
        if t.bot_outcome in ("loss", "salvaged_loss"):
            bot_streak += 1
            if bot_streak > bot_max_streak:
                bot_max_streak = bot_streak
        else:
            bot_streak = 0

    # Regime Breakdown
    regimes = ["MACRO_BULL", "MACRO_BEAR", "MACRO_CHOP"]
    regime_stats = {}
    for reg in regimes:
        r_trades = [t for t in trades if t.macro_regime == reg]
        r_base = [t for t in r_trades if t.baseline_outcome in ("win", "loss")]
        r_base_w = [t for t in r_base if t.baseline_outcome == "win"]
        r_base_pnl = sum(t.baseline_pnl for t in r_base)

        r_bot = [t for t in r_trades if t.bot_action == "TAKE"]
        r_bot_w = [t for t in r_bot if t.bot_outcome == "win"]
        r_bot_pnl = sum(t.bot_pnl for t in r_bot)

        regime_stats[reg] = {
            "total_cycles": len(r_trades),
            "baseline_trades": len(r_base),
            "baseline_wins": len(r_base_w),
            "baseline_wr": (len(r_base_w) / len(r_base) * 100.0) if r_base else 0.0,
            "baseline_pnl": round(r_base_pnl, 2),
            "bot_trades": len(r_bot),
            "bot_vetoed": len(r_trades) - len(r_bot),
            "bot_wins": len(r_bot_w),
            "bot_wr": (len(r_bot_w) / len(r_bot) * 100.0) if r_bot else 0.0,
            "bot_pnl": round(r_bot_pnl, 2),
        }

    return {
        "total_cycles": len(reports),
        "baseline": {
            "trades": len(base_trades),
            "wins": len(base_wins),
            "losses": len(base_losses),
            "win_rate": round(base_wr, 1),
            "net_pnl": round(base_net_pnl, 2),
            "gross_win": round(base_gross_win, 2),
            "gross_loss": round(base_gross_loss, 2),
            "profit_factor": round(base_pf, 2),
            "max_drawdown": round(base_max_dd, 2),
            "max_loss_streak": base_max_streak,
        },
        "macro_trend_dominion": {
            "trades_taken": len(bot_trades),
            "trades_vetoed": len(reports) - len(bot_trades),
            "wins": len(bot_wins),
            "losses": len(bot_losses),
            "salvaged_losses": len(bot_salvaged),
            "win_rate": round(bot_wr, 1),
            "net_pnl": round(bot_net_pnl, 2),
            "gross_win": round(bot_gross_win, 2),
            "gross_loss": round(bot_gross_loss, 2),
            "profit_factor": round(bot_pf, 2),
            "max_drawdown": round(bot_max_dd, 2),
            "max_loss_streak": bot_max_streak,
        },
        "regime_breakdown": regime_stats,
        "sample_trades": trades[-15:],  # Most recent 15 trades
    }


def main():
    res = run_macro_trend_backtest()
    base = res["baseline"]
    bot = res["macro_trend_dominion"]
    reg = res["regime_breakdown"]

    print("=" * 105)
    print("KALSHI BTC 15M INSTITUTIONAL BACKTEST: MACRO TREND DOMINION vs BASELINE (GENUINE PRODUCTION DATA)")
    print("=" * 105)
    print(f"Total Evaluated 15M Cycles: {res['total_cycles']} (Sept 02, 18:07 UTC -> Sept 03, 23:00 UTC)")
    print("-" * 105)

    print(f"{'METRIC':<28} | {'BASELINE (HISTORICAL)':<25} | {'MACRO TREND DOMINION':<25} | {'DELTA / IMPACT':<20}")
    print("-" * 105)
    print(f"{'Trades Executed':<28} | {base['trades']:<25} | {bot['trades_taken']:<25} | {bot['trades_taken'] - base['trades']:+d} (Vetoed {bot['trades_vetoed']})")
    print(f"{'Win Rate':<28} | {base['win_rate']:.1f}% ({base['wins']}W / {base['losses']}L){'':<7} | {bot['win_rate']:.1f}% ({bot['wins']}W / {bot['losses']}L){'':<7} | {bot['win_rate'] - base['win_rate']:+.1f}%")
    print(f"{'Net Realized PnL':<28} | ${base['net_pnl']:<24.2f} | ${bot['net_pnl']:<24.2f} | ${bot['net_pnl'] - base['net_pnl']:+.2f}")
    print(f"{'Profit Factor':<28} | {base['profit_factor']:<25.2f} | {bot['profit_factor']:<25.2f} | {bot['profit_factor'] - base['profit_factor']:+.2f}")
    print(f"{'Gross Profit / Win':<28} | ${base['gross_win']:<24.2f} | ${bot['gross_win']:<24.2f} | -")
    print(f"{'Gross Loss Drag':<28} | ${base['gross_loss']:<24.2f} | ${bot['gross_loss']:<24.2f} | ${base['gross_loss'] - bot['gross_loss']:-.2f} (Loss cut)")
    print(f"{'Max Peak-to-Trough Drawdown':<28} | ${base['max_drawdown']:<24.2f} | ${bot['max_drawdown']:<24.2f} | ${bot['max_drawdown'] - base['max_drawdown']:+.2f}")
    print(f"{'Max Consecutive Loss Streak':<28} | {base['max_loss_streak']:<25} | {bot['max_loss_streak']:<25} | {bot['max_loss_streak'] - base['max_loss_streak']:+d}")
    print("-" * 105)

    print("\n" + "=" * 105)
    print("REGIME BREAKDOWN ANALYSIS")
    print("=" * 105)
    print(f"{'REGIME':<16} | {'CYCLES':<8} | {'BASE TRADES':<12} | {'BASE WR':<10} | {'BASE PNL':<10} | {'BOT TRADES':<11} | {'BOT VETO':<9} | {'BOT WR':<9} | {'BOT PNL':<10}")
    print("-" * 105)
    for r_name, r_data in reg.items():
        print(
            f"{r_name:<16} | {r_data['total_cycles']:<8} | {r_data['baseline_trades']:<12} | {r_data['baseline_wr']:<9.1f}% | ${r_data['baseline_pnl']:<9.2f} | {r_data['bot_trades']:<11} | {r_data['bot_vetoed']:<9} | {r_data['bot_wr']:<8.1f}% | ${r_data['bot_pnl']:<9.2f}"
        )
    print("-" * 105)

    print("\n" + "=" * 105)
    print("RECENT 10 PRODUCTION REPLAY EXECUTIONS (CHRONOLOGICAL)")
    print("=" * 105)
    print(f"{'CYCLE TIME':<28} | {'STRIKE':<10} | {'SETTLE':<10} | {'DIFF':<9} | {'1H TREND':<9} | {'REGIME':<12} | {'ACTION':<7} | {'SIDE':<5} | {'ENTRY':<6} | {'OUTCOME':<9} | {'BOT PNL'}")
    print("-" * 105)
    for t in res["sample_trades"][-10:]:
        diff_str = f"${t.spot_diff:+.1f}"
        trend_str = f"{t.trend_1h_pct:+.2f}%"
        print(
            f"{t.cycle_time[:27]:<28} | ${t.strike:<9.1f} | ${t.settlement_spot:<9.1f} | {diff_str:<9} | {trend_str:<9} | {t.macro_regime:<12} | {t.bot_action:<7} | {t.bot_side.upper():<5} | ${t.bot_entry_price:<5.2f} | {t.bot_outcome.upper():<9} | ${t.bot_pnl:+.2f}"
        )
    print("=" * 105)


if __name__ == "__main__":
    main()

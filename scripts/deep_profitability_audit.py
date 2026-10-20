import json
import sqlite3
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict
from decimal import Decimal

def run_analysis():
    # Load JSON records
    btc_reports = []
    eth_reports = []
    try:
        btc_reports = json.load(open("data/win_loss_reports.json", encoding="utf-8"))
    except Exception as e:
        print("Error loading btc reports:", e)

    try:
        eth_reports = json.load(open("data/eth_win_loss_reports.json", encoding="utf-8"))
    except Exception as e:
        print("Error loading eth reports:", e)

    all_trades = []
    for r in btc_reports:
        all_trades.append(("BTC", r))
    for r in eth_reports:
        all_trades.append(("ETH", r))

    print(f"Loaded {len(btc_reports)} BTC reports, {len(eth_reports)} ETH reports. Total: {len(all_trades)}")

    # Analysis by Hour ET
    hour_stats = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0, "pnl": Decimal("0.0"), "win_pnl": Decimal("0.0"), "loss_pnl": Decimal("0.0")})
    regime_stats = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0, "pnl": Decimal("0.0"), "win_pnl": Decimal("0.0"), "loss_pnl": Decimal("0.0")})
    hour_regime_stats = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0, "pnl": Decimal("0.0"), "win_pnl": Decimal("0.0"), "loss_pnl": Decimal("0.0")})
    entry_price_stats = defaultdict(lambda: {"total": 0, "wins": 0, "pnl": Decimal("0.0")})
    tau_stats = defaultdict(lambda: {"total": 0, "wins": 0, "pnl": Decimal("0.0")})
    spot_diff_stats = defaultdict(lambda: {"total": 0, "wins": 0, "pnl": Decimal("0.0")})

    for asset, r in all_trades:
        ts_str = r.get("timestamp_utc")
        if not ts_str:
            continue
        try:
            ts_clean = ts_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_clean)
        except Exception:
            continue

        # Convert to America/New_York (ET)
        try:
            dt_et = dt.astimezone(ZoneInfo("America/New_York"))
        except Exception:
            dt_et = dt.astimezone(timezone(timedelta(hours=-4)))
        h_et = dt_et.hour

        outcome = str(r.get("outcome", "")).lower()
        pnl = Decimal(str(r.get("pnl", 0.0)))
        regime = str(r.get("market_condition", "UNKNOWN")).upper()
        if regime == "NONE" or not regime:
            regime = "UNKNOWN"

        entry_pr = float(r.get("entry_price", 0.0))
        entry_bucket = round(entry_pr, 2)
        pr_range = f"${int(entry_bucket*100)//5 * 5}c-${(int(entry_bucket*100)//5 + 1)*5}c"

        tau = float(r.get("time_to_expiry_s", 0.0) or 0.0)
        tau_bucket = "Late (<300s)" if tau < 300 else ("Mid (300-600s)" if tau <= 600 else "Early (>600s)")

        diff = abs(float(r.get("spot_diff", 0.0) or r.get("entry_spot_diff", 0.0) or 0.0))
        if asset == "ETH":
            diff_bucket = "Tight (<= $2.00)" if diff <= 2.0 else ("Mid ($2.00-$5.00)" if diff <= 5.0 else "Wide (> $5.00)")
        else:
            diff_bucket = "Tight (<= $20.00)" if diff <= 20.0 else ("Mid ($20.00-$60.00)" if diff <= 60.0 else "Wide (> $60.00)")

        is_win = (outcome == "win")

        for d in [hour_stats[h_et], regime_stats[regime], hour_regime_stats[(h_et, regime)]]:
            d["total"] += 1
            d["pnl"] += pnl
            if is_win:
                d["wins"] += 1
                d["win_pnl"] += pnl
            else:
                d["losses"] += 1
                d["loss_pnl"] += abs(pnl)

        entry_price_stats[pr_range]["total"] += 1
        entry_price_stats[pr_range]["pnl"] += pnl
        if is_win:
            entry_price_stats[pr_range]["wins"] += 1

        tau_stats[tau_bucket]["total"] += 1
        tau_stats[tau_bucket]["pnl"] += pnl
        if is_win:
            tau_stats[tau_bucket]["wins"] += 1

        spot_diff_stats[diff_bucket]["total"] += 1
        spot_diff_stats[diff_bucket]["pnl"] += pnl
        if is_win:
            spot_diff_stats[diff_bucket]["wins"] += 1

    print("\n" + "="*85)
    print("1. EMPIRICAL HOURLY PERFORMANCE AUDIT (BY SESSION WINDOW)")
    print("="*85)
    print(f"{'Hour ET':<10} | {'Hour Qatar':<12} | {'Trades':<7} | {'Win %':<8} | {'Net PnL':<11} | {'Profit Factor':<14} | {'Classification'}")
    print("-" * 85)

    golden_hours = []
    toxic_hours = []
    neutral_hours = []

    for h in range(24):
        st = hour_stats[h]
        n = st["total"]
        if n == 0:
            continue
        wr = (st["wins"] / n) * 100
        pnl = st["pnl"]
        pf = (float(st["win_pnl"]) / float(st["loss_pnl"])) if st["loss_pnl"] > 0 else (99.0 if st["win_pnl"] > 0 else 1.0)
        h_qatar = (h + 7) % 24
        
        if wr >= 60.0 and pnl > Decimal("0.0"):
            verdict = "[GOLDEN - APPROVED]"
            golden_hours.append((h, h_qatar, n, wr, pnl, pf))
        elif wr < 48.0 or pnl < Decimal("0.0"):
            verdict = "[TOXIC - VETO/OFF]"
            toxic_hours.append((h, h_qatar, n, wr, pnl, pf))
        else:
            verdict = "[NEUTRAL - SELECTIVE]"
            neutral_hours.append((h, h_qatar, n, wr, pnl, pf))

        print(f"{h:02d}:00 ET   | {h_qatar:02d}:00 Qatar  | {n:<7} | {wr:6.1f}%  | ${pnl:>9.2f} | {pf:14.2f} | {verdict}")

    print("\n" + "="*85)
    print("2. MARKET REGIME & CONDITION PERFORMANCE AUDIT")
    print("="*85)
    print(f"{'Market Condition':<20} | {'Trades':<7} | {'Win %':<8} | {'Net PnL':<11} | {'Profit Factor':<14} | {'Status'}")
    print("-" * 85)
    for reg, st in sorted(regime_stats.items(), key=lambda x: x[1]["pnl"], reverse=True):
        n = st["total"]
        if n == 0:
            continue
        wr = (st["wins"] / n) * 100
        pnl = st["pnl"]
        pf = (float(st["win_pnl"]) / float(st["loss_pnl"])) if st["loss_pnl"] > 0 else (99.0 if st["win_pnl"] > 0 else 1.0)
        status = "[HIGH ALPHA]" if (wr >= 60.0 and pnl > 0) else ("[DRAWS CAPITAL]" if pnl < 0 else "[MARGINAL]")
        print(f"{reg:<20} | {n:<7} | {wr:6.1f}%  | ${pnl:>9.2f} | {pf:14.2f} | {status}")

    print("\n" + "="*85)
    print("3. TOP 10 GOLDEN CLUSTERS (HOUR ET + REGIME COMBINATIONS)")
    print("="*85)
    sorted_clusters = sorted(hour_regime_stats.items(), key=lambda x: (x[1]["pnl"], x[1]["total"]), reverse=True)
    print(f"{'Hour ET':<10} | {'Regime':<18} | {'Trades':<7} | {'Win %':<8} | {'Net PnL':<11} | {'Status'}")
    print("-" * 80)
    for (h, reg), st in sorted_clusters[:12]:
        n = st["total"]
        if n < 5:
            continue
        wr = (st["wins"] / n) * 100
        pnl = st["pnl"]
        print(f"{h:02d}:00 ET   | {reg:<18} | {n:<7} | {wr:6.1f}%  | ${pnl:>9.2f} | [GOLDEN COMBINATION]")

    print("\n" + "="*85)
    print("4. ENTRY PRICE DECILE & EDGE SENSITIVITY")
    print("="*85)
    print(f"{'Entry Price Band':<18} | {'Trades':<7} | {'Win %':<8} | {'Net PnL':<11}")
    print("-" * 55)
    for band, st in sorted(entry_price_stats.items(), key=lambda x: x[0]):
        n = st["total"]
        if n == 0:
            continue
        wr = (st["wins"] / n) * 100
        pnl = st["pnl"]
        print(f"{band:<18} | {n:<7} | {wr:6.1f}%  | ${pnl:>9.2f}")

    print("\n" + "="*85)
    print("5. TIME-TO-EXPIRY (TAU) & SPOT-TO-STRIKE SEPARATION SENSITIVITY")
    print("="*85)
    for name, stat_dict in [("TAU EXPIRY HORIZON", tau_stats), ("SPOT-TO-STRIKE SEPARATION", spot_diff_stats)]:
        print(f"\n--- {name} ---")
        for bucket, st in sorted(stat_dict.items(), key=lambda x: x[1]["pnl"], reverse=True):
            n = st["total"]
            if n == 0:
                continue
            wr = (st["wins"] / n) * 100
            pnl = st["pnl"]
            print(f"{bucket:<25} | Trades: {n:<5} | Win%: {wr:5.1f}% | Net PnL: ${pnl:>8.2f}")

if __name__ == "__main__":
    run_analysis()

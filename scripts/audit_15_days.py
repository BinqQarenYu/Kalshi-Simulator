import json
import sqlite3
from datetime import datetime, timezone, timedelta
from collections import defaultdict

def parse_iso(ts_str):
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None

def main():
    cutoff = datetime(2026, 10, 5, 0, 0, 0, tzinfo=timezone.utc)
    print(f"Auditing settled trades from 15 days ago ({cutoff.isoformat()}) to now...")

    all_records = []
    seen_keys = set()

    # 1. JSON reports
    for p, asset in [("data/win_loss_reports.json", "BTC"), ("data/eth_win_loss_reports.json", "ETH")]:
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            for r in data:
                dt = parse_iso(r.get("timestamp_utc"))
                if dt and dt >= cutoff:
                    key = (r.get("ticker"), round(dt.timestamp()))
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_records.append({
                            "source": "json",
                            "asset": asset,
                            "ticker": r.get("ticker"),
                            "dt_utc": dt,
                            "pnl": float(r.get("pnl", 0.0)),
                            "is_win": r.get("outcome") == "win",
                            "market_condition": r.get("market_condition", "UNKNOWN"),
                            "entry_price": float(r.get("entry_price", 0.0)),
                        })
        except Exception as e:
            print(f"Error reading {p}: {e}")

    # 2. SQLite settlements
    try:
        conn = sqlite3.connect("data/kalshi_history.db")
        c = conn.cursor()
        for row in c.execute("SELECT ticker, timestamp_utc, pnl, outcome, entry_price FROM settlements WHERE timestamp_utc >= '2026-10-05'"):
            ticker, ts_str, pnl, outcome, entry_price = row
            dt = parse_iso(ts_str)
            if dt and dt >= cutoff:
                key = (ticker, round(dt.timestamp()))
                if key not in seen_keys:
                    seen_keys.add(key)
                    asset = "ETH" if "ETH" in (ticker or "") else "BTC"
                    all_records.append({
                        "source": "sqlite",
                        "asset": asset,
                        "ticker": ticker,
                        "dt_utc": dt,
                        "pnl": float(pnl or 0.0),
                        "is_win": outcome == "win",
                        "market_condition": "UNKNOWN",
                        "entry_price": float(entry_price or 0.0),
                    })
        conn.close()
    except Exception as e:
        print(f"Error reading sqlite: {e}")

    print(f"Total Unique Settled Trades in Last 15 Days: {len(all_records)}")

    # Hourly distribution (in Qatar time and ET)
    # Qatar time = UTC + 3
    # ET = UTC - 4 (EDT)
    hourly_stats = defaultdict(lambda: {"count": 0, "wins": 0, "pnl": 0.0, "gross_win": 0.0, "gross_loss": 0.0})

    for r in all_records:
        dt = r["dt_utc"]
        # Qatar hour:
        qatar_dt = dt.astimezone(timezone(timedelta(hours=3)))
        qatar_hour = qatar_dt.hour
        # ET hour:
        et_dt = dt.astimezone(timezone(timedelta(hours=-4)))
        et_hour = et_dt.hour

        h = hourly_stats[qatar_hour]
        h["count"] += 1
        h["et_hour"] = et_hour
        pnl = r["pnl"]
        h["pnl"] += pnl
        if r["is_win"]:
            h["wins"] += 1
            h["gross_win"] += pnl
        else:
            h["gross_loss"] += abs(pnl)

    # Sort by Qatar hour
    print("\n=== HOURLY PROFITABILITY BREAKDOWN (LAST 15 DAYS) ===")
    print(f"{'Qatar Hour':<12} | {'ET Hour':<8} | {'Trades':<6} | {'Win Rate':<10} | {'Net PnL ($)':<12} | {'PF':<6}")
    print("-" * 65)

    sorted_hours = sorted(hourly_stats.keys())
    for qh in range(24):
        s = hourly_stats.get(qh, {"count": 0, "wins": 0, "pnl": 0.0, "gross_win": 0.0, "gross_loss": 0.0, "et_hour": (qh - 7) % 24})
        cnt = s["count"]
        wr = (s["wins"] / cnt * 100.0) if cnt > 0 else 0.0
        pnl = s["pnl"]
        pf = (s["gross_win"] / s["gross_loss"]) if s["gross_loss"] > 0 else (99.0 if s["gross_win"] > 0 else 1.0)
        eth = s.get("et_hour", (qh - 7) % 24)
        print(f"{qh:02d}:00 AST    | {eth:02d}:00 ET | {cnt:<6} | {wr:6.1f}%    | ${pnl:10.2f}  | {pf:5.2f}")

    # Top Most Profitable vs Worst
    ranked = sorted(hourly_stats.items(), key=lambda x: x[1]["pnl"], reverse=True)
    print("\n=== TOP 5 MOST PROFITABLE HOURS (LAST 15 DAYS) ===")
    for qh, s in ranked[:5]:
        cnt = s["count"]
        wr = (s["wins"] / cnt * 100.0) if cnt > 0 else 0.0
        eth = s.get("et_hour", (qh - 7) % 24)
        print(f"Qatar {qh:02d}:00 ({eth:02d}:00 ET): +${s['pnl']:.2f} PnL, {wr:.1f}% WR ({s['wins']}/{cnt} trades)")

    print("\n=== TOP 5 WORST (MOST TOXIC) HOURS (LAST 15 DAYS) ===")
    for qh, s in ranked[-5:]:
        cnt = s["count"]
        wr = (s["wins"] / cnt * 100.0) if cnt > 0 else 0.0
        eth = s.get("et_hour", (qh - 7) % 24)
        print(f"Qatar {qh:02d}:00 ({eth:02d}:00 ET): ${s['pnl']:.2f} PnL, {wr:.1f}% WR ({s['wins']}/{cnt} trades)")

if __name__ == "__main__":
    main()

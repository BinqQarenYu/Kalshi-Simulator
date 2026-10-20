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
    
    records = []
    seen = set()

    for p, asset in [("data/eth_win_loss_reports.json", "ETH"), ("data/win_loss_reports.json", "BTC")]:
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            for r in data:
                dt = parse_iso(r.get("timestamp_utc"))
                if dt and dt >= cutoff:
                    k = (r.get("ticker"), round(dt.timestamp()))
                    if k not in seen:
                        seen.add(k)
                        records.append({
                            "asset": asset,
                            "dt_utc": dt,
                            "pnl": float(r.get("pnl", 0.0)),
                            "is_win": r.get("outcome") == "win",
                            "condition": r.get("market_condition", "UNKNOWN"),
                            "entry_price": float(r.get("entry_price", 0.0)),
                        })
        except Exception as e:
            print(f"Error {p}: {e}")

    # Add SQLite settlements
    try:
        conn = sqlite3.connect("data/kalshi_history.db")
        c = conn.cursor()
        for row in c.execute("SELECT ticker, timestamp_utc, pnl, outcome, entry_price FROM settlements WHERE timestamp_utc >= '2026-10-05'"):
            ticker, ts_str, pnl, outcome, entry_price = row
            dt = parse_iso(ts_str)
            if dt and dt >= cutoff:
                k = (ticker, round(dt.timestamp()))
                if k not in seen:
                    seen.add(k)
                    records.append({
                        "asset": "ETH" if "ETH" in (ticker or "") else "BTC",
                        "dt_utc": dt,
                        "pnl": float(pnl or 0.0),
                        "is_win": outcome == "win",
                        "condition": "UNKNOWN",
                        "entry_price": float(entry_price or 0.0),
                    })
        conn.close()
    except Exception as e:
        print(f"Error SQLite: {e}")

    print(f"Total Records for 15-Day Window: {len(records)}")

    # 1. Hourly Stats in Qatar AST (UTC+3)
    hourly = defaultdict(lambda: {"count": 0, "wins": 0, "pnl": 0.0, "gross_win": 0.0, "gross_loss": 0.0})
    daily = defaultdict(lambda: {"count": 0, "wins": 0, "pnl": 0.0})
    conditions = defaultdict(lambda: {"count": 0, "wins": 0, "pnl": 0.0})

    for r in records:
        dt = r["dt_utc"]
        qatar_dt = dt.astimezone(timezone(timedelta(hours=3)))
        qh = qatar_dt.hour
        day_str = qatar_dt.strftime("%Y-%m-%d")

        pnl = r["pnl"]
        is_win = r["is_win"]

        # Hourly
        hourly[qh]["count"] += 1
        hourly[qh]["pnl"] += pnl
        if is_win:
            hourly[qh]["wins"] += 1
            hourly[qh]["gross_win"] += pnl
        else:
            hourly[qh]["gross_loss"] += abs(pnl)

        # Daily
        daily[day_str]["count"] += 1
        daily[day_str]["pnl"] += pnl
        if is_win:
            daily[day_str]["wins"] += 1

        # Regime / Condition
        cond = r["condition"].upper() if r["condition"] else "UNKNOWN"
        conditions[cond]["count"] += 1
        conditions[cond]["pnl"] += pnl
        if is_win:
            conditions[cond]["wins"] += 1

    print("\n--- DAILY PnL (QATAR AST) ---")
    cum_pnl = 0.0
    for d in sorted(daily.keys()):
        cnt = daily[d]["count"]
        pnl = daily[d]["pnl"]
        wr = daily[d]["wins"] / cnt * 100.0 if cnt else 0.0
        cum_pnl += pnl
        print(f"{d} | PnL: ${pnl:+6.2f} | Cum: ${cum_pnl:+6.2f} | Trades: {cnt:4d} | WR: {wr:5.1f}%")

    print("\n--- HOURLY PnL (QATAR AST) FOR MERMAID ---")
    hours_labels = []
    pnl_values = []
    wr_values = []
    for h in range(24):
        s = hourly.get(h, {"count": 0, "wins": 0, "pnl": 0.0, "gross_win": 0.0, "gross_loss": 0.0})
        cnt = s["count"]
        wr = (s["wins"] / cnt * 100.0) if cnt else 0.0
        pnl = round(s["pnl"], 2)
        hours_labels.append(f'"{h:02d}:00"')
        pnl_values.append(str(pnl))
        wr_values.append(str(round(wr, 1)))
        print(f"Hour {h:02d}:00 AST: Net PnL = ${pnl:+6.2f}, WR = {wr:5.1f}% ({s['wins']}/{cnt} trades)")

    print("\nMermaid xychart categories:")
    print("[" + ", ".join(hours_labels) + "]")
    print("Mermaid xychart bar values:")
    print("[" + ", ".join(pnl_values) + "]")
    print("Mermaid xychart win rate line:")
    print("[" + ", ".join(wr_values) + "]")

    print("\n--- REGIMES / CONDITIONS ---")
    for c, s in sorted(conditions.items(), key=lambda x: x[1]["pnl"], reverse=True):
        cnt = s["count"]
        wr = (s["wins"] / cnt * 100.0) if cnt else 0.0
        print(f"{c:<20} | PnL: ${s['pnl']:+7.2f} | Trades: {cnt:4d} | WR: {wr:5.1f}%")

if __name__ == "__main__":
    main()

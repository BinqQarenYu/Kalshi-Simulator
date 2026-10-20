import os
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

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
        if os.path.exists(p):
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
                        })

    if os.path.exists("data/kalshi_history.db"):
        conn = sqlite3.connect("data/kalshi_history.db")
        c = conn.cursor()
        for row in c.execute("SELECT ticker, timestamp_utc, pnl, outcome FROM settlements WHERE timestamp_utc >= '2026-10-05'"):
            ticker, ts_str, pnl, outcome = row
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
                    })
        conn.close()

    print(f"Total Records: {len(records)}")

    # 1. Hourly aggregation in Qatar Time (AST, UTC+3)
    hourly = defaultdict(lambda: {"count": 0, "wins": 0, "pnl": 0.0})
    daily = defaultdict(lambda: {"count": 0, "wins": 0, "pnl": 0.0})
    regimes = defaultdict(lambda: {"count": 0, "wins": 0, "pnl": 0.0})

    for r in records:
        dt = r["dt_utc"]
        qatar_dt = dt.astimezone(timezone(timedelta(hours=3)))
        qh = qatar_dt.hour
        d_str = qatar_dt.strftime("%b %d")
        pnl = r["pnl"]
        is_win = r["is_win"]

        hourly[qh]["count"] += 1
        hourly[qh]["pnl"] += pnl
        if is_win:
            hourly[qh]["wins"] += 1

        daily[d_str]["count"] += 1
        daily[d_str]["pnl"] += pnl
        if is_win:
            daily[d_str]["wins"] += 1

        c_name = r["condition"].upper() if r["condition"] else "UNKNOWN"
        regimes[c_name]["count"] += 1
        regimes[c_name]["pnl"] += pnl
        if is_win:
            regimes[c_name]["wins"] += 1

    # Prepare plot data
    hours = list(range(24))
    hour_labels = [f"{h:02d}:00" for h in hours]
    pnls = [round(hourly[h]["pnl"], 2) for h in hours]
    win_rates = [(hourly[h]["wins"] / hourly[h]["count"] * 100.0) if hourly[h]["count"] > 0 else 0.0 for h in hours]
    trade_counts = [hourly[h]["count"] for h in hours]

    # Create figure with 3 panels
    plt.style.use("dark_background")
    fig, axes = plt.subplots(3, 1, figsize=(15, 13), gridspec_kw={"height_ratios": [1.4, 1.2, 1.0]})
    fig.patch.set_facecolor("#0b0e14")

    # Panel 1: Hourly Net PnL (Qatar AST)
    ax1 = axes[0]
    ax1.set_facecolor("#111622")
    colors = ["#00e676" if p >= 0 else "#ff1744" for p in pnls]
    bars = ax1.bar(hours, pnls, color=colors, width=0.68, edgecolor="#ffffff", linewidth=0.5, alpha=0.9)
    ax1.axhline(0, color="#ffffff", linestyle="--", linewidth=0.8, alpha=0.5)

    for i, (b, p) in enumerate(zip(bars, pnls)):
        y_pos = b.get_height() + (0.15 if p >= 0 else -0.35)
        ax1.text(b.get_x() + b.get_width() / 2, y_pos, f"${p:+.2f}", ha="center", va="bottom" if p >= 0 else "top",
                 fontsize=8.5, fontweight="bold", color="#00e676" if p >= 0 else "#ff5252")

    ax1.set_xticks(hours)
    ax1.set_xticklabels(hour_labels, fontsize=9, fontweight="bold")
    ax1.set_ylabel("Net PnL ($)", fontsize=11, fontweight="bold", color="#ffffff")
    ax1.set_title("15-Day Real Trade Profitability by Hour (Qatar AST / UTC+3)\n[Green = Approved Golden Window | Red = Auto-Off Dead Zone]",
                  fontsize=13, fontweight="bold", pad=12, color="#00e5ff")
    ax1.grid(True, linestyle=":", alpha=0.25, color="#78909c")

    # Panel 2: Hourly Win Rate (%)
    ax2 = axes[1]
    ax2.set_facecolor("#111622")
    line = ax2.plot(hours, win_rates, color="#00e5ff", marker="o", linewidth=2.2, markersize=6, label="Win Rate %")
    ax2.axhline(50, color="#ffeb3b", linestyle=":", linewidth=1.2, alpha=0.7, label="50% Breakeven Mark")
    ax2.axhline(60, color="#00e676", linestyle="--", linewidth=1.0, alpha=0.6, label="60% Target Edge")

    for h, wr, cnt in zip(hours, win_rates, trade_counts):
        if cnt > 0:
            c = "#00e676" if wr >= 55 else ("#ff1744" if wr < 40 else "#ffeb3b")
            ax2.text(h, wr + 2.5, f"{wr:.0f}%\n(n={cnt})", ha="center", va="bottom", fontsize=7.5, color=c, fontweight="bold")

    ax2.set_xticks(hours)
    ax2.set_xticklabels(hour_labels, fontsize=9, fontweight="bold")
    ax2.set_ylabel("Win Rate (%)", fontsize=11, fontweight="bold", color="#ffffff")
    ax2.set_ylim(0, 100)
    ax2.set_title("Hourly Win Rate % & Sample Size (n = Number of Settled Trades)", fontsize=12, fontweight="bold", pad=10, color="#ffffff")
    ax2.grid(True, linestyle=":", alpha=0.25, color="#78909c")
    ax2.legend(loc="lower right", facecolor="#1b2234", edgecolor="#ffffff", fontsize=9)

    # Panel 3: Cumulative Daily Equity Progression
    ax3 = axes[2]
    ax3.set_facecolor("#111622")
    days_sorted = sorted(daily.keys(), key=lambda d: datetime.strptime(d + " 2026", "%b %d %Y"))
    daily_pnls = [daily[d]["pnl"] for d in days_sorted]
    cum_pnl = []
    tot = 0.0
    for p in daily_pnls:
        tot += p
        cum_pnl.append(tot)

    ax3.plot(range(len(days_sorted)), cum_pnl, color="#76ff03", marker="s", linewidth=2.5, markersize=7, label="Cumulative Realized Net PnL")
    ax3.fill_between(range(len(days_sorted)), cum_pnl, 0, color="#76ff03", alpha=0.15)
    ax3.axhline(0, color="#ffffff", linestyle="--", linewidth=0.8, alpha=0.5)

    for i, (cp, dp) in enumerate(zip(cum_pnl, daily_pnls)):
        ax3.text(i, cp + (0.5 if cp >= 0 else -0.8), f"${cp:+.2f}\n(${dp:+.2f})", ha="center", va="bottom" if cp >= 0 else "top",
                 fontsize=8, fontweight="bold", color="#ffffff")

    ax3.set_xticks(range(len(days_sorted)))
    ax3.set_xticklabels(days_sorted, fontsize=9, fontweight="bold")
    ax3.set_ylabel("Cumulative PnL ($)", fontsize=11, fontweight="bold", color="#ffffff")
    ax3.set_title("15-Day Cumulative Equity Curve Progression (Oct 08 - Oct 20)", fontsize=12, fontweight="bold", pad=10, color="#ffffff")
    ax3.grid(True, linestyle=":", alpha=0.25, color="#78909c")
    ax3.legend(loc="upper left", facecolor="#1b2234", edgecolor="#ffffff", fontsize=9)

    plt.tight_layout()

    # Save to artifact dir and docs dir
    artifact_dir = "C:/Users/likha/.gemini/antigravity/brain/dcb617f1-b515-46b9-92dd-a98c5c4cabe6"
    os.makedirs(artifact_dir, exist_ok=True)
    artifact_path = os.path.join(artifact_dir, "fifteen_day_profitability_chart.png")
    fig.savefig(artifact_path, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())

    docs_path = "f:/012D_TRADE/Kalshi Simulator/docs/fifteen_day_profitability_chart.png"
    fig.savefig(docs_path, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())

    print(f"Chart successfully saved to:")
    print(f"  {artifact_path}")
    print(f"  {docs_path}")

if __name__ == "__main__":
    main()

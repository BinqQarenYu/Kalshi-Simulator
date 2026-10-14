"""
Empirical Maker vs. Taker Quantitative Analysis
Queries SQLite (Schema V5) and JSON historical trade records
to evaluate empirical fill rates, price distributions, adverse selection,
and profitability metrics.
"""
import sqlite3
import json
from decimal import Decimal
from collections import defaultdict

def run_analysis():
    conn = sqlite3.connect("data/kalshi_history.db")
    c = conn.cursor()

    # 1. Inspect tables
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in c.fetchall()]
    print(f"Tables in kalshi_history.db: {tables}")

    # 2. Query trades joined with settlements
    # Let's see settlements schema
    c.execute("PRAGMA table_info(settlements)")
    settle_cols = [col[1] for col in c.fetchall()]
    print(f"Settlement columns: {settle_cols}")

    # 3. Analyze Win Rates and PnL by entry price brackets from trades & settlements
    query = """
    SELECT 
        t.trade_id, t.price, t.fees, t.execution_mode, s.outcome, s.revenue - t.gross_value as net_pnl, s.strike_price, s.settlement_price
    FROM trades t
    INNER JOIN settlements s ON t.ticker = s.ticker AND t.timeframe = s.timeframe
    """
    try:
        c.execute(query)
        rows = c.fetchall()
        print(f"\nJoined Trade-Settlement Rows: {len(rows)}")
    except Exception as e:
        print(f"Join query failed: {e}")
        # fallback to settlements or reports
        rows = []

    # 4. Analyze win_loss_reports.json (100 rich records)
    with open("data/win_loss_reports.json", "r", encoding="utf-8") as f:
        reports = json.load(f)

    print(f"\n--- WIN_LOSS_REPORTS.JSON EMPIRICAL BREAKDOWN ({len(reports)} records) ---")
    
    price_buckets = {
        "Deep Discount ($0.30 - $0.42) [Maker Archetype]": {"wins": 0, "losses": 0, "pnl": Decimal("0"), "count": 0},
        "Mid Corridor ($0.43 - $0.48) [Marketable Limit Archetype]": {"wins": 0, "losses": 0, "pnl": Decimal("0"), "count": 0},
        "Premium Aggressive ($0.49 - $0.57) [Momentum Taker Archetype]": {"wins": 0, "losses": 0, "pnl": Decimal("0"), "count": 0},
        "Chasers (> $0.57) [Retail FOMO]": {"wins": 0, "losses": 0, "pnl": Decimal("0"), "count": 0},
    }

    regime_breakdown = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": Decimal("0")})
    live_trades = []

    for r in reports:
        price = Decimal(str(r.get("entry_price", 0.5)))
        pnl = Decimal(str(r.get("pnl", 0)))
        outcome = r.get("outcome", "").lower()
        market_cond = r.get("market_condition", "unknown")
        exec_mode = r.get("execution_mode", "simulated")
        
        if exec_mode == "live" or "LIVE" in r.get("lane", "") or "live" in r.get("report_id", ""):
            live_trades.append(r)

        # Bucket by price
        if price <= Decimal("0.42"):
            b = price_buckets["Deep Discount ($0.30 - $0.42) [Maker Archetype]"]
        elif price <= Decimal("0.48"):
            b = price_buckets["Mid Corridor ($0.43 - $0.48) [Marketable Limit Archetype]"]
        elif price <= Decimal("0.57"):
            b = price_buckets["Premium Aggressive ($0.49 - $0.57) [Momentum Taker Archetype]"]
        else:
            b = price_buckets["Chasers (> $0.57) [Retail FOMO]"]

        b["count"] += 1
        b["pnl"] += pnl
        if outcome == "win":
            b["wins"] += 1
            regime_breakdown[market_cond]["wins"] += 1
        else:
            b["losses"] += 1
            regime_breakdown[market_cond]["losses"] += 1
        regime_breakdown[market_cond]["pnl"] += pnl

    for bname, data in price_buckets.items():
        total = data["count"]
        win_rate = (data["wins"] / total * 100) if total > 0 else 0
        avg_pnl = (data["pnl"] / Decimal(str(total))) if total > 0 else Decimal("0")
        print(f"\n{bname}:")
        print(f"  Count: {total} trades")
        print(f"  Wins: {data['wins']}, Losses: {data['losses']} | Win Rate: {win_rate:.1f}%")
        print(f"  Total PnL: ${data['pnl']:.2f} | Avg PnL/Trade: ${avg_pnl:.4f}")

    print("\n--- REGIME PERFORMANCE BREAKDOWN ---")
    for rname, rdata in regime_breakdown.items():
        tot = rdata["wins"] + rdata["losses"]
        wr = (rdata["wins"] / tot * 100) if tot > 0 else 0
        print(f"Regime: {rname:15} | Trades: {tot:3} | Win Rate: {wr:5.1f}% | Total PnL: ${rdata['pnl']:.2f}")

    print(f"\nLive Real Trades Found: {len(live_trades)}")
    for lt in live_trades:
        print(f"  ID: {lt.get('report_id')} | Price: {lt.get('entry_price')} | Outcome: {lt.get('outcome')} | PnL: ${lt.get('pnl')}")

if __name__ == "__main__":
    run_analysis()

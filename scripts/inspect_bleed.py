"""Deep audit of recent bleed patterns, side bias, failure autopsies, and DoF patch state."""

import json
from pathlib import Path
import sqlite3


def audit(label: str, path_str: str) -> None:
    p = Path(path_str)
    if not p.exists():
        print(f"[{label}] Not found: {path_str}")
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        print("=" * 70)
        print(f"[{label}] Total reports: {len(data)}")
        recent = data[:20]
        wins = sum(1 for r in recent if str(r.get("outcome")).lower() == "win")
        losses = sum(1 for r in recent if str(r.get("outcome")).lower() == "loss")
        pnl = sum(float(r.get("pnl", 0.0) or 0.0) for r in recent)
        
        # Side bias audit
        yes_trades = [r for r in recent if str(r.get("bot_side")).lower() == "yes"]
        no_trades = [r for r in recent if str(r.get("bot_side")).lower() == "no"]
        yes_wins = sum(1 for r in yes_trades if str(r.get("outcome")).lower() == "win")
        no_wins = sum(1 for r in no_trades if str(r.get("outcome")).lower() == "win")
        
        print(f"Recent {len(recent)} Trades: Wins={wins}, Losses={losses}, Net PnL=${pnl:+.4f}")
        print(f"Side Breakdown: YES={len(yes_trades)} (Wins: {yes_wins}), NO={len(no_trades)} (Wins: {no_wins})")
        print("-" * 70)
        for i, r in enumerate(recent, 1):
            ts = r.get("cycle_time") or r.get("timestamp_utc", "")
            tk = r.get("ticker", "")
            side = str(r.get("bot_side", ""))
            entry = float(r.get("entry_price", 0.0) or 0.0)
            settle = float(r.get("settlement_spot_price", 0.0) or 0.0)
            strike = float(r.get("strike_price", 0.0) or 0.0)
            out = str(r.get("outcome", ""))
            p = float(r.get("pnl", 0.0) or 0.0)
            fcode = str(r.get("failure_code") or "")
            bal = float(r.get("balance_after", 0.0) or 0.0)
            cond = str(r.get("market_condition", ""))
            print(f"#{i:02d} | {ts[:23]:23s} | {tk} | {side.upper():4s} @ ${entry:.2f} | Strike: ${strike:.2f} | Settle: ${settle:.2f} | {out.upper():4s} (${p:+.2f}) | Bal: ${bal:.2f} | Cond: {cond:7s} | {fcode}")
    except Exception as e:
        print(f"Error reading {path_str}: {e}")


def check_sqlite(db_path_str: str) -> None:
    p = Path(db_path_str)
    if not p.exists():
        return
    print("=" * 70)
    print(f"[SQLITE AUTOPSIES] {db_path_str}")
    try:
        conn = sqlite3.connect(p)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        if "failure_autopsies" in tables:
            cur.execute("""
                SELECT ticker, failure_code, realized_pnl, is_counter_trend, macro_1h_slope, 
                       is_double_wick_trap, wick_to_body_ratio, was_salvageable, is_twap_pin_victim, created_time
                FROM failure_autopsies ORDER BY id DESC LIMIT 10
            """)
            rows = cur.fetchall()
            print(f"Latest {len(rows)} Failure Autopsies:")
            for r in rows:
                print(f"  {r[9]} | {r[0]} | Code: {r[1]} | PnL: ${r[2]:.4f} | CounterTrend: {r[3]} (Slope: {r[4]:.4f}) | DoubleWick: {r[5]} (Ratio: {r[6]:.2f}) | Salvageable: {r[7]} | TwapPin: {r[8]}")
        conn.close()
    except Exception as e:
        print(f"SQLite error {db_path_str}: {e}")


def check_dof_patches() -> None:
    p = Path("data/active_dof_patches.json")
    if p.exists():
        print("=" * 70)
        print("[ACTIVE DoF PATCHES ON DISK]")
        data = json.loads(p.read_text(encoding="utf-8"))
        for asset in ["ETH", "BTC"]:
            active = [k for k, v in data.get(asset, {}).items() if v.get("active")]
            print(f"  {asset}: Active Patches = {active}")


if __name__ == "__main__":
    audit("ETH REPORTS", "data/eth_win_loss_reports.json")
    audit("BTC REPORTS", "data/win_loss_reports.json")
    check_sqlite("data/kalshi_history.db")
    check_sqlite("data/kalshi_history_eth.db")
    check_dof_patches()

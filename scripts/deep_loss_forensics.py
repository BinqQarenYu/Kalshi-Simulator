"""Deep forensics on recent losses on AWS."""
import json
from decimal import Decimal
from pathlib import Path

root = Path(__file__).resolve().parent.parent
eth_path = root / "data" / "eth_win_loss_reports.json"

if eth_path.exists():
    data = json.loads(eth_path.read_text(encoding="utf-8"))
    print("=== RECENT 12 TRADES DETAILED FORENSICS ===")
    for i, t in enumerate(data[:12]):
        ticker = t.get("ticker", "UNKNOWN")
        side = t.get("decision_side") or t.get("bot_side") or t.get("side", "N/A")
        outcome = t.get("outcome", "N/A")
        pnl = t.get("pnl", "0.00")
        diff = t.get("spot_diff") or t.get("entry_spot_diff", "N/A")
        tau = t.get("entry_tau_s") or t.get("time_to_expiry_s", "N/A")
        price = t.get("entry_price", "N/A")
        vpin = t.get("vpin") or t.get("vpin_score", "N/A")
        regime = t.get("regime") or t.get("wave_region", "N/A")
        hour_et = t.get("session_hour_et", "N/A")
        ts = t.get("timestamp_utc") or t.get("cycle_time", "N/A")
        print(f"[{i+1}] {ticker} | {side.upper()} | {outcome.upper()} | PnL: ${pnl} | Price: ${price}")
        print(f"     Moat: ${diff} | Tau: {tau}s | VPIN: {vpin} | Regime: {regime} | HourET: {hour_et} | Time: {ts}")

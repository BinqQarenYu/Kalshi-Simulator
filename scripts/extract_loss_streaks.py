"""Extract all loss streaks of length >= 5 from historical trade logs on AWS."""
import json
from decimal import Decimal
from pathlib import Path
from datetime import datetime

root = Path(__file__).resolve().parent.parent

for name, rel_path in [
    ("BTC", "data/win_loss_reports.json"),
    ("ETH", "data/eth_win_loss_reports.json"),
]:
    p = root / rel_path
    if not p.exists():
        continue
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue

        # Sort chronological if needed, but data is usually reverse-chronological (newest first)
        # Let's inspect order:
        trades = list(reversed(data)) # Chronological: oldest to newest

        loss_streaks = []
        current_streak = []

        for t in trades:
            outcome = str(t.get("outcome", "")).lower()
            if outcome == "loss":
                current_streak.append(t)
            elif outcome == "win":
                if len(current_streak) >= 5:
                    loss_streaks.append(current_streak)
                current_streak = []

        if len(current_streak) >= 5:
            loss_streaks.append(current_streak)

        print(f"============================================================")
        print(f"  {name} AUDIT: FOUND {len(loss_streaks)} STREAKS OF 5+ LOSSES")
        print(f"============================================================")

        for s_idx, streak in enumerate(loss_streaks):
            streak_pnl = sum((Decimal(str(x.get("pnl", "0.00"))) for x in streak), Decimal("0.00"))
            print(f"\n--- Streak #{s_idx + 1}: {len(streak)} Consecutive Losses | Total PnL: ${streak_pnl} ---")
            for t in streak:
                ticker = t.get("ticker", "UNKNOWN")
                side = t.get("decision_side") or t.get("bot_side") or t.get("side", "N/A")
                pnl = t.get("pnl", "0.00")
                diff = t.get("spot_diff") or t.get("entry_spot_diff", "N/A")
                tau = t.get("entry_tau_s") or t.get("time_to_expiry_s", "N/A")
                price = t.get("entry_price", "N/A")
                vpin = t.get("vpin") or t.get("vpin_score", "N/A")
                ts = t.get("timestamp_utc") or t.get("cycle_time", "N/A")
                hour = t.get("session_hour_et", "N/A")
                regime = t.get("regime") or t.get("wave_region", "N/A")
                reason = t.get("first_failed_reason") or t.get("rationale", "")
                print(f"  {ticker} | Side: {str(side).upper():4s} | PnL: ${pnl} | Price: ${price} | Moat: ${diff} | Tau: {tau}s | HourET: {hour} | Time: {ts}")
    except Exception as e:
        print(f"Error processing {name}: {e}")

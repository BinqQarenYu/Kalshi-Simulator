"""Audit live trades and balance on AWS."""
import json
import os
from decimal import Decimal
from pathlib import Path

root = Path(__file__).resolve().parent.parent

for name, rel_path in [
    ("BTC", "data/win_loss_reports.json"),
    ("ETH", "data/eth_win_loss_reports.json")
]:
    p = root / rel_path
    if not p.exists():
        print(f"File not found: {p}")
        continue
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            print(f"Data in {rel_path} is not a list")
            continue
        recent = data[:15]
        wins = sum(1 for t in recent if t.get("outcome") == "win")
        losses = sum(1 for t in recent if t.get("outcome") == "loss")
        pnl = sum((Decimal(str(t.get("pnl", "0.00"))) for t in recent), Decimal("0.00"))
        print(f"=== {name} (Last {len(recent)} Trades in {rel_path}) ===")
        print(f"Total in file: {len(data)} | Recent Wins: {wins} | Losses: {losses} | PnL: ${pnl}")
        for t in recent[:10]:
            ticker = t.get("ticker", "N/A")
            side = t.get("bot_side") or t.get("side") or t.get("decision_side", "N/A")
            outcome = t.get("outcome", "N/A")
            tpnl = t.get("pnl", "0.00")
            ts = t.get("timestamp_utc") or t.get("cycle_time") or t.get("exit_time", "N/A")
            moat = t.get("spot_diff") or t.get("entry_spot_diff", "N/A")
            print(f"  {ticker} | Side: {side} | Outcome: {outcome} | PnL: ${tpnl} | Moat: {moat} | Time: {ts}")
    except Exception as e:
        print(f"Error reading {name}: {e}")

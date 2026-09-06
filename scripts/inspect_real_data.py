import json
from pathlib import Path
from datetime import datetime

data_dir = Path("data")

with open(data_dir / "win_loss_reports.json", "r", encoding="utf-8") as f:
    reports = json.load(f)

print(f"Total reports: {len(reports)}")
for idx, r in enumerate(reports[:5]):
    print(f"Report {idx}:")
    print(f"  Ticker: {r.get('ticker')}")
    print(f"  Cycle Time: {r.get('cycle_time')}")
    print(f"  Timestamp UTC: {r.get('timestamp_utc')}")
    print(f"  Strike: {r.get('strike_price')}")
    print(f"  Settlement BTC: {r.get('settlement_btc_price')}")
    print(f"  Bot Side: {r.get('bot_side')}")
    print(f"  Entry: {r.get('entry_price')}")
    print(f"  Contracts: {r.get('contracts')}")
    print(f"  Outcome: {r.get('outcome')}")
    print(f"  PnL: {r.get('pnl')}")
    print(f"  VPIN: {r.get('vpin_score')}")
    print(f"  EV Edge: {r.get('ev_edge')}")

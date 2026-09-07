import sqlite3
from pathlib import Path
from datetime import datetime
import json

print("=== 1. DB TRADES & SETTLEMENTS SINCE 05:00 UTC TODAY ===")
conn = sqlite3.connect("data/kalshi_history.db")
cursor = conn.cursor()

cursor.execute("SELECT id, trade_id, timestamp_utc, ticker, side, size, price, status, bot_type FROM trades WHERE timestamp_utc >= '2026-09-07T05:00:00'")
trades = cursor.fetchall()
print(f"Total trades since 05:00 UTC: {len(trades)}")
for t in trades:
    print(" ", t)

cursor.execute("SELECT id, settlement_id, timestamp_utc, ticker, side, size, entry_price, settlement_price, outcome, pnl, balance_after FROM settlements WHERE timestamp_utc >= '2026-09-07T05:00:00'")
settlements = cursor.fetchall()
print(f"\nTotal settlements since 05:00 UTC: {len(settlements)}")
for s in settlements:
    print(" ", s)

print("\n=== 2. STREAM FILES BETWEEN 05:00 AND 10:00 UTC TODAY ===")
data_dir = Path("data")
stream_files = sorted(list(data_dir.glob("stream_KXBTC15M-26SEP07*.jsonl")), key=lambda x: x.stat().st_mtime)
print(f"Total Sept 7 15M stream files: {len(stream_files)}")
for sf in stream_files:
    mtime = datetime.fromtimestamp(sf.stat().st_mtime)
    print(f"  {sf.name} ({sf.stat().st_size / (1024*1024):.1f} MB) - MTime: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

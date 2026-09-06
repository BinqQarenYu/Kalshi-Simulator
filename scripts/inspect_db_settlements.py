import sqlite3
import json
from pathlib import Path

conn = sqlite3.connect("data/kalshi_history.db")
c = conn.cursor()

settlements = c.execute("SELECT * FROM settlements").fetchall()
col_names = [d[0] for d in c.description]
print(f"Total settlements in DB: {len(settlements)}")
print("Columns:", col_names)

for s in settlements[:5]:
    row = dict(zip(col_names, s))
    print(row)

trades = c.execute("SELECT * FROM trades").fetchall()
t_cols = [d[0] for d in c.description]
print(f"\nTotal trades in DB: {len(trades)}")
print("Trades columns:", t_cols)
for t in trades[:3]:
    print(dict(zip(t_cols, t)))

conn.close()

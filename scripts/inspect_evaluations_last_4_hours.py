import sqlite3
from pathlib import Path
from datetime import datetime

conn = sqlite3.connect("data/kalshi_history.db")
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(ai_predictions)")
cols = [c[1] for c in cursor.fetchall()]
print("ai_predictions columns:", cols)

cursor.execute("SELECT COUNT(*) FROM ai_predictions WHERE timestamp_utc >= '2026-09-07T05:30:00'")
print("Predictions since 05:30 UTC:", cursor.fetchone()[0])

cursor.execute("SELECT ticker, spot_price, target_strike, recommended_side, rationale, timestamp_utc FROM ai_predictions WHERE timestamp_utc >= '2026-09-07T05:30:00' ORDER BY id DESC LIMIT 20")
rows = cursor.fetchall()
print(f"\nLast 20 predictions:")
for r in rows:
    diff = float(r[1]) - float(r[2]) if r[1] and r[2] else 0.0
    print(f"[{r[5]}] {r[0]} | Spot={r[1]} Strike={r[2]} Diff={diff:+.2f} | Rec={r[3]}")
    print(f"   Rationale: {r[4]}")

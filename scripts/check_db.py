import sqlite3
from pathlib import Path

for db_name in ["kalshi_history.db", "data/kalshi_history.db", "kalshi_sim.db", "data/kalshi_sim.db"]:
    p = Path(db_name)
    if not p.exists():
        continue
    try:
        conn = sqlite3.connect(p)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f"DB: {p} ({p.stat().st_size / 1024:.1f} KB)")
        for t in tables:
            cnt = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  Table '{t}': {cnt} rows")
        conn.close()
    except Exception as e:
        print(f"DB: {p} Error: {e}")

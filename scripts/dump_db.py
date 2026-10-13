import sqlite3
import json
import os

print("=== RECENT TRADES IN KALSHI_HISTORY.DB ===")
db_path = '/home/ec2-user/kalshi-bot/data/kalshi_history.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute('SELECT trade_id, ticker, side, size, price, timestamp_utc, execution_mode FROM trades ORDER BY timestamp_utc DESC LIMIT 20')
        for r in c.fetchall():
            print(r)
    except Exception as e:
        print("Trades query error:", e)

    print("\n=== RECENT SETTLEMENTS IN KALSHI_HISTORY.DB ===")
    try:
        c.execute('SELECT settlement_id, ticker, side, outcome, pnl, balance_after, timestamp_utc, execution_mode FROM settlements ORDER BY timestamp_utc DESC LIMIT 20')
        for r in c.fetchall():
            print(r)
    except Exception as e:
        print("Settlements query error:", e)
    conn.close()

print("\n=== CHECKING ACTIVE BOT CONFIG IN RUNNING LOGS ===")
EOF

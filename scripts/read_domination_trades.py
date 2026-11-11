import sqlite3

con = sqlite3.connect('data/kalshi_history.db')
cur = con.cursor()
rows = cur.execute("SELECT ticker, side, price, size, status, execution_mode, timestamp_utc FROM trades WHERE bot_type = '3_step_domination_bot' ORDER BY id DESC LIMIT 10").fetchall()
print("=== Latest 3_step_domination_bot Trades ===")
for r in rows:
    print(r)
con.close()

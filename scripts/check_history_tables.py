import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_eval_history.py
import sqlite3

con = sqlite3.connect('/home/ec2-user/kalshi-bot/data/kalshi_history.db')
cur = con.cursor()

# Check how many ai_predictions or trades occurred since Nov 7
rows = cur.execute("SELECT count(*) FROM trades WHERE timestamp_utc > '2026-11-04'").fetchone()[0]
print(f"Trades since Nov 4: {rows}")

latest_trades = cur.execute("SELECT trade_id, timestamp_utc, ticker, side, price, execution_mode FROM trades ORDER BY id DESC LIMIT 5").fetchall()
print("Latest trades in DB:")
for t in latest_trades:
    print(t)

# Check settlements
latest_settlements = cur.execute("SELECT settlement_id, timestamp_utc, ticker, outcome, pnl FROM settlements ORDER BY id DESC LIMIT 5").fetchall()
print("Latest settlements in DB:")
for s in latest_settlements:
    print(s)

con.close()
EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_eval_history.py
rm -f /home/ec2-user/kalshi-bot/inspect_eval_history.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_retention.py
import sqlite3
con = sqlite3.connect('/home/ec2-user/kalshi-bot/data/kalshi_history.db')
cur = con.cursor()
r1 = cur.execute("SELECT min(timestamp_utc), max(timestamp_utc), count(*) FROM equity_snapshots").fetchone()
print(f"equity_snapshots: min={r1[0]}, max={r1[1]}, count={r1[2]}")

r2 = cur.execute("SELECT min(timestamp_utc), max(timestamp_utc), count(*) FROM ai_predictions").fetchone()
print(f"ai_predictions: min={r2[0]}, max={r2[1]}, count={r2[2]}")

# Count how many equity snapshots are older than 7 days
cutoff_7d = "datetime('now', '-7 days')"
old_eq = cur.execute(f"SELECT count(*) FROM equity_snapshots WHERE timestamp_utc < {cutoff_7d}").fetchone()[0]
print(f"equity_snapshots older than 7 days: {old_eq}")

# Count ai predictions older than 7 days
old_ai = cur.execute(f"SELECT count(*) FROM ai_predictions WHERE timestamp_utc < {cutoff_7d}").fetchone()[0]
print(f"ai_predictions older than 7 days: {old_ai}")

con.close()
EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_retention.py
rm -f /home/ec2-user/kalshi-bot/inspect_retention.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
print("STDERR:", stderr.read().decode('utf-8', errors='replace'))
ssh.close()

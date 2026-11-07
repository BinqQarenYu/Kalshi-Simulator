import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

# 1. Vacuum DB after purging old snapshots and predictions (older than 7 days)
# Keeping ALL trades, settlements, forensices, autopsies, lessons, brains.
cmd_clean_db = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/prune_db_bloat.py
import sqlite3
import os

db_path = '/home/ec2-user/kalshi-bot/data/kalshi_history.db'
size_before = os.path.getsize(db_path) / (1024 * 1024)
print(f"kalshi_history.db size before: {size_before:.2f} MB")

con = sqlite3.connect(db_path)
cur = con.cursor()

# Prune equity_snapshots older than 7 days
cur.execute("DELETE FROM equity_snapshots WHERE timestamp_utc < datetime('now', '-7 days')")
deleted_eq = cur.rowcount
print(f"Deleted {deleted_eq} old equity snapshots (>7d old)")

# Prune ai_predictions older than 7 days
cur.execute("DELETE FROM ai_predictions WHERE timestamp_utc < datetime('now', '-7 days')")
deleted_ai = cur.rowcount
print(f"Deleted {deleted_ai} old ai predictions (>7d old)")

con.commit()
print("Running VACUUM...")
cur.execute("VACUUM")
con.close()

size_after = os.path.getsize(db_path) / (1024 * 1024)
print(f"kalshi_history.db size after VACUUM: {size_after:.2f} MB (Reclaimed: {size_before - size_after:.2f} MB)")
EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/prune_db_bloat.py
rm -f /home/ec2-user/kalshi-bot/prune_db_bloat.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd_clean_db)
print("DB PRUNE OUTPUT:\n", stdout.read().decode('utf-8', errors='replace'))
print("DB PRUNE STDERR:\n", stderr.read().decode('utf-8', errors='replace'))
ssh.close()

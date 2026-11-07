import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_equity.py
import sqlite3
con = sqlite3.connect('/home/ec2-user/kalshi-bot/data/kalshi_history.db')
cur = con.cursor()
row = cur.execute("SELECT min(timestamp), max(timestamp), count(*) FROM equity_snapshots").fetchone()
print(f"Equity snapshots: min_ts={row[0]}, max_ts={row[1]}, total={row[2]}")

row2 = cur.execute("SELECT min(timestamp), max(timestamp), count(*) FROM ai_predictions").fetchone()
print(f"AI predictions: min_ts={row2[0]}, max_ts={row2[1]}, total={row2[2]}")

con.close()
EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_equity.py
rm -f /home/ec2-user/kalshi-bot/inspect_equity.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
print("STDERR:", stderr.read().decode('utf-8', errors='replace'))
ssh.close()

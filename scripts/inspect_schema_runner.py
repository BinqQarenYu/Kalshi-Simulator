import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_schema.py
import sqlite3
con = sqlite3.connect('/home/ec2-user/kalshi-bot/data/kalshi_history.db')
cur = con.cursor()
for table in ['equity_snapshots', 'ai_predictions', 'trades', 'settlements']:
    cols = [col[1] for col in cur.execute(f"PRAGMA table_info({table})").fetchall()]
    print(f"{table} columns: {cols}")
    sample = cur.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 1").fetchone()
    print(f"Latest row in {table}: {sample}")
con.close()
EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_schema.py
rm -f /home/ec2-user/kalshi-bot/inspect_schema.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
print("STDERR:", stderr.read().decode('utf-8', errors='replace'))
ssh.close()

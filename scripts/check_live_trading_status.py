import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
echo "=== 1. SERVICE STATUS & UPTIME ==="
sudo systemctl status kalshi-bot.service --no-pager

echo "=== 2. MEMORY & DISK USAGE ==="
free -h
df -h /

echo "=== 3. RECENT LOGS (LAST 30 LINES) ==="
journalctl -u kalshi-bot.service -n 30 --no-pager

echo "=== 4. LIVE / PAPER TRADES IN DATABASE (LAST 10) ==="
/home/ec2-user/kalshi-bot/venv/bin/python -c "
import sqlite3
con = sqlite3.connect('/home/ec2-user/kalshi-bot/data/kalshi_history.db')
cur = con.cursor()
trades = cur.execute('SELECT trade_id, timestamp_utc, ticker, side, price, size, execution_mode, status FROM trades ORDER BY id DESC LIMIT 10').fetchall()
print(f'Total trades in DB: {cur.execute(\"SELECT count(*) FROM trades\").fetchone()[0]}')
for t in trades:
    print(t)
con.close()
"
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
if err.strip():
    print("STDERR:", err.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

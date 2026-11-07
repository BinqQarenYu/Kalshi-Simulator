import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = """
echo "=== PYTHON / PIP CACHES ==="
du -sh /home/ec2-user/.cache/* 2>/dev/null
echo "=== TMP DIR ==="
ls -lah /tmp
echo "=== KALSHI HISTORY DB TABLES ==="
python3 -c "
import sqlite3
con = sqlite3.connect('/home/ec2-user/kalshi-bot/data/kalshi_history.db')
cur = con.cursor()
tables = [row[0] for row in cur.execute(\"SELECT name FROM sqlite_master WHERE type='table';\").fetchall()]
for t in tables:
    count = cur.execute(f'SELECT count(*) FROM {t}').fetchone()[0]
    print(f'Table {t}: {count} rows')
con.close()
"
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
ssh.close()

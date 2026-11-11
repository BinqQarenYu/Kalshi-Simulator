import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
echo "=== 1. UPTIME & SERVICE STATUS ==="
uptime
sudo systemctl status kalshi-bot.service --no-pager

echo "=== 2. LATEST 50 LOG LINES ==="
journalctl -u kalshi-bot.service -n 50 --no-pager

echo "=== 3. CHECK ORDER ATTEMPTS / PLACEMENT IN RECENT LOGS ==="
journalctl -u kalshi-bot.service --since "2 hours ago" | grep -iE "order|trade|eval|signal|veto|skip|placed|placing|reject" | tail -n 30
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
if err.strip():
    print("STDERR:", err.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

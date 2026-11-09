import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
echo "=== 1. SYSTEM UPTIME & SYSTEMCTL STATUS ==="
uptime
sudo systemctl status kalshi-bot.service --no-pager

echo "=== 2. MEMORY & DISK USAGE ==="
free -h
df -h /

echo "=== 3. LAST 40 LINES OF SERVICE JOURNAL ==="
journalctl -u kalshi-bot.service -n 40 --no-pager

echo "=== 4. ANY ERRORS IN JOURNAL (LAST 2 DAYS) ==="
journalctl -u kalshi-bot.service --since "2 days ago" -p err --no-pager | tail -n 30
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
if err.strip():
    print("STDERR:", err.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

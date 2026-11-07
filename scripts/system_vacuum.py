import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
echo "=== JOURNAL DISK USAGE BEFORE ==="
sudo journalctl --disk-usage

echo "=== VACUUMING JOURNAL LOGS ==="
sudo journalctl --vacuum-size=50M
sudo journalctl --vacuum-time=3d

echo "=== JOURNAL DISK USAGE AFTER ==="
sudo journalctl --disk-usage

echo "=== PURGING PIP CACHE AND PYTEST CACHE ==="
rm -rf /home/ec2-user/.cache/pip
rm -rf /home/ec2-user/.pytest_cache
find /home/ec2-user/kalshi-bot -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
rm -f /home/ec2-user/kalshi-bot/out.txt
rm -rf /tmp/torchinductor* /tmp/.ses

echo "=== CHECK DISK SPACE AFTER SYSTEM PURGE ==="
df -h /
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
print("STDERR:", stderr.read().decode('utf-8', errors='replace'))
ssh.close()

import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = """
echo "=== DISK USAGE ==="
df -h
echo "=== RAM USAGE ==="
free -h
echo "=== SYSTEM VIRTUAL MEM / SWAP ==="
swapon --show
echo "=== APP DIRECTORY USAGE ==="
du -sh /home/ec2-user/kalshi-bot/* 2>/dev/null | sort -hr | head -n 30
echo "=== HOME DIRECTORY USAGE ==="
du -sh /home/ec2-user/.* 2>/dev/null | sort -hr | head -n 15
echo "=== LOGS / DUMPS / TEMPS ==="
find /home/ec2-user -name "*.log" -o -name "*.dump" -o -name "*.tmp" -o -name "*.pyc" -o -name "__pycache__" -o -name "*.bak" | head -n 30
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
ssh.close()

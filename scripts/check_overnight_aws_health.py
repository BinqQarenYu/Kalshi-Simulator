import subprocess
import json

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

cmd = [
    'ssh', '-i', key_path,
    '-o', 'StrictHostKeyChecking=no',
    host,
    'free -m; uptime; systemctl status kalshi-bot.service --no-pager | head -n 12'
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
print("=== AWS EC2 OVERNIGHT HEALTH ===")
print(res.stdout.decode('utf-8', errors='ignore').encode('ascii', errors='replace').decode('ascii'))

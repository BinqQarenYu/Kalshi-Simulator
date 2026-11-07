import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

cmd = [
    'ssh', '-i', key_path,
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'ConnectTimeout=10',
    host,
    'uptime; df -h; free -m; systemctl status kalshi-bot.service --no-pager | head -n 12'
]
try:
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    print("=== AWS EC2 REACHABILITY & SYSTEM STATUS ===")
    print(res.stdout.decode('utf-8', errors='ignore').encode('ascii', errors='replace').decode('ascii'))
except Exception as e:
    print("Error connecting to EC2:", e)

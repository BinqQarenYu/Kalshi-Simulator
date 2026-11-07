import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

cmd = [
    'ssh', '-i', key_path,
    '-o', 'StrictHostKeyChecking=no',
    host,
    'uptime; systemctl status kalshi-bot.service --no-pager | head -n 15'
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
print("=== SERVICE STATUS ===")
print(res.stdout.decode('utf-8', errors='ignore').encode('ascii', errors='replace').decode('ascii'))

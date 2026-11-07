import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

cmd = [
    'ssh', '-i', key_path,
    '-o', 'StrictHostKeyChecking=no',
    host,
    'journalctl -u kalshi-bot.service --since "8 hours ago" --no-pager | grep -iE "ORDER EXECUTED|DYNAMIC REGIME SIGNAL|LIVE ORDER|KXBTC|KXETH" | tail -n 30'
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
text = res.stdout.decode('utf-8', errors='ignore')
for line in text.splitlines():
    print(line.encode('ascii', errors='replace').decode('ascii'))

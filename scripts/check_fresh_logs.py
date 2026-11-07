import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

cmd = [
    'ssh', '-i', key_path,
    '-o', 'StrictHostKeyChecking=no',
    host,
    'sleep 5; journalctl -u kalshi-bot.service -n 25 --no-pager'
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
text = res.stdout.decode('utf-8', errors='ignore')
print("=== FRESH LOGS AFTER RESTART ===")
for line in text.splitlines():
    print(line.encode('ascii', errors='replace').decode('ascii'))

import subprocess

cmd = [
    'ssh', '-i', 'kalshi_aws_key.pem',
    '-o', 'StrictHostKeyChecking=no',
    'ec2-user@13.63.158.94',
    'journalctl -u kalshi-bot.service --since "12 hours ago" | grep -i "is stale"'
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
print("STALE LOGS:")
print(res.stdout.decode('utf-8', errors='ignore'))

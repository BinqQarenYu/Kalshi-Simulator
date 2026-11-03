import subprocess

cmd = [
    'ssh', '-i', 'kalshi_aws_key.pem',
    '-o', 'StrictHostKeyChecking=no',
    'ec2-user@13.63.158.94',
    'journalctl -u kalshi-bot.service -n 120 --no-pager'
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
stdout_text = res.stdout.decode('utf-8', errors='ignore')
for line in stdout_text.splitlines():
    if any(k in line.lower() for k in ["best known", "loaded baseline", "promoted", "stale", "retention"]):
        print(line.encode('ascii', errors='replace').decode('ascii'))

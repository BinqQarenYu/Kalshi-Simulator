import subprocess

cmd = [
    'ssh', '-i', 'kalshi_aws_key.pem',
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'ConnectTimeout=10',
    'ec2-user@13.63.158.94',
    'journalctl -u kalshi-bot.service -b | grep -i "best known" | tail -n 15'
]
res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)

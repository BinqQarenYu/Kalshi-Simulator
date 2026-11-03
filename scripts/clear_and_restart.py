import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

cmd = [
    'ssh', '-i', key_path,
    '-o', 'StrictHostKeyChecking=no',
    host,
    'sudo kill -9 1640236 2>/dev/null; sudo systemctl restart kalshi-bot.service; sleep 2; systemctl status kalshi-bot.service --no-pager'
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
print(res.stdout.decode('utf-8', errors='ignore').encode('ascii', errors='replace').decode('ascii'))

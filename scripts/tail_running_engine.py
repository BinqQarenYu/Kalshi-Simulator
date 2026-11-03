import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

cmd = [
    'ssh', '-i', key_path,
    '-o', 'StrictHostKeyChecking=no',
    host,
    'sleep 10; journalctl -u kalshi-bot.service -n 15 --no-pager'
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
text = res.stdout.decode('utf-8', errors='ignore')
for line in text.splitlines():
    print(line.encode('ascii', errors='replace').decode('ascii'))

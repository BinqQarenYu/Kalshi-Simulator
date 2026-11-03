import subprocess

cmd = [
    'ssh', '-i', 'kalshi_aws_key.pem',
    '-o', 'StrictHostKeyChecking=no',
    'ec2-user@13.63.158.94',
    'journalctl -u kalshi-bot.service -n 600 --no-pager | grep "CONTINUOUS EVAL"'
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
text = res.stdout.decode('utf-8', errors='ignore')
for line in text.splitlines():
    print(line.encode('ascii', errors='replace').decode('ascii'))

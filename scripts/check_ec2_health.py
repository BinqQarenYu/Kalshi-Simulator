import subprocess

cmd = [
    'ssh', '-i', 'kalshi_aws_key.pem',
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'ConnectTimeout=15',
    'ec2-user@13.63.158.94',
    'systemctl status kalshi-bot.service --no-pager'
]
try:
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
    print("STDOUT:")
    print(res.stdout.decode('utf-8', errors='ignore').encode('ascii', errors='replace').decode('ascii'))
    print("STDERR:")
    print(res.stderr.decode('utf-8', errors='ignore').encode('ascii', errors='replace').decode('ascii'))
except Exception as e:
    print("Error:", e)

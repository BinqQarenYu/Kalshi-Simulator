import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

cmd = [
    'ssh', '-i', key_path,
    '-o', 'StrictHostKeyChecking=no',
    host,
    'df -h; ls -la /tmp | head -n 25; find /tmp -maxdepth 1 -name "tmp*" | wc -l'
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
print(res.stdout.decode('utf-8', errors='ignore'))

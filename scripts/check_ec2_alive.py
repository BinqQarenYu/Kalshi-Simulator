import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

cmd = [
    'ssh', '-i', key_path,
    '-o', 'StrictHostKeyChecking=no',
    host,
    'uptime; ps aux | grep -E "python|kalshi" | head -n 10'
]
try:
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=12)
    print("STDOUT:")
    print(res.stdout.decode('utf-8', errors='ignore'))
except Exception as e:
    print("Error:", e)

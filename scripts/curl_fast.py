import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

cmd = [
    'ssh', '-i', key_path,
    '-o', 'StrictHostKeyChecking=no',
    host,
    'curl -m 3 -s http://127.0.0.1:8000/api/state'
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
print("STDOUT LEN:", len(res.stdout))
print("STDOUT HEAD:", res.stdout[:200])
print("STDERR:", res.stderr)

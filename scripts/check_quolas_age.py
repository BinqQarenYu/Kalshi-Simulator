import subprocess

cmd = [
    'ssh', '-i', 'kalshi_aws_key.pem',
    '-o', 'StrictHostKeyChecking=no',
    'ec2-user@13.63.158.94',
    'python3 -c "import time, os; st = os.stat(\x27/home/ec2-user/kalshi-bot/models/quolas.onnx\x27); print(\x27mtime:\x27, st.st_mtime, \x27age_s:\x27, time.time() - st.st_mtime)"'
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
print(res.stdout.decode('utf-8', errors='ignore'))
print(res.stderr.decode('utf-8', errors='ignore'))

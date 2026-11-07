import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def scp_file(local_path, remote_path):
    cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-i", key_path, str(local_path), f"{host}:{remote_path}"]
    res = subprocess.run(cmd, capture_output=True, timeout=30)
    return res.returncode == 0

def run_ssh(remote_cmd, timeout=30):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True, timeout=timeout)
    return res.stdout.decode("utf-8", errors="ignore").strip()

print("1. Uploading fixed onnx_engine.py with import sys...")
scp_file("src/kalshi_sim/ml/onnx_engine.py", "/home/ec2-user/kalshi-bot/src/kalshi_sim/ml/onnx_engine.py")

print("2. Restarting kalshi-bot.service on AWS...")
run_ssh("sudo systemctl restart kalshi-bot.service")

print("3. Sleeping 5 seconds and checking logs...")
import time
time.sleep(5)
logs = run_ssh("journalctl -u kalshi-bot.service -n 25 --no-pager")
for line in logs.splitlines():
    print(line.encode("ascii", errors="replace").decode("ascii"))

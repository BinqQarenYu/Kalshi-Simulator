import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd, timeout=30):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True, timeout=timeout)
    return res.stdout.decode("utf-8", errors="ignore").strip()

def scp_file(local_path, remote_path):
    cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-i", key_path, str(local_path), f"{host}:{remote_path}"]
    res = subprocess.run(cmd, capture_output=True, timeout=30)
    return res.returncode == 0

print("1. Cleaning up leaked tmp directories in /tmp on AWS...")
run_ssh("sudo find /tmp -maxdepth 1 -name 'tmp*' -exec rm -rf {} + 2>/dev/null || true")

print("2. Checking disk space in /tmp...")
df_out = run_ssh("df -h /tmp")
print(df_out)

print("3. Uploading patched onnx_engine.py...")
scp_file("src/kalshi_sim/ml/onnx_engine.py", "/home/ec2-user/kalshi-bot/src/kalshi_sim/ml/onnx_engine.py")

print("4. Restarting kalshi-bot.service on AWS...")
run_ssh("sudo systemctl restart kalshi-bot.service")

print("5. Verifying service status...")
status = run_ssh("systemctl status kalshi-bot.service --no-pager")
for line in status.splitlines()[:15]:
    print(line.encode("ascii", errors="replace").decode("ascii"))

import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    stdout = res.stdout.decode("utf-8", errors="ignore").strip()
    stderr = res.stderr.decode("utf-8", errors="ignore").strip()
    return stdout, stderr

print("Restarting Mother Server daemon...")
stdout, stderr = run_ssh("sudo systemctl restart kalshi-bot.service; sleep 3; systemctl status kalshi-bot.service --no-pager | head -n 15")
print(stdout)

print("\nChecking Memory (free -m)...")
stdout, stderr = run_ssh("free -m")
print(stdout)

print("\nChecking Log size...")
stdout, stderr = run_ssh("ls -lh /home/ec2-user/kalshi-bot/aws/logs/onnx_reload.log")
print(stdout)

print("\nQuerying API State...")
stdout, stderr = run_ssh("curl -s http://127.0.0.1:8000/api/state | head -c 250")
print(stdout)

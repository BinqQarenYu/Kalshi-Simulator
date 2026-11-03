import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def safe_print(title, text):
    clean = text.encode("ascii", errors="replace").decode("ascii")
    print(f"=== {title} ===\n{clean}\n")

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    stdout = res.stdout.decode("utf-8", errors="ignore").strip()
    stderr = res.stderr.decode("utf-8", errors="ignore").strip()
    return stdout, stderr

out, _ = run_ssh("systemctl status kalshi-bot.service --no-pager | head -n 12")
safe_print("Mother Service Status", out)

out, _ = run_ssh("free -m")
safe_print("Memory (free -m)", out)

out, _ = run_ssh("ls -lh /home/ec2-user/kalshi-bot/aws/logs/onnx_reload.log")
safe_print("Log Size", out)

out, _ = run_ssh("curl -s http://127.0.0.1:8000/api/state | head -c 250")
safe_print("Mother Service API Telemetry", out)

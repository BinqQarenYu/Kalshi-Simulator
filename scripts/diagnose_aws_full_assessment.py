import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def safe_print(title, text):
    clean = text.encode("ascii", errors="replace").decode("ascii")
    print(f"=== {title} ===\n{clean}\n")

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip()

# 1. Systemd service status
out = run_ssh("systemctl status kalshi-bot.service --no-pager | head -n 25")
safe_print("Kalshi-Bot Service Status", out)

# 2. System resources (RAM, CPU, Swap)
out = run_ssh("free -m; uptime")
safe_print("Memory & Uptime", out)

# 3. Disk space & Log files
out = run_ssh("df -h /; ls -lh /home/ec2-user/kalshi-bot/aws/logs/; ls -lh /home/ec2-user/kalshi-bot/quolas_24_7.log*")
safe_print("Disk & Log File Sizes", out)

# 4. API state & health
out = run_ssh("curl -s http://127.0.0.1:8000/api/health; echo ''; curl -s http://127.0.0.1:8000/api/state | head -c 400")
safe_print("Health & Telemetry Snapshot", out)

# 5. Recent journalctl logs (check why orders aren't firing)
out = run_ssh("journalctl -u kalshi-bot.service -n 50 --no-pager")
safe_print("Recent 50 Service Log Lines", out)

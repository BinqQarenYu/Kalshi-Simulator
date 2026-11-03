import subprocess, json

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def safe_print(title, text):
    clean = text.encode("ascii", errors="replace").decode("ascii")
    print(f"=== {title} ===\n{clean}\n")

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip()

# 1. Systemd uptime and process
out = run_ssh("systemctl status kalshi-bot.service --no-pager | head -n 15")
safe_print("Service Uptime & Status", out)

# 2. RAM and swap (Anti-bloat audit)
out = run_ssh("free -m; uptime")
safe_print("Memory & Load", out)

# 3. Log file sizes
out = run_ssh("ls -lh /home/ec2-user/kalshi-bot/aws/logs/; ls -lh /home/ec2-user/kalshi-bot/quolas_24_7.log*")
safe_print("Log Sizes", out)

# 4. Check all recent trades/orders on AWS since our deploy (~9 hours ago)
out = run_ssh("journalctl -u kalshi-bot.service -n 2000 --no-pager | grep -iE 'SIGNAL|ORDER|TRADE|FILL|SETTLEMENT|EVAL' | tail -n 40")
safe_print("Recent Trading Activity / Evaluations", out)

# 5. Check if any trades were recorded in JSON files on AWS
out = run_ssh("ls -lt /home/ec2-user/kalshi-bot/data/*win_loss* /home/ec2-user/kalshi-bot/data/*supervisor*")
safe_print("Data files on AWS", out)

# 6. Check BNB reports on AWS vs Local
out = run_ssh("wc -l /home/ec2-user/kalshi-bot/data/bnb_win_loss_reports.json 2>/dev/null || echo 'No BNB file on AWS'")
safe_print("BNB file on AWS", out)

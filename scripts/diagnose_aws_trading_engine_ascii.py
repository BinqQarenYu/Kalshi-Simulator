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

out = run_ssh("journalctl -u kalshi-bot.service -n 120 --no-pager | grep -E 'TRADE|ORDER|EVAL|GATE|SKIP|V4|DISQUALIFIED|REJECT|QUALIFIED|INSPECTOR|SIGNAL'")
safe_print("Filtered Logs", out)

out = run_ssh("ps aux | grep python")
safe_print("Running Python Processes", out)

out = run_ssh("cat /home/ec2-user/kalshi-bot/aws_headless_daemon.py | head -n 45")
safe_print("Head of aws_headless_daemon.py", out)

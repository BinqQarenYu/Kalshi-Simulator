import subprocess, json

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip()

print("=== CHECKING AWS ENVIRONMENT & LIVE TRADING STATE ===")
out = run_ssh("cat /home/ec2-user/kalshi-bot/.env | grep -E 'DRY_RUN|SIMULATION|TRADING_ENABLED|LIVE|ENV'")
print(".env flags:\n", out)

out = run_ssh("cat /home/ec2-user/kalshi-bot/data/bot_parameters_domination.json | grep -E 'is_armed|brain_priority_mode|min_confidence'")
print("Domination armed state:\n", out)

out = run_ssh("curl -s http://127.0.0.1:8000/api/state | head -c 500")
print("API state:\n", out)

out = run_ssh("journalctl -u kalshi-bot.service -n 25 --no-pager")
clean_logs = out.encode("ascii", errors="replace").decode("ascii")
print("Recent logs:\n", clean_logs)

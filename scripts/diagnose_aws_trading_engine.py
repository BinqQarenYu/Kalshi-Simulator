import subprocess, json

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip()

print("=== CHECKING V4_TELEMETRY IN DAEMON ===")
out = run_ssh("cat /home/ec2-user/kalshi-bot/aws_headless_daemon.py | grep -n -C 5 'v4_telemetry'")
print(out[:1000])

print("=== CHECKING TRADING ENGINE IN DAEMON ===")
out = run_ssh("cat /home/ec2-user/kalshi-bot/aws_headless_daemon.py | grep -n -E 'engine|bot1_v4|DynamicRegime|is_armed|execute_order|send_order'")
print(out[:1000])

print("=== CHECKING RECENT EXECUTIONS OR GATES ===")
out = run_ssh("journalctl -u kalshi-bot.service -n 100 --no-pager | grep -E 'TRADE|ORDER|EVAL|GATE|SKIP|V4|DISQUALIFIED|REJECT|QUALIFIED'")
print(out[-1000:] if len(out) > 1000 else out)

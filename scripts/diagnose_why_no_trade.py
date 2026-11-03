import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True, timeout=25)
    return res.stdout.decode("utf-8", errors="ignore").strip()

out1 = run_ssh("cat /home/ec2-user/kalshi-bot/data/bot_parameters_domination.json")
print("=== DOMINATION PARAMS ===")
print(out1[:1000])

out2 = run_ssh("journalctl -u kalshi-bot.service -n 200 --no-pager")
print("=== RECENT LOGS ===")
for line in out2.splitlines():
    if any(k in line.lower() for k in ["eval", "signal", "confidence", "skip", "veto", "order", "trade", "reject", "standby", "storm"]):
        print(line.encode("ascii", errors="replace").decode("ascii"))

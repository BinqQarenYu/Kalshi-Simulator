import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True, timeout=25)
    return res.stdout.decode("utf-8", errors="ignore").strip()

out = run_ssh("journalctl -u kalshi-bot.service --since '30 minutes ago' --no-pager")
lines = out.splitlines()
print(f"Total lines in last 30m: {len(lines)}")
for line in lines[-40:]:
    print(line.encode("ascii", errors="replace").decode("ascii"))

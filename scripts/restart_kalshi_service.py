import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd, timeout=15):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True, timeout=timeout)
    return res.stdout.decode("utf-8", errors="ignore").strip()

print("Restarting kalshi-bot.service...")
out = run_ssh("sudo systemctl restart kalshi-bot.service", timeout=15)
print("Restart output:", out)

print("Checking systemctl status...")
status = run_ssh("systemctl status kalshi-bot.service --no-pager", timeout=15)
for line in status.splitlines()[:15]:
    print(line.encode("ascii", errors="replace").decode("ascii"))

import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip()

out = run_ssh("journalctl -u kalshi-bot.service -n 45 --no-pager")
clean = out.encode("ascii", errors="replace").decode("ascii")
print("Latest Logs from AWS:\n", clean)

import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip()

out = run_ssh('journalctl -u kalshi-bot.service -n 500 --no-pager | grep -F "SNAPSHOT" | tail -n 25')
clean = out.encode("ascii", errors="replace").decode("ascii")
print("Recent snapshots on AWS:\n", clean)

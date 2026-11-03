import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip(), res.stderr.decode("utf-8", errors="ignore").strip()

out, err = run_ssh("cat /home/ec2-user/kalshi-bot/aws_headless_daemon.py")
with open("aws_daemon_code.py", "w", encoding="utf-8") as f:
    f.write(out)

print(f"Downloaded aws_headless_daemon.py ({len(out)} bytes)")
print("First 30 lines:\n", "\n".join(out.splitlines()[:30]))

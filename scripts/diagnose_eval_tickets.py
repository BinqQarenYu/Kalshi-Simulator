import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True, timeout=25)
    return res.stdout.decode("utf-8", errors="ignore").strip()

out = run_ssh("journalctl -u kalshi-bot.service -n 5000 --no-pager | grep -iE 'evaluate|ticket|entry|qualif|standby|rejected|gate' | tail -n 35")
for line in out.splitlines():
    print(line.encode("ascii", errors="replace").decode("ascii"))

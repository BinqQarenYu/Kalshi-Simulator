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

out = run_ssh("journalctl -u kalshi-bot.service -n 1500 --no-pager | grep -iE 'trade|order|evaluated|standing down|disqualified|skipping|brier|streak' | tail -n 35")
safe_print("Trading activity or stand-down reasons", out)

out = run_ssh("cat /home/ec2-user/kalshi-bot/data/active_dof_patches.json")
safe_print("Active DOF Patches", out)

out = run_ssh("cat /home/ec2-user/kalshi-bot/data/kalshi_maintenance.json")
safe_print("Maintenance state", out)

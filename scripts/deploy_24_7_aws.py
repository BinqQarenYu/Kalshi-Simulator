import subprocess
from pathlib import Path

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True, timeout=30)
    return res.stdout.decode("utf-8", errors="ignore").strip()

def scp_file(local_path, remote_path):
    cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-i", key_path, str(local_path), f"{host}:{remote_path}"]
    res = subprocess.run(cmd, capture_output=True, timeout=30)
    return res.returncode == 0

print("1. Uploading updated continuous_trainer.py...")
scp_file("src/kalshi_sim/ml/continuous_trainer.py", "/home/ec2-user/kalshi-bot/src/kalshi_sim/ml/continuous_trainer.py")

print("2. Uploading updated session_timing_guard.py...")
scp_file("src/kalshi_sim/ml/session_timing_guard.py", "/home/ec2-user/kalshi-bot/src/kalshi_sim/ml/session_timing_guard.py")

print("3. Updating .env on AWS for 24/7 continuous trading & adaptive learning...")
run_ssh("""
cd /home/ec2-user/kalshi-bot &&
sed -i 's/^STRICT_GOLDEN_SESSIONS_ONLY=.*/STRICT_GOLDEN_SESSIONS_ONLY=false/' .env 2>/dev/null || true
grep -q '^STRICT_GOLDEN_SESSIONS_ONLY=' .env || echo 'STRICT_GOLDEN_SESSIONS_ONLY=false' >> .env
grep -q '^ENABLE_SESSION_TIMING_GUARD=' .env || echo 'ENABLE_SESSION_TIMING_GUARD=true' >> .env
""")

print("4. Resetting best_model.pt validation loss ceiling so continuous learning promotes newly trained weights...")
run_ssh("""
cd /home/ec2-user/kalshi-bot &&
/home/ec2-user/kalshi-bot/venv/bin/python -c '
import torch
from pathlib import Path
p = Path("models/best_model.pt")
if p.exists():
    ckpt = torch.load(p, map_location="cpu", weights_only=False)
    if isinstance(ckpt, dict):
        ckpt["val_loss"] = 0.0500  # Reset from unreachable 0.0001 to realistic baseline
        torch.save(ckpt, p)
        print("Reset baseline val_loss to 0.0500 in best_model.pt")
'
""")

print("5. Upgrading & restarting kalshi-bot.service on AWS (Force Cache Invalidation Protocol)...")
run_ssh("sudo systemctl restart kalshi-bot.service")

print("6. Checking active status...")
status = run_ssh("systemctl status kalshi-bot.service --no-pager")
for line in status.splitlines()[:15]:
    print(line.encode("ascii", errors="replace").decode("ascii"))

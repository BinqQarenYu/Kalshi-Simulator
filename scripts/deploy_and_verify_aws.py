import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip()

def run_scp(local_file, remote_file):
    full_cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-i", key_path, local_file, f"{host}:{remote_file}"]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip()

print("1. Uploading patched files to AWS...")
run_scp("src/kalshi_sim/server.py", "/home/ec2-user/kalshi-bot/src/kalshi_sim/server.py")
run_scp("src/kalshi_sim/ml/dynamic_regime_strategy.py", "/home/ec2-user/kalshi-bot/src/kalshi_sim/ml/dynamic_regime_strategy.py")

print("2. Restarting kalshi-bot service (Rule 6: Kick out the old)...")
run_ssh("sudo systemctl restart kalshi-bot.service; sleep 4")

print("3. Re-arming and selecting dynamic_trading_strategy...")
run_ssh('curl -s -X POST http://127.0.0.1:8000/api/settings -H "Content-Type: application/json" -d \'{"ai_auto_trade": true, "active_strategy_bot": "dynamic_trading_strategy"}\'')
run_ssh("curl -s -X POST http://127.0.0.1:8000/api/bot/arm")
run_ssh("curl -s -X POST http://127.0.0.1:8000/api/circuit-breaker/reset")

print("4. Inspecting status after update...")
out = run_ssh("journalctl -u kalshi-bot.service -n 25 --no-pager")
clean = out.encode("ascii", errors="replace").decode("ascii")
print(clean)

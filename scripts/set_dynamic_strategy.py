import subprocess, json

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip()

print("1. Selecting dynamic_trading_strategy via /api/settings...")
out = run_ssh('curl -s -X POST http://127.0.0.1:8000/api/settings -H "Content-Type: application/json" -d \'{"ai_auto_trade": true, "active_strategy_bot": "dynamic_trading_strategy"}\'')
print(out)

print("\n2. Arming bot...")
out = run_ssh("curl -s -X POST http://127.0.0.1:8000/api/bot/arm")
print(out)

print("\n3. Resetting circuit breaker...")
out = run_ssh("curl -s -X POST http://127.0.0.1:8000/api/circuit-breaker/reset")
print(out)

print("\n4. Checking state summary...")
out = run_ssh("curl -s http://127.0.0.1:8000/api/state | head -c 300")
print(out)

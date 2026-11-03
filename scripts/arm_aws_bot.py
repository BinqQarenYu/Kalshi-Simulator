import subprocess, json

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip()

print("1. Arming Bot...")
out = run_ssh("curl -s -X POST http://127.0.0.1:8000/api/bot/arm")
print("Response:", out)

print("\n2. Setting ai_auto_trade=True and active_strategy_bot=bot1_v4_domination...")
out = run_ssh('curl -s -X POST http://127.0.0.1:8000/api/settings -H "Content-Type: application/json" -d \'{"ai_auto_trade": true, "active_strategy_bot": "bot1_v4_domination"}\'')
print("Response:", out)

print("\n3. Verifying /api/state telemetry...")
out = run_ssh("curl -s http://127.0.0.1:8000/api/state")
try:
    d = json.loads(out)
    print("ai_auto_trade:", d.get("ai_auto_trade"))
    print("active_strategy_bot:", d.get("active_strategy_bot"))
    print("execution_mode:", d.get("execution_mode"))
    print("v4_telemetry:", d.get("v4_telemetry"))
except Exception as e:
    print("Parse error:", e, out[:200])

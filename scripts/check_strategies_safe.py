import subprocess, json

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip()

out = run_ssh("curl -s http://127.0.0.1:8000/api/bot/strategies")
try:
    data = json.loads(out)
    print("Active Strategy in strategies response:", data.get("active_strategy"))
    bots = data.get("strategies", [])
    print(f"Total strategies: {len(bots)}")
    for b in bots:
        print(" -", b.get("strategy_id"), "|", b.get("strategy_name"))
except Exception as e:
    print("Error:", e, out[:200])

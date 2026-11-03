import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True, timeout=25)
    return res.stdout.decode("utf-8", errors="ignore").strip()

out = run_ssh("""python3 -c '
import urllib.request, json
try:
    state = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/state").read().decode("utf-8"))
    print("ai_auto_trade:", state.get("ai_auto_trade"))
    print("active_strategy_bot:", state.get("active_strategy_bot"))
    print("active_ticker:", state.get("active_ticker"))
    print("active_timeframe:", state.get("active_timeframe"))
    print("mode:", state.get("mode"))
    print("connected_websockets:", state.get("connected_websockets"))
except Exception as e:
    print("Error:", e)
'""")
print(out)

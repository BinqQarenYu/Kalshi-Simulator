import subprocess, json

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip()

print("1. Fetching active ticker and orderbook from API...")
out = run_ssh("curl -s http://127.0.0.1:8000/api/state")
try:
    d = json.loads(out)
    m = d.get("market", {})
    print("Active Asset:", m.get("active_asset"))
    print("Active Ticker:", m.get("ticker"))
    print("Target Strike:", m.get("target_strike"))
    print("Spot Price:", m.get("current_btc_price"))
    print("Diff to Strike:", m.get("diff"))
    ob = d.get("orderbook", {})
    print("Yes Bid/Ask:", ob.get("yes_bid"), "/", ob.get("yes_ask"))
    print("No Bid/Ask:", ob.get("no_bid"), "/", ob.get("no_ask"))
except Exception as e:
    print("Error parsing /api/state:", e, out[:300])

print("\n2. Checking recent evaluation logs...")
out = run_ssh("journalctl -u kalshi-bot.service -n 500 --no-pager | grep -iE 'disqualif|eval|gate|skip|trade|order|veto' | tail -n 25")
clean = out.encode("ascii", errors="replace").decode("ascii")
print(clean)

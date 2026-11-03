import subprocess, json

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip()

print("1. Checking active_strategy_bot & ai_auto_trade on AWS...")
out = run_ssh('python3 -c "import json; from kalshi_sim.server import state; print(\'active_strategy_bot:\', state.active_strategy_bot, \'ai_auto_trade:\', state.ai_auto_trade, \'mode:\', state.mode)"')
print("State:", out)

print("\n2. Checking reason for NO trades in recent evaluations...")
out = run_ssh('journalctl -u kalshi-bot.service -n 1500 --no-pager | grep -iE "DYNAMIC REGIME|WAIT|DISQUALIFIED|VETO|SKIP|HOLDING OFF|GATE|BLACKOUT" | tail -n 30')
clean = out.encode("ascii", errors="replace").decode("ascii")
print("Reasons:", clean)

print("\n3. Inspecting active market and orderbook on AWS...")
out = run_ssh('curl -s http://127.0.0.1:8000/api/state')
try:
    d = json.loads(out)
    m = d.get("market", {})
    ob = d.get("orderbook", {})
    print("Market:", m.get("ticker"), "| Spot:", m.get("current_btc_price"), "| Strike:", m.get("target_strike"), "| Diff:", m.get("diff"))
    print("CLOB:", "best_yes_bid=", ob.get("best_yes_bid"), "best_yes_ask=", ob.get("best_yes_ask"), "spread=", ob.get("spread"))
except Exception as e:
    print("API state parse err:", e)

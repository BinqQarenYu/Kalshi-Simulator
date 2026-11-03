import subprocess
import json

cmd = [
    'ssh', '-i', 'kalshi_aws_key.pem',
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'ConnectTimeout=10',
    'ec2-user@13.63.158.94',
    'python3 -c "import urllib.request, json; print(urllib.request.urlopen(\x27http://127.0.0.1:8000/api/state\x27).read().decode(\x27utf-8\x27))"'
]
try:
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    data = json.loads(res.stdout.decode('utf-8', errors='ignore'))
    print("MODE:", data.get("mode"))
    print("AI_AUTO_TRADE:", data.get("ai_auto_trade"))
    print("ACTIVE_BOT:", data.get("active_strategy_bot"))
    print("BALANCE:", data.get("balance"))
    print("ACTIVE_ORDERS:", len(data.get("active_orders", [])))
    print("POSITIONS:", len(data.get("positions", [])))
    print("BOT_CERTIFIED:", data.get("bot_certified"))
    print("BOT_SEALED:", data.get("bot_sealed"))
    print("MARKET_ACTIVE_ASSET:", data.get("market", {}).get("active_asset"))
except Exception as e:
    print("Error:", e)

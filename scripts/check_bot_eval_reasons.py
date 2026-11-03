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

out = run_ssh("python3 -c \"
import json
with open('data/bot_parameters_domination.json') as f:
    d = json.load(f)
print('Domination keys:', list(d.keys()))
print('is_armed:', d.get('is_armed'))
print('BTC params:', d.get('assets', {}).get('BTC', {}))
with open('data/bot_parameters_eth.json') as f:
    e = json.load(f)
print('ETH params:', e.get('eth_bot1_v4', {}))
\"")
safe_print("Python Bot Parameters on AWS", out)

out = run_ssh("journalctl -u kalshi-bot.service -n 500 --no-pager | grep -iE 'disqualified|gate|filter|regime|streak' | tail -n 25")
safe_print("Recent gate decisions", out)

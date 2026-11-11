import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_after_load.py
import requests

r = requests.get('http://127.0.0.1:8000/api/state', timeout=5)
data = r.json()
print("Active Strategy Bot:", data.get("settings", {}).get("active_strategy_bot"))
print("Active Preset:", data.get("settings", {}).get("active_preset"))
print("AI Signals Strategy:", data.get("ai_signals", {}).get("strategy_id"))
print("Preflight Gates:", data.get("preflight_gates"))

r2 = requests.get('http://127.0.0.1:8000/api/bot/parameters', timeout=5)
d2 = r2.json()
print("Current discount_limit_price:", d2.get("limit_price_cents"))
print("Current min_spot_diff:", d2.get("volatility_moat_dollars"))
print("Current dynamic_moat_multiplier:", d2.get("dynamic_moat_multiplier"))
EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_after_load.py
rm -f /home/ec2-user/kalshi-bot/inspect_after_load.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

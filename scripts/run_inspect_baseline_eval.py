import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_baseline_eval.py
import requests

r = requests.get('http://127.0.0.1:8000/api/state', timeout=5)
data = r.json()
m = data.get("market")
print("=== LIVE STATE UNDER BASELINE V3.2 ===")
print("Active Strategy:", data.get("settings", {}).get("active_strategy_bot"))
print("Active Market Ticker:", m.get("ticker"))
print("Current Spot:", m.get("current_btc_price"))
print("Target Strike:", m.get("target_strike"))
print("Diff:", m.get("diff"), m.get("diff_str"))
print("Countdown to Expiry:", m.get("expiry_countdown_seconds"))
print("AI Signals:", data.get("ai_signals"))
print("Preflight Gates:", data.get("preflight_gates"))

EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_baseline_eval.py
rm -f /home/ec2-user/kalshi-bot/inspect_baseline_eval.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

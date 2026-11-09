import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_recent_regimes.py
import requests

try:
    r = requests.get('http://127.0.0.1:8000/api/state', timeout=5)
    data = r.json()
    m = data.get("market")
    print("Active Ticker:", m.get("ticker"))
    print("Target Strike:", m.get("target_strike"))
    print("Spot Price:", m.get("current_btc_price"))
    print("Diff:", m.get("diff"), m.get("diff_str"))
    print("Countdown:", m.get("expiry_countdown_seconds"))
    print("Best Yes Bid/Ask:", m.get("best_yes_bid"), m.get("best_yes_ask"))
    print("Best No Bid/Ask:", m.get("best_no_bid"), m.get("best_no_ask"))
    print("AI Signals:", data.get("ai_signals"))
    print("Preflight Gates:", data.get("preflight_gates"))
    print("Guardrails:", data.get("guardrails_status"))
except Exception as e:
    print("Error:", e)
EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_recent_regimes.py
rm -f /home/ec2-user/kalshi-bot/inspect_recent_regimes.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

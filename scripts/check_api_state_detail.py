import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_state_detail.py
import requests

try:
    r = requests.get('http://127.0.0.1:8000/api/state', timeout=5)
    data = r.json()
    print("ai_signals:", data.get("ai_signals"))
    print("preflight_gates:", data.get("preflight_gates"))
    print("guardrails_status:", data.get("guardrails_status"))
    print("compliance_status:", data.get("compliance_status"))
    print("live_portfolio:", data.get("live_portfolio"))
    print("v4_telemetry:", data.get("v4_telemetry"))
except Exception as e:
    print("API Error:", e)

EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_state_detail.py
rm -f /home/ec2-user/kalshi-bot/inspect_state_detail.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

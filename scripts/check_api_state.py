import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_state.py
import requests

try:
    r = requests.get('http://127.0.0.1:8000/api/state', timeout=5)
    data = r.json()
    print("API /state reachable! Keys:", list(data.keys()))
    print("active_tickers:", data.get("active_tickers"))
    print("active_positions:", data.get("active_positions"))
    print("balance:", data.get("balance"))
    print("latest_decisions:", data.get("latest_decisions"))
    print("open_orders:", data.get("open_orders"))
except Exception as e:
    print("API Error:", e)

EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_state.py
rm -f /home/ec2-user/kalshi-bot/inspect_state.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

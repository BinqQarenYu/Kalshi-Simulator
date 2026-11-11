import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_bot_params.py
import requests

try:
    r = requests.get('http://127.0.0.1:8000/api/bot/parameters', timeout=5)
    print('Parameters status:', r.status_code)
    d = r.json()
    for k in ['discount_limit_price', 'momentum_max_price', 'min_spot_diff', 'enable_chop_trading', 'brain_priority_mode']:
        print(f"{k}: {d.get(k)}")
except Exception as e:
    print("Error:", e)

EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_bot_params.py
rm -f /home/ec2-user/kalshi-bot/inspect_bot_params.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

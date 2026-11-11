import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_bot_params_full.py
import requests

try:
    r = requests.get('http://127.0.0.1:8000/api/bot/parameters', timeout=5)
    d = r.json()
    print("Full keys in /api/bot/parameters:", list(d.keys()))
    for k, v in d.items():
        print(f"  {k}: {v}")
except Exception as e:
    print("Error:", e)

EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_bot_params_full.py
rm -f /home/ec2-user/kalshi-bot/inspect_bot_params_full.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

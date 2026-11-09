import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_ladder.py
import requests

r = requests.get('http://127.0.0.1:8000/api/state', timeout=5)
data = r.json()
print("Market:", data.get("market"))
print("Ladder:", data.get("orderbook_ladder"))
EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_ladder.py
rm -f /home/ec2-user/kalshi-bot/inspect_ladder.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

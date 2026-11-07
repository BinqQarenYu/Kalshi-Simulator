import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_eth_dates.py
import json

with open('/home/ec2-user/kalshi-bot/data/eth_win_loss_reports.json', 'r') as f:
    data = json.load(f)

print(f"Total entries: {len(data)}")
timestamps = [d.get('timestamp_utc') for d in data if d.get('timestamp_utc')]
print(f"Valid timestamps: {len(timestamps)}")
if timestamps:
    print(f"Min timestamp: {min(timestamps)}")
    print(f"Max timestamp: {max(timestamps)}")

import sys
print(f"JSON in memory size: {sys.getsizeof(data)} bytes")
EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_eth_dates.py
rm -f /home/ec2-user/kalshi-bot/inspect_eth_dates.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
print("STDERR:", stderr.read().decode('utf-8', errors='replace'))
ssh.close()

import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_eth_reports.py
import json

with open('/home/ec2-user/kalshi-bot/data/eth_win_loss_reports.json', 'r') as f:
    data = json.load(f)

print(f"Total entries in eth_win_loss_reports: {len(data)}")
if isinstance(data, list) and len(data) > 0:
    print(f"Sample item keys: {list(data[0].keys())}")
    print(f"First item: {data[0].get('ticker')}, {data[0].get('result')}, {data[0].get('timestamp')}")
    print(f"Last item: {data[-1].get('ticker')}, {data[-1].get('result')}, {data[-1].get('timestamp')}")

with open('/home/ec2-user/kalshi-bot/data/win_loss_reports.json', 'r') as f:
    data2 = json.load(f)
print(f"Total entries in win_loss_reports: {len(data2)}")

EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_eth_reports.py
rm -f /home/ec2-user/kalshi-bot/inspect_eth_reports.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
print("STDERR:", stderr.read().decode('utf-8', errors='replace'))
ssh.close()

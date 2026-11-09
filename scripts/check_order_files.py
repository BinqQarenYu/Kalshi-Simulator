import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_active_orders.py
import json, glob, os

files = glob.glob('/home/ec2-user/kalshi-bot/data/*order*.json')
for f in files:
    try:
        with open(f, 'r') as fp:
            d = json.load(fp)
            print(f"File {f}: {d}")
    except Exception as e:
        print(f"File {f} error: {e}")

EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_active_orders.py
rm -f /home/ec2-user/kalshi-bot/inspect_active_orders.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

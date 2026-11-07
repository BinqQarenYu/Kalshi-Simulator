import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_models.py
import os

print("=== MODELS DIRECTORY ===")
for root, dirs, files in os.walk('/home/ec2-user/kalshi-bot/models'):
    for f in files:
        fp = os.path.join(root, f)
        print(f"{os.path.getsize(fp) / 1024:.1f} KB: {fp}")

print("=== DATA DIRECTORY FILES ===")
for root, dirs, files in os.walk('/home/ec2-user/kalshi-bot/data'):
    for f in files:
        fp = os.path.join(root, f)
        size = os.path.getsize(fp)
        if size > 1024 * 100: # > 100KB
            print(f"{size / 1024:.1f} KB: {fp}")
EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_models.py
rm -f /home/ec2-user/kalshi-bot/inspect_models.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
print("STDERR:", stderr.read().decode('utf-8', errors='replace'))
ssh.close()

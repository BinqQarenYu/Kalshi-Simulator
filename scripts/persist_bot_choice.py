import paramiko
import json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

# 1. Update local seal_of_excellence.json and bot_parameters_domination.json to mirror baseline
with open('data/seal_of_excellence.json', 'r') as f:
    s = json.load(f)
s['active_live_strategy'] = '3_step_domination_bot'
with open('data/seal_of_excellence.json', 'w') as f:
    json.dump(s, f, indent=2)

sftp = ssh.open_sftp()
sftp.put('data/seal_of_excellence.json', '/home/ec2-user/kalshi-bot/data/seal_of_excellence.json')
sftp.close()

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/persist_settings.py
import json

with open('/home/ec2-user/kalshi-bot/data/seal_of_excellence.json', 'r') as f:
    s = json.load(f)
s['active_live_strategy'] = '3_step_domination_bot'
with open('/home/ec2-user/kalshi-bot/data/seal_of_excellence.json', 'w') as f:
    json.dump(s, f, indent=2)

print("Persisted 3_step_domination_bot in seal_of_excellence.json!")

EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/persist_settings.py
rm -f /home/ec2-user/kalshi-bot/persist_settings.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

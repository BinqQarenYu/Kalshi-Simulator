import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/test_switch_bot.py
import requests

try:
    r = requests.post('http://127.0.0.1:8000/api/bot/strategy/select', json={'strategy_id': '3_step_domination_bot'}, timeout=10)
    print('Select 3_step_domination_bot response:', r.status_code, r.text)
except Exception as e:
    print('Select error:', e)

try:
    r2 = requests.post('http://127.0.0.1:8000/api/presets/load', json={'preset_id': 'baseline_council_v3.2'}, timeout=10)
    print('Load baseline_council_v3.2 response:', r2.status_code, r2.text)
except Exception as e:
    print('Load error:', e)

EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/test_switch_bot.py
rm -f /home/ec2-user/kalshi-bot/test_switch_bot.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

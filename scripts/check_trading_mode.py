import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
echo "=== CHECKING KALSHI_SIMULATION_MODE & EXECUTION MODE IN ENV ==="
grep -E "SIMULATION|PAPER|EXECUTION|MODE|LIVE" /home/ec2-user/kalshi-bot/.env
echo "=== ACTIVE PRESET FILE ==="
cat /home/ec2-user/kalshi-bot/data/active_preset.json
echo "=== CHECKING REST / WEBSOCKET ORDER PLACEMENT ATTEMPTS ==="
journalctl -u kalshi-bot.service --since "40 minutes ago" | grep -iE "placing order|placed order|order placed|submitting order|submit order|order submitted|limit order" | tail -n 20
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

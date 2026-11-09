import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
echo "=== FLEET STATUS IN STATE ==="
cat /home/ec2-user/kalshi-bot/data/subagent_fleet.json
echo "=== ACTIVE DOFS / STRATEGY CONFIG ==="
cat /home/ec2-user/kalshi-bot/data/active_preset.json
cat /home/ec2-user/kalshi-bot/data/bot_parameters_domination.json
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

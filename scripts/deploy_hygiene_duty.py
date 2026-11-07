import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

sftp = ssh.open_sftp()
sftp.put('src/kalshi_sim/utils/system_hygiene.py', '/home/ec2-user/kalshi-bot/src/kalshi_sim/utils/system_hygiene.py')
sftp.put('src/kalshi_sim/batch_supervisor.py', '/home/ec2-user/kalshi-bot/src/kalshi_sim/batch_supervisor.py')
sftp.close()

# Verify syntax on AWS
stdin, stdout, stderr = ssh.exec_command('/home/ec2-user/kalshi-bot/venv/bin/python -m py_compile /home/ec2-user/kalshi-bot/src/kalshi_sim/utils/system_hygiene.py /home/ec2-user/kalshi-bot/src/kalshi_sim/batch_supervisor.py')
print("Compile output:", stdout.read().decode('utf-8', errors='replace'))
print("Compile stderr:", stderr.read().decode('utf-8', errors='replace'))

# Restart service safely
stdin, stdout, stderr = ssh.exec_command('sudo systemctl restart kalshi-bot.service && sleep 2 && sudo systemctl status kalshi-bot.service --no-pager')
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))

ssh.close()

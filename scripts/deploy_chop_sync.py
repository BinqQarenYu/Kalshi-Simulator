import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

# SFTP upload the modified files
sftp = ssh.open_sftp()
sftp.put('src/kalshi_sim/ml/dynamic_regime_strategy.py', '/home/ec2-user/kalshi-bot/src/kalshi_sim/ml/dynamic_regime_strategy.py')
sftp.put('src/kalshi_sim/strategy_evaluator.py', '/home/ec2-user/kalshi-bot/src/kalshi_sim/strategy_evaluator.py')
sftp.put('data/bot_parameters_domination.json', '/home/ec2-user/kalshi-bot/data/bot_parameters_domination.json')
sftp.close()

# Compile check on remote
stdin, stdout, stderr = ssh.exec_command('/home/ec2-user/kalshi-bot/venv/bin/python -m py_compile /home/ec2-user/kalshi-bot/src/kalshi_sim/ml/dynamic_regime_strategy.py /home/ec2-user/kalshi-bot/src/kalshi_sim/strategy_evaluator.py')
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print("Compile stdout:", out)
print("Compile stderr:", err)

# Forceful restart per Rule 6 (Upgrade & Cache Invalidation Protocol)
cmd_restart = 'sudo systemctl restart kalshi-bot.service && sleep 2 && sudo systemctl status kalshi-bot.service --no-pager'
stdin, stdout, stderr = ssh.exec_command(cmd_restart)
res = stdout.read().decode('utf-8', errors='replace')
print(res.encode('ascii', errors='replace').decode('ascii'))

ssh.close()

import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
echo "=== RESTARTING SERVICE TO CLEAR RAM & RELOAD CLEAN STATE ==="
sudo systemctl restart kalshi-bot.service
sleep 3
sudo systemctl status kalshi-bot.service --no-pager
echo "=== FRESH MEMORY FOOTPRINT ==="
free -h
ps aux --sort=-%mem | head -n 5
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
print("STDERR:", err.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

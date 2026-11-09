import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
echo "=== INSPECTING KXBTC15M-26NOV071600-00 EVALUATIONS ==="
journalctl -u kalshi-bot.service --since "5 minutes ago" | grep -v "DRSA LEARNING DIALS" | tail -n 40
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

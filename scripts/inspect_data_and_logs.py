import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = """
echo "=== DATA DIRECTORY BREAKDOWN ==="
du -sh /home/ec2-user/kalshi-bot/data/* 2>/dev/null | sort -hr
echo "=== LOG SIZES IN VAR/LOG ==="
sudo du -sh /var/log/* 2>/dev/null | sort -hr | head -n 15
echo "=== SYSTEMD JOURNAL USAGE ==="
journalctl --disk-usage
echo "=== PROCESS MEMORY LIST ==="
ps aux --sort=-%mem | head -n 15
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
ssh.close()

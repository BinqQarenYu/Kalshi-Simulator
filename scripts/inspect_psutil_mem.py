import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_memory_footprint.py
import os, psutil

p = psutil.Process()
print("Memory usage:", p.memory_info().rss / 1024 / 1024, "MB")

for pid in psutil.pids():
    try:
        proc = psutil.Process(pid)
        if 'python' in proc.name() or 'daemon' in ' '.join(proc.cmdline()):
            print(f"PID {proc.pid}: {proc.memory_info().rss / 1024 / 1024:.2f} MB - {' '.join(proc.cmdline())[:80]}")
    except:
        pass
EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_memory_footprint.py
rm -f /home/ec2-user/kalshi-bot/inspect_memory_footprint.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
print("STDERR:", stderr.read().decode('utf-8', errors='replace'))
ssh.close()

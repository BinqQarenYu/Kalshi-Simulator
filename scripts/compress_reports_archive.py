import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/archive_eth_reports.py
import json
import gzip
import os

fp = '/home/ec2-user/kalshi-bot/data/eth_win_loss_reports.json'
archive_fp = '/home/ec2-user/kalshi-bot/data/eth_win_loss_reports_archive.json.gz'

with open(fp, 'r') as f:
    data = json.load(f)

total = len(data)
print(f"Total entries before: {total}")

if total > 500:
    archive_data = data[:-300]
    kept_data = data[-300:]
    
    # Save archive safely with gzip compression
    with gzip.open(archive_fp, 'wt', encoding='utf-8') as f_out:
        json.dump(archive_data, f_out)
    print(f"Archived {len(archive_data)} historical reports to {archive_fp} ({os.path.getsize(archive_fp)/1024:.1f} KB)")
    
    # Write back the compact kept data
    with open(fp, 'w') as f_in:
        json.dump(kept_data, f_in, indent=2)
    print(f"Active file pruned to {len(kept_data)} most recent reports ({os.path.getsize(fp)/1024:.1f} KB)")
else:
    print("No archive needed.")
EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/archive_eth_reports.py
rm -f /home/ec2-user/kalshi-bot/archive_eth_reports.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
print("STDERR:", stderr.read().decode('utf-8', errors='replace'))
ssh.close()

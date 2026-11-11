import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_truth_sync.py
import sys
sys.path.insert(0, '/home/ec2-user/kalshi-bot/src')
import json
from kalshi_sim.truth_synchronizer import truth_synchronizer
from kalshi_sim.ml.dynamic_regime_strategy import DynamicRegimeStrategy

engine = DynamicRegimeStrategy(asset="BTC")
print("Before sync, enable_chop_trading:", engine.enable_chop_trading)

params = truth_synchronizer.get_truth_parameters("BTC")
print("Truth parameters for BTC enable_chop_trading:", params.get("enable_chop_trading"))
print("Truth parameters for BTC keys:", list(params.keys())[:10])

synced = truth_synchronizer.sync_engine(engine, asset="BTC")
print("Sync result:", synced)
print("After sync, enable_chop_trading:", engine.enable_chop_trading)

# Also check data/bot_parameters_domination.json on disk
with open('/home/ec2-user/kalshi-bot/data/bot_parameters_domination.json') as f:
    d = json.load(f)
print("Disk JSON BTC enable_chop_trading:", d.get('assets', {}).get('BTC', {}).get('enable_chop_trading'))
print("Disk JSON root enable_chop_trading:", d.get('enable_chop_trading'))

EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_truth_sync.py
rm -f /home/ec2-user/kalshi-bot/inspect_truth_sync.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/audit_brains_lessons.py
import json
import sqlite3
import os

print("=== CHECKING BRAINS, SEALS, MODELS, LESSONS ===")

# 1. Models
for m in ['quolas.onnx', 'feature_stats.json', 'hmm_latest.pkl', 'best_model.pt', 'quolas_backup.onnx']:
    p = os.path.join('/home/ec2-user/kalshi-bot/models', m)
    if os.path.exists(p):
        print(f"Model File intact: {m} ({os.path.getsize(p)} bytes)")
    else:
        print(f"MISSING: {m}")

# 2. Critical data registries
for r in ['seal_of_excellence.json', 'poe_deep_diagnostics.json', 'active_preset.json', 
          'bot_parameters_domination.json', 'incubator_state.json', 'immutable_truth_vault.json',
          'subagent_fleet.json']:
    p = os.path.join('/home/ec2-user/kalshi-bot/data', r)
    if os.path.exists(p):
        print(f"State File intact: {r} ({os.path.getsize(p)} bytes)")
    else:
        print(f"MISSING: {r}")

# 3. Database trade and forensics records
con = sqlite3.connect('/home/ec2-user/kalshi-bot/data/kalshi_history.db')
cur = con.cursor()
t_count = cur.execute("SELECT count(*) FROM trades").fetchone()[0]
s_count = cur.execute("SELECT count(*) FROM settlements").fetchone()[0]
f_count = cur.execute("SELECT count(*) FROM trade_lifecycle_forensics").fetchone()[0]
a_count = cur.execute("SELECT count(*) FROM trade_failure_autopsies").fetchone()[0]
b_count = cur.execute("SELECT count(*) FROM batch_assessments").fetchone()[0]
con.close()

print(f"DB Trades intact: {t_count}")
print(f"DB Settlements intact: {s_count}")
print(f"DB Forensics intact: {f_count}")
print(f"DB Autopsies (Lessons) intact: {a_count}")
print(f"DB Batch Assessments intact: {b_count}")

EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/audit_brains_lessons.py
rm -f /home/ec2-user/kalshi-bot/audit_brains_lessons.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
print("STDERR:", stderr.read().decode('utf-8', errors='replace'))
ssh.close()

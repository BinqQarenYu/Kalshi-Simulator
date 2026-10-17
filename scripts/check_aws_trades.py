import subprocess

remote_cmd = """
import urllib.request
import json
try:
    with urllib.request.urlopen('http://127.0.0.1:8000/api/state') as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print('keys:', list(data.keys()))
        print('settings:', data.get('settings'))
        print('bot_audit_status:', data.get('bot_audit_status'))
except Exception as e:
    print('Error:', e)
"""

res = subprocess.run(
    ["ssh", "-i", "kalshi_aws_key.pem", "-o", "StrictHostKeyChecking=no", "ec2-user@13.63.158.94", "python3", "-"],
    input=remote_cmd,
    text=True,
    encoding="utf-8",
    errors="replace",
    capture_output=True
)

with open("aws_recent_logs.txt", "w", encoding="utf-8") as f:
    f.write(res.stdout)
    if res.stderr:
        f.write("\nSTDERR:\n" + res.stderr)
print("Wrote aws_recent_logs.txt, length:", len(res.stdout))

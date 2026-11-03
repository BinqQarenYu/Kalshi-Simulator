import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip()

print("1. Available Strategies on AWS:")
out = run_ssh("curl -s http://127.0.0.1:8000/api/bot/strategies")
print(out)

print("\n2. Health check mode:")
out = run_ssh("curl -s http://127.0.0.1:8000/api/health")
print(out)

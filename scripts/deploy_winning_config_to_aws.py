import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True, text=True)
    return res.stdout.strip(), res.stderr.strip()

def run_scp(local_file, remote_file):
    full_cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-i", key_path, local_file, f"{host}:{remote_file}"]
    res = subprocess.run(full_cmd, capture_output=True, text=True)
    return res.stdout.strip(), res.stderr.strip()

print("1. Truncating onnx_reload.log on AWS...")
out, err = run_ssh("cat /dev/null > /home/ec2-user/kalshi-bot/aws/logs/onnx_reload.log && ls -lh /home/ec2-user/kalshi-bot/aws/logs/onnx_reload.log")
print(out)

print("2. Disabling redundant individual bots...")
out, err = run_ssh("sudo systemctl stop kalshi-btc-bot kalshi-eth-bot; sudo systemctl disable kalshi-btc-bot kalshi-eth-bot")
print(out)

print("3. Deploying updated files to AWS...")
files = [
    ("src/kalshi_sim/ml/onnx_engine.py", "/home/ec2-user/kalshi-bot/src/kalshi_sim/ml/onnx_engine.py"),
    ("data/bot_parameters_domination.json", "/home/ec2-user/kalshi-bot/data/bot_parameters_domination.json"),
    ("data/bot_parameters_eth.json", "/home/ec2-user/kalshi-bot/data/bot_parameters_eth.json"),
    ("data/presets/dynamic_trading_strategy_v1.json", "/home/ec2-user/kalshi-bot/data/presets/dynamic_trading_strategy_v1.json"),
    ("data/seal_of_excellence.json", "/home/ec2-user/kalshi-bot/data/seal_of_excellence.json")
]

for loc, rem in files:
    out, err = run_scp(loc, rem)
    print(f"Uploaded {loc} -> {rem}")

print("4. Restarting Mother Server daemon (Rule 6: Kick out the old)...")
out, err = run_ssh("sudo systemctl restart kalshi-bot.service; sleep 3; systemctl status kalshi-bot.service --no-pager | head -n 15")
print(out)

print("5. Checking EC2 RAM usage...")
out, err = run_ssh("free -m")
print(out)

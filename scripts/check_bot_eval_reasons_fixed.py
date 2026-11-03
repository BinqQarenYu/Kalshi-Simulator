import subprocess

key_path = "kalshi_aws_key.pem"
host = "ec2-user@13.63.158.94"

def safe_print(title, text):
    clean = text.encode("ascii", errors="replace").decode("ascii")
    print(f"=== {title} ===\n{clean}\n")

def run_ssh(remote_cmd):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", key_path, host, remote_cmd]
    res = subprocess.run(full_cmd, capture_output=True)
    return res.stdout.decode("utf-8", errors="ignore").strip()

py_cmd = (
    "cd /home/ec2-user/kalshi-bot && "
    "python3 -c \\\"import json; "
    "d=json.load(open('data/bot_parameters_domination.json')); "
    "print('is_armed:', d.get('is_armed')); "
    "print('active_asset:', d.get('active_asset')); "
    "print('BTC min_confidence:', d.get('assets',{}).get('BTC',{}).get('min_confidence')); "
    "print('BTC min_spot_diff:', d.get('assets',{}).get('BTC',{}).get('min_spot_diff')); "
    "print('BTC discount_limit_price:', d.get('assets',{}).get('BTC',{}).get('discount_limit_price')); "
    "print('BTC momentum_max_price:', d.get('assets',{}).get('BTC',{}).get('momentum_max_price')); "
    "print('BTC silas_pinning_blackout_seconds:', d.get('assets',{}).get('BTC',{}).get('silas_pinning_blackout_seconds')); "
    "e=json.load(open('data/bot_parameters_eth.json')); "
    "print('ETH min_confidence:', e.get('eth_bot1_v4',{}).get('min_confidence')); "
    "print('ETH min_spot_diff:', e.get('eth_bot1_v4',{}).get('min_spot_diff')); "
    "print('ETH max_entry_price:', e.get('eth_bot1_v4',{}).get('max_entry_price')); "
    "print('ETH current_regime:', e.get('eth_bot1_v4',{}).get('current_regime'))\\\""
)

out = run_ssh(py_cmd)
safe_print("Parsed Bot Parameters", out)

out = run_ssh("journalctl -u kalshi-bot.service -n 1000 --no-pager | grep -iE 'skip|disqualif|veto|holding off|gate|blackout' | tail -n 20")
safe_print("Filter & Gate Triggers", out)

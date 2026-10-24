import subprocess
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

for ticker in ['KXBTC15M-26OCT211700-00', 'KXBTC15M-26OCT211900-00', 'KXBTC15M-26OCT220300-00']:
    print(f"\n==================== TICKER: {ticker} ====================")
    cmd = [
        "ssh", "-i", "kalshi_aws_key.pem", "-o", "StrictHostKeyChecking=no", "ec2-user@13.63.158.94",
        f"sudo journalctl -u kalshi-btc-bot.service --since '24 hours ago' -g '{ticker}' -n 40 --no-pager"
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    lines = proc.stdout.splitlines()
    for l in lines:
        if 'ORDER EXECUTED' in l or 'SETTLEMENT' in l or 'TELEMETRY' in l or 'TAKER' in l:
            print(l)

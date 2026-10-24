import subprocess
import re
import sys

# Force utf-8 output
sys.stdout.reconfigure(encoding='utf-8')

cmd = [
    "ssh", "-i", "kalshi_aws_key.pem", "-o", "StrictHostKeyChecking=no", "ec2-user@13.63.158.94",
    "sudo journalctl -u kalshi-btc-bot.service -u kalshi-eth-bot.service -u kalshi-bot.service --since '24 hours ago' -g 'KXBTC15M-26OCT211700-00|KXBTC15M-26OCT211900-00|KXBTC15M-26OCT220300-00' --no-pager"
]

proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
lines = proc.stdout.splitlines()

for line in lines:
    if any(k in line for k in ["LIVE ENTRY", "ORDER EXECUTED", "ORDER FILLED", "Tau:", "Diff:", "OFI:", "SETTLEMENT", "DoF", "MISTAKE", "Why", "salvage", "Salvage", "VOL MOAT", "P(Win)", "Action:"]):
        print(line[:160])

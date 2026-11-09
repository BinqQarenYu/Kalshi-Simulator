import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_live_eval_details.py
import sys
sys.path.insert(0, '/home/ec2-user/kalshi-bot/src')
import requests
from decimal import Decimal
from kalshi_sim.ml.dynamic_regime_strategy import DynamicRegimeStrategy
from kalshi_sim.schemas import L2BookState
from datetime import datetime, timezone, timedelta

r = requests.get('http://127.0.0.1:8000/api/state', timeout=5)
data = r.json()
m = data.get("market")
ladder = data.get("orderbook_ladder")

# Test 1: With enable_chop_trading=False (current default in code)
eng_default = DynamicRegimeStrategy(asset="BTC", enable_timing_guard=True, enable_chop_trading=False)
# Test 2: With enable_chop_trading=True
eng_chop = DynamicRegimeStrategy(asset="BTC", enable_timing_guard=True, enable_chop_trading=True)

book = L2BookState(market_ticker=m.get("ticker"))
yes_dict, no_dict = {}, {}
for l in ladder:
    side = l['side']
    px = Decimal(str(l['price_raw']))
    qty = Decimal(str(l['contracts']))
    if side == 'yes':
        yes_dict[px] = qty
    else:
        no_dict[px] = qty
book.yes_book = yes_dict
book.no_book = no_dict

exp_time = datetime.now(timezone.utc) + timedelta(seconds=m.get("expiry_countdown_seconds"))
spot_p = Decimal(str(m.get("current_btc_price")))
strike_p = Decimal(str(m.get("target_strike")))

dec_def = eng_default.evaluate(m.get("ticker"), book, spot_p, strike_p, exp_time, Decimal("16.00"), Decimal("0.487"))
dec_chop = eng_chop.evaluate(m.get("ticker"), book, spot_p, strike_p, exp_time, Decimal("16.00"), Decimal("0.487"))

print(f"Market: {m.get('ticker')}")
print(f"Spot: {spot_p} | Strike: {strike_p} | Diff: {spot_p - strike_p}")
print(f"Default Decision -> Side: {dec_def.recommended_side} | Contracts: {dec_def.recommended_contracts} | Reason: {dec_def.rationale}")
print(f"Chop Enabled Decision -> Side: {dec_chop.recommended_side} | Contracts: {dec_chop.recommended_contracts} | Reason: {dec_chop.rationale}")
EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_live_eval_details.py
rm -f /home/ec2-user/kalshi-bot/inspect_live_eval_details.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

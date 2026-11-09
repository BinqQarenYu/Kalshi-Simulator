import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_live_eval.py
import sys
sys.path.insert(0, '/home/ec2-user/kalshi-bot/src')
import requests
from decimal import Decimal
from kalshi_sim.ml.dynamic_regime_strategy import DynamicRegimeStrategy
from kalshi_sim.schemas import L2BookState

r = requests.get('http://127.0.0.1:8000/api/state', timeout=5)
data = r.json()
m = data.get("market")
ladder = data.get("orderbook_ladder")

engine = DynamicRegimeStrategy(asset="BTC")
book = L2BookState(market_ticker=m.get("ticker"))

yes_dict = {}
no_dict = {}
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

from datetime import datetime, timezone, timedelta
exp_time = datetime.now(timezone.utc) + timedelta(seconds=m.get("expiry_countdown_seconds"))

dec = engine.evaluate(
    ticker=m.get("ticker"),
    book=book,
    spot_price=Decimal(str(m.get("current_btc_price"))),
    strike_price=Decimal(str(m.get("target_strike"))),
    expiration_time=exp_time,
    volatility_1m=Decimal("16.00"),
    vpin=Decimal("0.487")
)
print("=== DYNAMIC REGIME EVALUATION RESULT ===")
print("Recommended side:", dec.recommended_side)
print("Contracts:", dec.recommended_contracts)
print("Regime:", dec.regime)
print("Limit price:", dec.limit_price)
print("EV:", dec.expected_value)
print("Rationale:", dec.rationale)
EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_live_eval.py
rm -f /home/ec2-user/kalshi-bot/inspect_live_eval.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
if err.strip():
    print("STDERR:", err.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

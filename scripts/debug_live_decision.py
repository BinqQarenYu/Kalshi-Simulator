import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_decision.py
import sys
sys.path.insert(0, '/home/ec2-user/kalshi-bot/src')
import requests

r = requests.get('http://127.0.0.1:8000/api/state', timeout=5)
data = r.json()
m = data.get("market")
ladder = data.get("orderbook_ladder")
print("Target Strike:", m.get("target_strike"))
print("Current Spot:", m.get("current_btc_price"))
print("Expiry Countdown:", m.get("expiry_countdown_seconds"))
print("Best Yes Bid/Ask:", m.get("best_yes_bid"), m.get("best_yes_ask"))
print("Best No Bid/Ask:", m.get("best_no_bid"), m.get("best_no_ask"))

from decimal import Decimal
from kalshi_sim.ml.dynamic_regime_strategy import DynamicRegimeStrategy
from kalshi_sim.schemas import L2BookState

engine = DynamicRegimeStrategy(asset="BTC")
book = L2BookState(
    market_ticker=m.get("ticker"),
    yes_bids=[(Decimal(str(l['price_raw'])), l['contracts']) for l in ladder if l['side'] == 'yes'],
    no_bids=[(Decimal(str(l['price_raw'])), l['contracts']) for l in ladder if l['side'] == 'no'],
    timestamp=1794084605.0
)

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
print("Decision Result:", dec)
EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_decision.py
rm -f /home/ec2-user/kalshi-bot/inspect_decision.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
if err.strip():
    print("STDERR:", err.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

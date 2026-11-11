import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('13.63.158.94', username='ec2-user', key_filename='kalshi_aws_key.pem')

cmd = r'''
cat << 'EOF' > /home/ec2-user/kalshi-bot/inspect_live_tick_eval.py
import sys
sys.path.insert(0, '/home/ec2-user/kalshi-bot/src')
import requests
from decimal import Decimal
from kalshi_sim.ml.dynamic_regime_strategy import DynamicRegimeStrategy
from kalshi_sim.schemas import L2BookState
from datetime import datetime, timezone, timedelta
from kalshi_sim.truth_synchronizer import truth_synchronizer

r = requests.get('http://127.0.0.1:8000/api/state', timeout=5)
data = r.json()
m = data.get("market")
ladder = data.get("orderbook_ladder")

engine = DynamicRegimeStrategy(asset="BTC", enable_timing_guard=True)
truth_synchronizer.sync_engine(engine, asset="BTC")

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

print(f"=== LIVE EVALUATION FOR {m.get('ticker')} ===")
print(f"Spot: {spot_p} | Strike: {strike_p} | Diff: {spot_p - strike_p}")
print(f"Expiry Countdown: {m.get('expiry_countdown_seconds')}s")
print(f"Best Yes Bid/Ask: {m.get('best_yes_bid')}/{m.get('best_yes_ask')}")
print(f"Best No Bid/Ask: {m.get('best_no_bid')}/{m.get('best_no_ask')}")
print(f"Engine enable_chop_trading: {engine.enable_chop_trading}")
print(f"Engine enable_timing_guard: {engine.enable_timing_guard}")
print(f"Engine max_momentum_price: {engine.max_momentum_price}")
print(f"Engine vol_trend_trigger: {engine.vol_trend_trigger} | vol_chop_trigger: {engine.vol_chop_trigger}")

dec = engine.evaluate(m.get("ticker"), book, spot_p, strike_p, exp_time, Decimal("16.00"), Decimal("0.487"))
print(f"Decision -> Regime: {dec.regime} | Side: {dec.recommended_side} | Contracts: {dec.recommended_contracts} | Limit: {dec.limit_price}")
print(f"Rationale: {dec.rationale}")

EOF
/home/ec2-user/kalshi-bot/venv/bin/python /home/ec2-user/kalshi-bot/inspect_live_tick_eval.py
rm -f /home/ec2-user/kalshi-bot/inspect_live_tick_eval.py
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
print(out.encode('ascii', errors='replace').decode('ascii'))
ssh.close()

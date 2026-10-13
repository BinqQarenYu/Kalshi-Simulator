import json
import sys

with open('/home/ec2-user/kalshi-bot/data/win_loss_reports.json') as f:
    data = json.load(f)

for r in data:
    t = r.get('timestamp_utc', '')
    ticker = r.get('ticker')
    side = r.get('bot_side')
    outcome = r.get('outcome')
    pnl = r.get('pnl')
    strike = r.get('strike_price')
    settle = r.get('settlement_btc_price')
    bal = r.get('balance_after')
    print(f"{t} | {ticker} | {side} | {outcome} | PnL: {pnl} | Strike: {strike} | Settle: {settle} | Bal: {bal}")

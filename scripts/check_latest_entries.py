import json

with open('/home/ec2-user/kalshi-bot/data/win_loss_reports.json', 'r') as f:
    btc = json.load(f)
with open('/home/ec2-user/kalshi-bot/data/eth_win_loss_reports.json', 'r') as f:
    eth = json.load(f)

print(f"Total BTC records: {len(btc)}")
print("Latest 5 BTC entries:")
for x in btc[-5:]:
    print(x.get('timestamp') or x.get('settled_time') or x.get('created_at'), x.get('ticker'), x.get('net_pnl') or x.get('pnl'), x.get('result'))

print(f"\nTotal ETH records: {len(eth)}")
print("Latest 5 ETH entries:")
for x in eth[-5:]:
    print(x.get('timestamp') or x.get('settled_time') or x.get('created_at'), x.get('ticker'), x.get('net_pnl') or x.get('pnl'), x.get('result'))

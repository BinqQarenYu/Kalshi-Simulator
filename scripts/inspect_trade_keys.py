import json

with open('/home/ec2-user/kalshi-bot/data/win_loss_reports.json', 'r') as f:
    btc = json.load(f)

print("Keys in BTC trade record:")
if btc:
    print(list(btc[-1].keys()))
    print("Full latest record:")
    print(json.dumps(btc[-1], indent=2))

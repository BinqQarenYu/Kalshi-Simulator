import re

log_path = '/home/ec2-user/kalshi-bot/quolas_24_7.log'

with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

trade_events = []
for i, line in enumerate(lines):
    if "ORDER EXECUTED: BUY" in line:
        # Grab surrounding 15 lines before and 5 lines after
        start = max(0, i - 15)
        end = min(len(lines), i + 5)
        trade_events.append((line.strip(), lines[start:end]))

print(f"Found {len(trade_events)} order execution events in log.")
print("\n--- LAST 4 TRADE EVENTS WITH CONTEXT ---")
for evt_line, context in trade_events[-4:]:
    print("\n" + "="*80)
    print("EVENT:", evt_line)
    print("="*80)
    for l in context:
        print(l.rstrip())

import json
from pathlib import Path
from collections import Counter

data_dir = Path("data")
with open(data_dir / "win_loss_reports.json", "r", encoding="utf-8") as f:
    reports = json.load(f)

# Chronological order
chron_reports = list(reversed(reports))

print(f"Total reports: {len(chron_reports)}")

tickers = [r.get("ticker", "") for r in chron_reports]
print(f"Unique tickers: {len(set(tickers))}")

bot_types = Counter(r.get("bot_type", "unknown") for r in chron_reports)
print("Bot types breakdown:", dict(bot_types))

modes = Counter(r.get("execution_mode", "unknown") for r in chron_reports)
print("Execution modes:", dict(modes))

outcomes = Counter(r.get("outcome", "unknown") for r in chron_reports)
print("Actual Outcomes:", dict(outcomes))

total_pnl = sum(float(r.get("pnl", 0)) for r in chron_reports)
print(f"Total actual PnL: ${total_pnl:.2f}")

# Group by unique ticker
unique_events = {}
for idx, r in enumerate(chron_reports):
    t = r.get("ticker", f"UNK-{idx}")
    if t not in unique_events:
        unique_events[t] = []
    unique_events[t].append(r)

print(f"\nGrouped into {len(unique_events)} distinct market events:")
for t, r_list in list(unique_events.items())[:15]:
    strike = r_list[0].get("strike_price")
    settle = r_list[0].get("settlement_btc_price")
    diff = (settle - strike) if (settle and strike) else 0.0
    side = r_list[0].get("bot_side")
    wins = sum(1 for x in r_list if x.get("outcome") == "win")
    losses = sum(1 for x in r_list if x.get("outcome") == "loss")
    ct = r_list[0].get("cycle_time", "")
    print(f"  {t} ({ct[:22]}) | Diff: ${diff:+.1f} | Reports: {len(r_list)} | W/L: {wins}W/{losses}L")

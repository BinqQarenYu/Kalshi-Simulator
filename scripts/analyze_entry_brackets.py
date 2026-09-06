import json
from pathlib import Path
from decimal import Decimal

with open("data/win_loss_reports.json", "r", encoding="utf-8") as f:
    reports = json.load(f)

expensive_trades = [r for r in reports if float(r.get("entry_price", 0)) > 0.50]
discount_trades = [r for r in reports if float(r.get("entry_price", 0)) <= 0.50]

print(f"Total reports: {len(reports)}")
print(f"Expensive entries (>50c): {len(expensive_trades)}")
exp_wins = sum(1 for r in expensive_trades if r.get("outcome") == "win")
exp_losses = sum(1 for r in expensive_trades if r.get("outcome") == "loss")
exp_pnl = sum(float(r.get("pnl", 0)) for r in expensive_trades)
print(f"  >50c Win Rate: {exp_wins}/{len(expensive_trades)} ({exp_wins/len(expensive_trades)*100:.1f}%) | Net PnL: ${exp_pnl:.2f}")

print(f"Discount entries (<=50c): {len(discount_trades)}")
disc_wins = sum(1 for r in discount_trades if r.get("outcome") == "win")
disc_losses = sum(1 for r in discount_trades if r.get("outcome") == "loss")
disc_pnl = sum(float(r.get("pnl", 0)) for r in discount_trades)
print(f"  <=50c Win Rate: {disc_wins}/{len(discount_trades)} ({disc_wins/len(discount_trades)*100:.1f}%) | Net PnL: ${disc_pnl:.2f}")

# Distribution of entries
print("\nEntries breakdown:")
for bracket in [(0.10, 0.30), (0.30, 0.40), (0.40, 0.50), (0.50, 0.65), (0.65, 0.85), (0.85, 1.00)]:
    b_trades = [r for r in reports if bracket[0] <= float(r.get("entry_price", 0)) < bracket[1]]
    b_w = sum(1 for r in b_trades if r.get("outcome") == "win")
    b_l = sum(1 for r in b_trades if r.get("outcome") == "loss")
    b_pnl = sum(float(r.get("pnl", 0)) for r in b_trades)
    print(f"  {bracket[0]:.2f} - {bracket[1]:.2f}: {len(b_trades):2d} trades | {b_w}W / {b_l}L | Net PnL: ${b_pnl:+.2f}")

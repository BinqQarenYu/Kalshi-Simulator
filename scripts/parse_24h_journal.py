import subprocess
import re
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Run journalctl on AWS
cmd = [
    "ssh", "-i", "kalshi_aws_key.pem", "-o", "StrictHostKeyChecking=no", "ec2-user@13.63.158.94",
    "sudo journalctl -u kalshi-btc-bot.service -u kalshi-eth-bot.service -u kalshi-bot.service --since '24 hours ago' --no-pager"
]

print("Fetching 24h journalctl logs from AWS...")
proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
logs = proc.stdout.splitlines()
print(f"Total log lines fetched: {len(logs)}")

settlement_re = re.compile(r"🎯 \[(BTC|ETH) SETTLEMENT RECONCILED\] ([^|]+) \| (WIN|LOSS) \| PnL: \$([+-]?[\d\.]+) \| Why: (.*)")
entry_re = re.compile(r"🚀 \[(BTC|ETH) (?:ORDER EXECUTED|LIVE ENTRY EXECUTED|ORDER FILLED)\] ([^|]+) \| Side: (YES|NO) \| Price: \$?([\d\.]+) \| (?:Contracts|Qty): (\d+)")
salvage_re = re.compile(r"🛡️ \[(?:SALVAGE DERISK EXECUTED|ETH SALVAGE DERISK EXECUTED|BTC SALVAGE DERISK EXECUTED)\] Salvaged \$?([\d\.]+)/ct! Loss capped at -\$?([\d\.]+)")

settlements = []
salvages = []
entries = []

for line in logs:
    m_settle = settlement_re.search(line)
    if m_settle:
        asset, ticker, outcome, pnl, why = m_settle.groups()
        # Parse timestamp from line
        ts_match = re.match(r"^([A-Z][a-z]{2}\s+\d+\s+\d+:\d+:\d+)", line)
        ts_str = ts_match.group(1) if ts_match else "Unknown"
        settlements.append({
            "ts": ts_str,
            "asset": asset,
            "ticker": ticker.strip(),
            "outcome": outcome,
            "pnl": Decimal(pnl),
            "why": why.strip(),
            "line": line
        })
    m_salvage = salvage_re.search(line)
    if m_salvage:
        salvaged_price, loss_capped = m_salvage.groups()
        salvages.append((salvaged_price, loss_capped, line))

print("\n================== SETTLED TRADES IN PAST 24 HOURS ==================")
total_pnl = Decimal("0")
wins = 0
losses = 0

for s in settlements:
    pnl = s["pnl"]
    total_pnl += pnl
    if s["outcome"] == "WIN":
        wins += 1
    else:
        losses += 1
    print(f"[{s['ts']}] Asset: {s['asset']} | Ticker: {s['ticker']} | Outcome: {s['outcome']} | PnL: ${pnl:+.4f} | Gate/Reason: {s['why']}")

print(f"\nTotal Settled: {len(settlements)} | Wins: {wins} | Losses: {losses} | Win Rate: {wins/len(settlements)*100 if settlements else 0:.1f}%")
print(f"Net Realized PnL: ${total_pnl:+.4f}")

print("\n================== SALVAGE EXECUTIONS ==================")
for sal in salvages:
    print(f"Salvage: Price=${sal[0]}/ct, Loss Capped=${sal[1]} | Raw: {sal[2][:120]}")

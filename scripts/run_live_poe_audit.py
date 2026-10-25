import sys
sys.path.insert(0, '/home/ec2-user/kalshi-bot/src')
import subprocess
import re
from kalshi_sim.ml.poe_graph_evaluator import run_poe_audit

cmd = [
    'sudo', 'journalctl', '-u', 'kalshi-btc-bot.service', '-u', 'kalshi-eth-bot.service',
    '--since', '-48h', '-g', 'SETTLEMENT RECONCILED', '--no-pager'
]
output = subprocess.check_output(cmd, text=True, errors='ignore')

pattern = re.compile(r'🎯 \[(BTC|ETH) SETTLEMENT RECONCILED\] ([^|]+) \| (WIN|LOSS) \| PnL: \$([+-]?[\d\.]+) \| Why: (.*)')

trades = []
for line in output.splitlines():
    m = pattern.search(line)
    if m:
        asset, ticker, outcome, pnl, why = m.groups()
        # Parse timestamp
        ts_match = re.match(r"^([A-Z][a-z]{2}\s+\d+\s+\d+:\d+:\d+)", line)
        ts_str = ts_match.group(1) if ts_match else ""
        trades.append({
            'report_id': f"TR-{ticker.strip()}",
            'ticker': ticker.strip(),
            'asset': asset,
            'pnl': float(pnl),
            'outcome': outcome,
            'why': why.strip(),
            'timestamp': f"2026 {ts_str}"
        })

print(f"Extracted {len(trades)} trades from live journal. Executing LangGraph POE Audit...")
result = run_poe_audit(trades, hours=48)
print(result['audit_report_markdown'])

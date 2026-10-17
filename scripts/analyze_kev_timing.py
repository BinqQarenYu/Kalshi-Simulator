import sys
import re
import json
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8')

# Map of settled results from our verified exchange records:
settled = {
    'KXETH15M-26OCT150230-30': 'YES',
    'KXETH15M-26OCT150915-15': 'YES',
    'KXETH15M-26OCT150930-30': 'NO',
    'KXETH15M-26OCT150945-45': 'YES',
    'KXETH15M-26OCT151000-00': 'NO',
    'KXETH15M-26OCT151015-15': 'YES',
    'KXETH15M-26OCT151030-30': 'NO',
    'KXETH15M-26OCT151045-45': 'YES',
    'KXETH15M-26OCT151100-00': 'YES',
    'KXETH15M-26OCT151115-15': 'YES',
    'KXETH15M-26OCT151130-30': 'YES',
    'KXETH15M-26OCT151145-45': 'YES',
    'KXETH15M-26OCT151200-00': 'YES',
    'KXETH15M-26OCT151215-15': 'NO',
    'KXETH15M-26OCT151230-30': 'NO',
    'KXETH15M-26OCT151245-45': 'YES',
    'KXETH15M-26OCT151300-00': 'YES',
    'KXETH15M-26OCT151315-15': 'YES',
    'KXETH15M-26OCT151330-30': 'YES',
    'KXETH15M-26OCT151345-45': 'YES',
    'KXETH15M-26OCT151400-00': 'NO',
    'KXETH15M-26OCT151415-15': 'NO',
    'KXETH15M-26OCT151430-30': 'YES',
}

evals = []
curr_ticker = None
curr_diff = None

with open('logs/live_dual_bots.log', 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        m_bot = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3}).*\[ETH BOT 1 V4\]\s+(KXETH15M-[^\s|]+)', line)
        if m_bot:
            curr_ticker = m_bot.group(2)
            m_diff = re.search(r'\|Diff\|\s+\$([0-9.]+)', line)
            curr_diff = float(m_diff.group(1)) if m_diff else None

        m_kev = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3}).*\[KEV SHADOW ORACLE\] Rec:\s+([A-Z]+)\s+\(Conf:\s+([0-9.]+)%\)', line)
        if m_kev and curr_ticker and curr_ticker in settled:
            k_time_str = m_kev.group(1)
            rec = m_kev.group(2)
            conf = float(m_kev.group(3))

            m_tick = re.search(r'KXETH15M-\d{2}[A-Z]{3}\d{2}(\d{2})(\d{2})', curr_ticker)
            if m_tick:
                edt_h = int(m_tick.group(1))
                edt_m = int(m_tick.group(2))
                log_dt = datetime.strptime(k_time_str.split(',')[0], '%Y-%m-%d %H:%M:%S')
                local_h = (edt_h + 7) % 24
                expiry_dt = log_dt.replace(hour=local_h, minute=edt_m, second=0)
                if expiry_dt < log_dt and (log_dt - expiry_dt).total_seconds() > 3600:
                    expiry_dt += timedelta(days=1)
                tau = (expiry_dt - log_dt).total_seconds()

                if -30 <= tau <= 930:
                    is_correct = (rec == settled[curr_ticker])
                    evals.append({
                        'ticker': curr_ticker,
                        'log_time': k_time_str,
                        'tau': tau,
                        'rec': rec,
                        'conf': conf,
                        'diff': curr_diff,
                        'actual': settled[curr_ticker],
                        'is_correct': is_correct,
                    })

print(f"Total timestamped Kev evaluations analyzed: {len(evals)}")

# Define timing buckets (Tau = seconds remaining until cycle close)
# Bucket 1: 15m to 10m remaining (tau 600 - 900s) -> Cycle Open / Early
# Bucket 2: 10m to 5m remaining (tau 300 - 600s) -> Mid-Cycle
# Bucket 3: 5m to 2m remaining (tau 120 - 300s) -> Prime Sweet Spot
# Bucket 4: 2m to 0m remaining (tau 0 - 120s) -> Late Expiration Sniper

buckets = [
    ("Opening Window (15m - 10m left: tau 600-900s)", 600, 900),
    ("Mid-Cycle Window (10m - 5m left: tau 300-600s)", 300, 600),
    ("Prime Harvest Window (5m - 2m left: tau 120-300s)", 120, 300),
    ("Late Endgame Window (2m - 0m left: tau 0-120s)", 0, 120),
]

print("\n" + "="*75)
print("KEV WIN RATE & PREDICTION ACCURACY BY CYCLE TIMING (TAU)")
print("="*75)

for name, min_tau, max_tau in buckets:
    b_evals = [e for e in evals if min_tau <= e['tau'] < max_tau and e['rec'] in ('YES', 'NO')]
    b_waits = [e for e in evals if min_tau <= e['tau'] < max_tau and e['rec'] == 'WAIT']
    if not b_evals:
        continue
    correct = sum(1 for e in b_evals if e['is_correct'])
    incorrect = len(b_evals) - correct
    acc = (correct / len(b_evals)) * 100
    print(f"\n⏱️  {name}:")
    print(f"   Total Signals Emitted: {len(b_evals)} (plus {len(b_waits)} WAIT calls)")
    print(f"   Correct: {correct} | Incorrect: {incorrect}")
    print(f"   Accuracy: {acc:.2f}%")

# Now inspect specifically the 2 INCORRECT cycles:
print("\n" + "="*75)
print("DEEP DIVE: WHAT CAUSED THE 2 INCORRECT PREDICTIONS?")
print("="*75)
for ticker in ['KXETH15M-26OCT151030-30', 'KXETH15M-26OCT151215-15']:
    t_evals = [e for e in evals if e['ticker'] == ticker]
    if not t_evals:
        continue
    actual = settled[ticker]
    print(f"\n🔍 Cycle: {ticker} (Actual Settlement Result: {actual})")
    # Group by 1-minute intervals of tau
    for min_left in range(14, -1, -1):
        min_tau = min_left * 60
        max_tau = min_tau + 60
        sub = [e for e in t_evals if min_tau <= e['tau'] < max_tau]
        if sub:
            recs = [s['rec'] for s in sub]
            mode_rec = max(set(recs), key=recs.count)
            avg_diff = sum(s['diff'] for s in sub if s['diff'] is not None) / max(1, sum(1 for s in sub if s['diff'] is not None))
            print(f"   Tau ~{min_left}m remaining ({min_tau}s): Kev called {mode_rec} (Diff ~${avg_diff:.2f}) -> {'✅ Matches' if mode_rec == actual else '❌ Flips'}")

import json
from decimal import Decimal
from pathlib import Path

with open("data/win_loss_reports.json", "r", encoding="utf-8") as f:
    reports = json.load(f)

chron_reports = list(reversed(reports))

with open("data/stream_profiles_cache.json", "r", encoding="utf-8") as f:
    profiles = json.load(f)

# Let's inspect where actual bot_side differed from settlement outcome
diff_count = 0
for idx, r in enumerate(chron_reports):
    bot_side = r.get("bot_side", "").lower()
    strike = float(r.get("strike_price", 0))
    settle = float(r.get("settlement_btc_price", 0))
    outcome = r.get("outcome", "").lower()
    entry = float(r.get("entry_price", 0.50))
    bot_type = r.get("bot_type", "")
    cycle_yes_won = settle >= strike
    actual_winner = "yes" if cycle_yes_won else "no"

    if bot_side != actual_winner:
        diff_count += 1
        t = r.get("ticker", "")
        prof = profiles.get(t, {})
        print(f"Loss Cycle {idx}: Ticker={t} | BotSide={bot_side} vs Actual={actual_winner} | Entry={entry:.2f} | Strike={strike:.1f} Settle={settle:.1f} (Diff={settle-strike:+.1f}) | Bot={bot_type}")
        print(f"   Stream for {t}: min_trade_yes={prof.get('min_trade_yes')}, min_trade_no={prof.get('min_trade_no')}")

print(f"\nTotal losing cycles in actual history: {diff_count} out of {len(chron_reports)}")

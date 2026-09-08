import urllib.request
import json
import time
from datetime import datetime, timezone

cycles = [
    {"ticker": "KXBTC15M-26SEP071900-00", "strike": 78822.48, "start": "2026-09-07T22:45:00Z", "end": "2026-09-07T23:00:00Z"},
    {"ticker": "KXBTC15M-26SEP071915-15", "strike": 78934.67, "start": "2026-09-07T23:00:00Z", "end": "2026-09-07T23:15:00Z"},
    {"ticker": "KXBTC15M-26SEP071945-45", "strike": 78996.17, "start": "2026-09-07T23:30:00Z", "end": "2026-09-07T23:45:00Z"},
    {"ticker": "KXBTC15M-26SEP072045-45", "strike": 79009.66, "start": "2026-09-08T00:30:00Z", "end": "2026-09-08T00:45:00Z"},
    {"ticker": "KXBTC15M-26SEP072100-00", "strike": 79199.01, "start": "2026-09-08T00:45:00Z", "end": "2026-09-08T01:00:00Z"},
    {"ticker": "KXBTC15M-26SEP072130-30", "strike": 79298.69, "start": "2026-09-08T01:15:00Z", "end": "2026-09-08T01:30:00Z"},
    {"ticker": "KXBTC15M-26SEP072200-00", "strike": 79308.06, "start": "2026-09-08T01:45:00Z", "end": "2026-09-08T02:00:00Z"},
]

def fetch_all_trades_for_window(ticker, start_iso, end_iso):
    st_epoch = int(datetime.fromisoformat(start_iso.replace("Z", "+00:00")).timestamp())
    et_epoch = int(datetime.fromisoformat(end_iso.replace("Z", "+00:00")).timestamp())
    
    all_trades = []
    # Sample every 2 minutes across the 15m window to avoid huge payload
    for cur_st in range(st_epoch, et_epoch, 120):
        cur_et = min(et_epoch, cur_st + 120)
        url = f"https://api.elections.kalshi.com/trade-api/v2/markets/trades?ticker={ticker}&min_ts={cur_st}&max_ts={cur_et}&limit=100"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                d = json.loads(resp.read().decode())
                tr = d.get("trades", [])
                all_trades.extend(tr)
        except Exception as e:
            pass
        time.sleep(0.05)
    return all_trades

print("=" * 85)
print("AUDIT OF ACTUAL KALSHI YES PRICES ACROSS ENTIRE DURATION OF ALL 7 OVERNIGHT CYCLES")
print("=" * 85)

for c in cycles:
    ticker = c["ticker"]
    trades = fetch_all_trades_for_window(ticker, c["start"], c["end"])
    yes_prices = [float(t["yes_price_dollars"]) for t in trades if "yes_price_dollars" in t]
    
    if yes_prices:
        min_p = min(yes_prices)
        max_p = max(yes_prices)
        p_under_50 = [p for p in yes_prices if p <= 0.50]
        p_under_48 = [p for p in yes_prices if p <= 0.48]
        
        # Sort trades chronologically
        trades.sort(key=lambda x: x["created_time"])
        first_t = trades[0]["created_time"][11:19]
        first_p = float(trades[0].get("yes_price_dollars", 0))
        last_t = trades[-1]["created_time"][11:19]
        last_p = float(trades[-1].get("yes_price_dollars", 0))
        
        print(f"\nCycle: {ticker} (Strike: ${c['strike']:,.2f})")
        print(f"  Window: {c['start'][11:16]} -> {c['end'][11:16]} UTC | Sampled Trades: {len(trades)}")
        print(f"  First Trade ({first_t}): YES = ${first_p:.3f} | Last Trade ({last_t}): YES = ${last_p:.3f}")
        print(f"  Lowest Traded YES Price: ${min_p:.3f} | Highest: ${max_p:.3f}")
        print(f"  Trades <= $0.50: {len(p_under_50)} / {len(yes_prices)} ({len(p_under_50)/len(yes_prices)*100:.1f}%)")
        print(f"  Trades <= $0.48: {len(p_under_48)} / {len(yes_prices)} ({len(p_under_48)/len(yes_prices)*100:.1f}%)")
    else:
        print(f"\nCycle: {ticker} — No trades found in sampled window.")

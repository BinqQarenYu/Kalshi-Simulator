import urllib.request
import json
from datetime import datetime

cycles = [
    {"ticker": "KXBTC15M-26SEP071900-00", "strike": 78822.48, "order_time": "22:59:00"},
    {"ticker": "KXBTC15M-26SEP071915-15", "strike": 78934.67, "order_time": "23:14:00"},
    {"ticker": "KXBTC15M-26SEP071945-45", "strike": 78996.17, "order_time": "23:43:59"},
    {"ticker": "KXBTC15M-26SEP072045-45", "strike": 79009.66, "order_time": "00:43:22"},
    {"ticker": "KXBTC15M-26SEP072100-00", "strike": 79199.01, "order_time": "00:59:08"},
    {"ticker": "KXBTC15M-26SEP072130-30", "strike": 79298.69, "order_time": "01:28:58"},
    {"ticker": "KXBTC15M-26SEP072200-00", "strike": 79308.06, "order_time": "01:58:28"},
]

print("=" * 80)
print("HISTORICAL KALSHI TRADES FOR THE 7 OVERNIGHT CYCLES")
print("=" * 80)

for c in cycles:
    ticker = c["ticker"]
    url = f"https://api.elections.kalshi.com/trade-api/v2/markets/trades?ticker={ticker}&limit=1000"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            trades = data.get("trades", [])
            trades.sort(key=lambda x: x["created_time"])
            print(f"\n>>> {ticker} (Strike: ${c['strike']:,.2f}, Order Placed: {c['order_time']}) <<<")
            print(f"Total Market Trades: {len(trades)}")
            if not trades:
                continue
            first_time = trades[0]["created_time"]
            last_time = trades[-1]["created_time"]
            print(f"Time Range: {first_time} -> {last_time}")
            
            # Print sample throughout the cycle
            step = max(1, len(trades) // 8)
            sample_trades = trades[::step]
            if trades[-1] not in sample_trades:
                sample_trades.append(trades[-1])
                
            for t in sample_trades:
                ts = t["created_time"][11:19]
                yp = float(t.get("yes_price_dollars", 0))
                np = float(t.get("no_price_dollars", 0))
                side = t.get("taker_side", "")
                cnt = float(t.get("count_fp", 0))
                print(f"  {ts} UTC | YES: ${yp:.3f} | NO: ${np:.3f} | Taker: {side.upper():4} | Size: {cnt:6.1f} cts")
    except Exception as e:
        print(f"Err fetching {ticker}: {e}")

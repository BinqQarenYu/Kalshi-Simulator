import asyncio
import json
import os
import sys
sys.path.insert(0, os.path.abspath("src"))
import sqlite3
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

from app_2_execution_bot.order_client import KalshiLiveOrderClient
from shared.auth import PROD_REST_BASE

async def main():
    print("=" * 80)
    print("OVERNIGHT TRADING ASSESSMENT: 2026-09-07 20:00 UTC -> 2026-09-08 03:15 UTC")
    print("=" * 80)

    # 1. Database Trades Analysis
    conn = sqlite3.connect("data/kalshi_history.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp_utc, ticker, side, size, price, gross_value, status, execution_mode
        FROM trades
        WHERE timestamp_utc >= '2026-09-07T20:00:00'
        ORDER BY timestamp_utc ASC
    """)
    trades = cursor.fetchall()
    print(f"\n1. TOTAL ORDERS DISPATCHED BY STANDALONE BOT: {len(trades)}")
    for t in trades:
        print(f"  ID: {t[0]} | Time: {t[1]} | Ticker: {t[2]} | {t[3].upper()} {t[4]} cts @ ${t[5]:.2f} | Status: {t[7]}")

    # 2. Kalshi Exchange Fills & Orders
    print("\n2. KALSHI EXCHANGE AUDIT:")
    client = KalshiLiveOrderClient(
        api_key_id=os.getenv("KALSHI_API_KEY_ID", ""),
        private_key_path=os.getenv("KALSHI_PRIVATE_KEY_PATH", ""),
        base_url=PROD_REST_BASE,
    )
    
    bal = await client.get_balance()
    print(f"  Current Live Balance: {bal.get('balance_dollars')}")
    
    open_orders = await client.get_open_orders()
    print(f"  Current Open Orders: {len(open_orders)}")
    
    fills = await client.get_fills(limit=50)
    overnight_fills = [f for f in fills if f.get("created_time", "") >= "2026-09-07T20:00:00Z"]
    print(f"  Overnight Fills on Exchange: {len(overnight_fills)}")
    for of in overnight_fills:
        print(f"   Fill: {of}")
        
    settlements = await client.get_settlements(limit=50)
    overnight_settlements = [s for s in settlements if s.get("settled_time", "") >= "2026-09-07T20:00:00Z"]
    print(f"  Overnight Settlements on Exchange: {len(overnight_settlements)}")
    for os_item in overnight_settlements:
        print(f"   Settlement: {os_item}")

    # 4. Minute-by-minute simulation for the 7 cycles
    print("\n" + "=" * 80)
    print("4. MINUTE-BY-MINUTE SIMULATION: SPOT DIFF $60 vs $70 & DISCOUNT 50c")
    print("=" * 80)
    import urllib.request
    cycles = [
        {"ticker": "KXBTC15M-26SEP071900-00", "start": 1788821100000, "end": 1788822000000, "strike": 78822.48, "order_ts": "22:59:00"},
        {"ticker": "KXBTC15M-26SEP071915-15", "start": 1788822000000, "end": 1788822900000, "strike": 78934.67, "order_ts": "23:14:00"},
        {"ticker": "KXBTC15M-26SEP071945-45", "start": 1788823800000, "end": 1788824700000, "strike": 78996.17, "order_ts": "23:43:59"},
        {"ticker": "KXBTC15M-26SEP072045-45", "start": 1788827400000, "end": 1788828300000, "strike": 79009.66, "order_ts": "00:43:22"},
        {"ticker": "KXBTC15M-26SEP072100-00", "start": 1788828300000, "end": 1788829200000, "strike": 79199.01, "order_ts": "00:59:08"},
        {"ticker": "KXBTC15M-26SEP072130-30", "start": 1788830100000, "end": 1788831000000, "strike": 79298.69, "order_ts": "01:28:58"},
        {"ticker": "KXBTC15M-26SEP072200-00", "start": 1788831900000, "end": 1788832800000, "strike": 79308.06, "order_ts": "01:58:28"},
    ]

    for c in cycles:
        t_str = c["ticker"]
        st = c["start"]
        et = c["end"]
        k = c["strike"]
        url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={st}&endTime={et}&limit=20"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            klines = json.loads(resp.read().decode())
        
        print(f"\n--- {t_str} (Strike: ${k:,.2f}) ---")
        for kl in klines:
            t_ms = kl[0]
            dt_str = datetime.fromtimestamp(t_ms / 1000, tz=timezone.utc).strftime("%H:%M")
            close_px = float(kl[4])
            diff = close_px - k
            t_rem_s = (et - t_ms) / 1000.0
            
            ge_70 = abs(diff) >= 70.0
            ge_60 = abs(diff) >= 60.0
            
            if t_rem_s > 600:
                stage = "P1 (>600s)"
            elif t_rem_s > 240:
                stage = "P2 (240-600s)"
            elif t_rem_s >= 45:
                stage = "P3 (45-240s)"
            else:
                stage = "LOCK (<45s)"
                
            if ge_60 and not ge_70:
                flag = ">>> GAINED AT $60 (was vetoed at $70) <<<"
            elif ge_70:
                flag = "OK at BOTH"
            else:
                flag = "VETOED (diff < $60)"
                
            print(f"  {dt_str} (T_rem={t_rem_s:3.0f}s): Spot=${close_px:,.2f} | Diff={diff:+7.2f} | {stage:12} | {flag}")

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
import sqlite3
import aiohttp
from dotenv import load_dotenv
load_dotenv()

from kalshi_sim.auth import PROD_REST_BASE, DEMO_REST_BASE, get_auth_headers, load_private_key, create_aiohttp_connector

async def fetch_recent_eth_tickers():
    c = sqlite3.connect("data/kalshi_history_eth.db")
    trades = c.execute("SELECT id, timestamp_utc, ticker, side, price FROM trades WHERE id >= 47 ORDER BY id ASC").fetchall()
    print(f"Total recent trades: {len(trades)}")

    api_key_id = os.getenv("KALSHI_API_KEY_ID", "")
    key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")
    env = os.getenv("KALSHI_ENV", "live").lower()
    base_url = PROD_REST_BASE if env in ("prod", "live") else DEMO_REST_BASE
    priv_key = load_private_key(key_path)

    connector = create_aiohttp_connector(limit=5)
    results = []

    async with aiohttp.ClientSession(connector=connector) as session:
        for t in trades:
            trade_id, ts, ticker, side, price = t
            path = f"/trade-api/v2/markets/{ticker}"
            headers = get_auth_headers(api_key_id, priv_key, "GET", path)
            try:
                async with session.get(f"{base_url}/markets/{ticker}", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        m = data.get("market", {})
                        results.append({
                            "trade_id": trade_id,
                            "timestamp": ts,
                            "ticker": ticker,
                            "bot_side": side,
                            "bot_price": price,
                            "market_result": m.get("result"),
                            "status": m.get("status"),
                            "floor_strike": m.get("floor_strike"),
                            "expiration_time": m.get("expiration_time"),
                        })
                    else:
                        print(f"HTTP {resp.status} for {ticker}")
            except Exception as e:
                print(f"Error {ticker}: {e}")

    print("\nRecent ETH trade market results:")
    for r in results:
        won = (r["bot_side"].lower() == str(r["market_result"]).lower())
        print(f"Trade #{r['trade_id']} | {r['timestamp'][:16]} | {r['ticker']} | Bot: {r['bot_side']} @ ${r['bot_price']} | Mkt: {r['market_result']} (status={r['status']}) | Floor: {r['floor_strike']} | Won: {won}")

    import json
    with open("data/recent_eth_trade_results.json", "w") as fp:
        json.dump(results, fp, indent=2)

if __name__ == "__main__":
    asyncio.run(fetch_recent_eth_tickers())

import asyncio
import os
import aiohttp
from dotenv import load_dotenv
load_dotenv()

from kalshi_sim.auth import PROD_REST_BASE, DEMO_REST_BASE, get_auth_headers, load_private_key, create_aiohttp_connector
from kalshi_sim.order_client import KalshiLiveOrderClient

async def get_all_eth_market_details():
    api_key_id = os.getenv("KALSHI_API_KEY_ID", "")
    key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")
    env = os.getenv("KALSHI_ENV", "live").lower()
    base_url = PROD_REST_BASE if env in ("prod", "live") else DEMO_REST_BASE
    priv_key = load_private_key(key_path)

    client = KalshiLiveOrderClient(api_key_id, priv_key, base_url)
    settlements = await client.get_settlements(limit=100)
    eth_settles = [s for s in settlements if "ETH" in s.get("ticker", "")]
    print(f"Total ETH settlements: {len(eth_settles)}")

    connector = create_aiohttp_connector(limit=5)
    markets = []
    async with aiohttp.ClientSession(connector=connector) as session:
        for s in eth_settles:
            ticker = s.get("ticker")
            path = f"/trade-api/v2/markets/{ticker}"
            headers = get_auth_headers(api_key_id, priv_key, "GET", path)
            try:
                async with session.get(f"{base_url}/markets/{ticker}", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        m = data.get("market", {})
                        markets.append({
                            "ticker": ticker,
                            "settled_time": s.get("settled_time"),
                            "market_result": s.get("market_result"),
                            "revenue": s.get("revenue"),
                            "floor_strike": m.get("floor_strike"),
                            "cap_strike": m.get("cap_strike"),
                            "expiration_time": m.get("expiration_time"),
                            "last_price": m.get("last_price"),
                            "yes_bid": m.get("yes_bid"),
                            "yes_ask": m.get("yes_ask"),
                        })
                    else:
                        print(f"Failed {ticker}: HTTP {resp.status}")
            except Exception as e:
                print(f"Error {ticker}: {e}")

    await client.close()

    print("\n--- Fetched Market Details for ETH ---")
    for idx, m in enumerate(markets):
        print(f"#{idx+1}: {m['ticker']} | settle={m['settled_time']} | res={m['market_result']} | floor={m['floor_strike']} | cap={m['cap_strike']}")

    import json
    with open("data/eth_settlement_markets.json", "w") as fp:
        json.dump(markets, fp, indent=2)
    print("Saved to data/eth_settlement_markets.json")

if __name__ == "__main__":
    asyncio.run(get_all_eth_market_details())

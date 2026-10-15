import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from kalshi_sim.order_client import KalshiLiveOrderClient
from kalshi_sim.auth import PROD_REST_BASE, DEMO_REST_BASE

async def fetch_kalshi_settlements():
    api_key_id = os.getenv("KALSHI_API_KEY_ID", "")
    private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")
    env = os.getenv("KALSHI_ENV", "live").lower()
    base_url = PROD_REST_BASE if env in ("prod", "live") else DEMO_REST_BASE

    client = KalshiLiveOrderClient(
        api_key_id=api_key_id,
        private_key_path=private_key_path,
        base_url=base_url,
    )
    
    # fetch all settlements
    settlements = await client.get_settlements(limit=100)
    print(f"Total settlements retrieved: {len(settlements)}")
    
    btc_settlements = [s for s in settlements if "BTC" in s.get("ticker", "")]
    eth_settlements = [s for s in settlements if "ETH" in s.get("ticker", "")]
    
    print(f"BTC settlements: {len(btc_settlements)}")
    print(f"ETH settlements: {len(eth_settlements)}")
    
    print("\nSample BTC settlements (last 3):")
    for s in btc_settlements[:3]:
        print(" ", s)
        
    print("\nSample ETH settlements (last 3):")
    for s in eth_settlements[:3]:
        print(" ", s)

    await client.close()

if __name__ == "__main__":
    asyncio.run(fetch_kalshi_settlements())

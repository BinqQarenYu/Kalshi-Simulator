import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from app_2_execution_bot.order_client import KalshiLiveOrderClient
from shared.auth import PROD_REST_BASE, DEMO_REST_BASE

async def main():
    api_key_id = os.getenv("KALSHI_API_KEY_ID", "")
    private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")
    env = os.getenv("KALSHI_ENV", "live").lower()
    base_url = PROD_REST_BASE if env in ("prod", "live") else DEMO_REST_BASE

    print(f"Connecting to Kalshi API ({env}, {base_url})...")
    client = KalshiLiveOrderClient(
        api_key_id=api_key_id,
        private_key_path=private_key_path,
        base_url=base_url,
    )
    
    # 1. Balance
    bal = await client.get_balance()
    print(f"\n1. Balance: {bal}")
    
    # 2. Open Orders
    orders = await client.get_open_orders()
    print(f"\n2. Open / Resting Orders ({len(orders)}):")
    for o in orders:
        print(" ", o)
        
    # 3. Positions
    positions = await client.get_positions()
    print(f"\n3. Positions ({len(positions)}):")
    for p in positions:
        print(" ", p)
        
    # 4. Fills (Recent)
    fills = await client.get_fills(limit=15)
    print(f"\n4. Recent Fills ({len(fills)}):")
    for f in fills:
        print(" ", f)
        
    # 5. Settlements (Recent)
    settlements = await client.get_settlements(limit=15)
    print(f"\n5. Recent Settlements ({len(settlements)}):")
    for s in settlements:
        print(" ", s)

if __name__ == "__main__":
    asyncio.run(main())

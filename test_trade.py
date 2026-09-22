import asyncio
import os
import sys

sys.path.append('.')

from src.kalshi_sim.order_client import KalshiLiveOrderClient
from src.kalshi_sim.schemas import OrderSide
from decimal import Decimal

async def main():
    try:
        api_key_id = os.environ.get("KALSHI_API_KEY_ID")
        private_key_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "./keys/kalshi_live.pem")
        
        client = KalshiLiveOrderClient(api_key_id=api_key_id, private_key_path=private_key_path)
        
        # Placing order on the specific ticker we just found
        ticker = "KXMVECROSSCATEGORY-S2026AD831A5163B-99435AFB0CE"
            
        print(f"Targeting active ticker: {ticker}")
        
        print(f"Placing market buy YES on {ticker}...")
        res = await client.place_order(
            ticker=ticker,
            side=OrderSide.YES,
            count=1,
            price=Decimal("1.0"),
            action="buy",
            resting_only=False
        )
        print(f"Order Result: {res}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(main())

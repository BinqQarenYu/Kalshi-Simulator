import asyncio
import os
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv(".env")
from kalshi_sim.order_client import KalshiLiveOrderClient

async def rebalance():
    c = KalshiLiveOrderClient()
    bal = await c.get_balance()
    print("Pre-rebalance breakdown:", bal.get("balance_breakdown"))
    success = await c.transfer_between_shards(0, 2, Decimal("5.00"))
    print("Transfer success:", success)
    bal_after = await c.get_balance()
    print("Post-rebalance breakdown:", bal_after.get("balance_breakdown"))

if __name__ == "__main__":
    asyncio.run(rebalance())

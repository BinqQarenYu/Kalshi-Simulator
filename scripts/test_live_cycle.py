import asyncio
import os
import sys
from pathlib import Path
from decimal import Decimal

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from kalshi_sim.order_client import KalshiLiveOrderClient
from kalshi_sim.ml.eth_bot1v4.eth_bot1v4_engine import EthBot1V4Engine
from kalshi_sim.ml.bot1_v4_engine import Bot1V4DominationEngine

async def run():
    print("Initializing KalshiLiveOrderClient...")
    client = KalshiLiveOrderClient()
    bal = await client.get_balance()
    print("Kalshi Live Balance:", bal.get("balance_dollars"))
    
    positions = await client.get_positions()
    print(f"Open Positions: {len(positions)}")
    for p in positions:
        print(f"  {p.get('ticker')}: {p.get('position_fp')} contracts @ market exposure ${p.get('market_exposure_dollars')}")

    print("\n[ETH BOT] Initializing EthBot1V4Engine...")
    eth_bot = EthBot1V4Engine(order_client=client)
    mkt_eth = await eth_bot.fetch_active_market()
    print("Discovered ETH Market:", mkt_eth.ticker if mkt_eth else "None")
    
    print("\n[BTC BOT] Initializing Bot1V4DominationEngine...")
    btc_bot = Bot1V4DominationEngine(order_client=client, asset="BTC")
    mkt_btc = await btc_bot.fetch_active_market()
    print("Discovered BTC Market:", mkt_btc.ticker if mkt_btc else "None")

    await client.close()
    print("\nTest completed successfully!")

if __name__ == "__main__":
    asyncio.run(run())

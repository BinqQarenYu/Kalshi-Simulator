import os, sys, json, asyncio
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path('/home/ec2-user/kalshi-bot')
os.chdir(_ROOT)
load_dotenv(_ROOT / '.env')
sys.path.insert(0, str(_ROOT / 'src'))

from kalshi_sim.order_client import KalshiLiveOrderClient

async def check():
    key_id = os.getenv("KALSHI_API_KEY_ID")
    key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")
    if key_path and not os.path.isabs(key_path):
        key_path = str(_ROOT / key_path)
    client = KalshiLiveOrderClient(api_key_id=key_id, private_key_path=key_path)
    settlements = await client.get_settlements(limit=25)
    print(f"Total settlements fetched: {len(settlements)}")
    for s in settlements:
        ticker = s.get('ticker')
        res = s.get('market_result')
        rev = s.get('revenue')
        yes_cnt = s.get('yes_count_fp')
        no_cnt = s.get('no_count_fp')
        settled_time = s.get('settled_time')
        print(f"{settled_time} | {ticker} | result={res} | rev={rev} | yes_cnt={yes_cnt} | no_cnt={no_cnt}")
    await client.close()

asyncio.run(check())

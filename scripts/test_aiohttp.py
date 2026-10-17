import asyncio
import aiohttp
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from kalshi_sim.auth import create_aiohttp_connector

async def test_connector():
    url = "https://api.elections.kalshi.com/trade-api/v2/exchange/status"
    connector = create_aiohttp_connector()
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                print("aiohttp + create_aiohttp_connector status:", resp.status)
                text = await resp.text()
                print("Response:", text[:100])
    except Exception as e:
        print("error:", type(e), e)

if __name__ == "__main__":
    asyncio.run(test_connector())

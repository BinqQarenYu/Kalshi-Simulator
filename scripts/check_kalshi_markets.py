"""Check active Kalshi markets and inspect strikes and tickers."""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
load_dotenv(_ROOT / ".env")

from kalshi_sim.order_client import KalshiLiveOrderClient
from kalshi_sim.auth import PROD_REST_BASE, get_auth_headers


async def main() -> None:
    client = KalshiLiveOrderClient(
        os.getenv("KALSHI_API_KEY_ID"),
        os.getenv("KALSHI_PRIVATE_KEY_PATH"),
        base_url=PROD_REST_BASE,
    )
    headers = get_auth_headers(client.api_key_id, client.private_key, "GET", "/trade-api/v2/markets")
    session = await client._get_session()
    for series in ["KXBTC15M", "KXETH15M"]:
        url = f"{PROD_REST_BASE}/markets?series_ticker={series}&status=open"
        async with session.get(url, headers=headers) as r:
            data = await r.json()
            markets = data.get("markets", [])
            print(f"=== {series}: Total open markets = {len(markets)} ===")
            for m in markets[:5]:
                print(
                    f"Ticker: {m.get('ticker')} | Floor: {m.get('floor_strike')} | "
                    f"Cap: {m.get('cap_strike')} | Close: {m.get('close_time')} | "
                    f"Subtitle: {m.get('subtitle')}"
                )
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())

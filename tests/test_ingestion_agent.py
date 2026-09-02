import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Mock missing modules before importing modules that depend on them
for mod in ["aiosqlite", "fastapi", "torch", "fastapi.testclient"]:
    sys.modules[mod] = MagicMock()

from kalshi_sim.ingestion_agent import IngestionAgent

@pytest.mark.asyncio
async def test_stale_tickers_resubscription():
    with patch("kalshi_sim.ingestion_agent.load_private_key", return_value=MagicMock()):
        agent = IngestionAgent(api_key_id="test_key", private_key_path="test_path", timeframes=[])

    agent._ws_client = MagicMock()
    agent._ws_client.subscribe = AsyncMock()

    agent._orderbook = MagicMock()
    agent._orderbook.get_stale_tickers.return_value = ["KXBTC-STALE-TICKER"]

    with patch.object(agent, "_refresh_markets", new=AsyncMock()), \
         patch("kalshi_sim.ingestion_agent.MARKET_REFRESH_INTERVAL_S", 0.01):

        async def stop_soon():
            await asyncio.sleep(0.05)
            agent._shutdown_event.set()

        task = asyncio.create_task(agent._market_refresh_loop())
        stop_task = asyncio.create_task(stop_soon())
        await asyncio.gather(task, stop_task)

    agent._ws_client.subscribe.assert_called_with(
        channels=["orderbook_delta", "ticker", "trade"],
        market_tickers=["KXBTC-STALE-TICKER"],
    )

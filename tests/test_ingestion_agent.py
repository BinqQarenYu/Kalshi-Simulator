import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from kalshi_sim.ingestion_agent import IngestionAgent

@pytest.mark.asyncio
async def test_stale_tickers_resubscription():
    with patch("kalshi_sim.ingestion_agent.load_private_key", return_value=MagicMock()):
        agent = IngestionAgent(api_key_id="test_key", private_key_path="test_path", timeframes=[])

    agent._ws_client = MagicMock()
    agent._ws_client.is_connected = True
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
        await asyncio.sleep(0.02)

    agent._ws_client.subscribe.assert_called_with(
        channels=["orderbook_delta"],
        market_tickers=["KXBTC-STALE-TICKER"],
    )

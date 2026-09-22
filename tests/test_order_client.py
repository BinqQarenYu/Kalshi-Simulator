"""Unit tests for the KalshiDemoOrderClient."""

import asyncio
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app_2_execution_bot.order_client import KalshiDemoOrderClient
from shared.schemas import OrderSide


class TestKalshiDemoOrderClient(unittest.IsolatedAsyncioTestCase):
    """Test suite for KalshiDemoOrderClient."""

    @patch("kalshi_sim.order_client.load_private_key")
    def setUp(self, mock_load_key) -> None:
        mock_load_key.return_value = "mock_key"
        self.client = KalshiDemoOrderClient(
            api_key_id="test_key_id",
            private_key_path="./keys/kalshi_demo.pem",
        )

    async def test_order_client_initialization(self) -> None:
        self.assertEqual(self.client.api_key_id, "test_key_id")
        self.assertTrue(self.client.base_url.startswith("https://"))
        self.assertEqual(self.client._primary_exchange_index, 0)

    @patch("kalshi_sim.order_client.get_auth_headers", return_value={"mock": "header"})
    async def test_shard_dynamic_selection_from_balance(self, mock_auth) -> None:
        mock_response = {
            "balance": 3038,
            "balance_breakdown": [
                {"balance": "30.3705", "exchange_index": 0},
                {"balance": "0.0000", "exchange_index": 1},
                {"balance": "0.0126", "exchange_index": 2},
                {"balance": "0.0000", "exchange_index": 3},
            ],
            "balance_dollars": "30.3831",
        }
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)
        
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get.return_value = mock_cm

        with patch.object(self.client, "_get_session", new_callable=AsyncMock) as mock_get_session:
            mock_get_session.return_value = mock_session
            res = await self.client.get_balance()
            self.assertEqual(res["balance"], 3038)
            # Must detect shard 0 as the highest funded exchange shard
            self.assertEqual(self.client._primary_exchange_index, 0)


if __name__ == "__main__":
    unittest.main()

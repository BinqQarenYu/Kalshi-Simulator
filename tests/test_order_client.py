"""Unit tests for the KalshiDemoOrderClient."""

import asyncio
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from kalshi_sim.order_client import KalshiDemoOrderClient
from kalshi_sim.schemas import OrderSide


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


if __name__ == "__main__":
    unittest.main()

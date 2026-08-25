"""Kalshi Demo Order Execution Client.

Provides full order management for Kalshi's Demo (Paper Trading) environment:
- Submits market and limit orders (Yes/No)
- Cancels active orders
- Fetches real-time portfolio balance, positions, open orders, and fills
- Implements idempotent UUID tracking and RSA-PSS signed requests
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

import aiohttp

from kalshi_sim.auth import DEMO_REST_BASE, get_auth_headers, load_private_key
from kalshi_sim.schemas import OrderSide, OrderType

logger = logging.getLogger("OrderClient")


class KalshiDemoOrderClient:
    """Asynchronous client for placing and managing orders on Kalshi Demo."""

    def __init__(
        self,
        api_key_id: str,
        private_key_path: str,
        base_url: str = DEMO_REST_BASE,
    ) -> None:
        self.api_key_id = api_key_id
        self.private_key = load_private_key(private_key_path)
        self.base_url = base_url.rstrip("/")

    async def get_balance(self) -> Dict[str, Any]:
        """Fetch current demo account cash balance and credit line."""
        endpoint = "/trade-api/v2/portfolio/balance"
        url = f"{self.base_url}/portfolio/balance"
        headers = get_auth_headers(self.api_key_id, self.private_key, "GET", endpoint)

        connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    logger.error("Failed to fetch balance (HTTP %d): %s", resp.status, err_text)
                    return {"balance": 0, "status": resp.status, "error": err_text}
                data = await resp.json()
                logger.info("Kalshi Demo Account Balance: %s", data)
                return data

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Fetch all currently open market positions on Kalshi Demo."""
        endpoint = "/trade-api/v2/portfolio/positions"
        url = f"{self.base_url}/portfolio/positions"
        headers = get_auth_headers(self.api_key_id, self.private_key, "GET", endpoint)

        connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    logger.error("Failed to fetch positions (HTTP %d): %s", resp.status, err_text)
                    return []
                data = await resp.json()
                return data.get("market_positions", [])

    async def get_open_orders(self) -> List[Dict[str, Any]]:
        """Fetch all resting limit orders currently active on Kalshi Demo."""
        endpoint = "/trade-api/v2/portfolio/orders"
        url = f"{self.base_url}/portfolio/orders"
        params = {"status": "resting"}
        headers = get_auth_headers(self.api_key_id, self.private_key, "GET", endpoint)

        connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    logger.error("Failed to fetch open orders (HTTP %d): %s", resp.status, err_text)
                    return []
                data = await resp.json()
                return data.get("orders", [])

    async def place_order(
        self,
        ticker: str,
        side: OrderSide | str,
        count: int,
        action: str = "buy",
        order_type: str = "market",
        price_dollars: Optional[Decimal] = None,
        client_order_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Submit a new order to the Kalshi Demo exchange.

        Args:
            ticker: Market contract ticker (e.g. 'KXBTC15M-26AUG251830-30').
            side: OrderSide.YES or OrderSide.NO.
            count: Number of contracts to buy/sell.
            action: 'buy' or 'sell' (default: 'buy').
            order_type: 'market' or 'limit' (default: 'market').
            price_dollars: Limit price in dollars ($0.01 - $0.99) if limit order.
            client_order_id: Optional idempotency UUID. Generated automatically if omitted.

        Returns:
            Dict containing order response and fill details, or None on failure.
        """
        side_val = side.value if hasattr(side, "value") else str(side).lower()
        endpoint = "/trade-api/v2/portfolio/orders"
        url = f"{self.base_url}/portfolio/orders"

        order_uuid = client_order_id or str(uuid.uuid4())

        payload: Dict[str, Any] = {
            "action": action.lower(),
            "count": count,
            "type": order_type.lower(),
            "ticker": ticker,
            "side": side_val,
            "client_order_id": order_uuid,
        }

        # Handle price specifications
        if price_dollars is not None:
            # Send fixed-point dollar price
            if side_val == "yes":
                payload["yes_price_dollars"] = f"{price_dollars:.4f}"
            else:
                payload["no_price_dollars"] = f"{price_dollars:.4f}"

        headers = get_auth_headers(self.api_key_id, self.private_key, "POST", endpoint)
        headers["Content-Type"] = "application/json"

        connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status not in (200, 201):
                        err_text = await resp.text()
                        logger.error(
                            "Order rejected by Kalshi Demo (HTTP %d): %s | Payload: %s",
                            resp.status, err_text, payload,
                        )
                        return None
                    order_data = await resp.json()
                    order_info = order_data.get("order", order_data)
                    logger.info(
                        "DEMO ORDER PLACED: %s %s %d %s | ID: %s | Status: %s",
                        action.upper(), side_val.upper(), count, ticker,
                        order_info.get("order_id", order_uuid),
                        order_info.get("status", "executed"),
                    )
                    return order_info
            except Exception as exc:
                logger.error("Network error placing order on Kalshi Demo: %s", exc, exc_info=True)
                return None

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a resting order on Kalshi Demo."""
        endpoint = f"/trade-api/v2/portfolio/orders/{order_id}"
        url = f"{self.base_url}/portfolio/orders/{order_id}"
        headers = get_auth_headers(self.api_key_id, self.private_key, "DELETE", endpoint)

        connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.delete(url, headers=headers) as resp:
                if resp.status == 200:
                    logger.info("Successfully cancelled demo order: %s", order_id)
                    return True
                err_text = await resp.text()
                logger.error("Failed to cancel order %s (HTTP %d): %s", order_id, resp.status, err_text)
                return False

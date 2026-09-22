"""Multi-Exchange Routing & Connectivity Architecture.

Provides unified gateway interfaces for routing orders and streaming order flow
across multiple prediction and continuous spot venues:
- Kalshi Production / Demo Exchange (Binary options execution)
- CME CF Benchmarks BRTI 5Hz (Settlement parity reference)
- Binance / Coinbase Continuous Spot Feeds (Microstructure lead indicators)
- Extensible adapters for future prediction venues (e.g. Polymarket, ForecastEx)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from shared.schemas import L2BookState, OrderSide, OrderType

logger = logging.getLogger("ExchangeRouter")


class BaseExchangeClient(ABC):
    """Abstract interface for all exchange execution and market data adapters."""

    def __init__(self, exchange_id: str, exchange_name: str, is_live: bool = False) -> None:
        self.exchange_id = exchange_id
        self.exchange_name = exchange_name
        self.is_live = is_live
        self._connected: bool = False
        self._last_heartbeat: float = 0.0
        self._latency_ms: float = 0.0

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def latency_ms(self) -> float:
        return self._latency_ms

    @abstractmethod
    async def get_balance(self) -> Decimal:
        """Fetch available cash balance in Decimal USD."""
        raise NotImplementedError

    @abstractmethod
    async def place_order(
        self,
        ticker: str,
        side: OrderSide | str,
        count: int,
        order_type: OrderType | str,
        price_dollars: Optional[Decimal] = None,
        action: str = "buy",
        exchange_index: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Submit an order to the exchange."""
        raise NotImplementedError

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open resting order."""
        raise NotImplementedError

    @abstractmethod
    async def get_open_orders(self, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch active open orders."""
        raise NotImplementedError

    @abstractmethod
    async def check_health(self) -> Tuple[bool, float, str]:
        """Perform a ping/healthcheck and return (is_healthy, latency_ms, status_message)."""
        raise NotImplementedError

    def get_status_summary(self) -> Dict[str, Any]:
        """Return standardized status telemetry."""
        return {
            "exchange_id": self.exchange_id,
            "exchange_name": self.exchange_name,
            "is_live": self.is_live,
            "connected": self._connected,
            "latency_ms": round(self._latency_ms, 2),
            "last_heartbeat": self._last_heartbeat,
        }


class KalshiExchangeAdapter(BaseExchangeClient):
    """Adapter wrapping KalshiLiveOrderClient / KalshiDemoOrderClient."""

    def __init__(self, inner_client: Any, is_live: bool = True) -> None:
        super().__init__(
            exchange_id="kalshi",
            exchange_name="Kalshi Prediction Exchange",
            is_live=is_live,
        )
        self.inner_client = inner_client
        self._connected = inner_client is not None

    async def get_balance(self) -> Decimal:
        if not self.inner_client:
            return Decimal("0.00")
        try:
            state = await self.inner_client.get_live_portfolio_state()
            self._connected = True
            return state.balance_dollars
        except Exception as exc:
            logger.error("Failed to fetch Kalshi balance: %s", exc)
            self._connected = False
            return Decimal("0.00")

    async def place_order(
        self,
        ticker: str,
        side: OrderSide | str,
        count: int,
        order_type: OrderType | str,
        price_dollars: Optional[Decimal] = None,
        action: str = "buy",
        exchange_index: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self.inner_client:
            return None
        t0 = time.perf_counter()
        res = await self.inner_client.place_order(
            ticker=ticker,
            side=side.value if hasattr(side, "value") else str(side),
            count=count,
            action=action,
            order_type=order_type.value if hasattr(order_type, "value") else str(order_type),
            price_dollars=price_dollars,
            exchange_index=exchange_index,
        )
        self._latency_ms = (time.perf_counter() - t0) * 1000.0
        self._last_heartbeat = time.time()
        return res

    async def cancel_order(self, order_id: str) -> bool:
        if not self.inner_client:
            return False
        return await self.inner_client.cancel_order(order_id)

    async def get_open_orders(self, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.inner_client:
            return []
        orders = await self.inner_client.get_open_orders()
        if ticker:
            return [o for o in orders if o.get("ticker") == ticker]
        return orders

    async def check_health(self) -> Tuple[bool, float, str]:
        if not self.inner_client:
            return False, 0.0, "CLIENT_NOT_INITIALIZED"
        t0 = time.perf_counter()
        try:
            orders = await self.inner_client.get_open_orders()
            lat = (time.perf_counter() - t0) * 1000.0
            self._latency_ms = lat
            self._connected = True
            self._last_heartbeat = time.time()
            return True, lat, f"OK ({len(orders)} open orders)"
        except Exception as exc:
            self._connected = False
            return False, 0.0, f"DISCONNECTED: {exc}"


class SpotExchangeAdapter(BaseExchangeClient):
    """Adapter for high-frequency continuous spot reference feeds (Binance / Coinbase)."""

    def __init__(self, exchange_id: str, exchange_name: str, spot_getter: Optional[Any] = None) -> None:
        super().__init__(exchange_id=exchange_id, exchange_name=exchange_name, is_live=False)
        self.spot_getter = spot_getter
        self._connected = spot_getter is not None

    async def get_balance(self) -> Decimal:
        return Decimal("0.00")

    async def place_order(
        self,
        ticker: str,
        side: OrderSide | str,
        count: int,
        order_type: OrderType | str,
        price_dollars: Optional[Decimal] = None,
        action: str = "buy",
        exchange_index: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        logger.info("[SPOT FEED ONLY] %s is a market data reference; orders are routed to primary execution venue.", self.exchange_name)
        return None

    async def cancel_order(self, order_id: str) -> bool:
        return True

    async def get_open_orders(self, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        return []

    async def check_health(self) -> Tuple[bool, float, str]:
        t0 = time.perf_counter()
        if self.spot_getter:
            try:
                price = self.spot_getter()
                lat = (time.perf_counter() - t0) * 1000.0
                self._latency_ms = lat
                self._connected = True
                self._last_heartbeat = time.time()
                return True, lat, f"STREAMING (${float(price):,.2f})"
            except Exception as exc:
                self._connected = False
                return False, 0.0, f"GETTER_ERROR: {exc}"
        return False, 0.0, "NO_DATA_STREAM"


class ExchangeRouter:
    """Institutional Gateway coordinating multi-exchange order routing and feed status."""

    def __init__(self, primary_exchange: Optional[BaseExchangeClient] = None) -> None:
        self.exchanges: Dict[str, BaseExchangeClient] = {}
        self.primary_exchange_id: str = "kalshi"
        if primary_exchange:
            self.register_exchange(primary_exchange, is_primary=True)

    def register_exchange(self, client: BaseExchangeClient, is_primary: bool = False) -> None:
        self.exchanges[client.exchange_id] = client
        if is_primary:
            self.primary_exchange_id = client.exchange_id
        logger.info("Registered exchange adapter: %s (Primary: %s)", client.exchange_id, is_primary)

    def get_exchange(self, exchange_id: Optional[str] = None) -> Optional[BaseExchangeClient]:
        target_id = exchange_id or self.primary_exchange_id
        return self.exchanges.get(target_id)

    async def route_order(
        self,
        ticker: str,
        side: OrderSide | str,
        count: int,
        order_type: OrderType | str,
        price_dollars: Optional[Decimal] = None,
        exchange_id: Optional[str] = None,
        action: str = "buy",
        exchange_index: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Route order to target exchange client."""
        client = self.get_exchange(exchange_id)
        if not client:
            logger.error("No exchange registered for id: %s", exchange_id or self.primary_exchange_id)
            return None
        return await client.place_order(
            ticker=ticker,
            side=side,
            count=count,
            order_type=order_type,
            price_dollars=price_dollars,
            action=action,
            exchange_index=exchange_index,
        )

    async def get_all_status(self) -> Dict[str, Any]:
        """Aggregate health and status telemetry across all configured exchanges."""
        status_map: Dict[str, Any] = {}
        for ex_id, client in self.exchanges.items():
            is_ok, lat, msg = await client.check_health()
            summary = client.get_status_summary()
            summary.update({
                "healthy": is_ok,
                "latency_ms": round(lat, 2),
                "status_message": msg,
                "is_primary": (ex_id == self.primary_exchange_id),
            })
            status_map[ex_id] = summary
        return {
            "primary_exchange": self.primary_exchange_id,
            "total_venues": len(self.exchanges),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "venues": status_map,
        }

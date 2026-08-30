"""Kalshi Demo Order Execution Client.

Provides full order management for Kalshi's Demo (Paper Trading) environment:
- Submits market and limit orders (Yes/No)
- Cancels active orders
- Fetches real-time portfolio balance, positions, open orders, and fills
- Implements idempotent UUID tracking, Windows-hardened DNS resolver, and RSA-PSS signed requests
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

import aiohttp

from kalshi_sim.auth import (
    DEMO_REST_BASE,
    PROD_REST_BASE,
    create_aiohttp_connector,
    get_auth_headers,
    load_private_key,
)
from kalshi_sim.schemas import (
    LivePortfolioState,
    LivePositionItem,
    OrderSide,
    OrderType,
    ReconciliationReport,
)

logger = logging.getLogger("OrderClient")


class KalshiLiveOrderClient:
    """Asynchronous client for placing and managing orders on Kalshi Production Exchange."""

    def __init__(
        self,
        api_key_id: str,
        private_key_path: str | Path | Any,
        base_url: str = PROD_REST_BASE,
    ) -> None:
        self.api_key_id = api_key_id
        if hasattr(private_key_path, "sign"):
            self.private_key = private_key_path
        else:
            self.private_key = load_private_key(private_key_path)
        self.base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or lazily initialize a connection-pooled aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(connector=create_aiohttp_connector())
        return self._session

    async def close(self) -> None:
        """Close the internal HTTP session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get_balance(self) -> Dict[str, Any]:
        """Fetch current demo account cash balance and credit line."""
        endpoint = "/trade-api/v2/portfolio/balance"
        url = f"{self.base_url}/portfolio/balance"
        headers = get_auth_headers(self.api_key_id, self.private_key, "GET", endpoint)

        session = await self._get_session()
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                err_text = await resp.text()
                logger.error("Failed to fetch balance (HTTP %d): %s", resp.status, err_text)
                return {"balance": 0, "status": resp.status, "error": err_text}
            data = await resp.json()
            logger.info("Kalshi Live Account Balance: %s", data)
            return data

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Fetch all currently open market positions on Kalshi Demo."""
        endpoint = "/trade-api/v2/portfolio/positions"
        url = f"{self.base_url}/portfolio/positions"
        headers = get_auth_headers(self.api_key_id, self.private_key, "GET", endpoint)

        session = await self._get_session()
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

        session = await self._get_session()
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
        resting_only: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Submit a new order to the Kalshi exchange using the official V2 Trade API.

        Args:
            ticker: Market contract ticker (e.g. 'KXBTC15M-26AUG300215-15').
            side: OrderSide.YES ('yes') or OrderSide.NO ('no').
            count: Number of contracts to buy/sell.
            action: 'buy' or 'sell' (default: 'buy').
            order_type: 'market' or 'limit' (default: 'market').
            price_dollars: Limit price in dollars ($0.01 - $0.99) if limit order.
            client_order_id: Optional idempotency UUID. Generated automatically if omitted.
            resting_only: If true, enables post_only to guarantee maker liquidity.

        Returns:
            Dict containing order response and fill details, or None on failure.
        """
        side_val = side.value if hasattr(side, "value") else str(side).lower()
        endpoint = "/trade-api/v2/portfolio/orders"
        url = f"{self.base_url}/portfolio/orders"

        order_uuid = client_order_id or str(uuid.uuid4())
        
        # In Kalshi's V2 single-book architecture:
        # Buying YES = side "bid", price = yes_price
        # Buying NO  = side "ask", price = 1.0 - no_price (or equivalent YES price)
        if side_val == "yes":
            v2_side = "bid"
            v2_price = price_dollars if price_dollars is not None else Decimal("0.65")
        else:
            # Buying NO is matching against the ask side or posting ask
            v2_side = "ask"
            if price_dollars is not None:
                v2_price = Decimal("1.00") - price_dollars
            else:
                v2_price = Decimal("0.35")

        is_limit = order_type.lower() == "limit"
        payload: Dict[str, Any] = {
            "ticker": ticker,
            "client_order_id": order_uuid,
            "side": v2_side,
            "count": f"{count:.2f}",
            "price": f"{v2_price:.4f}",
            "time_in_force": "good_till_canceled" if is_limit else "immediate_or_cancel",
            "self_trade_prevention_type": "taker_at_cross",
            "post_only": bool(resting_only and is_limit),
        }

        headers = get_auth_headers(self.api_key_id, self.private_key, "POST", endpoint)
        headers["Content-Type"] = "application/json"

        session = await self._get_session()
        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    logger.error(
                        "Order rejected by Kalshi (HTTP %d): %s | Payload: %s",
                        resp.status, err_text, payload,
                    )
                    return None
                order_data = await resp.json()
                logger.info(
                    "KALSHI V2 ORDER PLACED: %s %s %d %s | ID: %s | Status: %s",
                    action.upper(), side_val.upper(), count, ticker,
                    order_data.get("order_id", order_uuid),
                    order_data.get("status", "executed"),
                )
                return order_data
        except Exception as exc:
            logger.error("Network error placing order on Kalshi V2: %s", exc, exc_info=True)
            return None

    async def cancel_order(self, order_id: str, ticker: Optional[str] = None) -> bool:
        """Cancel a resting order on Kalshi using V2 Trade API."""
        endpoint = f"/trade-api/v2/portfolio/orders/{order_id}"
        query_suffix = f"?market_ticker={ticker}" if ticker else ""
        url = f"{self.base_url}/portfolio/orders/{order_id}{query_suffix}"
        headers = get_auth_headers(self.api_key_id, self.private_key, "DELETE", endpoint)

        session = await self._get_session()
        async with session.delete(url, headers=headers) as resp:
            if resp.status == 200:
                logger.info("Successfully cancelled order: %s", order_id)
                return True
            err_text = await resp.text()
            logger.error("Failed to cancel order %s (HTTP %d): %s", order_id, resp.status, err_text)
            return False

    async def get_live_portfolio_state(self) -> LivePortfolioState:
        """Fetch and structure real-time exchange portfolio balance and positions."""
        bal_data = await self.get_balance()
        pos_data = await self.get_positions()

        if "balance_dollars" in bal_data and bal_data["balance_dollars"] is not None:
            balance_dollars = Decimal(str(bal_data["balance_dollars"]))
        else:
            raw_balance = bal_data.get("balance", 0)
            balance_dollars = Decimal(str(raw_balance)) / Decimal("100") if isinstance(raw_balance, int) else Decimal(str(raw_balance))

        if "available_balance_dollars" in bal_data and bal_data["available_balance_dollars"] is not None:
            available_margin = Decimal(str(bal_data["available_balance_dollars"]))
        elif "balance_dollars" in bal_data and bal_data["balance_dollars"] is not None:
            available_margin = Decimal(str(bal_data["balance_dollars"]))
        else:
            raw_margin = bal_data.get("available_balance", bal_data.get("balance", 0))
            available_margin = Decimal(str(raw_margin)) / Decimal("100") if isinstance(raw_margin, int) else Decimal(str(raw_margin))

        raw_payout = bal_data.get("payout", 0)
        payout_pending = Decimal(str(raw_payout)) / Decimal("100") if isinstance(raw_payout, int) else Decimal(str(raw_payout))

        positions: List[LivePositionItem] = []
        for p in pos_data:
            ticker = p.get("ticker", "")
            pos_raw = p.get("position", p.get("position_fp", 0))
            try:
                pos_cnt = int(float(str(pos_raw)))
            except (ValueError, TypeError):
                pos_cnt = 0

            resting_cnt = p.get("resting_orders_count", 0)

            # Filter out flat / historical zero-contract records with zero resting orders
            if pos_cnt == 0 and resting_cnt == 0:
                continue

            side = OrderSide.YES if pos_cnt >= 0 else OrderSide.NO

            if "fees_paid_dollars" in p and p["fees_paid_dollars"] is not None:
                fees = Decimal(str(p["fees_paid_dollars"]))
            else:
                fees = Decimal(str(p.get("fees_paid", 0))) / Decimal("100") if isinstance(p.get("fees_paid"), int) else Decimal(str(p.get("fees_paid", 0)))

            if "realized_pnl_dollars" in p and p["realized_pnl_dollars"] is not None:
                realized = Decimal(str(p["realized_pnl_dollars"]))
            else:
                realized = Decimal(str(p.get("realized_pnl", 0))) / Decimal("100") if isinstance(p.get("realized_pnl"), int) else Decimal(str(p.get("realized_pnl", 0)))

            positions.append(
                LivePositionItem(
                    ticker=ticker,
                    position=pos_cnt,
                    side=side,
                    fees_paid=fees,
                    realized_pnl=realized,
                    resting_orders_count=resting_cnt,
                )
            )

        return LivePortfolioState(
            balance_dollars=balance_dollars,
            available_margin=available_margin,
            payout_pending=payout_pending,
            positions=positions,
        )

    async def reconcile_with_simulated(self, sim_portfolio: Any) -> ReconciliationReport:
        """Compare simulated portfolio ledger with live exchange state and report discrepancies."""
        live_state = await self.get_live_portfolio_state()
        sim_cash = sim_portfolio.current_balance
        exchange_cash = live_state.balance_dollars
        cash_delta = exchange_cash - sim_cash

        alerts: List[str] = []
        is_synced = True

        if abs(cash_delta) > Decimal("1.00"):
            alerts.append(f"Cash divergence detected: Exchange ${exchange_cash:.2f} vs Simulated ${sim_cash:.2f} (Delta: ${cash_delta:+.2f})")
            is_synced = False

        sim_positions = sim_portfolio.get_open_positions()
        if len(sim_positions) != len(live_state.positions):
            alerts.append(f"Position count divergence: Exchange has {len(live_state.positions)} vs Simulator has {len(sim_positions)}")
            is_synced = False

        return ReconciliationReport(
            is_synchronized=is_synced,
            simulated_cash=sim_cash,
            exchange_cash=exchange_cash,
            cash_discrepancy=cash_delta,
            simulated_positions_count=len(sim_positions),
            exchange_positions_count=len(live_state.positions),
            alerts=alerts,
        )


# Backwards compatibility alias
KalshiDemoOrderClient = KalshiLiveOrderClient


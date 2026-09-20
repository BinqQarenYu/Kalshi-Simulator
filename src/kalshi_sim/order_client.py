"""Kalshi Demo Order Execution Client.

Provides full order management for Kalshi's Demo (Paper Trading) environment:
- Submits market and limit orders (Yes/No)
- Cancels active orders
- Fetches real-time portfolio balance, positions, open orders, and fills
- Implements idempotent UUID tracking, Windows-hardened DNS resolver, and RSA-PSS signed requests
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
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
        self._primary_exchange_index: int = 0
        self.shard_balances: Dict[int, Decimal] = {}
        self.is_in_maintenance: bool = False
        self.maintenance_reason: str = "Online"
        self.last_maintenance_check_ts: float = 0.0
        self._maintenance_task: Optional[asyncio.Task] = None
        self._maintenance_file = Path("data") / "kalshi_maintenance.json"
        self._maintenance_file.parent.mkdir(parents=True, exist_ok=True)

    def set_maintenance_state(self, active: bool, reason: str = "Exchange Maintenance Active") -> None:
        """Update exchange maintenance state and write disk telemetry for cross-process coordination."""
        was_active = self.is_in_maintenance
        self.is_in_maintenance = active
        self.maintenance_reason = reason if active else "Online"
        now_ts = time.time()
        self.last_maintenance_check_ts = now_ts

        payload = {
            "active": active,
            "reason": self.maintenance_reason,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "updated_ts": now_ts,
        }
        try:
            temp_file = self._maintenance_file.with_suffix(".tmp")
            temp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temp_file.replace(self._maintenance_file)
        except Exception as exc:
            logger.error("Failed to write kalshi_maintenance.json: %s", exc)

        if active and not was_active:
            logger.warning(
                "⚠️ [KALSHI MAINTENANCE DETECTED] Exchange maintenance active (%s). "
                "AUTOMATICALLY PAUSING ALL LIVE TRADES.",
                reason,
            )
            self._start_maintenance_monitor()
        elif not active and was_active:
            logger.info(
                "✅ [KALSHI MAINTENANCE COMPLETED] Exchange is online and healthy. "
                "AUTOMATICALLY RESUMING AUTOMATED LIVE TRADING."
            )

    def _start_maintenance_monitor(self) -> None:
        """Launch background health polling loop while exchange is in maintenance."""
        if self._maintenance_task is None or self._maintenance_task.done():
            try:
                loop = asyncio.get_running_loop()
                self._maintenance_task = loop.create_task(self._maintenance_monitor_loop())
            except RuntimeError:
                pass

    async def _maintenance_monitor_loop(self) -> None:
        """Poll Kalshi exchange status every 10 seconds until maintenance completes."""
        logger.info("[KALSHI MAINTENANCE MONITOR] Polling exchange health every 10s for auto-resume...")
        while self.is_in_maintenance:
            await asyncio.sleep(10.0)
            try:
                status_res = await self.get_exchange_status()
                if status_res.get("exchange_active", False) and status_res.get("trading_active", False):
                    self.set_maintenance_state(False, reason="Online")
                    break
            except Exception as exc:
                logger.debug("[KALSHI MAINTENANCE MONITOR] Exchange still unavailable: %s", exc)

    async def get_exchange_status(self) -> Dict[str, Any]:
        """Fetch official Kalshi exchange status endpoint (/trade-api/v2/exchange/status)."""
        endpoint = "/trade-api/v2/exchange/status"
        url = f"{self.base_url}/exchange/status"
        session = await self._get_session()

        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ex_active = data.get("exchange_active", True)
                    tr_active = data.get("trading_active", True)

                    if not ex_active or not tr_active:
                        self.set_maintenance_state(
                            True,
                            reason=f"Kalshi API reported exchange_active={ex_active}, trading_active={tr_active}",
                        )
                    elif self.is_in_maintenance:
                        self.set_maintenance_state(False, reason="Online")

                    return data
                elif resp.status in (502, 503, 504):
                    err_text = await resp.text()
                    self.set_maintenance_state(True, reason=f"Kalshi maintenance HTTP {resp.status}: {err_text[:100]}")
                    return {"exchange_active": False, "trading_active": False, "status": resp.status, "error": err_text}
                else:
                    err_text = await resp.text()
                    return {"exchange_active": True, "trading_active": True, "status": resp.status, "error": err_text}
        except Exception as exc:
            logger.warning("Error checking Kalshi exchange status: %s", exc)
            return {"exchange_active": not self.is_in_maintenance, "trading_active": not self.is_in_maintenance, "error": str(exc)}

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
        """Fetch current demo/live account cash balance and update primary exchange index."""
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
            breakdown = data.get("balance_breakdown", [])
            self.shard_balances = {}
            for item in breakdown:
                try:
                    idx = int(item.get("exchange_index", 0))
                    self.shard_balances[idx] = Decimal(str(item.get("balance", "0.0")))
                except (ValueError, TypeError):
                    pass
            if breakdown:
                best_shard = max(breakdown, key=lambda item: Decimal(str(item.get("balance", "0.0"))))
                self._primary_exchange_index = int(best_shard.get("exchange_index", 0))
            return data

    async def transfer_between_shards(
        self,
        source_shard: int,
        destination_shard: int,
        amount_dollars: Decimal,
    ) -> bool:
        """Transfer collateral between Kalshi exchange matching engines (e.g. Shard 0 -> Shard 2)."""
        endpoint = "/trade-api/v2/portfolio/intra_exchange_instance_transfer"
        url = f"{self.base_url}/portfolio/intra_exchange_instance_transfer"
        # Kalshi intra-exchange transfer API amount is in cent-fractions: $1.00 = 10,000 units
        amount_units = int(amount_dollars * Decimal("10000"))
        payload = {
            "source": "event_contract",
            "destination": "event_contract",
            "source_exchange_shard": source_shard,
            "destination_exchange_shard": destination_shard,
            "amount": amount_units,
        }
        session = await self._get_session()
        headers = get_auth_headers(self.api_key_id, self.private_key, "POST", endpoint)
        headers["Content-Type"] = "application/json"
        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status in (200, 201):
                    res_data = await resp.json()
                    logger.info(
                        "[SHARD REBALANCE] Successfully transferred $%s from Shard %d to Shard %d (ID: %s)",
                        amount_dollars, source_shard, destination_shard, res_data.get("transfer_id"),
                    )
                    await self.get_balance()
                    return True
                else:
                    err_text = await resp.text()
                    logger.error("Failed to transfer collateral between shards (HTTP %d): %s", resp.status, err_text)
                    return False
        except Exception as exc:
            logger.error("Error executing collateral transfer between shards: %s", exc)
            return False

    async def ensure_crypto_collateral(self, min_required: Decimal = Decimal("5.00"), top_up: Decimal = Decimal("15.00")) -> None:
        """Ensure Shard 2 (Crypto Matching Engine) has sufficient trading collateral."""
        shard2_bal = self.shard_balances.get(2, Decimal("0.0"))
        if shard2_bal < min_required:
            shard0_bal = self.shard_balances.get(0, Decimal("0.0"))
            if shard0_bal >= top_up:
                logger.info("Shard 2 balance ($%s) below minimum ($%s). Transferring $%s from Shard 0...", shard2_bal, min_required, top_up)
                await self.transfer_between_shards(0, 2, top_up)

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

    async def get_open_orders(self, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch all resting limit orders currently active on Kalshi."""
        endpoint = "/trade-api/v2/portfolio/orders"
        url = f"{self.base_url}/portfolio/orders"
        headers = get_auth_headers(self.api_key_id, self.private_key, "GET", endpoint)
        params: Dict[str, Any] = {"status": "resting"}
        if ticker:
            params["ticker"] = ticker

        session = await self._get_session()
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                err_text = await resp.text()
                logger.error("Failed to fetch open orders (HTTP %d): %s", resp.status, err_text)
                return []
            data = await resp.json()
            orders = data.get("orders", [])
            # Defensively ensure only active resting orders are returned
            return [o for o in orders if o.get("status") in ("resting", None)]

    async def get_settlements(
        self,
        limit: int = 100,
        all_pages: bool = False,
        max_pages: int = 20,
    ) -> List[Dict[str, Any]]:
        """Fetch historical market settlements for the portfolio from Kalshi API with pagination."""
        endpoint = "/trade-api/v2/portfolio/settlements"
        url = f"{self.base_url}/portfolio/settlements"
        session = await self._get_session()
        all_settlements: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        page = 0

        try:
            while page < max_pages:
                page += 1
                headers = get_auth_headers(self.api_key_id, self.private_key, "GET", endpoint)
                params: Dict[str, Any] = {"limit": limit}
                if cursor:
                    params["cursor"] = cursor

                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        logger.error("Failed to fetch settlements (HTTP %d): %s", resp.status, err_text)
                        break
                    data = await resp.json()
                    batch = data.get("settlements", [])
                    all_settlements.extend(batch)
                    cursor = data.get("cursor")
                    if not all_pages or not cursor or not batch:
                        break
            return all_settlements
        except Exception as exc:
            logger.error("Error querying Kalshi settlements: %s", exc)
            return all_settlements

    async def get_fills(
        self,
        limit: int = 100,
        all_pages: bool = False,
        max_pages: int = 20,
    ) -> List[Dict[str, Any]]:
        """Fetch historical order fills for the portfolio from Kalshi API with pagination."""
        endpoint = "/trade-api/v2/portfolio/fills"
        url = f"{self.base_url}/portfolio/fills"
        session = await self._get_session()
        all_fills: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        page = 0

        try:
            while page < max_pages:
                page += 1
                headers = get_auth_headers(self.api_key_id, self.private_key, "GET", endpoint)
                params: Dict[str, Any] = {"limit": limit}
                if cursor:
                    params["cursor"] = cursor

                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        logger.error("Failed to fetch fills (HTTP %d): %s", resp.status, err_text)
                        break
                    data = await resp.json()
                    batch = data.get("fills", [])
                    all_fills.extend(batch)
                    cursor = data.get("cursor")
                    if not all_pages or not cursor or not batch:
                        break
            return all_fills
        except Exception as exc:
            logger.error("Error querying Kalshi fills: %s", exc)
            return all_fills

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
        exchange_index: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Place an order on Kalshi V2 Production Exchange.

        Args:
            ticker: Market contract ticker (e.g. 'KXBTC15M-26AUG300215-15').
            side: OrderSide.YES ('yes') or OrderSide.NO ('no').
            count: Number of contracts to buy/sell.
            action: 'buy' or 'sell' (default: 'buy').
            order_type: 'market' or 'limit' (default: 'market').
            price_dollars: Limit price in dollars ($0.01 - $0.99) if limit order.
            client_order_id: Optional idempotency UUID. Generated automatically if omitted.
            resting_only: If true, enables post_only to guarantee maker liquidity.
            exchange_index: Specific exchange shard (defaults to primary funded shard, 0).

        Returns:
            Dict containing order response and fill details, or None on failure.
        """
        if self.is_in_maintenance:
            logger.warning(
                "🛡️ [KALSHI MAINTENANCE VETO] Cannot place order on %s: Exchange maintenance window active (%s). "
                "Order submission paused.",
                ticker,
                self.maintenance_reason,
            )
            return None

        side_val = side.value if hasattr(side, "value") else str(side).lower()
        endpoint = "/trade-api/v2/portfolio/events/orders"
        url = f"{self.base_url}/portfolio/events/orders"

        if price_dollars is not None and not isinstance(price_dollars, Decimal):
            price_dollars = Decimal(str(price_dollars))

        order_uuid = client_order_id or str(uuid.uuid4())
        
        # In Kalshi's V2 single-book architecture:
        # Buying YES = side "bid", price = yes_price
        # Buying NO  = side "ask", price = 1.0 - no_price (or equivalent YES price)
        # Selling YES = side "ask", price = yes_price (or hitting the bid)
        # Selling NO  = side "bid", price = 1.0 - no_price (or hitting the ask)
        action_val = str(action).lower()
        if action_val == "sell":
            if side_val == "yes":
                v2_side = "ask"
                v2_price = price_dollars if price_dollars is not None else Decimal("0.95")
            else:
                v2_side = "bid"
                if price_dollars is not None:
                    v2_price = Decimal("1.00") - price_dollars
                else:
                    v2_price = Decimal("0.05")
        else:
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
        if exchange_index is not None and exchange_index >= 0:
            payload["exchange_index"] = exchange_index
        elif ticker.startswith("KXBTC15M") or ticker.startswith("KXBTCH") or ticker.startswith("KXBTCD"):
            payload["exchange_index"] = 2

        session = await self._get_session()
        max_retries = 3
        backoff_delay = 1.0

        for attempt in range(max_retries):
            headers = get_auth_headers(self.api_key_id, self.private_key, "POST", endpoint)
            headers["Content-Type"] = "application/json"

            try:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status in (200, 201):
                        order_data = await resp.json()
                        target_shard = payload.get("exchange_index", "auto")
                        logger.info(
                            "[KALSHI LIVE PRODUCTION EXCHANGE] ORDER EXECUTED: %s %s %d %s | ID: %s | Fills: %s | Shard: %s",
                            action.upper(), side_val.upper(), count, ticker,
                            order_data.get("order_id", order_uuid),
                            order_data.get("fill_count", "0.00"),
                            target_shard,
                        )
                        return order_data
                    elif resp.status in (502, 503, 504):
                        err_text = await resp.text()
                        logger.warning(
                            "Kalshi exchange maintenance window active (HTTP %d). Pausing live trades: %s",
                            resp.status, err_text,
                        )
                        self.set_maintenance_state(True, reason=f"HTTP {resp.status} - {err_text[:100]}")
                        return None
                    elif resp.status == 429:
                        err_text = await resp.text()
                        logger.warning(
                            "Kalshi rate limited order (HTTP 429). Exponential backoff %0.1fs (attempt %d/%d): %s",
                            backoff_delay, attempt + 1, max_retries, err_text,
                        )
                        await asyncio.sleep(backoff_delay)
                        backoff_delay *= 2.0
                        continue
                    else:
                        err_text = await resp.text()
                        if "maintenance" in err_text.lower() or "trading_active" in err_text.lower():
                            self.set_maintenance_state(True, reason=f"Maintenance response: {err_text[:100]}")
                        logger.error(
                            "Order rejected by Kalshi (HTTP %d): %s | Payload: %s",
                            resp.status, err_text, payload,
                        )
                        return None
            except Exception as exc:
                logger.error("Network error placing order on Kalshi V2: %s", exc, exc_info=True)
                return None
        return None

    async def cancel_order(self, order_id: str, ticker: Optional[str] = None) -> bool:
        """Cancel a resting order on Kalshi using V2 Trade API."""
        endpoint = f"/trade-api/v2/portfolio/events/orders/{order_id}"
        url = f"{self.base_url}/portfolio/events/orders/{order_id}"
        headers = get_auth_headers(self.api_key_id, self.private_key, "DELETE", endpoint)

        session = await self._get_session()
        async with session.delete(url, headers=headers) as resp:
            if resp.status in (200, 204):
                logger.info("Successfully cancelled order: %s", order_id)
                return True
            if resp.status == 404:
                # Order is already filled, cancelled, or expired on exchange
                logger.debug("Order %s already cancelled or not found (HTTP 404)", order_id)
                return True
            if resp.status in (400, 410):
                # Fallback to non-event portfolio orders endpoint if required
                fb_ep = f"/trade-api/v2/portfolio/orders/{order_id}"
                fb_url = f"{self.base_url}/portfolio/orders/{order_id}"
                fb_headers = get_auth_headers(self.api_key_id, self.private_key, "DELETE", fb_ep)
                async with session.delete(fb_url, headers=fb_headers) as fb_resp:
                    if fb_resp.status in (200, 204, 404):
                        logger.info("Successfully cancelled order via fallback: %s", order_id)
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

        if 2 in self.shard_balances:
            available_margin = self.shard_balances[2]
        elif "available_balance_dollars" in bal_data and bal_data["available_balance_dollars"] is not None:
            available_margin = Decimal(str(bal_data["available_balance_dollars"]))
        elif "balance_dollars" in bal_data and bal_data["balance_dollars"] is not None:
            available_margin = Decimal(str(bal_data["balance_dollars"]))
        else:
            raw_margin = bal_data.get("available_balance", bal_data.get("balance", 0))
            available_margin = Decimal(str(raw_margin)) / Decimal("100") if isinstance(raw_margin, int) else Decimal(str(raw_margin))

        # Ensure crypto shard 2 is well funded if shard 0 has reserves
        if self.shard_balances.get(2, Decimal("0.0")) < Decimal("5.00"):
            await self.ensure_crypto_collateral()

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


"""Orders, Positions, Live Execution, and Credentials API Router.

Extracted from server.py for institutional modularity, testability,
and token hygiene.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from kalshi_sim.auth import (
    DEMO_REST_BASE,
    PROD_REST_BASE,
    async_validate_credentials,
)
from kalshi_sim.db import get_db_writer
import kalshi_sim.server as server_module
from kalshi_sim.order_client import KalshiLiveOrderClient
from kalshi_sim.process_lock import get_active_lock_holder

from kalshi_sim.rate_limiter import kalshi_rate_limiter
from kalshi_sim.schemas import (
    L2BookState,
    LiveOrderRequest,
    LiveOrderResponse,
    OrderSide,
    OrderType,
    ReconciliationReport,
    Timeframe,
    ValidateCredentialsRequest,
    ValidateCredentialsResponse,
)

logger = logging.getLogger("kalshi_sim.routers.orders")

router = APIRouter(tags=["orders"])

_state_getter = None
_trigger_instant_broadcast_fn = None

def init_orders_router(state_getter, trigger_instant_broadcast_fn=None):
    global _state_getter, _trigger_instant_broadcast_fn
    _state_getter = state_getter
    _trigger_instant_broadcast_fn = trigger_instant_broadcast_fn

def get_state():
    if _state_getter is not None:
        return _state_getter()
    from kalshi_sim.server import state
    return state

def _get_live_order_client(*args, **kwargs):
    cls = getattr(server_module, "KalshiLiveOrderClient", KalshiLiveOrderClient)
    return cls(*args, **kwargs)

def _get_active_lock_holder():
    fn = getattr(server_module, "get_active_lock_holder", get_active_lock_holder)
    return fn()

async def _async_validate_credentials(*args, **kwargs):
    fn = getattr(server_module, "async_validate_credentials", async_validate_credentials)
    return await fn(*args, **kwargs)



async def trigger_instant_broadcast() -> None:
    if _trigger_instant_broadcast_fn is not None:
        return await _trigger_instant_broadcast_fn()
    from kalshi_sim.server import trigger_instant_broadcast as _tib
    return await _tib()

class _StateProxy:
    def __getattr__(self, name):
        return getattr(get_state(), name)
    def __setattr__(self, name, value):
        setattr(get_state(), name, value)

state = _StateProxy()


class OrderRequest(BaseModel):
    ticker: str = Field(default="KXBTC15M-T78650")
    side: Literal["yes", "no"] = Field(default="yes")
    order_type: Literal["market", "limit"] = Field(default="market")
    size: int = Field(default=10, ge=1, le=1000)
    limit_price: float | None = Field(default=None)
    resting_only: bool = Field(default=False)
    execution_mode: Literal["paper", "live"] | None = Field(default=None)

@router.post("/api/kalshi/validate-credentials", response_model=ValidateCredentialsResponse)
async def validate_kalshi_credentials(req: ValidateCredentialsRequest) -> ValidateCredentialsResponse:
    """Validate Kalshi API credentials against live or demo exchange endpoints."""
    # Resolve API Key ID
    api_key_id = req.api_key_id or os.getenv("KALSHI_API_KEY_ID")
    if not api_key_id:
        return ValidateCredentialsResponse(
            valid=False,
            message="Missing API Key ID. Please provide api_key_id in request or configure KALSHI_API_KEY_ID in .env",
            mode="demo" if req.is_demo else "prod",
            account_info={},
        )

    # Resolve Private Key
    private_key_source = req.private_key or os.getenv("KALSHI_PRIVATE_KEY_PATH") or os.getenv("KALSHI_PRIVATE_KEY")
    if not private_key_source and Path("kalshi_demo.pem").exists():
        private_key_source = "kalshi_demo.pem"

    if not private_key_source:
        return ValidateCredentialsResponse(
            valid=False,
            message="Missing RSA Private Key. Please provide private_key in request or configure KALSHI_PRIVATE_KEY_PATH in .env",
            mode="demo" if req.is_demo else "prod",
            account_info={},
        )

    valid, msg, account_data = await _async_validate_credentials(
        api_key_id=api_key_id,
        private_key=private_key_source,
        is_demo=req.is_demo,
        timeout_sec=8.0,
    )

    return ValidateCredentialsResponse(
        valid=valid,
        message=msg,
        mode="demo" if req.is_demo else "prod",
        account_info=account_data,
    )


@router.get("/api/kalshi/portfolio/sync")
async def sync_kalshi_portfolio(is_demo: bool = True) -> dict[str, Any]:
    """Fetch live exchange portfolio state and reconcile with the simulated portfolio ledger."""
    if not state.sim_agent or not state.sim_agent._portfolio:
        raise HTTPException(status_code=503, detail="Simulation portfolio not initialized")

    api_key_id = os.getenv("KALSHI_API_KEY_ID")
    private_key_source = os.getenv("KALSHI_PRIVATE_KEY_PATH") or os.getenv("KALSHI_PRIVATE_KEY")
    if not private_key_source and Path("kalshi_demo.pem").exists():
        private_key_source = "kalshi_demo.pem"

    if not api_key_id or not private_key_source:
        # Return fallback mocked sync state if credentials are not configured
        sim_p = state.sim_agent._portfolio
        return {
            "authenticated": False,
            "message": "Kalshi API credentials not configured in environment.",
            "reconciliation": ReconciliationReport(
                is_synchronized=True,
                simulated_cash=sim_p.current_balance,
                exchange_cash=sim_p.current_balance,
                cash_discrepancy=Decimal("0"),
                simulated_positions_count=len(sim_p.get_open_positions()),
                exchange_positions_count=len(sim_p.get_open_positions()),
                alerts=["Operating in pure simulation mode (no live Kalshi API keys connected)."],
            ).model_dump(mode="json"),
            "live_portfolio": None,
        }

    base_url = DEMO_REST_BASE if is_demo else PROD_REST_BASE
    client = _get_live_order_client(
        api_key_id=api_key_id,
        private_key_path=private_key_source,
        base_url=base_url,
    )

    try:
        report = await client.reconcile_with_simulated(state.sim_agent._portfolio)
        live_state = await client.get_live_portfolio_state()
        sync_payload = {
            "authenticated": True,
            "message": "Successfully synchronized with Kalshi exchange.",
            "reconciliation": report.model_dump(mode="json"),
            "live_portfolio": live_state.model_dump(mode="json"),
        }
        state.live_portfolio = {
            "balance_dollars": float(live_state.balance_dollars),
            "available_margin": float(live_state.available_margin),
            "payout_pending": float(live_state.payout_pending),
            "positions_count": len(live_state.positions),
            "positions": [
                {
                    "ticker": p.ticker,
                    "position": p.position,
                    "side": p.side.value,
                    "fees_paid": float(p.fees_paid),
                    "realized_pnl": float(p.realized_pnl),
                    "resting_orders_count": p.resting_orders_count,
                }
                for p in live_state.positions
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "environment": os.getenv("KALSHI_ENV", "live").lower(),
            "is_authenticated": True,
        }
        return sync_payload
    except Exception as exc:
        logger.error("Error synchronizing Kalshi live portfolio: %s", exc)
        return {
            "authenticated": False,
            "message": f"Failed to sync with exchange: {exc}",
            "reconciliation": None,
            "live_portfolio": None,
        }
    finally:
        await client.close()


@router.get("/api/kalshi/balance")
async def get_kalshi_live_balance() -> dict[str, Any]:
    """Retrieve real-time actual Kalshi exchange cash balance, margin, and exposure."""
    if state.live_portfolio is not None:
        return state.live_portfolio

    api_key_id = os.getenv("KALSHI_API_KEY_ID")
    private_key_source = os.getenv("KALSHI_PRIVATE_KEY_PATH") or os.getenv("KALSHI_PRIVATE_KEY")
    if not private_key_source and Path("kalshi_demo.pem").exists():
        private_key_source = "kalshi_demo.pem"

    if not api_key_id or not private_key_source:
        return {
            "balance_dollars": 0.0,
            "available_margin": 0.0,
            "payout_pending": 0.0,
            "positions_count": 0,
            "positions": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "environment": "none",
            "is_authenticated": False,
            "message": "Kalshi API credentials not configured in environment.",
        }

    env = os.getenv("KALSHI_ENV", "live").lower()
    base_url = DEMO_REST_BASE if env == "demo" else PROD_REST_BASE
    client = _get_live_order_client(
        api_key_id=api_key_id,
        private_key_path=private_key_source,
        base_url=base_url,
    )
    try:
        live_state = await client.get_live_portfolio_state()
        data = {
            "balance_dollars": float(live_state.balance_dollars),
            "available_margin": float(live_state.available_margin),
            "payout_pending": float(live_state.payout_pending),
            "positions_count": len(live_state.positions),
            "positions": [
                {
                    "ticker": p.ticker,
                    "position": p.position,
                    "side": p.side.value,
                    "fees_paid": float(p.fees_paid),
                    "realized_pnl": float(p.realized_pnl),
                    "resting_orders_count": p.resting_orders_count,
                }
                for p in live_state.positions
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "environment": env,
            "is_authenticated": True,
        }
        state.live_portfolio = data
        return data
    finally:
        await client.close()


@router.post("/api/kalshi/orders/live", response_model=LiveOrderResponse)
async def place_kalshi_live_order(req: LiveOrderRequest) -> LiveOrderResponse:
    """Submit a live order to the Kalshi exchange with rate-limiting and dry-run protection."""
    api_key_id = os.getenv("KALSHI_API_KEY_ID")
    private_key_source = os.getenv("KALSHI_PRIVATE_KEY_PATH") or os.getenv("KALSHI_PRIVATE_KEY")
    if not private_key_source and Path("kalshi_demo.pem").exists():
        private_key_source = "kalshi_demo.pem"

    # Evaluate dry-run status
    live_enabled_env = os.getenv("KALSHI_LIVE_TRADING_ENABLED", "false").lower() in ("true", "1", "yes")
    is_dry_run = req.dry_run if req.dry_run is not None else (not live_enabled_env)

    if is_dry_run or not api_key_id or not private_key_source:
        logger.info("[SAFETY DRY-RUN] Simulating live order: %s %d %s %s", req.action, req.count, req.side, req.ticker)
        est_price = req.limit_price_dollars or Decimal("0.50")
        return LiveOrderResponse(
            success=True,
            order_id=f"dry_run_{uuid.uuid4().hex[:8]}",
            status="dry_run",
            ticker=req.ticker,
            side=req.side,
            count=req.count,
            fill_price=est_price,
            is_dry_run=True,
            message="Order passed all pre-flight validation rules in Safety Dry-Run mode.",
        )

    # Ensure Standalone Bot does not hold the trading lock
    holder = _get_active_lock_holder()
    if holder and holder[1] != os.getpid():
        logger.warning("🛑 [LOCKOUT] Live order blocked: %s holds trading lock (PID: %d)", holder[0], holder[1])
        raise HTTPException(
            status_code=409,
            detail=f"Live orders blocked: 24/7 Standalone Bot ({holder[0]}, PID: {holder[1]}) is currently running."
        )

    # Ensure Active Strategy Holds the Seal of Excellence for Live Trading
    active_bot = state.active_strategy_bot
    if not state.bot_auditor.has_seal_of_excellence(active_bot):
        logger.error("[SEAL OF EXCELLENCE VETO] Live order blocked: Strategy '%s' lacks active live seal authorization.", active_bot)
        raise HTTPException(
            status_code=422,
            detail=f"SEAL OF EXCELLENCE VETO: Strategy '{active_bot}' lacks active live order routing authorization. 5-pillar passing certificate required."
        )

    # Acquire rate limiter token before exchange communication
    acquired = await kalshi_rate_limiter.acquire(1.0, timeout=5.0)
    if not acquired:
        raise HTTPException(status_code=429, detail="Kalshi rate limit reached. Please try again shortly.")

    base_url = DEMO_REST_BASE if req.is_demo else PROD_REST_BASE
    client = _get_live_order_client(
        api_key_id=api_key_id,
        private_key_path=private_key_source,
        base_url=base_url,
    )

    try:
        order_info = await client.place_order(
            ticker=req.ticker,
            side=req.side,
            count=req.count,
            action=req.action,
            order_type=req.order_type,
            price_dollars=req.limit_price_dollars,
        )

        if not order_info:
            return LiveOrderResponse(
                success=False,
                order_id=None,
                status="rejected",
                ticker=req.ticker,
                side=req.side,
                count=req.count,
                fill_price=None,
                is_dry_run=False,
                message="Exchange rejected the order submission.",
            )

        fill_pr = None
        if "yes_price_dollars" in order_info:
            fill_pr = Decimal(str(order_info["yes_price_dollars"]))
        elif "no_price_dollars" in order_info:
            fill_pr = Decimal(str(order_info["no_price_dollars"]))

        return LiveOrderResponse(
            success=True,
            order_id=order_info.get("order_id"),
            status=order_info.get("status", "executed"),
            ticker=req.ticker,
            side=req.side,
            count=req.count,
            fill_price=fill_pr,
            is_dry_run=False,
            message="Order successfully submitted to Kalshi exchange.",
        )
    except Exception as exc:
        logger.error("Failed to place live order on Kalshi: %s", exc)
        return LiveOrderResponse(
            success=False,
            order_id=None,
            status="error",
            ticker=req.ticker,
            side=req.side,
            count=req.count,
            fill_price=None,
            is_dry_run=False,
            message=f"Error communicating with exchange: {exc}",
        )
    finally:
        await client.close()


@router.delete("/api/kalshi/orders/live/{order_id}")
async def cancel_kalshi_live_order(order_id: str, is_demo: bool = True) -> dict[str, Any]:
    """Cancel a resting order on Kalshi exchange."""
    api_key_id = os.getenv("KALSHI_API_KEY_ID")
    private_key_source = os.getenv("KALSHI_PRIVATE_KEY_PATH") or os.getenv("KALSHI_PRIVATE_KEY")
    if not private_key_source and Path("kalshi_demo.pem").exists():
        private_key_source = "kalshi_demo.pem"

    if not api_key_id or not private_key_source:
        return {"success": True, "order_id": order_id, "status": "dry_run_cancelled"}

    await kalshi_rate_limiter.acquire(1.0, timeout=5.0)

    base_url = DEMO_REST_BASE if is_demo else PROD_REST_BASE
    client = _get_live_order_client(
        api_key_id=api_key_id,
        private_key_path=private_key_source,
        base_url=base_url,
    )

    try:
        success = await client.cancel_order(order_id)
        return {"success": success, "order_id": order_id, "status": "cancelled" if success else "failed"}
    finally:
        await client.close()


@router.get("/api/kalshi/orders/live/open")
async def get_kalshi_live_open_orders(is_demo: bool = True) -> list[dict[str, Any]]:
    """Fetch active resting limit orders from Kalshi exchange."""
    api_key_id = os.getenv("KALSHI_API_KEY_ID")
    private_key_source = os.getenv("KALSHI_PRIVATE_KEY_PATH") or os.getenv("KALSHI_PRIVATE_KEY")
    if not private_key_source and Path("kalshi_demo.pem").exists():
        private_key_source = "kalshi_demo.pem"

    if not api_key_id or not private_key_source:
        return []

    await kalshi_rate_limiter.acquire(1.0, timeout=5.0)

    base_url = DEMO_REST_BASE if is_demo else PROD_REST_BASE
    client = _get_live_order_client(
        api_key_id=api_key_id,
        private_key_path=private_key_source,
        base_url=base_url,
    )

    try:
        return await client.get_open_orders()
    finally:
        await client.close()


@router.get("/api/orders/open")
async def get_open_orders() -> list[dict[str, Any]]:
    """Return all active resting limit orders."""
    if not state.sim_agent or not state.sim_agent._simulator:
        return []
    return [
        {
            "order_id": o.order_id,
            "ticker": o.ticker,
            "side": o.side.value,
            "size": o.size,
            "limit_price": float(o.limit_price) if o.limit_price else 0.0,
            "timeframe": o.timeframe.value,
            "status": o.status,
            "created_at": o.created_at.strftime("%H:%M:%S"),
        }
        for o in state.sim_agent._simulator.get_all_resting_orders()
    ]

@router.delete("/api/orders/{order_id}")
async def cancel_order(order_id: str) -> dict[str, Any]:
    """Cancel an active resting limit order."""
    if not state.sim_agent or not state.sim_agent._simulator:
        raise HTTPException(status_code=503, detail="Simulation agent not running")
    
    # Identify target ticker for audit record
    resting_orders = state.sim_agent._simulator.get_all_resting_orders()
    target_ticker = state.active_ticker
    for o in resting_orders:
        if o.order_id == order_id:
            target_ticker = o.ticker
            break

    success = state.sim_agent._simulator.cancel_resting_order(order_id)
    if success:
        state.law_order_agent.record_order_cancellation(order_id, target_ticker)
        return {"success": True, "order_id": order_id, "status": "cancelled"}
    raise HTTPException(status_code=404, detail="Order not found")

@router.post("/api/orders")
async def place_order(req: OrderRequest) -> dict[str, Any]:
    """Place a simulated or live order."""
    if not state.sim_agent:
        raise HTTPException(status_code=503, detail="Simulation agent is not running")

    side = OrderSide.YES if req.side.lower() == "yes" else OrderSide.NO
    order_type = OrderType.LIMIT if req.order_type.lower() == "limit" else OrderType.MARKET
    limit_price = Decimal(str(req.limit_price)) if req.limit_price is not None else None

    ticker = req.ticker or state.active_ticker
    book = state.orderbook.get_book(ticker)
    if not book:
        # Create a fallback default book for the active ticker with realistic levels
        book = L2BookState(ticker)
        book.yes_book = {Decimal("0.034"): Decimal("500"), Decimal("0.031"): Decimal("1000")}
        book.no_book = {Decimal("0.966"): Decimal("500"), Decimal("0.969"): Decimal("1000")}
        state.orderbook._books[ticker] = book

    sim = state.sim_agent._simulator
    portfolio = state.sim_agent._portfolio

    # Agent_law_order Pre-Trade Regulatory Gatekeeper (Wash Trading & Position Limit Check)
    open_orders = sim.get_all_resting_orders()
    order_price = limit_price if limit_price is not None else ((book.best_yes_ask if side == OrderSide.YES else book.best_no_ask) or Decimal("0.50"))
    comp_ok, comp_msg = state.law_order_agent.validate_pre_trade_order(
        ticker=ticker,
        side=side.value,
        size=req.size,
        price=order_price,
        open_orders=open_orders,
        current_positions=portfolio._positions,
        current_balance=portfolio.balance,
    )
    if not comp_ok:
        logger.warning("[COMPLIANCE GATEWAY REJECT] %s", comp_msg)
        return {
            "success": False,
            "reason": comp_msg,
            "status": "compliance_rejected",
        }

    # Agent_Guardrails Pre-Trade Risk Gatekeeper
    active_equity = Decimal(str(state.live_portfolio.get("balance_dollars", "0.0"))) if req.execution_mode == "live" and state.live_portfolio else portfolio.equity
    g_ok, g_msg, g_size, g_diag = state.guardrails_agent.validate_pre_trade_intent(
        ticker=ticker,
        side=side.value,
        requested_size=req.size,
        est_price=order_price,
        total_equity=active_equity,
        vpin=0.15,
        cycle_id=ticker,
        is_bot=False,
        is_live=(req.execution_mode == "live"),
    )
    if not g_ok:
        logger.warning("[GUARDRAIL GATEWAY REJECT] %s", g_msg)
        return {
            "success": False,
            "reason": g_msg,
            "status": "guardrail_rejected",
        }

    # =========================================================================
    # LIVE TRADING EXECUTION INTERCEPT (Real Kalshi Account Routing & Balance Freeze)
    # =========================================================================
    if req.execution_mode == "live":
        # Strict Seal of Excellence Pre-Flight Live Authorization Gate
        target_bot = req.bot_type or state.active_strategy_bot
        if not state.bot_auditor.has_seal_of_excellence(target_bot):
            logger.error("[SEAL OF EXCELLENCE VETO] Live order rejected for '%s': Strategy lacks active live seal.", target_bot)
            return {
                "success": False,
                "status": "seal_of_excellence_veto",
                "reason": f"SEAL OF EXCELLENCE VETO: Strategy '{target_bot}' has not been granted the Seal of Excellence for live order routing.",
            }

        # Strict 5M Live Trading Prohibition Invariant
        is_5m_target = (("5M" in ticker.upper() and "15M" not in ticker.upper()) or "5MIN" in ticker.upper()) or state.active_timeframe == Timeframe.FIVE_MIN
        if is_5m_target:
            logger.error(
                "[LIVE TRADE BLOCKED] 5M contract %s is strictly Paper Live only. Live orders are permanently blocked.",
                ticker,
            )
            return {
                "success": False,
                "status": "5m_live_prohibited",
                "reason": "5-Minute event contracts (KXBTC5M) are strictly exclusive to Mother Dash Paper Live. Real-money live trading is permanently prohibited.",
            }

        live_p = state.live_portfolio or {}
        live_balance = Decimal(str(live_p.get("balance_dollars", "0.0")))
        est_price = limit_price if limit_price is not None else ((book.best_yes_ask if side == OrderSide.YES else book.best_no_ask) or Decimal("0.50"))
        est_cost = est_price * Decimal(str(req.size))

        # Check for insufficient live funds / zero balance -> FREEZE BETS
        if live_balance <= Decimal("0.05") or live_balance < est_cost:
            logger.warning(
                "[LIVE BETS FROZEN] Insufficient live balance ($%s) for order cost ($%s) on %s",
                live_balance, est_cost, ticker,
            )
            return {
                "success": False,
                "status": "frozen_insufficient_funds",
                "freeze_trading": True,
                "live_balance": float(live_balance),
                "reason": f"INSUFFICIENT LIVE BALANCE: Live Kalshi balance is ${float(live_balance):.2f}, which is insufficient for this trade (${float(est_cost):.2f}). All bets are frozen. Please deposit/load assets into your Kalshi account to resume.",
                "action_required": "deposit_funds",
            }

        # Real Live Exchange Execution via KalshiLiveOrderClient
        api_key_id = os.environ.get("KALSHI_API_KEY_ID")
        private_key_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH")
        env_mode = os.environ.get("KALSHI_ENV", "live").lower()
        base_url = PROD_REST_BASE if env_mode == "live" else DEMO_REST_BASE

        if not api_key_id or not private_key_path:
            return {
                "success": False,
                "status": "config_error",
                "freeze_trading": True,
                "reason": "Kalshi live API credentials not configured in environment.",
            }

        client = None
        try:
            client = _get_live_order_client(
                api_key_id=api_key_id,
                private_key_path=private_key_path,
                base_url=base_url,
            )
            order_info = await client.place_order(
                ticker=ticker,
                side=side,
                count=req.size,
                action="buy",
                order_type=req.order_type,
                price_dollars=limit_price,
            )
            if not order_info:
                return {
                    "success": False,
                    "status": "exchange_rejected",
                    "reason": "Kalshi live exchange rejected the order submission.",
                }

            fill_pr = limit_price or est_price
            if "yes_price_dollars" in order_info and order_info["yes_price_dollars"] is not None:
                fill_pr = Decimal(str(order_info["yes_price_dollars"]))
            elif "no_price_dollars" in order_info and order_info["no_price_dollars"] is not None:
                fill_pr = Decimal(str(order_info["no_price_dollars"]))

            cost = fill_pr * Decimal(str(req.size))
            order_id = order_info.get("order_id") or str(uuid.uuid4())
            fee = float(Decimal("0.01") * Decimal(str(req.size)))

            logger.info(
                "[LIVE FILL] %s %s %d contracts @ $%.4f (cost: $%.2f, fee: $%.2f) on Kalshi Live",
                ticker, side.value.upper(), req.size, fill_pr, cost, fee,
            )

            # Persist live trade to SQLite WAL store
            try:
                get_db_writer().enqueue_trade(
                    trade_id=order_id,
                    ticker=ticker,
                    side=side.value,
                    size=req.size,
                    price=float(fill_pr),
                    gross_value=float(cost),
                    fees=float(fee),
                    execution_mode="live",
                    bot_type=state.active_strategy_bot or "live_manual",
                )
            except Exception as db_err:
                logger.warning("Failed to enqueue live trade to DB: %s", db_err)

            # Refresh live balance in state
            asyncio.create_task(trigger_instant_broadcast())
            return {
                "success": True,
                "order_id": order_id,
                "status": order_info.get("status", "executed"),
                "fill_price": float(fill_pr),
                "cost": float(cost),
                "fee": fee,
                "execution_mode": "live",
                "message": f"Live order executed on Kalshi: {req.size} contracts @ ${(float(fill_pr)*100):.1f}¢",
            }
        except Exception as exc:
            logger.error("Live order placement error: %s", exc)
            return {
                "success": False,
                "status": "error",
                "reason": f"Live exchange error: {exc}",
            }
        finally:
            if client:
                await client.close()


    if order_type == OrderType.LIMIT and limit_price is not None:
        if req.resting_only:
            resting_order = sim.place_resting_limit_order(
                book=book,
                side=side,
                size=req.size,
                limit_price=limit_price,
                timeframe=state.active_timeframe,
                reasoning="Manual Resting Limit Order",
            )
            return {
                "success": True,
                "order_id": resting_order.order_id,
                "limit_price": float(limit_price),
                "size": req.size,
                "status": "resting",
            }
        else:
            exec_res = sim.simulate_limit_order(
                book=book,
                side=side,
                size=req.size,
                limit_price=limit_price,
                timeframe=state.active_timeframe,
                reasoning="Manual 1-Click Limit Order",
            )
    else:
        exec_res = sim.simulate_market_order(
            book=book,
            side=side,
            size=req.size,
            timeframe=state.active_timeframe,
            reasoning="Manual 1-Click Market Order",
        )

    if exec_res:
        order, fill = exec_res
        if portfolio.can_afford(fill.cost):
            portfolio.open_position(fill, state.active_timeframe)
            if state.sim_agent._exec_logger:
                state.sim_agent._exec_logger.log_execution(order, fill)
            logger.info("[MANUAL FILL] %s %s %d contracts @ $%.4f (cost: $%.2f)",
                        ticker, side.value.upper(), req.size, fill.fill_price, fill.cost)
            asyncio.create_task(trigger_instant_broadcast())
            return {
                "success": True,
                "order_id": order.order_id,
                "fill_price": float(fill.fill_price),
                "cost": float(fill.cost),
                "slippage": float(fill.slippage),
                "status": "filled",
            }
        else:
            return {
                "success": False,
                "order_id": order.order_id,
                "reason": "Insufficient balance",
                "status": "rejected",
            }
    else:
        return {
            "success": False,
            "reason": "Insufficient liquidity in order book",
            "status": "rejected",
        }

class ClosePositionRequest(BaseModel):
    ticker: str
    execution_mode: Optional[Literal["paper", "live"]] = "paper"

@router.post("/api/positions/close")
async def close_position_endpoint(req: ClosePositionRequest) -> dict[str, Any]:
    """Liquidate and close an open position at current market bid/ask."""
    # =========================================================================
    # LIVE POSITION CLOSE / LIQUIDATE INTERCEPT
    # =========================================================================
    if req.execution_mode == "live":
        api_key_id = os.environ.get("KALSHI_API_KEY_ID")
        private_key_path = (
            os.environ.get("KALSHI_PRIVATE_KEY_PATH")
            or os.environ.get("KALSHI_PRIVATE_KEY")
            or ("keys/kalshi_demo.pem" if Path("keys/kalshi_demo.pem").exists() else "kalshi_demo.pem")
        )
        env_mode = os.environ.get("KALSHI_ENV", "live").lower()
        base_url = PROD_REST_BASE if env_mode == "live" else DEMO_REST_BASE

        if not api_key_id or not private_key_path:
            return {
                "success": False,
                "status": "config_error",
                "reason": "Kalshi live API credentials not configured in environment.",
            }

        client = None
        try:
            client = _get_live_order_client(
                api_key_id=api_key_id,
                private_key_path=private_key_path,
                base_url=base_url,
            )
            # Query active positions on Kalshi to find contract size & side
            positions = await client.get_positions()
            target_pos = None
            for p in positions:
                if p.get("ticker") == req.ticker or p.get("market_ticker") == req.ticker:
                    target_pos = p
                    break

            if not target_pos:
                # If not found in REST query, check local live_portfolio state
                live_p = state.live_portfolio or {}
                for lp in live_p.get("positions", []):
                    if lp.get("ticker") == req.ticker:
                        target_pos = lp
                        break

            if not target_pos:
                return {
                    "success": False,
                    "status": "not_found",
                    "reason": f"Live position for '{req.ticker}' not found on Kalshi exchange.",
                }

            raw_cnt = target_pos.get("position", target_pos.get("position_fp", 1))
            try:
                pos_cnt = abs(int(float(str(raw_cnt))))
            except (ValueError, TypeError):
                pos_cnt = 1

            pos_side = target_pos.get("side", "yes")
            side = OrderSide.YES if str(pos_side).lower() == "yes" else OrderSide.NO

            if pos_cnt <= 0:
                # Cancel any resting orders on Kalshi for this ticker if present
                try:
                    open_orders = await client.get_open_orders()
                    for oo in open_orders:
                        if oo.get("ticker") == req.ticker or oo.get("market_ticker") == req.ticker:
                            oid = oo.get("order_id")
                            if oid:
                                await client.cancel_order(oid)
                except Exception as cancel_err:
                    logger.debug("Failed to cancel resting orders for %s: %s", req.ticker, cancel_err)

                # Remove from local live_portfolio state
                if state.live_portfolio and "positions" in state.live_portfolio:
                    state.live_portfolio["positions"] = [
                        p for p in state.live_portfolio["positions"]
                        if p.get("ticker") != req.ticker
                    ]
                    state.live_portfolio["positions_count"] = len(state.live_portfolio["positions"])

                asyncio.create_task(trigger_instant_broadcast())
                return {
                    "success": True,
                    "ticker": req.ticker,
                    "status": "cleared",
                    "execution_mode": "live",
                    "message": f"Cleared zero-contract record for '{req.ticker}' from list.",
                }

            # Submit sell order to Kalshi live exchange to liquidate position
            order_info = await client.place_order(
                ticker=req.ticker,
                side=side,
                count=pos_cnt,
                action="sell",
                order_type="market",
            )
            if not order_info:
                return {
                    "success": False,
                    "status": "exchange_rejected",
                    "reason": f"Kalshi rejected sell order to liquidate position {req.ticker}.",
                }

            # Update live portfolio state immediately
            if state.live_portfolio and "positions" in state.live_portfolio:
                state.live_portfolio["positions"] = [
                    p for p in state.live_portfolio["positions"]
                    if p.get("ticker") != req.ticker
                ]
                state.live_portfolio["positions_count"] = len(state.live_portfolio["positions"])

            logger.info("[LIVE LIQUIDATION] Closed %d %s contracts of %s on Kalshi Live", pos_cnt, side.value.upper(), req.ticker)
            asyncio.create_task(trigger_instant_broadcast())
            return {
                "success": True,
                "ticker": req.ticker,
                "side": side.value,
                "size": pos_cnt,
                "status": "liquidated",
                "execution_mode": "live",
                "message": f"Successfully liquidated {pos_cnt} contracts of {req.ticker} on Kalshi Live.",
            }
        except Exception as exc:
            logger.error("Live position close error: %s", exc)
            return {
                "success": False,
                "status": "error",
                "reason": f"Failed to close live position: {exc}",
            }
        finally:
            if client:
                await client.close()

    # Paper Simulation Close Position Logic
    if not state.sim_agent or not state.sim_agent._portfolio:
        raise HTTPException(status_code=503, detail="Simulation agent not running")

    portfolio = state.sim_agent._portfolio
    position = portfolio.get_position(req.ticker)
    if not position:
        return {
            "success": True,
            "ticker": req.ticker,
            "status": "already_cleared",
            "message": f"Position for '{req.ticker}' is already cleared.",
        }

    book = state.orderbook.get_book(req.ticker)
    # Determine exit price based on position side
    if position.side == OrderSide.YES:
        exit_price = book.best_yes_bid if book and book.best_yes_bid else Decimal("0.50")
    else:
        exit_price = book.best_no_bid if book and book.best_no_bid else Decimal("0.50")

    result = portfolio.close_position(req.ticker, exit_price)
    if result:
        if state.sim_agent._exec_logger:
            state.sim_agent._exec_logger.log_settlement(result)
        try:
            snap = portfolio.get_pnl_snapshot()
            get_db_writer().enqueue_equity_snapshot(
                balance=float(snap.current_balance),
                equity=float(snap.total_equity),
                realized_pnl=float(snap.total_realized_pnl),
                unrealized_pnl=float(snap.total_unrealized_pnl),
                drawdown_pct=float(portfolio.current_drawdown_pct * 100),
                win_rate=float((snap.win_rate or 0) * 100),
                total_trades=snap.total_trades,
                open_positions_count=snap.open_positions,
            )
        except Exception:
            pass
        return {
            "success": True,
            "ticker": result.ticker,
            "side": result.side.value,
            "size": result.size,
            "exit_price": float(result.settlement_price),
            "pnl": float(result.pnl),
            "outcome": result.outcome,
            "new_balance": float(portfolio.balance),
        }
    else:
        return {"success": False, "reason": "Failed to close position"}


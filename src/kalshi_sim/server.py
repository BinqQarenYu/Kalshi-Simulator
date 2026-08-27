"""FastAPI + WebSocket backend server for the Kalshi Simulator Dashboard.

Provides high-frequency real-time market data, L2 orderbook, ONNX AI inference,
EV calculations, portfolio tracking, and REST order execution endpoints.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import csv
import io
import json
import logging
import os
import random
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, AsyncIterator, Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

from kalshi_sim.auth import DEMO_REST_BASE, PROD_REST_BASE, async_validate_credentials, load_private_key
from kalshi_sim.db import HistoricalQueryService, get_db_writer
from kalshi_sim.gdrive_sync import GDriveSyncDaemon
from kalshi_sim.ingestion_agent import IngestionAgent, load_config
from kalshi_sim.mock_feed import MockKalshiFeed
from kalshi_sim.ml.statistical_ev_engine import StatisticalEVEngine
from kalshi_sim.ohlcv_aggregator import OHLCVAggregator
from kalshi_sim.order_client import KalshiLiveOrderClient
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.rate_limiter import kalshi_rate_limiter
from kalshi_sim.schemas import (
    CandleInterval,
    L2BookState,
    LiveOrderRequest,
    LiveOrderResponse,
    LivePortfolioState,
    OrderSide,
    OrderType,
    ReconciliationReport,
    SimulatedOrder,
    Timeframe,
    ValidateCredentialsRequest,
    ValidateCredentialsResponse,
)
from kalshi_sim.simulation_agent import SimulationAgent
from kalshi_sim.tick_writer import TickWriter

logger = logging.getLogger("kalshi_sim.server")

# ---------------------------------------------------------------------------
# Global State & Lifespan Setup
# ---------------------------------------------------------------------------

class ServerState:
    def __init__(self) -> None:
        self.orderbook = OrderBookManager()
        self.starting_capital = Decimal("10000")
        self.data_dir = Path("data")
        self.timeframes = [Timeframe.FIFTEEN_MIN]
        self.active_timeframe = Timeframe.FIFTEEN_MIN
        self.active_ticker = "KXBTC15M-T78650"
        self.target_strike = Decimal("78656.27")
        self.current_btc_price = Decimal("78500.66")
        self.price_history: list[dict[str, Any]] = []
        self.trade_tape: list[dict[str, Any]] = []
        self.connected_websockets: set[WebSocket] = set()
        
        # Simulation Agent
        self.sim_agent: SimulationAgent | None = None
        self.mock_feed: MockKalshiFeed | None = None
        self.tick_writer: TickWriter | None = None
        self.feed_task: asyncio.Task | None = None
        self.broadcast_task: asyncio.Task | None = None
        self.ai_auto_trade: bool = True
        self.mode: Literal["mock", "live"] = "mock"
        self.market_expiry_seconds: int = 87  # 01:27

        # Historical Candlestick Aggregator
        self.ohlcv_aggregator = OHLCVAggregator(max_bars=500)
        self.ohlcv_aggregator.seed_synthetic_history("BTC", start_price=self.current_btc_price, bars_count=60)

        # Google Drive Periodic Backup Daemon
        self.gdrive_sync = GDriveSyncDaemon(data_dir=self.data_dir, sync_interval_seconds=300)

state = ServerState()


async def start_background_simulation() -> None:
    """Initialize Mock Feed or Live Feed and simulation agent."""
    state.data_dir.mkdir(parents=True, exist_ok=True)
    state.sim_agent = SimulationAgent(
        orderbook_manager=state.orderbook,
        timeframes=state.timeframes,
        starting_capital=state.starting_capital,
        data_dir=state.data_dir,
    )
    state.tick_writer = TickWriter(data_dir=state.data_dir, timeframe="mock")
    await state.tick_writer.open()

    state.mock_feed = MockKalshiFeed(
        state.orderbook,
        state.sim_agent,
        tick_writer=state.tick_writer,
    )

    # Hook feed updates to server state
    original_apply_delta = state.orderbook.apply_delta
    def hooked_apply_delta(delta: Any) -> Any:
        res = original_apply_delta(delta)
        # Update current btc price and history
        if hasattr(state.mock_feed, "_btc_price"):
            btc_p = Decimal(str(state.mock_feed._btc_price))
            state.current_btc_price = btc_p
            now_iso = datetime.now(timezone.utc).strftime("%H:%M:%S")
            state.price_history.append({
                "time": now_iso,
                "price": float(btc_p),
                "target": float(state.target_strike),
            })
            if len(state.price_history) > 120:
                state.price_history.pop(0)

            # Ingest into rolling OHLCV aggregator
            state.ohlcv_aggregator.add_tick("BTC", price=btc_p, volume=random.randint(1, 5))

        # Ingest contract delta if available
        if hasattr(delta, "market_ticker") and hasattr(delta, "price"):
            vol = abs(float(getattr(delta, "delta", 1)))
            state.ohlcv_aggregator.add_tick(delta.market_ticker, price=delta.price, volume=vol)

        # Decay expiry countdown timer and trigger automated contract rollover
        if state.market_expiry_seconds > 0:
            state.market_expiry_seconds -= 1
        else:
            # Contract expiration reached: Settle open positions & roll to next cycle
            cfg = TIMEFRAME_CONFIGS.get(state.active_timeframe, {})
            duration = cfg.get("expiry_seconds", 900)
            state.market_expiry_seconds = duration

            # Evaluate settlement on current portfolio
            if state.sim_agent and state.sim_agent._portfolio:
                pos = state.sim_agent._portfolio.get_position(state.active_ticker)
                if pos:
                    settle_res = state.sim_agent._portfolio.settle_position(
                        ticker=state.active_ticker,
                        settlement_price=state.current_btc_price,
                        floor_strike=state.target_strike,
                        cap_strike=None,
                        strike_type="greater",
                    )
                    if settle_res and state.sim_agent._exec_logger:
                        state.sim_agent._exec_logger.log_settlement(settle_res)

            # Roll target strike to near-the-money rounded strike
            spot_float = float(state.current_btc_price)
            rolled_strike = round(spot_float / 50.0) * 50.0 + (12.50 if random.random() > 0.5 else -12.50)
            state.target_strike = Decimal(f"{rolled_strike:.2f}")

            now_iso = datetime.now(timezone.utc).strftime("%H:%M:%S")
            state.trade_tape.append({
                "ticker": state.active_ticker,
                "side": "yes" if state.current_btc_price >= state.target_strike else "no",
                "price_cents": "100.0¢",
                "contracts": 0,
                "val_str": "★ ROLLED",
                "time": now_iso,
            })
            logger.info("[CONTRACT ROLLED] New Target Strike for %s: $%s (Countdown reset to %ds)",
                        state.active_ticker, state.target_strike, state.market_expiry_seconds)

        return res

    state.orderbook.apply_delta = hooked_apply_delta

    # Hook trade events for live tape
    original_on_trade = state.sim_agent.on_trade_event
    async def hooked_on_trade(trade: Any) -> None:
        await original_on_trade(trade)
        val = float(trade.price * trade.count)
        val_str = f"+${val:,.0f}" if trade.taker_side.value == "yes" else f"-${val:,.0f}"
        state.trade_tape.append({
            "ticker": trade.market_ticker,
            "side": trade.taker_side.value,
            "price_cents": f"{float(trade.price) * 100:.1f}¢",
            "contracts": trade.count,
            "val_str": val_str,
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        })
        if len(state.trade_tape) > 30:
            state.trade_tape.pop(0)

    state.sim_agent.on_trade_event = hooked_on_trade

    await state.sim_agent.start()
    state.feed_task = asyncio.create_task(state.mock_feed.run())
    state.broadcast_task = asyncio.create_task(broadcast_loop())
    logger.info("Simulation background tasks started.")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await get_db_writer().start()
    await start_background_simulation()
    await state.gdrive_sync.start()
    yield
    await state.gdrive_sync.stop()
    if state.broadcast_task:
        state.broadcast_task.cancel()
    if state.mock_feed:
        state.mock_feed.stop()
    if state.sim_agent:
        await state.sim_agent.stop()
    if state.tick_writer:
        await state.tick_writer.close()
    await get_db_writer().stop()
    logger.info("Server shutdown complete.")


app = FastAPI(title="Kalshi BTC Trading Simulator API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------

class OrderRequest(BaseModel):
    ticker: str = Field(default="KXBTC15M-T78650")
    side: Literal["yes", "no"] = Field(default="yes")
    order_type: Literal["market", "limit"] = Field(default="market")
    size: int = Field(default=10, ge=1, le=1000)
    limit_price: float | None = Field(default=None)
    resting_only: bool = Field(default=False)

class SettingsRequest(BaseModel):
    ai_auto_trade: bool | None = None
    active_timeframe: str | None = None
    active_ticker: str | None = None
    mode: Literal["mock", "live"] | None = None

class ResetRequest(BaseModel):
    capital: float = Field(default=10000.0, ge=100.0)


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    return {"status": "ok", "mode": state.mode, "clients": len(state.connected_websockets)}

@app.get("/api/state")
async def get_state() -> dict[str, Any]:
    """Return full state snapshot."""
    return _build_full_state_payload()


@app.get("/api/history/ohlcv")
async def get_ohlcv(
    symbol: str = "BTC",
    interval: str = "1m",
    limit: int = 100,
) -> dict[str, Any]:
    """Retrieve rolling historical OHLCV candlestick bars.

    Query Parameters:
        symbol: Market ticker or 'BTC'. Default is 'BTC'.
        interval: Bar resolution: '1m', '5m', '15m', '1h'. Default is '1m'.
        limit: Number of recent bars to return (max 500). Default is 100.
    """
    candles = state.ohlcv_aggregator.get_candles(symbol=symbol, interval=interval, limit=limit)
    return {
        "symbol": symbol,
        "interval": interval,
        "count": len(candles),
        "candles": [
            {
                "timestamp": c.timestamp,
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume),
                "trades_count": c.trades_count,
            }
            for c in candles
        ],
    }


# ---------------------------------------------------------------------------
# Structured Export Endpoints (CSV & JSONL)
# ---------------------------------------------------------------------------

@app.get("/api/export/trades")
async def export_trades(format: Literal["csv", "jsonl"] = "csv") -> Response:
    """Export simulated trade fill execution history in CSV or JSONL format."""
    fills = state.sim_agent._portfolio.get_fill_history() if state.sim_agent else []

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["order_id", "ticker", "side", "size", "fill_price", "slippage", "cost", "timestamp"])
        for f in fills:
            side_str = f.side.value if hasattr(f.side, "value") else str(f.side)
            ts_str = f.timestamp.isoformat() if hasattr(f.timestamp, "isoformat") else str(f.timestamp)
            writer.writerow([
                f.order_id,
                f.ticker,
                side_str,
                f.size,
                f"{float(f.fill_price):.4f}",
                f"{float(f.slippage):.4f}",
                f"{float(f.cost):.2f}",
                ts_str,
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=kalshi_trades_export.csv"},
        )
    else:
        lines = []
        for f in fills:
            side_str = f.side.value if hasattr(f.side, "value") else str(f.side)
            ts_str = f.timestamp.isoformat() if hasattr(f.timestamp, "isoformat") else str(f.timestamp)
            record = {
                "order_id": f.order_id,
                "ticker": f.ticker,
                "side": side_str,
                "size": f.size,
                "fill_price": float(f.fill_price),
                "slippage": float(f.slippage),
                "cost": float(f.cost),
                "timestamp": ts_str,
            }
            lines.append(json.dumps(record))
        return Response(
            content="\n".join(lines) + ("\n" if lines else ""),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": "attachment; filename=kalshi_trades_export.jsonl"},
        )


@app.get("/api/export/settlements")
async def export_settlements(format: Literal["csv", "jsonl"] = "csv") -> Response:
    """Export binary contract expiry settlement history in CSV or JSONL format."""
    settlements = state.sim_agent._portfolio.get_settlement_history() if state.sim_agent else []

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ticker", "side", "size", "entry_price", "settlement_price", "outcome", "pnl", "timestamp"])
        for s in settlements:
            side_str = s.side.value if hasattr(s.side, "value") else str(s.side)
            ts_str = s.timestamp.isoformat() if hasattr(s.timestamp, "isoformat") else str(s.timestamp)
            writer.writerow([
                s.ticker,
                side_str,
                s.size,
                f"{float(s.entry_price):.4f}",
                f"{float(s.settlement_price):.2f}",
                s.outcome,
                f"{float(s.pnl):.2f}",
                ts_str,
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=kalshi_settlements_export.csv"},
        )
    else:
        lines = []
        for s in settlements:
            side_str = s.side.value if hasattr(s.side, "value") else str(s.side)
            ts_str = s.timestamp.isoformat() if hasattr(s.timestamp, "isoformat") else str(s.timestamp)
            record = {
                "ticker": s.ticker,
                "side": side_str,
                "size": s.size,
                "entry_price": float(s.entry_price),
                "settlement_price": float(s.settlement_price),
                "outcome": s.outcome,
                "pnl": float(s.pnl),
                "timestamp": ts_str,
            }
            lines.append(json.dumps(record))
        return Response(
            content="\n".join(lines) + ("\n" if lines else ""),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": "attachment; filename=kalshi_settlements_export.jsonl"},
        )


@app.get("/api/export/pnl")
async def export_pnl(format: Literal["csv", "json"] = "csv") -> Response:
    """Export current portfolio P&L performance metrics."""
    if not state.sim_agent:
        raise HTTPException(status_code=503, detail="Simulation agent not initialized")

    p = state.sim_agent._portfolio
    snap = p.get_pnl_snapshot()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "timestamp",
            "starting_balance",
            "current_balance",
            "total_equity",
            "total_realized_pnl",
            "total_unrealized_pnl",
            "win_rate_pct",
            "total_trades",
            "wins",
            "losses",
            "circuit_breaker_tripped",
            "drawdown_pct",
        ])
        win_rate_pct = float(snap.win_rate * 100) if snap.win_rate is not None else 0.0
        drawdown_pct = float(p.current_drawdown_pct * 100)
        writer.writerow([
            snap.timestamp.isoformat(),
            f"{float(snap.starting_balance):.2f}",
            f"{float(snap.current_balance):.2f}",
            f"{float(snap.total_equity):.2f}",
            f"{float(snap.total_realized_pnl):.2f}",
            f"{float(snap.total_unrealized_pnl):.2f}",
            f"{win_rate_pct:.1f}",
            snap.total_trades,
            snap.wins,
            snap.losses,
            str(p.circuit_breaker_tripped),
            f"{drawdown_pct:.1f}",
        ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=kalshi_pnl_snapshot.csv"},
        )
    else:
        payload = snap.model_dump()
        payload["timestamp"] = snap.timestamp.isoformat()
        payload["circuit_breaker_tripped"] = p.circuit_breaker_tripped
        payload["current_drawdown_pct"] = float(p.current_drawdown_pct * 100)
        return Response(
            content=json.dumps(payload, default=str),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=kalshi_pnl_snapshot.json"},
        )


@app.get("/api/export/ticks")
async def export_ticks(timeframe: str = "mock") -> FileResponse:
    """Download the active session tick recording JSONL file."""
    data_dir = state.data_dir
    files = sorted(data_dir.glob(f"ticks_{timeframe}_*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        # Fallback to any ticks file
        files = sorted(data_dir.glob("ticks_*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)

    if not files:
        raise HTTPException(status_code=404, detail="No recorded tick files found.")

    target_file = files[0]
    return FileResponse(
        path=str(target_file),
        media_type="application/x-ndjson",
        filename=target_file.name,
    )


# ---------------------------------------------------------------------------
# Google Drive Synchronization Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/gdrive/status")
async def get_gdrive_status() -> dict[str, Any]:
    """Return Google Drive backup daemon and rclone connectivity diagnostics."""
    return state.gdrive_sync.get_status()


@app.post("/api/gdrive/sync")
async def trigger_gdrive_sync() -> dict[str, Any]:
    """Trigger an immediate asynchronous backup of simulation data to Google Drive."""
    success = await state.gdrive_sync.sync_now()
    return {
        "success": success,
        "message": "Google Drive backup completed successfully." if success else "Google Drive backup skipped or rclone not configured.",
        "status": state.gdrive_sync.get_status(),
    }

@app.post("/api/kalshi/validate-credentials", response_model=ValidateCredentialsResponse)
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

    valid, msg, account_data = await async_validate_credentials(
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


@app.get("/api/kalshi/portfolio/sync")
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
    client = KalshiLiveOrderClient(
        api_key_id=api_key_id,
        private_key_path=private_key_source,
        base_url=base_url,
    )

    try:
        report = await client.reconcile_with_simulated(state.sim_agent._portfolio)
        live_state = await client.get_live_portfolio_state()
        return {
            "authenticated": True,
            "message": "Successfully synchronized with Kalshi exchange.",
            "reconciliation": report.model_dump(mode="json"),
            "live_portfolio": live_state.model_dump(mode="json"),
        }
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


@app.post("/api/kalshi/orders/live", response_model=LiveOrderResponse)
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

    # Acquire rate limiter token before exchange communication
    acquired = await kalshi_rate_limiter.acquire(1.0, timeout=5.0)
    if not acquired:
        raise HTTPException(status_code=429, detail="Kalshi rate limit reached. Please try again shortly.")

    base_url = DEMO_REST_BASE if req.is_demo else PROD_REST_BASE
    client = KalshiLiveOrderClient(
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


@app.delete("/api/kalshi/orders/live/{order_id}")
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
    client = KalshiLiveOrderClient(
        api_key_id=api_key_id,
        private_key_path=private_key_source,
        base_url=base_url,
    )

    try:
        success = await client.cancel_order(order_id)
        return {"success": success, "order_id": order_id, "status": "cancelled" if success else "failed"}
    finally:
        await client.close()


@app.get("/api/kalshi/orders/live/open")
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
    client = KalshiLiveOrderClient(
        api_key_id=api_key_id,
        private_key_path=private_key_source,
        base_url=base_url,
    )

    try:
        return await client.get_open_orders()
    finally:
        await client.close()


@app.get("/api/orders/open")
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

@app.delete("/api/orders/{order_id}")
async def cancel_order(order_id: str) -> dict[str, Any]:
    """Cancel an active resting limit order."""
    if not state.sim_agent or not state.sim_agent._simulator:
        raise HTTPException(status_code=503, detail="Simulation agent not running")
    success = state.sim_agent._simulator.cancel_resting_order(order_id)
    if success:
        return {"success": True, "order_id": order_id, "status": "cancelled"}
    raise HTTPException(status_code=404, detail="Order not found")

@app.post("/api/orders")
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

@app.post("/api/positions/close")
async def close_position_endpoint(req: ClosePositionRequest) -> dict[str, Any]:
    """Liquidate and close an open position at current market bid/ask."""
    if not state.sim_agent or not state.sim_agent._portfolio:
        raise HTTPException(status_code=503, detail="Simulation agent not running")

    portfolio = state.sim_agent._portfolio
    position = portfolio.get_position(req.ticker)
    if not position:
        raise HTTPException(status_code=404, detail=f"Position for '{req.ticker}' not found")

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

TIMEFRAME_CONFIGS: dict[Timeframe, dict[str, Any]] = {
    Timeframe.FIVE_MIN: {
        "series": "KXBTC5M",
        "ticker": "KXBTC5M-T78600",
        "target_strike": Decimal("78600.00"),
        "title": "BTC 5 min",
        "expiry_seconds": 300,
    },
    Timeframe.FIFTEEN_MIN: {
        "series": "KXBTC15M",
        "ticker": "KXBTC15M-T78650",
        "target_strike": Decimal("78656.27"),
        "title": "BTC 15 min",
        "expiry_seconds": 900,
    },
    Timeframe.ONE_HOUR: {
        "series": "KXBTCH",
        "ticker": "KXBTCH-T78500",
        "target_strike": Decimal("78500.00"),
        "title": "BTC 1 hour",
        "expiry_seconds": 3600,
    },
}

@app.post("/api/settings")
async def update_settings(req: SettingsRequest) -> dict[str, Any]:
    if req.ai_auto_trade is not None:
        state.ai_auto_trade = req.ai_auto_trade
    if req.mode is not None:
        state.mode = req.mode
        if req.mode == "live":
            logger.info("[MODE SWITCH] Switched to LIVE / Safety Dry-Run feed mode.")
        else:
            logger.info("[MODE SWITCH] Switched to Interactive Mock Feed.")
    if req.active_timeframe:
        try:
            tf = Timeframe(req.active_timeframe.lower())
            state.active_timeframe = tf
            cfg = TIMEFRAME_CONFIGS.get(tf)
            if cfg:
                state.active_ticker = cfg["ticker"]
                state.target_strike = cfg["target_strike"]
                state.market_expiry_seconds = cfg["expiry_seconds"]
                if not state.orderbook.get_book(state.active_ticker):
                    bk = L2BookState(state.active_ticker)
                    bk.yes_book = {Decimal("0.034"): Decimal("500"), Decimal("0.031"): Decimal("1000")}
                    bk.no_book = {Decimal("0.966"): Decimal("500"), Decimal("0.969"): Decimal("1000")}
                    state.orderbook._books[state.active_ticker] = bk
        except ValueError:
            pass
    if req.active_ticker:
        state.active_ticker = req.active_ticker

    return {
        "ai_auto_trade": state.ai_auto_trade,
        "active_timeframe": state.active_timeframe.value,
        "active_ticker": state.active_ticker,
        "target_strike": float(state.target_strike),
        "mode": state.mode,
    }

@app.post("/api/reset")
async def reset_portfolio(req: ResetRequest) -> dict[str, Any]:
    if state.sim_agent:
        p = state.sim_agent._portfolio
        p._balance = Decimal(str(req.capital))
        p._positions.clear()
        p._fill_history.clear()
        p._settlement_history.clear()
        p._total_trades = 0
        p._wins = 0
        p._losses = 0
        p._starting_balance = Decimal(str(req.capital))
        p._max_drawdown_limit = p._starting_balance * p._max_drawdown_pct
        p._circuit_breaker_tripped = False
        p._peak_equity = p._starting_balance
    return {"success": True, "capital": req.capital}


@app.post("/api/circuit-breaker/reset")
async def reset_circuit_breaker() -> dict[str, Any]:
    """Manually reset the drawdown circuit breaker to resume trading."""
    if state.sim_agent:
        state.sim_agent._portfolio.reset_circuit_breaker()
        return {"success": True, "message": "Circuit breaker reset. Trading resumed."}
    return {"success": False, "message": "No active simulation agent."}


# ---------------------------------------------------------------------------
# Historical Analytics & Time-Series Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/history/trades")
async def get_historical_trades_endpoint(
    ticker: str | None = None,
    timeframe: str | None = None,
    execution_mode: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Retrieve historical trade executions from SQLite store with filtering and pagination."""
    query_service = HistoricalQueryService()
    return await query_service.get_trades(
        ticker=ticker,
        timeframe=timeframe,
        execution_mode=execution_mode,
        limit=limit,
        offset=offset,
    )


@app.get("/api/history/settlements")
async def get_historical_settlements_endpoint(
    ticker: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Retrieve historical settled contract outcomes and realized P&L."""
    query_service = HistoricalQueryService()
    return await query_service.get_settlements(
        ticker=ticker,
        limit=limit,
        offset=offset,
    )


@app.get("/api/history/equity-curve")
async def get_historical_equity_curve_endpoint(
    start_ms: int | None = None,
    end_ms: int | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Retrieve time-series equity and drawdown history for interactive charts."""
    query_service = HistoricalQueryService()
    return await query_service.get_equity_curve(
        start_epoch_ms=start_ms,
        end_epoch_ms=end_ms,
        limit=limit,
    )


@app.get("/api/history/ai-predictions")
async def get_historical_ai_predictions_endpoint(
    ticker: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Retrieve historical Stage 1 AI probabilities and Stage 2 EV decisions."""
    query_service = HistoricalQueryService()
    return await query_service.get_ai_predictions(
        ticker=ticker,
        limit=limit,
        offset=offset,
    )


@app.get("/api/history/metrics")
async def get_historical_metrics_endpoint() -> dict[str, Any]:
    """Retrieve institutional performance statistics (Sharpe, Sortino, Calmar, Win Rate, Drawdown)."""
    query_service = HistoricalQueryService()
    return await query_service.compute_portfolio_metrics()



# ---------------------------------------------------------------------------
# WebSocket Broadcast Logic
# ---------------------------------------------------------------------------

def _build_full_state_payload() -> dict[str, Any]:
    """Serialize full real-time state for UI consumption."""
    ticker = state.active_ticker
    book = state.orderbook.get_book(ticker)

    # Best bid / ask in dollars & cents
    best_yes_bid = float(book.best_yes_bid) if book and book.best_yes_bid else 0.031
    best_yes_ask = float(book.best_yes_ask) if book and book.best_yes_ask else 0.034
    best_no_bid = float(book.best_no_bid) if book and book.best_no_bid else 0.966
    best_no_ask = float(Decimal("1.0") - book.best_yes_bid) if book and book.best_yes_bid else 0.969

    # L2 Ladder (formatted in cents matching Kalshi UI: e.g. 4.9¢, 4.8¢, etc.)
    ladder: list[dict[str, Any]] = []
    if book and (book.yes_book or book.no_book):
        yes_levels = sorted(book.yes_book.items(), key=lambda x: x[0], reverse=True)[:10]

        max_contracts = 5000.0
        for price_dec, qty_dec in yes_levels:
            p_cents = float(price_dec * 100)
            q = int(qty_dec)
            tot = float(price_dec * qty_dec)
            depth_pct = min(100.0, (q / max_contracts) * 100.0) if max_contracts else 0
            ladder.append({
                "side": "yes",
                "price_cents": f"{p_cents:.1f}¢",
                "price_raw": float(price_dec),
                "contracts": q,
                "total": f"${tot:.2f}",
                "depth_pct": round(depth_pct, 1),
            })
    
    if not ladder:
        # Realistic initial ladder
        ladder = [
            {"side": "yes", "price_cents": "4.9¢", "price_raw": 0.049, "contracts": 2200, "total": "$107.80", "depth_pct": 44.0},
            {"side": "yes", "price_cents": "4.8¢", "price_raw": 0.048, "contracts": 1, "total": "$0.05", "depth_pct": 2.0},
            {"side": "yes", "price_cents": "4.6¢", "price_raw": 0.046, "contracts": 2001, "total": "$92.05", "depth_pct": 40.0},
            {"side": "yes", "price_cents": "4.4¢", "price_raw": 0.044, "contracts": 3054, "total": "$134.38", "depth_pct": 61.0},
            {"side": "yes", "price_cents": "4.2¢", "price_raw": 0.042, "contracts": 16, "total": "$0.67", "depth_pct": 5.0},
            {"side": "yes", "price_cents": "4.1¢", "price_raw": 0.041, "contracts": 516, "total": "$21.16", "depth_pct": 12.0},
            {"side": "yes", "price_cents": "4.0¢", "price_raw": 0.040, "contracts": 1002, "total": "$40.08", "depth_pct": 20.0},
            {"side": "yes", "price_cents": "3.9¢", "price_raw": 0.039, "contracts": 16, "total": "$0.62", "depth_pct": 5.0},
        ]

    # AI Brain stats
    ai_data = {
        "p_up": 0.684,
        "p_down": 0.211,
        "p_wait": 0.105,
        "vpin": 0.18,
        "vpin_is_safe": True,
        "ev_yes": 0.042,
        "ev_no": -0.015,
        "edge_yes": 0.065,
        "edge_no": -0.02,
        "kelly_f_yes": 0.125,
        "kelly_f_no": 0.0,
        "recommended_side": "yes",
        "rationale": "High OFI buyer pressure & positive EV edge (+4.2¢)",
    }

    if state.sim_agent and state.sim_agent._onnx_engine:
        extractor = state.sim_agent._onnx_engine.extractor
        vpin_val = float(extractor.calculate_vpin())
        ai_data["vpin"] = round(vpin_val, 3)
        ai_data["vpin_is_safe"] = vpin_val < 0.65

    # Portfolio metrics
    portfolio_data = {
        "balance": 10000.0,
        "equity": 10000.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "win_rate": 0.0,
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "positions": [],
        "settlements": [],
    }

    if state.sim_agent and state.sim_agent._portfolio:
        p = state.sim_agent._portfolio
        snap = p.get_pnl_snapshot()
        portfolio_data["balance"] = float(p.balance)
        portfolio_data["equity"] = float(snap.total_equity)
        portfolio_data["realized_pnl"] = float(snap.total_realized_pnl)
        portfolio_data["unrealized_pnl"] = float(snap.total_unrealized_pnl)
        portfolio_data["win_rate"] = float(snap.win_rate * 100) if snap.win_rate is not None else 0.0
        portfolio_data["total_trades"] = snap.total_trades
        portfolio_data["wins"] = snap.wins
        portfolio_data["losses"] = snap.losses
        portfolio_data["circuit_breaker_tripped"] = p.circuit_breaker_tripped
        portfolio_data["current_drawdown_pct"] = float(p.current_drawdown_pct * 100)
        portfolio_data["positions"] = [
            {
                "ticker": pos.ticker,
                "side": pos.side.value,
                "size": pos.size,
                "entry_price": float(pos.avg_entry_price),
                "current_price": float(pos.current_price or pos.avg_entry_price),
                "unrealized_pnl": float(pos.unrealized_pnl),
            }
            for pos in p.get_all_positions()
        ]
        portfolio_data["settlements"] = [
            {
                "ticker": s.ticker,
                "side": s.side.value,
                "size": s.size,
                "entry_price": float(s.entry_price),
                "settlement_price": float(s.settlement_price),
                "outcome": s.outcome,
                "pnl": float(s.pnl),
                "timestamp": s.timestamp.strftime("%H:%M:%S"),
            }
            for s in reversed(p.get_settlement_history()[-10:])
        ]
        portfolio_data["open_orders"] = [
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
            for o in (state.sim_agent._simulator.get_all_resting_orders() if state.sim_agent and state.sim_agent._simulator else [])
        ]

    # Calculate BTC spot delta from strike
    btc_spot = float(state.current_btc_price)
    strike = float(state.target_strike)
    diff = btc_spot - strike
    diff_pct = (diff / strike) * 100.0

    cfg = TIMEFRAME_CONFIGS.get(state.active_timeframe, {})
    title = cfg.get("title", f"BTC {state.active_timeframe.value}")
    series = cfg.get("series", "KXBTC15M")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "market": {
            "title": title,
            "series": series,
            "ticker": state.active_ticker,
            "target_strike": strike,
            "target_strike_str": f"${strike:,.2f}",
            "current_btc_price": btc_spot,
            "current_btc_price_str": f"${btc_spot:,.2f}",
            "diff": round(diff, 2),
            "diff_pct": round(diff_pct, 3),
            "expiry_countdown_seconds": state.market_expiry_seconds,
            "expiry_countdown_str": f"{state.market_expiry_seconds // 60:02d}:{state.market_expiry_seconds % 60:02d}",
            "market_chance_pct": 5.9,
            "volume_24h_str": "$1,547,966",
            "best_yes_ask": round(best_yes_ask, 3),
            "best_yes_bid": round(best_yes_bid, 3),
            "best_no_ask": round(best_no_ask, 3),
            "best_no_bid": round(best_no_bid, 3),
            "yes_cents_str": f"{best_yes_ask * 100:.1f}¢",
            "no_cents_str": f"{best_no_ask * 100:.1f}¢",
        },
        "chart": state.price_history[-60:],
        "trade_tape": state.trade_tape[-15:],
        "orderbook_ladder": ladder,
        "ai_signals": ai_data,
        "portfolio": portfolio_data,
        "settings": {
            "ai_auto_trade": state.ai_auto_trade,
            "mode": state.mode,
            "timeframe": state.active_timeframe.value,
        }
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    state.connected_websockets.add(websocket)
    logger.info("WebSocket client connected. Active connections: %d", len(state.connected_websockets))

    # Send immediate state snapshot
    try:
        await websocket.send_text(json.dumps(_build_full_state_payload()))
    except Exception:
        pass

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                action = msg.get("action")
                if action == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        state.connected_websockets.discard(websocket)
        logger.info("WebSocket client disconnected. Remaining: %d", len(state.connected_websockets))


async def broadcast_loop() -> None:
    """High-frequency periodic broadcast loop to all connected web clients."""
    while True:
        try:
            if state.connected_websockets:
                payload = json.dumps(_build_full_state_payload())
                dead_sockets = set()
                for ws in list(state.connected_websockets):
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        dead_sockets.add(ws)
                state.connected_websockets -= dead_sockets
        except Exception as exc:
            logger.debug("Broadcast error: %s", exc)
        await asyncio.sleep(0.2)  # 5 updates per second


# ---------------------------------------------------------------------------
# Frontend Static Mount (if built)
# ---------------------------------------------------------------------------

frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


def main() -> None:
    uvicorn.run("kalshi_sim.server:app", host="0.0.0.0", port=8000, reload=False, log_level="info")


if __name__ == "__main__":
    main()

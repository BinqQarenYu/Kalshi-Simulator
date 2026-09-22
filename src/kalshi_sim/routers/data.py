"""Data Feed, OHLCV, Memory Management, and Google Drive Export API Router.

Extracted from server.py for institutional modularity, testability,
and token hygiene.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse

logger = logging.getLogger("kalshi_sim.routers.data")

router = APIRouter(tags=["data"])

_state_getter = None

def init_data_router(state_getter):
    global _state_getter
    _state_getter = state_getter

def get_state():
    if _state_getter is not None:
        return _state_getter()
    from kalshi_sim.server import state
    return state

class _StateProxy:
    def __getattr__(self, name):
        return getattr(get_state(), name)
    def __setattr__(self, name, value):
        setattr(get_state(), name, value)

state = _StateProxy()


@router.get("/api/history/ohlcv")
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

@router.get("/api/export/trades")
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


@router.get("/api/export/settlements")
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


@router.get("/api/export/pnl")
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


# ---------------------------------------------------------------------------
# High-Throughput Quantitative Data & Memory Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/v1/data/memory-profile")
async def get_memory_profile() -> dict:
    """Return real-time quantitative memory and data throughput telemetry."""
    profile = state.memory_manager.get_memory_profile()
    return {
        "status": "healthy" if not profile.is_pressure_critical else "pressure_warning",
        "active_tickers_count": profile.active_tickers_count,
        "total_hot_ticks": profile.total_hot_ticks,
        "total_offloaded_ticks": profile.total_offloaded_ticks,
        "pending_disk_queue_depth": profile.pending_disk_queue_depth,
        "estimated_hot_memory_kb": round(profile.estimated_hot_memory_kb, 2),
        "is_pressure_critical": profile.is_pressure_critical,
        "mode": state.mode,
    }


@router.get("/api/v1/data/hot-ticks/{ticker}")
async def get_hot_ticks(ticker: str, limit: int = 100) -> dict:
    """Fetch recent hot ticks directly from zero-copy memory ring buffer."""
    clamped_limit = max(1, min(limit, 500))
    ticks = state.memory_manager.get_hot_ticks(ticker, limit=clamped_limit)
    return {
        "ticker": ticker,
        "count": len(ticks),
        "ticks": ticks,
    }


@router.get("/api/export/ticks")
async def export_ticks(timeframe: str = "mock") -> FileResponse:
    """Download the active session tick recording JSONL file."""
    # SECURITY: Validate timeframe parameter to prevent path traversal and glob injection
    if not re.match(r"^[a-zA-Z0-9_\-]+$", timeframe):
        raise HTTPException(status_code=400, detail="Invalid timeframe parameter")

    data_dir = state.data_dir
    files = sorted(data_dir.glob(f"ticks_{timeframe}_*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)

    # SECURITY: Never fall back to arbitrary tick files from other timeframes/sessions
    # to prevent cross-session/cross-timeframe sensitive data exposure.
    if not files:
        raise HTTPException(status_code=404, detail="No recorded tick files found for specified timeframe.")

    target_file = files[0]
    # SECURITY: Ensure target file is strictly inside data_dir to prevent path traversal
    try:
        if not target_file.resolve().is_relative_to(data_dir.resolve()):
            raise HTTPException(status_code=403, detail="Access denied")
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    return FileResponse(
        path=str(target_file),
        media_type="application/x-ndjson",
        filename=target_file.name,
    )


# ---------------------------------------------------------------------------
# Google Drive Synchronization Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/gdrive/status")
async def get_gdrive_status() -> dict[str, Any]:
    """Return Google Drive backup daemon and rclone connectivity diagnostics."""
    return state.gdrive_sync.get_status()


@router.post("/api/gdrive/sync")
async def trigger_gdrive_sync() -> dict[str, Any]:
    """Trigger an immediate asynchronous backup of simulation data to Google Drive."""
    success = await state.gdrive_sync.sync_now()
    return {
        "success": success,
        "message": "Google Drive backup completed successfully." if success else "Google Drive backup skipped or rclone not configured.",
        "status": state.gdrive_sync.get_status(),
    }


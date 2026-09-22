"""Analytics, Reports, and Historical Data API Router.

Extracted from server.py for institutional modularity, testability,
and token hygiene.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from kalshi_sim.db import HistoricalQueryService

logger = logging.getLogger("kalshi_sim.routers.analytics")

router = APIRouter(tags=["analytics"])

# State getter and sync callback references injected at startup
_state_getter = None
_sync_live_settlements_fn = None

def init_analytics_router(state_getter, sync_live_settlements_fn=None):
    global _state_getter, _sync_live_settlements_fn
    _state_getter = state_getter
    _sync_live_settlements_fn = sync_live_settlements_fn

def get_state():
    if _state_getter is not None:
        return _state_getter()
    from kalshi_sim.server import state
    return state

async def sync_live_settlements(full_sync: bool = False):
    if _sync_live_settlements_fn is not None:
        return await _sync_live_settlements_fn(full_sync=full_sync)
    from kalshi_sim.server import sync_live_settlements as _sync
    return await _sync(full_sync=full_sync)

class _StateProxy:
    def __getattr__(self, name):
        return getattr(get_state(), name)
    def __setattr__(self, name, value):
        setattr(get_state(), name, value)

state = _StateProxy()

# ---------------------------------------------------------------------------

@router.get("/api/history/trades")
async def get_historical_trades_endpoint(
    ticker: str | None = None,
    asset: str | None = None,
    timeframe: str | None = None,
    bot_type: str | None = None,
    execution_mode: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Retrieve historical trade executions from SQLite store with filtering and pagination."""
    query_service = HistoricalQueryService()
    return await query_service.get_trades(
        ticker=ticker,
        asset=asset,
        timeframe=timeframe,
        bot_type=bot_type,
        execution_mode=execution_mode,
        limit=limit,
        offset=offset,
    )


@router.get("/api/history/settlements")
async def get_historical_settlements_endpoint(
    ticker: str | None = None,
    asset: str | None = None,
    timeframe: str | None = None,
    bot_type: str | None = None,
    execution_mode: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Retrieve historical settled contract outcomes and realized P&L."""
    query_service = HistoricalQueryService()
    return await query_service.get_settlements(
        ticker=ticker,
        asset=asset,
        timeframe=timeframe,
        bot_type=bot_type,
        execution_mode=execution_mode,
        limit=limit,
        offset=offset,
    )


@router.get("/api/history/equity-curve")
async def get_historical_equity_curve_endpoint(
    start_ms: int | None = None,
    end_ms: int | None = None,
    bot_type: str | None = None,
    execution_mode: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Retrieve time-series equity and drawdown history for interactive charts."""
    query_service = HistoricalQueryService()
    return await query_service.get_equity_curve(
        start_epoch_ms=start_ms,
        end_epoch_ms=end_ms,
        bot_type=bot_type,
        execution_mode=execution_mode,
        limit=limit,
    )


@router.get("/api/history/ai-predictions")
async def get_historical_ai_predictions_endpoint(
    ticker: str | None = None,
    bot_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Retrieve historical Stage 1 AI probabilities and Stage 2 EV decisions."""
    query_service = HistoricalQueryService()
    return await query_service.get_ai_predictions(
        ticker=ticker,
        bot_type=bot_type,
        limit=limit,
        offset=offset,
    )


@router.get("/api/history/metrics")
async def get_historical_metrics_endpoint(
    bot_type: str | None = None,
    execution_mode: str | None = None,
    asset: str | None = None,
    timeframe: str | None = None,
) -> dict[str, Any]:
    """Retrieve institutional performance statistics (Sharpe, Sortino, Calmar, Win Rate, Drawdown)."""
    query_service = HistoricalQueryService()
    return await query_service.compute_portfolio_metrics(
        bot_type=bot_type,
        execution_mode=execution_mode,
        asset=asset,
        timeframe=timeframe,
    )


@router.get("/api/bot/forward-validation-status")
async def get_forward_validation_status_endpoint(
    bot_type: str | None = None,
    execution_mode: str | None = None,
) -> dict[str, Any]:
    """Retrieve 100-Cycle Forward Validation Telemetry, Gates, and Real-Money Readiness."""
    query_service = HistoricalQueryService()
    metrics = await query_service.compute_portfolio_metrics(
        bot_type=bot_type,
        execution_mode=execution_mode,
    )

    reports = state.win_loss_reports
    if bot_type and bot_type.lower() not in ("all", "combined"):
        reports = [r for r in reports if r.get("bot_type") == bot_type or r.get("strategy_id") == bot_type]
    if execution_mode and execution_mode.lower() != "all":
        reports = [r for r in reports if r.get("execution_mode") == execution_mode or r.get("mode") == execution_mode]

    db_total = metrics.get("total_trades", 0)
    total_cycles = max(len(reports), db_total)
    target_cycles = 100
    progress_pct = min(100.0, round((total_cycles / target_cycles) * 100.0, 1))

    # Pull and align wins/losses
    wins = metrics.get("wins", 0)
    losses = metrics.get("losses", 0)
    if (wins + losses == 0) and len(reports) > 0:
        wins = sum(1 for r in reports if r.get("outcome") == "win")
        losses = sum(1 for r in reports if r.get("outcome") == "loss")
    
    total_active_trades = wins + losses
    win_rate = (wins / total_active_trades * 100.0) if total_active_trades > 0 else 0.0

    # Real-money readiness criteria
    ev_positive = metrics.get("expectancy_per_trade", 0.0) > 0.0
    profit_factor_ok = metrics.get("profit_factor", 0.0) >= 1.40
    drawdown_ok = metrics.get("max_drawdown_pct", 0.0) < 15.0
    cycles_ok = total_cycles >= target_cycles
    
    p = (state.sim_agent._portfolio if state.sim_agent else None) or state.portfolio
    state.integrity_agent.run_full_audit(
        portfolio=p,
        orderbook=state.orderbook,
        active_ticker=state.active_ticker,
        mode=state.mode,
        btc_price=state.current_btc_price,
        ws_connected=state.is_connected,
    )
    integrity_status_data = state.integrity_agent.get_latest_status()
    integrity_ok = integrity_status_data.get("status") == "HEALTHY"

    is_ready = bool(ev_positive and profit_factor_ok and drawdown_ok and cycles_ok and integrity_ok)

    return {
        "forward_testing": {
            "total_cycles_completed": total_cycles,
            "target_cycles": target_cycles,
            "progress_pct": progress_pct,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(win_rate, 2),
            "net_pnl": metrics.get("net_pnl", 0.0),
            "total_fees_paid": metrics.get("total_fees_paid", 0.0),
            "expectancy_per_trade": metrics.get("expectancy_per_trade", 0.0),
            "profit_factor": metrics.get("profit_factor", 1.0),
            "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
        },
        "gates": {
            "gate_1_positive_expectancy": {
                "name": "Positive Net EV (After Fees)",
                "passed": ev_positive,
                "current": f"${metrics.get('expectancy_per_trade', 0.0):.2f}/trade",
                "threshold": "> $0.00",
            },
            "gate_2_profit_factor": {
                "name": "Profit Factor",
                "passed": profit_factor_ok,
                "current": f"{metrics.get('profit_factor', 1.0):.2f}",
                "threshold": ">= 1.40",
            },
            "gate_3_max_drawdown": {
                "name": "Max Drawdown Cap",
                "passed": drawdown_ok,
                "current": f"{metrics.get('max_drawdown_pct', 0.0):.1f}%",
                "threshold": "< 15.0%",
            },
            "gate_4_100_cycle_sample": {
                "name": "100-Cycle Forward Validation",
                "passed": cycles_ok,
                "current": f"{total_cycles}/{target_cycles} cycles ({progress_pct}%)",
                "threshold": ">= 100 cycles",
            },
            "gate_5_integrity_audit": {
                "name": "Continuous Integrity Guardian",
                "passed": integrity_ok,
                "current": integrity_status_data.get("status", "UNKNOWN"),
                "threshold": "HEALTHY (100% Score)",
            },
        },
        "real_money_readiness": {
            "is_ready_for_real_money": is_ready,
            "micro_capital_cap": {
                "max_contracts_per_trade": 2,
                "max_risk_per_trade_dollars": 1.50,
                "daily_max_loss_circuit_breaker": 10.00,
            },
            "live_account": state.live_portfolio,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }




def _calculate_15m_metrics(reports_subset: list[dict[str, Any]]) -> dict[str, Any]:
    """Helper to compute standard 15-minute event performance metrics."""
    total = len(reports_subset)
    wins = sum(1 for r in reports_subset if r.get("outcome") == "win")
    losses = sum(1 for r in reports_subset if r.get("outcome") == "loss")
    win_rate = (wins / total * 100.0) if total > 0 else 0.0
    total_pnl = sum(r.get("pnl", 0.0) for r in reports_subset)
    gross_profits = sum(r.get("pnl", 0.0) for r in reports_subset if r.get("pnl", 0.0) > 0)
    gross_losses = abs(sum(r.get("pnl", 0.0) for r in reports_subset if r.get("pnl", 0.0) < 0))
    profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else (99.9 if gross_profits > 0 else 1.0)
    avg_pnl = (total_pnl / total) if total > 0 else 0.0
    return {
        "total_events": total,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2),
        "profit_factor": round(profit_factor, 2),
        "avg_pnl_per_cycle": round(avg_pnl, 2),
    }


@router.get("/api/reports/live")
async def get_live_reports_endpoint(limit: int = 500) -> dict[str, Any]:
    """Retrieve live real-money execution win/loss reports."""
    if state.mode == "live":
        await sync_live_settlements(full_sync=True)

    live_reports = [
        r for r in state.win_loss_reports
        if (r.get("execution_mode") == "live" or r.get("bot_type") == "live")
    ]
    summary = _calculate_15m_metrics(live_reports)
    cur_bal = 21.97
    if state.live_portfolio and "balance_dollars" in state.live_portfolio:
        try:
            cur_bal = float(state.live_portfolio["balance_dollars"])
        except Exception:
            pass
    elif state.order_client and hasattr(state.order_client, "shard_balances"):
        b2 = state.order_client.shard_balances.get(2)
        if b2:
            cur_bal = float(b2)
    summary["current_balance"] = round(cur_bal, 2)
    summary["starting_capital"] = 25.00
    return {
        "summary": summary,
        "reports": live_reports[:limit],
        "total_count": len(live_reports),
        "status": "LIVE_PRODUCTION",
    }


def _matches_bot_id(r: dict[str, Any], target_bot: str) -> bool:
    """Check if a report record belongs to a specific bot, handling historical aliases."""
    target = target_bot.lower().strip()
    r_bot = str(r.get("bot_id") or r.get("strategy_id") or r.get("bot_type") or "").lower().strip()
    r_strat = str(r.get("strategy_name") or r.get("ai_rationale") or "").lower()

    if target in ("onnx_macro_v2", "the_onnx_strategy", "dual_onnx", "dual_onnx_bot", "dual_onnx_arbitrage", "onnx_macro"):
        return (
            r_bot in ("onnx_macro_v2", "the_onnx_strategy", "dual_onnx", "dual_onnx_bot", "dual_onnx_arbitrage", "onnx_macro")
            or "dual onnx" in r_strat
            or "the onnx strategy" in r_strat
            or "contradiction" in r_strat
            or "dual-brain" in r_strat
        )
    elif target in ("3_step_domination_bot", "domination_bot", "domination", "3_step_dom"):
        return (
            r_bot in ("3_step_domination_bot", "domination_bot", "domination")
            or ("domination" in r_strat and "macro" not in r_strat and "dominion 2" not in r_strat and "contradiction" not in r_strat)
        )
    elif target in ("dominion_2_bot", "dominion2", "dominion_v2", "dominion_2"):
        return (
            r_bot in ("dominion_2_bot", "dominion2", "dominion_v2")
            or "dominion 2" in r_strat
            or "anti-pin" in r_strat
        )
    elif target in ("macro_trend_dominion", "macro_trend", "macro_trend_dominion_bot", "macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion"):
        return (
            r_bot in ("macro_trend_dominion", "macro_trend", "macro_trend_dominion_bot", "macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion")
            or ("macro trend" in r_strat and "contradiction" not in r_strat)
        )
    elif target in ("ofi_sprint_scalper", "ofi_scalper"):
        return (
            r_bot in ("ofi_sprint_scalper", "ofi_scalper")
            or "ofi sprint" in r_strat
        )
    return r_bot == target


@router.get("/api/reports/win-loss")
async def get_win_loss_reports_endpoint(
    limit: int = 50,
    bot_id: str | None = None,
    bot_type: str | None = None,
    mode: str | None = None,
    execution_mode: str | None = None,
    timeframe: str | None = None,
    asset: str | None = None,
    date: str | None = None,
) -> dict[str, Any]:
    """Retrieve event Win/Loss reports (5M / 15M) with overall, per-bot, Today's, and Live breakdowns."""
    if state.mode == "live":
        await sync_live_settlements()

    # Synchronize with reports persisted to disk by Standalone Bot or prior sessions
    reports_file = state.data_dir / "win_loss_reports.json"
    if reports_file.exists():
        try:
            disk_reports = json.loads(reports_file.read_text(encoding="utf-8"))
            if isinstance(disk_reports, list):
                known_ids = {r.get("report_id") for r in state.win_loss_reports}
                new_added = False
                for dr in disk_reports:
                    if dr.get("report_id") and dr.get("report_id") not in known_ids:
                        state.win_loss_reports.append(dr)
                        known_ids.add(dr.get("report_id"))
                        new_added = True
                if new_added:
                    state.win_loss_reports.sort(key=lambda r: str(r.get("timestamp_utc", "")), reverse=True)
        except Exception:
            pass

    all_reports = state.win_loss_reports
    macro_reports = [r for r in all_reports if _matches_bot_id(r, "macro_trend_dominion")]
    dom_reports = [r for r in all_reports if _matches_bot_id(r, "3_step_domination_bot")]
    dom2_reports = [r for r in all_reports if _matches_bot_id(r, "dominion_2_bot")]
    onnx_reports = [r for r in all_reports if r.get("bot_type") in ("onnx_ml_bot", "onnx_microstructure_bot", "onnx")]
    dual_onnx_reports = [r for r in all_reports if _matches_bot_id(r, "onnx_macro_v2")]
    live_reports = [
        r for r in all_reports
        if (r.get("execution_mode") == "live" or r.get("bot_type") == "live" or str(r.get("report_id", "")).startswith("WLR-LIVE-"))
    ]
    sim_reports = [
        r for r in all_reports 
        if r.get("execution_mode") in ("simulated", "mock", "paper", None) and not str(r.get("report_id", "")).startswith("WLR-LIVE-")
    ]

    et_now = datetime.now(ZoneInfo("America/New_York"))
    today_et_prefix = et_now.strftime("%Y-%m-%d")
    today_et_month_day = et_now.strftime("%B %d")
    today_reports = [
        r for r in all_reports
        if (str(r.get("timestamp_utc", "")).startswith(today_et_prefix)
            or today_et_month_day in str(r.get("cycle_time", ""))
            or today_et_prefix.replace("-", "") in str(r.get("report_id", "")))
    ]

    filtered_reports = all_reports
    if date and date.lower() in ("today", "current"):
        filtered_reports = today_reports

    exec_m = mode or execution_mode
    if exec_m and exec_m.lower() not in ("all", "combined"):
        if exec_m.lower() in ("live", "real"):
            filtered_reports = [r for r in filtered_reports if r in live_reports]
        elif exec_m.lower() in ("simulated", "mock", "paper"):
            filtered_reports = [r for r in filtered_reports if r in sim_reports]

    effective_bot = bot_id or bot_type
    if effective_bot and effective_bot.lower() not in ("all", "combined"):
        filtered_reports = [r for r in filtered_reports if _matches_bot_id(r, effective_bot)]

    if timeframe and timeframe.lower() not in ("all", "combined"):
        tf_clean = timeframe.lower()
        filtered_reports = [r for r in filtered_reports if str(r.get("timeframe", "15m")).lower() == tf_clean or (f"KX{tf_clean.upper()}" in str(r.get("ticker", "")).upper())]

    if asset and asset.lower() not in ("all", "combined"):
        asset_clean = asset.upper().strip()
        filtered_reports = [
            r for r in filtered_reports
            if r.get("asset", "").upper() == asset_clean or (f"KX{asset_clean}" in r.get("ticker", "").upper())
        ]

    BOT_NAMES = {
        "3_step_domination_bot": "3-Step Dominion v3.2",
        "onnx_macro_v2": "The ONNX Strategy (Dual-Brain)",
        "the_onnx_strategy": "The ONNX Strategy (Dual-Brain)",
        "dual_onnx": "The ONNX Strategy (Dual-Brain)",
        "dominion_2_bot": "Dominion 2 (Anti-Pin Scalper)",
        "macro_trend_dominion": "Macro Trend Dominion",
        "ofi_sprint_scalper": "OFI Sprint Scalper",
    }
    bot_summary = None
    if effective_bot and effective_bot.lower() not in ("all", "combined"):
        b_metrics = _calculate_15m_metrics(filtered_reports)
        last_t = filtered_reports[0].get("timestamp_utc") if filtered_reports else None
        bot_summary = {
            "bot_id": effective_bot,
            "bot_name": BOT_NAMES.get(effective_bot, effective_bot.replace("_", " ").title()),
            "execution_mode": exec_m or "all",
            **b_metrics,
            "last_trade_time": last_t,
        }

    return {
        "summary": _calculate_15m_metrics(filtered_reports),
        "bot_summary": bot_summary,
        "all_summary": _calculate_15m_metrics(all_reports),
        "macro_trend_summary": _calculate_15m_metrics(macro_reports),
        "domination_summary": _calculate_15m_metrics(dom_reports),
        "dominion2_summary": _calculate_15m_metrics(dom2_reports),
        "onnx_summary": _calculate_15m_metrics(dual_onnx_reports if dual_onnx_reports else onnx_reports),
        "dual_onnx_summary": _calculate_15m_metrics(dual_onnx_reports),
        "live_summary": _calculate_15m_metrics(live_reports),
        "sim_summary": _calculate_15m_metrics(sim_reports),
        "today_summary": _calculate_15m_metrics(today_reports),
        "total_today_reports": len(today_reports),
        "filter_bot_id": bot_id or "all",
        "filter_bot_type": effective_bot or "all",
        "filter_mode": exec_m or "all",
        "filter_timeframe": timeframe or "all",
        "filter_asset": asset or "all",
        "filter_date": date or "all",
        "reports": filtered_reports[:limit],
        "live_reports": live_reports[:limit],
        "total_live_reports": len(live_reports),
    }


@router.get("/api/reports/win-loss/export.csv")
async def export_win_loss_reports_csv(
    bot_type: str | None = None,
    mode: str | None = None,
    timeframe: str | None = None,
    asset: str | None = None,
    date: str | None = None,
) -> Response:
    """Export event Win/Loss reports as a CSV document with bot_type, asset, timeframe, date, and execution_mode."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "report_id",
        "bot_type",
        "execution_mode",
        "asset",
        "cycle_time",
        "ticker",
        "timeframe",
        "strike_price",
        "settlement_spot_price",
        "settlement_btc_price",
        "bot_side",
        "contracts",
        "entry_price",
        "settlement_price",
        "outcome",
        "pnl",
        "roi_pct",
        "ai_confidence",
        "vpin_score",
        "ev_edge",
        "balance_after",
        "timestamp_utc",
        "ai_rationale",
    ])
    reports = state.win_loss_reports
    if date and date.lower() in ("today", "current"):
        et_now = datetime.now(ZoneInfo("America/New_York"))
        today_et_prefix = et_now.strftime("%Y-%m-%d")
        today_et_month_day = et_now.strftime("%B %d")
        reports = [
            r for r in reports
            if (str(r.get("timestamp_utc", "")).startswith(today_et_prefix)
                or today_et_month_day in str(r.get("cycle_time", ""))
                or today_et_prefix.replace("-", "") in str(r.get("report_id", "")))
        ]

    if mode and mode.lower() not in ("all", "combined"):
        if mode.lower() in ("live", "real"):
            reports = [r for r in reports if r.get("execution_mode") == "live" or str(r.get("report_id", "")).startswith("WLR-LIVE-")]
        else:
            reports = [r for r in reports if r.get("execution_mode") in ("simulated", "mock", "paper", None) and not str(r.get("report_id", "")).startswith("WLR-LIVE-")]

    if bot_type and bot_type.lower() not in ("all", "combined"):
        reports = [r for r in reports if r.get("bot_type") == bot_type or r.get("strategy_id") == bot_type]

    if timeframe and timeframe.lower() not in ("all", "combined"):
        reports = [r for r in reports if str(r.get("timeframe", "15m")).lower() == timeframe.lower()]

    if asset and asset.lower() not in ("all", "combined"):
        asset_clean = asset.upper().strip()
        reports = [r for r in reports if r.get("asset", "").upper() == asset_clean or f"KX{asset_clean}" in r.get("ticker", "").upper()]

    for r in reports:
        writer.writerow([
            r.get("report_id"),
            r.get("bot_type", "3_step_domination_bot"),
            r.get("execution_mode", "simulated"),
            r.get("asset", "BTC"),
            r.get("cycle_time"),
            r.get("ticker"),
            r.get("timeframe"),
            f"{r.get('strike_price', 0.0):.4f}",
            f"{r.get('settlement_spot_price', r.get('settlement_btc_price', 0.0)):.4f}",
            f"{r.get('settlement_btc_price', 0.0):.4f}",
            r.get("bot_side"),
            r.get("contracts"),
            f"{r.get('entry_price', 0.0):.4f}",
            f"{r.get('settlement_price', 0.0):.2f}",
            r.get("outcome"),
            f"{r.get('pnl', 0.0):.2f}",
            f"{r.get('roi_pct', 0.0):.2f}%",
            f"{r.get('ai_confidence', 0.0)*100:.1f}%",
            f"{r.get('vpin_score', 0.0):.3f}",
            f"{r.get('ev_edge', 0.0)*100:.1f}%",
            f"{r.get('balance_after', 0.0):.2f}",
            r.get("timestamp_utc"),
            r.get("ai_rationale"),
        ])
    prefix = f"kalshi_{asset.lower()}_" if asset and asset.lower() != "all" else "kalshi_"
    tf_str = f"{timeframe}_" if timeframe and timeframe.lower() != "all" else ""
    date_str = "today_" if date and date.lower() in ("today", "current") else ""
    filename = f"{prefix}{tf_str}{date_str}live_reports.csv" if mode == "live" else f"{prefix}{tf_str}{date_str}win_loss_reports.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/api/reports/win-loss/export.json")
async def export_win_loss_reports_json(
    bot_type: str | None = None,
    mode: str | None = None,
    timeframe: str | None = None,
    asset: str | None = None,
    date: str | None = None,
) -> Response:
    """Export event Win/Loss reports as formatted JSON."""
    reports = state.win_loss_reports
    if date and date.lower() in ("today", "current"):
        et_now = datetime.now(ZoneInfo("America/New_York"))
        today_et_prefix = et_now.strftime("%Y-%m-%d")
        today_et_month_day = et_now.strftime("%B %d")
        reports = [
            r for r in reports
            if (str(r.get("timestamp_utc", "")).startswith(today_et_prefix)
                or today_et_month_day in str(r.get("cycle_time", ""))
                or today_et_prefix.replace("-", "") in str(r.get("report_id", "")))
        ]

    if mode and mode.lower() not in ("all", "combined"):
        if mode.lower() in ("live", "real"):
            reports = [r for r in reports if r.get("execution_mode") == "live" or str(r.get("report_id", "")).startswith("WLR-LIVE-")]
        else:
            reports = [r for r in reports if r.get("execution_mode") in ("simulated", "mock", "paper", None) and not str(r.get("report_id", "")).startswith("WLR-LIVE-")]

    if bot_type and bot_type.lower() not in ("all", "combined"):
        reports = [r for r in reports if r.get("bot_type") == bot_type or r.get("strategy_id") == bot_type]

    if timeframe and timeframe.lower() not in ("all", "combined"):
        reports = [r for r in reports if str(r.get("timeframe", "15m")).lower() == timeframe.lower()]

    if asset and asset.lower() not in ("all", "combined"):
        asset_clean = asset.upper().strip()
        reports = [r for r in reports if r.get("asset", "").upper() == asset_clean or f"KX{asset_clean}" in r.get("ticker", "").upper()]

    prefix = f"kalshi_{asset.lower()}_" if asset and asset.lower() != "all" else "kalshi_"
    tf_str = f"{timeframe}_" if timeframe and timeframe.lower() != "all" else ""
    date_str = "today_" if date and date.lower() in ("today", "current") else ""
    filename = f"{prefix}{tf_str}{date_str}live_reports.json" if mode == "live" else f"{prefix}{tf_str}{date_str}win_loss_reports.json"
    return Response(
        content=json.dumps(reports, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/api/reports/full")
async def get_full_24h_reports(
    bot_type: str | None = None,
    mode: str | None = None,
    execution_mode: str | None = None,
) -> dict[str, Any]:
    """Retrieve complete persistent 24-hour 15-minute event win/loss reports with statistics."""
    if state.mode == "live":
        await sync_live_settlements()

    exec_m = mode or execution_mode
    reports = state.win_loss_reports
    if bot_type and bot_type.lower() not in ("all", "combined"):
        reports = [r for r in reports if r.get("bot_type") == bot_type or r.get("strategy_id") == bot_type]
    if exec_m and exec_m.lower() != "all":
        reports = [r for r in reports if r.get("execution_mode") == exec_m or r.get("mode") == exec_m]

    total_events = len(reports)
    wins = sum(1 for r in reports if r.get("outcome") == "win")
    losses = sum(1 for r in reports if r.get("outcome") == "loss")
    flats = sum(1 for r in reports if r.get("outcome") in ("flat", "skip", "veto"))
    trades_count = wins + losses
    win_rate = (wins / trades_count * 100.0) if trades_count > 0 else 0.0

    total_pnl = sum(r.get("pnl", 0.0) for r in reports)
    gross_profits = sum(r.get("pnl", 0.0) for r in reports if r.get("pnl", 0.0) > 0)
    gross_losses = abs(sum(r.get("pnl", 0.0) for r in reports if r.get("pnl", 0.0) < 0))
    profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else (99.9 if gross_profits > 0 else 1.0)
    
    if state.mode == "live" or mode == "live" or execution_mode == "live":
        current_equity = float(state.live_portfolio.get("balance_dollars", 21.97)) if state.live_portfolio else float(state.sim_agent._portfolio.equity if state.sim_agent else 100.0)
    else:
        current_equity = float(state.sim_agent._portfolio.equity) if state.sim_agent else 100.0

    return {
        "evaluation_window": "24_hours",
        "total_15m_events": total_events,
        "trades_executed": trades_count,
        "wins": wins,
        "losses": losses,
        "flats_or_vetoed": flats,
        "win_rate_pct": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "net_pnl": round(total_pnl, 2),
        "current_equity": round(current_equity, 2),
        "active_strategy": state.active_strategy_bot,
        "filter_bot_type": bot_type or "all",
        "filter_mode": mode or "all",
        "reports": reports,
    }

@router.post("/api/reports/reset")
async def reset_reports_manually(target: str = "all") -> dict[str, Any]:
    """Manually clear 15-minute event win/loss reports and SQLite store for a specific bot, table, or all systems."""
    target_clean = target.lower()
    query_service = HistoricalQueryService()
    db_counts = {"settlements": 0, "trades": 0, "ai_predictions": 0, "equity_snapshots": 0}

    if target_clean in ("all", "combined", "global"):
        state.win_loss_reports = []
        db_counts = await query_service.reset_history()
    elif target_clean in ("15m_reports", "win_loss_reports", "reports"):
        count = len(state.win_loss_reports)
        state.win_loss_reports = []
        db_counts = {"win_loss_reports": count}
    elif target_clean in ("trades", "trade_journal"):
        count = await query_service.delete_batch("trades", [t["id"] for t in await query_service.get_trades(limit=50000)])
        db_counts = {"trades": count}
    elif target_clean in ("settlements", "settlement_history"):
        count = await query_service.delete_batch("settlements", [s["id"] for s in await query_service.get_settlements(limit=50000)])
        db_counts = {"settlements": count}
    elif target_clean in ("ai", "ai_predictions", "predictions"):
        count = await query_service.delete_batch("ai_predictions", [p["id"] for p in await query_service.get_ai_predictions(limit=50000)])
        db_counts = {"ai_predictions": count}
    elif target_clean in ("live", "live_trading"):
        state.win_loss_reports = [
            r for r in state.win_loss_reports if r.get("execution_mode") != "live" and r.get("mode") != "live"
        ]
        db_counts = await query_service.reset_history(execution_mode="live")
    elif target_clean in ("3_step_domination_bot", "domination", "3_step"):
        state.win_loss_reports = [
            r
            for r in state.win_loss_reports
            if r.get("bot_type") not in ("3_step_domination_bot", None)
            and r.get("strategy_id") != "3_step_domination_bot"
        ]
        db_counts = await query_service.reset_history(bot_type="3_step_domination_bot")
    elif target_clean in ("onnx_microstructure_bot", "onnx_ml_bot", "onnx"):
        state.win_loss_reports = [
            r
            for r in state.win_loss_reports
            if r.get("bot_type") not in ("onnx_microstructure_bot", "onnx_ml_bot")
            and r.get("strategy_id") not in ("onnx_microstructure_bot", "onnx_ml_bot")
        ]
        db_counts = await query_service.reset_history(bot_type="onnx_ml_bot")
    else:
        state.win_loss_reports = []
        db_counts = await query_service.reset_history()

    state.save_persisted_reports()
    state.is_dirty = True
    logger.info("Historical ledger and analytics manually reset for target='%s': %s", target_clean, db_counts)
    return {
        "success": True,
        "target": target_clean,
        "remaining_reports": len(state.win_loss_reports),
        "deleted_db_records": db_counts,
        "message": f"Historical ledger and analytics reset successfully for target '{target_clean}'.",
    }


@router.delete("/api/reports/win-loss/{report_id}")
async def delete_win_loss_report_endpoint(report_id: str) -> dict[str, Any]:
    """Delete a single 15-minute event win/loss report by report_id."""
    initial_len = len(state.win_loss_reports)
    state.win_loss_reports = [r for r in state.win_loss_reports if str(r.get("report_id")) != report_id]
    deleted = len(state.win_loss_reports) < initial_len
    if deleted:
        state.save_persisted_reports()
        state.is_dirty = True
        logger.info("Deleted 15M event report: %s", report_id)
        return {"success": True, "deleted_id": report_id, "remaining": len(state.win_loss_reports)}
    raise HTTPException(status_code=404, detail=f"Report ID '{report_id}' not found.")


@router.delete("/api/history/trades/{trade_id}")
async def delete_trade_endpoint(trade_id: str) -> dict[str, Any]:
    """Delete a single trade record from the SQLite store."""
    query_service = HistoricalQueryService()
    success = await query_service.delete_trade(trade_id)
    if success:
        state.is_dirty = True
        logger.info("Deleted trade execution: %s", trade_id)
        return {"success": True, "deleted_trade": trade_id}
    raise HTTPException(status_code=404, detail=f"Trade '{trade_id}' not found.")


@router.delete("/api/history/settlements/{settlement_id}")
async def delete_settlement_endpoint(settlement_id: str) -> dict[str, Any]:
    """Delete a single settlement record from the SQLite store."""
    query_service = HistoricalQueryService()
    success = await query_service.delete_settlement(settlement_id)
    if success:
        state.is_dirty = True
        logger.info("Deleted settlement record: %s", settlement_id)
        return {"success": True, "deleted_settlement": settlement_id}
    raise HTTPException(status_code=404, detail=f"Settlement '{settlement_id}' not found.")


@router.delete("/api/history/ai-predictions/{prediction_id}")
async def delete_ai_prediction_endpoint(prediction_id: int) -> dict[str, Any]:
    """Delete an AI prediction record from the SQLite store."""
    query_service = HistoricalQueryService()
    success = await query_service.delete_ai_prediction(prediction_id)
    if success:
        state.is_dirty = True
        logger.info("Deleted AI prediction record: %s", prediction_id)
        return {"success": True, "deleted_prediction_id": prediction_id}
    raise HTTPException(status_code=404, detail=f"AI Prediction '{prediction_id}' not found.")


class BatchDeleteRequest(BaseModel):
    table: str = Field(..., description="Target table: 'trades', 'settlements', 'ai_predictions', 'win_loss_reports'")
    ids: list[Any] = Field(..., description="List of IDs or keys to delete")


ALLOWED_BATCH_DELETE_TABLES = {"trades", "settlements", "ai_predictions", "equity_snapshots", "win_loss_reports", "reports"}


@router.post("/api/history/batch-delete")
async def batch_delete_endpoint(req: BatchDeleteRequest) -> dict[str, Any]:
    """Batch delete records from a specified historical table or reports ledger."""
    table_clean = req.table.lower().strip()
    if table_clean not in ALLOWED_BATCH_DELETE_TABLES:
        raise HTTPException(status_code=400, detail=f"Invalid table name '{req.table}' for batch delete.")

    if table_clean in ("win_loss_reports", "reports"):
        id_set = {str(x) for x in req.ids}
        initial_len = len(state.win_loss_reports)
        state.win_loss_reports = [r for r in state.win_loss_reports if str(r.get("report_id")) not in id_set]
        deleted_count = initial_len - len(state.win_loss_reports)
        if deleted_count > 0:
            state.save_persisted_reports()
            state.is_dirty = True
        return {"success": True, "table": "win_loss_reports", "deleted_count": deleted_count, "remaining": len(state.win_loss_reports)}

    query_service = HistoricalQueryService()
    deleted_count = await query_service.delete_batch(table_clean, req.ids)
    state.is_dirty = True
    return {"success": True, "table": table_clean, "deleted_count": deleted_count}


# ---------------------------------------------------------------------------
# Additional Historical Table CSV/JSON Export Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/history/trades/export.csv")
async def export_trades_csv(
    bot_type: str | None = None,
    execution_mode: str | None = None,
) -> Response:
    """Export historical trade executions as CSV."""
    query_service = HistoricalQueryService()
    trades = await query_service.get_trades(bot_type=bot_type, execution_mode=execution_mode, limit=5000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "trade_id",
        "timestamp_utc",
        "ticker",
        "timeframe",
        "side",
        "size",
        "price",
        "gross_value",
        "fees",
        "vpin",
        "kelly_fraction",
        "bot_type",
        "execution_mode",
        "status",
    ])
    for t in trades:
        writer.writerow([
            t.get("trade_id"),
            t.get("timestamp_utc"),
            t.get("ticker"),
            t.get("timeframe"),
            t.get("side"),
            t.get("size"),
            f"{t.get('price', 0.0):.4f}",
            f"{t.get('gross_value', 0.0):.2f}",
            f"{t.get('fees', 0.0):.4f}",
            f"{t.get('vpin', 0.0):.4f}" if t.get("vpin") is not None else "",
            f"{t.get('kelly_fraction', 0.0):.4f}" if t.get("kelly_fraction") is not None else "",
            t.get("bot_type"),
            t.get("execution_mode"),
            t.get("status"),
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kalshi_trade_journal.csv"},
    )


@router.get("/api/history/trades/export.json")
async def export_trades_json(
    bot_type: str | None = None,
    execution_mode: str | None = None,
) -> Response:
    """Export historical trade executions as JSON."""
    query_service = HistoricalQueryService()
    trades = await query_service.get_trades(bot_type=bot_type, execution_mode=execution_mode, limit=5000)
    return Response(
        content=json.dumps(trades, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=kalshi_trade_journal.json"},
    )


@router.get("/api/history/settlements/export.csv")
async def export_settlements_csv(
    bot_type: str | None = None,
    execution_mode: str | None = None,
) -> Response:
    """Export historical settlements as CSV."""
    query_service = HistoricalQueryService()
    settlements = await query_service.get_settlements(bot_type=bot_type, execution_mode=execution_mode, limit=5000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "settlement_id",
        "timestamp_utc",
        "ticker",
        "side",
        "size",
        "entry_price",
        "settlement_price",
        "outcome",
        "pnl",
        "balance_after",
        "bot_type",
        "execution_mode",
    ])
    for s in settlements:
        writer.writerow([
            s.get("settlement_id"),
            s.get("timestamp_utc"),
            s.get("ticker"),
            s.get("side"),
            s.get("size"),
            f"{s.get('entry_price', 0.0):.4f}",
            f"{s.get('settlement_price', 0.0):.2f}",
            s.get("outcome"),
            f"{s.get('pnl', 0.0):.2f}",
            f"{s.get('balance_after', 0.0):.2f}",
            s.get("bot_type"),
            s.get("execution_mode"),
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kalshi_settlements.csv"},
    )


@router.get("/api/history/settlements/export.json")
async def export_settlements_json(
    bot_type: str | None = None,
    execution_mode: str | None = None,
) -> Response:
    """Export historical settlements as JSON."""
    query_service = HistoricalQueryService()
    settlements = await query_service.get_settlements(bot_type=bot_type, execution_mode=execution_mode, limit=5000)
    return Response(
        content=json.dumps(settlements, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=kalshi_settlements.json"},
    )


@router.get("/api/history/ai-predictions/export.csv")
async def export_ai_predictions_csv(
    bot_type: str | None = None,
) -> Response:
    """Export historical AI inferences and Stage 2 EV decisions as CSV."""
    query_service = HistoricalQueryService()
    predictions = await query_service.get_ai_predictions(bot_type=bot_type, limit=5000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id",
        "timestamp_utc",
        "ticker",
        "p_up",
        "p_down",
        "p_wait",
        "vpin",
        "ev_yes",
        "ev_no",
        "recommended_side",
        "bot_type",
        "rationale",
    ])
    for p in predictions:
        writer.writerow([
            p.get("id"),
            p.get("timestamp_utc"),
            p.get("ticker"),
            f"{p.get('p_up', 0.0):.4f}",
            f"{p.get('p_down', 0.0):.4f}",
            f"{p.get('p_wait', 0.0):.4f}",
            f"{p.get('vpin', 0.0):.4f}",
            f"{p.get('ev_yes', 0.0):.4f}",
            f"{p.get('ev_no', 0.0):.4f}",
            p.get("recommended_side"),
            p.get("bot_type"),
            p.get("rationale"),
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kalshi_ai_decisions.csv"},
    )


@router.get("/api/history/ai-predictions/export.json")
async def export_ai_predictions_json(
    bot_type: str | None = None,
) -> Response:
    """Export historical AI inferences as JSON."""
    query_service = HistoricalQueryService()
    predictions = await query_service.get_ai_predictions(bot_type=bot_type, limit=5000)
    return Response(
        content=json.dumps(predictions, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=kalshi_ai_decisions.json"},
    )


@router.get("/api/reports/executive-summary/export.json")
async def export_executive_summary_json() -> Response:
    """Export complete institutional executive summary combining portfolio metrics, multi-bot comparison, 5 gates, and all reports."""
    query_service = HistoricalQueryService()
    [m_all, m_macro, m_dom2, m_dom, m_onnx, m_live, trades, settlements, val_status] = await asyncio.gather(
        query_service.compute_portfolio_metrics(),
        query_service.compute_portfolio_metrics(bot_type="macro_trend_dominion", execution_mode="simulated"),
        query_service.compute_portfolio_metrics(bot_type="dominion_2_bot", execution_mode="simulated"),
        query_service.compute_portfolio_metrics(bot_type="3_step_domination_bot", execution_mode="simulated"),
        query_service.compute_portfolio_metrics(bot_type="onnx_ml_bot", execution_mode="simulated"),
        query_service.compute_portfolio_metrics(execution_mode="live"),
        query_service.get_trades(limit=1000),
        query_service.get_settlements(limit=1000),
        get_forward_validation_status_endpoint(),
    )

    all_reports = state.win_loss_reports
    macro_reports = [r for r in all_reports if r.get("bot_type") in ("macro_onnx", "macro_onnx_bot", "macro_trend_onnx_fusion", "macro_trend_dominion", "macro_trend", "macro_trend_dominion_bot")]
    dom2_reports = [r for r in all_reports if r.get("bot_type") in ("dominion_2_bot", "dominion2", "dominion_v2")]
    dom_reports = [r for r in all_reports if r.get("bot_type") in ("3_step_domination_bot", "domination_bot", "domination")]
    onnx_reports = [r for r in all_reports if r.get("bot_type") in ("onnx_ml_bot", "onnx_microstructure_bot", "onnx")]
    live_reports = [r for r in all_reports if r.get("execution_mode") == "live" or r.get("bot_type") == "live"]

    executive_payload = {
        "title": "Kalshi Institutional Performance Analytics & Trade Audit Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "combined_portfolio_metrics": m_all,
        "multi_system_comparison": {
            "macro_trend_dominion": m_macro,
            "dominion_2_bot": m_dom2,
            "domination_bot": m_dom,
            "onnx_ml_bot": m_onnx,
            "live_trading": m_live,
        },
        "multi_bot_15m_metrics": {
            "combined": _calculate_15m_metrics(all_reports),
            "macro_trend_dominion": _calculate_15m_metrics(macro_reports),
            "dominion_2_bot": _calculate_15m_metrics(dom2_reports),
            "domination_bot": _calculate_15m_metrics(dom_reports),
            "onnx_ml_bot": _calculate_15m_metrics(onnx_reports),
            "live_trading": _calculate_15m_metrics(live_reports),
        },
        "forward_validation_gates": val_status,
        "win_loss_event_reports": state.win_loss_reports,
        "recent_trades_count": len(trades),
        "recent_settlements_count": len(settlements),
    }

    return Response(
        content=json.dumps(executive_payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=kalshi_executive_audit_summary.json"},
    )





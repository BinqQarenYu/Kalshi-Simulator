"""FastAPI Pocket Cockpit API Router for Standalone Bot.

Extracts all route endpoints, middleware, and request/response models
from standalone_bot.py to keep the engine modular and maintainable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from kalshi_sim.incubator_manager import get_incubator_manager
from kalshi_sim.preset_manager import get_preset_manager
from kalshi_sim.schemas import CryptoAsset, get_asset_config
from kalshi_sim.standalone_bot_modules.config import QRCODE_PATH, TEMPLATE_PATH
def _get_sb():
    import kalshi_sim.standalone_bot as _sb
    return _sb


logger = logging.getLogger("StandaloneBot.Routes")

router = APIRouter()

# Engine accessor function injected by standalone_bot
_get_engine: Optional[Callable[[], Any]] = None


def set_engine_accessor(accessor: Callable[[], Any]) -> None:
    """Register the engine accessor callback."""
    global _get_engine
    _get_engine = accessor


def _require_engine() -> Any:
    """Retrieve active engine or raise 503 HTTP exception."""
    if _get_engine is None:
        raise HTTPException(status_code=503, detail="Engine not registered")
    engine = _get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Engine initializing or not ready")
    return engine


# ---------------------------------------------------------------------------
# Request / Response Pydantic Models
# ---------------------------------------------------------------------------

class AssetSelectRequest(BaseModel):
    asset: Optional[str] = None
    assets: Optional[List[str]] = None


class ParametersUpdateRequest(BaseModel):
    asset: Optional[str] = Field(default=None, description="Target asset for calibration (BTC, ETH, SOL, DOGE, GOLD, HYPER)")
    discount_limit_price: Optional[float] = Field(default=None, ge=0.10, le=0.65, description="Maker discount limit price ceiling")
    max_contracts: Optional[int] = Field(default=None, ge=1, le=1, description="Max contracts per cycle trade (strictly 1)")
    min_edge_pct: Optional[float] = Field(default=None, ge=1.0, le=50.0, description="Minimum edge percentage")
    min_ev_dollars: Optional[float] = Field(default=None, ge=0.01, le=0.50, description="Minimum net EV dollars per contract")
    min_spot_diff: Optional[float] = Field(default=None, ge=0.0, le=2000.0, description="Minimum distance from strike to avoid coin flips")
    typical_1m_volatility: Optional[float] = Field(default=None, ge=0.000001, le=500.0, description="Typical 1-minute baseline volatility")
    vpin_toxic_threshold: Optional[float] = Field(default=None, ge=0.10, le=0.95, description="VPIN toxicity threshold")
    take_profit_price_threshold: Optional[float] = Field(default=None, ge=0.50, le=0.99, description="Take profit ceiling")
    enable_take_profit_ceiling: Optional[bool] = Field(default=None, description="Take profit ceiling enabled toggle")
    require_reversal_for_tp_ceiling: Optional[bool] = Field(default=None, description="Require 85%+ reversal detection to exit at ceiling")
    enable_reverse_take_profit_roi: Optional[bool] = Field(default=None, description="Only take profit on min_take_profit_roi if indicators >= 85% reverse")
    reverse_indicator_threshold: Optional[float] = Field(default=None, ge=50.0, le=99.0, description="Conviction threshold in opposite direction required for take-profit harvest (e.g. 85.0%)")
    min_take_profit_roi: Optional[float] = Field(default=None, ge=5.0, le=100.0, description="Minimum take profit ROI percentage")
    min_confidence: Optional[float] = Field(default=None, ge=0.50, le=100.0, description="Minimum ONNX neural net confidence")
    momentum_max_price: Optional[float] = Field(default=None, ge=0.50, le=0.99, description="Maximum allowable entry price for momentum trades")
    brain_priority_mode: Optional[str] = Field(default=None, description="Brain priority arbitration mode: TREND_ALIGNED_SCALP, CONTRADICTION_SNIPER, UNANIMOUS_CONSENSUS")
    contract_scaling_mode: Optional[str] = Field(default=None, description="Contract sizing mode: TIER_0_STRICT_1, TIER_1_CONVICTION_2, TIER_2_KELLY")
    volatility_floor: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Dead chop cutoff threshold in dollars ($)")
    volatility_ceiling: Optional[float] = Field(default=None, ge=10.0, le=500.0, description="News event / high chaos cutoff in dollars ($)")
    entry_discount_depth: Optional[float] = Field(default=None, ge=0.10, le=0.65, description="Entry discount limit depth ceiling ($0.35 - $0.65)")
    tape_confirmation_ticks: Optional[int] = Field(default=None, ge=1, le=10, description="Number of consecutive orderflow tape ticks required for entry confirmation")
    taker_cross_ev_threshold: Optional[float] = Field(default=None, ge=0.01, le=0.30, description="Minimum EV required to pay taker spread/fee")
    dynamic_moat_multiplier: Optional[float] = Field(default=None, ge=0.5, le=3.0, description="Dynamic moat volatility multiplier")
    moneyness_moat_multiplier: Optional[float] = Field(default=None, ge=0.5, le=10.0, description="Moneyness Moat multiplier")
    opening_quarantine_seconds: Optional[float] = Field(default=None, ge=0.0, le=300.0, description="Opening quarantine in seconds")
    max_temporal_skew_ms: Optional[float] = Field(default=None, ge=100.0, le=10000.0, description="Max cross-brain temporal skew in milliseconds")
    gamma_cliff_seconds: Optional[float] = Field(default=None, ge=10.0, le=300.0, description="Gamma cliff late-cycle cutoff in seconds")
    auto_cancel_on_veto: Optional[bool] = Field(default=None, description="Automatically cancel resting orders on veto/cutoff")
    dynamic_volatility_mode: Optional[str] = Field(default=None, description="Volatility mode: REALIZED_ATR or FIXED_14")
    entry_window_open_minutes: Optional[float] = Field(default=None, ge=1.0, le=14.9, description="Earliest time remaining to enter cycle in minutes (e.g. 12.0m)")
    entry_window_close_minutes: Optional[float] = Field(default=None, ge=0.5, le=14.0, description="Latest time remaining to enter and sweep cutoff in minutes (e.g. 4.5m)")
    enable_trailing_ratchet: Optional[bool] = Field(default=None, description="Enable high-water mark trailing profit ratchet and breakeven armor")
    trailing_ratchet_buffer: Optional[float] = Field(default=None, ge=0.02, le=0.25, description="Trailing stop buffer in dollars below peak bid")
    spot_delta_front_run_threshold: Optional[float] = Field(default=None, ge=0.00001, le=100.0, description="Base rolling spot velocity threshold for 4-regime dynamic fading and pre-emptive front-run exit against orderbook gap")
    enable_dynamic_reversal_curve: Optional[bool] = Field(default=None, description="Dynamically decay reversal threshold from 85% to 55% as time to expiry nears")
    twap_immutability_sniper_cents: Optional[float] = Field(default=None, ge=0.50, le=0.95, description="Silas TWAP Immutability Sniper ceiling in dollars ($0.50 - $0.95)")
    max_queue_depth_ahead: Optional[int] = Field(default=None, ge=10, le=5000, description="Vance Anti-Toxic Queue Depth Shield: max resting contracts ahead at limit bid")
    max_clob_spread_cents: Optional[float] = Field(default=None, ge=0.01, le=0.25, description="Vance Max CLOB Spread Corridor Cap: maximum allowable bid-ask spread in dollars")


class SavePresetRequest(BaseModel):
    preset_name: str
    description: Optional[str] = ""
    author: Optional[str] = "Operator"


class LoadPresetRequest(BaseModel):
    preset_id: str


class ImportPresetRequest(BaseModel):
    preset_json: Optional[str] = None
    preset_data: Optional[Dict[str, Any]] = None
    apply_immediately: bool = False


class WindowPinRequest(BaseModel):
    topmost: bool = True
    width: Optional[int] = None
    height: Optional[int] = None


class WindowResizeRequest(BaseModel):
    width: int
    height: int
    topmost: Optional[bool] = None


class RemoteToggleRequest(BaseModel):
    enabled: bool


# ---------------------------------------------------------------------------
# Cockpit & Static Routes
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def get_cockpit() -> str:
    """Serve ultra-lean Pocket Cockpit UI."""
    if TEMPLATE_PATH.exists():
        return TEMPLATE_PATH.read_text(encoding="utf-8")
    return "<h1>Pocket Cockpit template not found.</h1>"


@router.get("/static/qrcode.min.js")
async def get_qrcode_js():
    """Serve offline, zero-dependency QR code generator."""
    if QRCODE_PATH.exists():
        return Response(content=QRCODE_PATH.read_text(encoding="utf-8"), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="qrcode.min.js not found")


# ---------------------------------------------------------------------------
# Telemetry & State Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/state")
async def get_state(asset: Optional[str] = None) -> Dict[str, Any]:
    """Provide real-time telemetry to Pocket Cockpit."""
    engine = _require_engine()

    view_asset_enum = engine.active_asset
    if asset:
        try:
            view_asset_enum = CryptoAsset(asset.upper())
        except ValueError:
            pass

    view_cfg = get_asset_config(view_asset_enum)
    is_view_active = (view_asset_enum == engine.active_asset)

    if is_view_active:
        t_rem = engine.get_time_to_expiry()
        spot_dec = engine.current_btc_spot
        strike_dec = engine.target_strike
        target_ticker = engine.active_ticker
        target_time_str = engine.target_time_str
        time_window_str = engine.time_window_str
        best_yes_bid = engine.best_yes_bid
        best_yes_ask = engine.best_yes_ask
        best_no_bid = engine.best_no_bid
        best_no_ask = engine.best_no_ask
        ladder_ticker = engine.active_ticker
    else:
        m_info = engine.asset_markets.get(view_asset_enum.value, {})
        target_ticker = m_info.get("ticker", "")
        close_dt = m_info.get("close_dt")
        t_rem = engine.get_time_to_expiry(close_dt) if close_dt else 0.0
        strike_dec = m_info.get("target_strike", Decimal("0.00"))
        spot_dec = m_info.get("spot_price", Decimal("0.00"))
        target_time_str = m_info.get("target_time_str", "")
        time_window_str = m_info.get("time_window_str", "")
        best_yes_bid = m_info.get("best_yes_bid")
        best_yes_ask = m_info.get("best_yes_ask")
        best_no_bid = m_info.get("best_no_bid")
        best_no_ask = m_info.get("best_no_ask")
        ladder_ticker = target_ticker

    mins = int(t_rem // 60)
    secs = int(t_rem % 60)
    t_str = f"{mins:02d}:{secs:02d}" if t_rem > 0 else "00:00"

    if strike_dec > Decimal("0.00") and spot_dec > Decimal("0.00"):
        diff_dec = spot_dec - strike_dec
        diff_pct_dec = (diff_dec / strike_dec) * Decimal("100.0")
    else:
        diff_dec = Decimal("0.00")
        diff_pct_dec = Decimal("0.00")

    is_up = diff_dec >= Decimal("0.00")
    diff_sign = "+" if is_up else "-"
    diff_abs = abs(diff_dec)
    diff_pct_abs = abs(diff_pct_dec)

    diff_str = f"{diff_sign}{view_cfg.format_price(diff_abs)}"
    pct_decimals = 4 if diff_pct_abs < Decimal("0.01") else (3 if diff_pct_abs < Decimal("0.10") else 2)
    diff_pct_str = f"{diff_sign}{diff_pct_abs:.{pct_decimals}f}%"
    moneyness_diff_str = f"{diff_str} ({diff_pct_str})"

    dec = engine.last_decision
    playbook = dec.active_playbook if dec else "none"
    edge = dec.edge_pct if dec else 0.0
    ev = dec.ev_yes if (dec and dec.recommended_side == "yes") else (dec.ev_no if dec else 0.0)
    vpin = dec.vpin if dec else 0.0
    vpin_safe = dec.vpin_is_safe if dec else True
    rationale = dec.rationale if dec else "Monitoring microstructure order flow..."

    # Position info
    resting_count = len(engine.active_resting_orders)
    locked = engine.guardrails.is_cycle_locked(engine.active_ticker)
    has_pos = bool(engine.active_position and engine.active_position.get("size", 0) > 0)
    if has_pos:
        pos_data = engine.active_position or {}
        pos_side = str(pos_data.get("side", "yes")).upper()
        pos_size = int(pos_data.get("size", 1))
        entry_p = Decimal(str(pos_data.get("entry_price", "0.52")))
        cur_bid = engine.best_yes_bid if pos_side == "YES" else engine.best_no_bid
        if cur_bid is not None:
            pnl_dec = (cur_bid - entry_p) * Decimal(str(pos_size))
            sign = "+" if pnl_dec >= Decimal("0.00") else "-"
            tp_thresh = engine.bot.take_profit_price_threshold
            tp_diff = tp_thresh - cur_bid
            pos_str = f"HOLDING {pos_size} {pos_side} @ ${entry_p:.2f} (Bid: ${cur_bid:.2f} | {sign}${abs(pnl_dec):.2f})"
            if engine.bot.enable_take_profit_ceiling:
                if engine.bot.require_reversal_for_tp_ceiling:
                    pos_sub = f"TP Ceiling: ${tp_thresh:.2f} · Gated by {engine.bot.reverse_indicator_threshold*100:.0f}% Reversal"
                else:
                    pos_sub = f"TP Ceiling: ${tp_thresh:.2f} (Dist: ${tp_diff:.2f}) · Auto-Exit Active"
            elif engine.bot.enable_reverse_take_profit_roi:
                pos_sub = f"Holding · Reversal TP ({engine.bot.min_take_profit_roi*100:.0f}% @ {engine.bot.reverse_indicator_threshold*100:.0f}% Rev) Active"
            else:
                pos_sub = f"Holding to expiry · Auto-Exits Disabled"
        else:
            pos_str = f"HOLDING {pos_size} {pos_side} @ ${entry_p:.2f}"
            pos_sub = f"TP Ceiling: ${engine.bot.take_profit_price_threshold:.2f}"
    elif resting_count > 0:
        pos_str = f"MAKER RESTING ({resting_count} active)"
        pos_sub = f"Resting limit order at ${engine.bot.discount_limit_price:.2f}"
    elif locked:
        pos_str = "IN CYCLE TRADE"
        pos_sub = "1 cycle entry active"
    else:
        pos_str = "FLAT"
        pos_sub = "0 contracts active"

    bal = float(engine.total_balance_dollars) if engine.total_balance_dollars > 0 else float(engine.balance_dollars)
    shard2_bal = float(engine.shard2_balance_dollars) if engine.shard2_balance_dollars > 0 else bal

    ladder_book = engine.orderbook.get_book(ladder_ticker) if ladder_ticker else None
    ladder_yes = []
    ladder_no = []
    if ladder_book:
        max_q = max([float(q) for q in list(ladder_book.yes_book.values()) + list(ladder_book.no_book.values())] or [1000.0])
        ladder_yes = [
            {
                "side": "yes",
                "price_cents": f"{float(pr * 100):.1f}¢",
                "price_raw": float(pr),
                "contracts": int(qty),
                "total": f"${float(pr * qty):,.0f}",
                "depth_pct": min(100, max(8, int((float(qty) / max_q) * 100))),
            }
            for pr, qty in sorted(ladder_book.yes_book.items(), key=lambda x: x[0], reverse=True)[:8]
        ]
        ladder_no = [
            {
                "side": "no",
                "price_cents": f"{float(pr * 100):.1f}¢",
                "price_raw": float(pr),
                "contracts": int(qty),
                "total": f"${float(pr * qty):,.0f}",
                "depth_pct": min(100, max(8, int((float(qty) / max_q) * 100))),
            }
            for pr, qty in sorted(ladder_book.no_book.items(), key=lambda x: x[0], reverse=True)[:8]
        ]

    return {
        "armed": engine.is_armed,
        "execution_mode": "LIVE" if engine.is_live else "PAPER",
        "balance": bal,
        "shard2_balance": shard2_bal,
        "polymarket_balance": float(engine.polymarket_balance_dollars),
        "today_pnl": float(engine.today_pnl),
        "settled_cycles": engine.settled_cycles,
        "today_wins": engine.today_wins,
        "today_losses": engine.today_losses,
        "today_win_rate": round(engine.today_win_rate, 1),
        "consecutive_losses": engine.consecutive_losses,
        "max_consecutive_losses": engine.max_consecutive_losses,
        "active_asset": engine.active_asset.value,
        "active_asset_name": engine.active_cfg.name,
        "active_asset_symbol": engine.active_cfg.symbol,
        "view_asset": view_asset_enum.value,
        "arbitrage_radar": engine.arb_scanner.latest_radar_scan if hasattr(engine, 'arb_scanner') else {},
        "view_asset_name": view_cfg.name,
        "view_asset_symbol": view_cfg.symbol,
        "series_ticker": view_cfg.series_ticker_15m,
        "active_ticker": target_ticker,
        "time_remaining_str": t_str,
        "target_time_str": target_time_str,
        "time_window_str": time_window_str,
        "expiry_countdown_seconds": int(t_rem),
        "position_str": pos_str,
        "position_sub": pos_sub,
        "resting_orders_count": resting_count,
        "spot_price": float(spot_dec),
        "spot_price_str": view_cfg.format_price(spot_dec) if spot_dec > Decimal("0.00") else "$0.00",
        "target_strike": float(strike_dec),
        "target_strike_str": view_cfg.format_price(strike_dec) if strike_dec > Decimal("0.00") else "$0.00",
        "spot_diff": float(round(diff_dec, view_cfg.price_decimals)),
        "spot_diff_pct": float(round(diff_pct_dec, 3)),
        "spot_diff_str": diff_str,
        "spot_diff_pct_str": diff_pct_str,
        "moneyness_diff_str": moneyness_diff_str,
        "is_above_strike": is_up,
        "best_yes_bid": float(best_yes_bid) if best_yes_bid is not None else None,
        "best_yes_ask": float(best_yes_ask) if best_yes_ask is not None else None,
        "best_no_bid": float(best_no_bid) if best_no_bid is not None else None,
        "best_no_ask": float(best_no_ask) if best_no_ask is not None else None,
        "playbook": playbook,
        "p_up": float(dec.p_up) if dec else 0.50,
        "p_down": float(dec.p_down) if dec else 0.50,
        "p_wait": float(dec.p_wait) if dec else 0.00,
        "edge_pct": edge,
        "ev": ev,
        "vpin": vpin,
        "vpin_is_safe": vpin_safe,
        "rationale": rationale,
        "spot_source": engine.spot_source if engine else "Unknown",
        "brti_connected": engine.brti_connected if engine else False,
        "twap_60s": float(engine.twap_60s_price) if (engine and engine.twap_60s_price and is_view_active) else None,
        "twap_60s_str": view_cfg.format_price(engine.twap_60s_price) if (engine and engine.twap_60s_price and is_view_active) else None,
        "recent_reports": engine.recent_reports,
        "kalshi_ws_connected": engine.kalshi_ws_connected,
        "spot_connected": engine.spot_connected,
        "coinbase_connected": engine.coinbase_connected,
        "binance_connected": engine.binance_connected,
        "enable_take_profit_ceiling": engine.bot.enable_take_profit_ceiling,
        "take_profit_price_threshold": float(engine.bot.take_profit_price_threshold),
        "require_reversal_for_tp_ceiling": engine.bot.require_reversal_for_tp_ceiling,
        "enable_reverse_take_profit_roi": engine.bot.enable_reverse_take_profit_roi,
        "reverse_indicator_threshold": float(engine.bot.reverse_indicator_threshold) * 100.0,
        "min_take_profit_roi": float(engine.bot.min_take_profit_roi) * 100.0,
        "has_active_position": has_pos,
        "asset_mode": engine.asset_mode if engine else "single",
        "active_assets": [a.value for a in engine.active_assets] if engine else ["BTC"],
        "max_concurrent_positions": engine.max_concurrent_positions if engine else 3,
        "open_positions_count": len(engine.active_positions) if engine else 0,
        "portfolio_positions": list(engine.active_positions.values()) if engine else [],
        "asset_markets": {
            k: {
                kk: float(vv) if isinstance(vv, Decimal) else (vv.isoformat() if isinstance(vv, datetime) else vv)
                for kk, vv in v.items()
            }
            for k, v in engine.asset_markets.items()
        } if engine else {},
        "remote_control": engine.remote_manager.get_info(port=8001) if hasattr(engine, "remote_manager") else {},
        "parameters": engine.get_parameters(),
        "orderbook_ladder": ladder_yes + ladder_no,
    }


# ---------------------------------------------------------------------------
# Asset Selection & Supported Assets
# ---------------------------------------------------------------------------

@router.get("/api/assets")
async def get_supported_assets() -> Dict[str, Any]:
    """Return supported cryptocurrency assets and live CF Benchmarks prices for Standalone Bot."""
    engine = _require_engine()
    cf_data = engine.cf_sync.get_all_state() if engine.cf_sync else {}
    assets_list = []
    active_set = set(engine.active_assets) if engine else {CryptoAsset.BTC}
    inc_mgr = get_incubator_manager()

    for a in CryptoAsset:
        cfg = get_asset_config(a)
        quote = cf_data.get(a.value, {})
        m_info = engine.asset_markets.get(a.value, {})
        p_val = quote.get("price", 0.0)
        if not p_val or float(p_val) <= 0:
            p_val = float(m_info.get("spot_price", 0.0))
        assets_list.append({
            "id": a.value,
            "name": cfg.name,
            "series_15m": cfg.series_ticker_15m,
            "cf_index_id": cfg.cf_index_id,
            "price_decimals": cfg.price_decimals,
            "strike_step": float(cfg.strike_step),
            "min_spot_diff": float(cfg.min_spot_diff),
            "price": float(p_val),
            "twap_60s": float(quote.get("twap_60s", 0.0)) if quote.get("twap_60s") else None,
            "is_active": (a in active_set),
            "current_ticker": m_info.get("ticker", ""),
            "is_incubator_locked": inc_mgr.is_locked(a),
            "incubator_lock_reason": inc_mgr.get_lock_reason(a),
        })
    return {
        "active_asset": "ALL" if engine.asset_mode == "all" else engine.active_asset.value,
        "active_assets": [a.value for a in engine.active_assets],
        "asset_mode": engine.asset_mode,
        "max_concurrent_positions": engine.max_concurrent_positions,
        "open_positions_count": len(engine.active_positions),
        "assets": assets_list,
    }


@router.post("/api/assets/select")
async def select_active_asset(req: AssetSelectRequest) -> Dict[str, Any]:
    """Switch active asset(s) on Standalone Bot (single, custom basket list, or 'ALL')."""
    engine = _require_engine()
    inc_mgr = get_incubator_manager()

    # Handle explicit list of assets
    if req.assets is not None and len(req.assets) > 0:
        valid_assets: List[CryptoAsset] = []
        quarantined_rejected: List[str] = []
        for item in req.assets:
            item_str = str(item).upper().strip()
            if item_str == "ALL":
                engine.set_asset("ALL")
                return {
                    "status": "SUCCESS",
                    "active_asset": "ALL",
                    "active_assets": [a.value for a in engine.active_assets],
                    "active_asset_name": "All Assets (Omnichannel Basket)",
                    "asset_mode": "all",
                    "series_ticker": "MULTI",
                    "max_concurrent_positions": engine.max_concurrent_positions,
                    "quarantined_incubator_assets": [a.value for a in CryptoAsset if inc_mgr.is_locked(a)] if engine.is_live else [],
                }
            try:
                c_asset = CryptoAsset(item_str)
                if engine.is_live and inc_mgr.is_locked(c_asset):
                    quarantined_rejected.append(c_asset.value)
                    continue
                if c_asset not in valid_assets:
                    valid_assets.append(c_asset)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid asset: '{item}'. Supported assets: {[a.value for a in CryptoAsset]}"
                )
        if not valid_assets:
            if quarantined_rejected:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"[INCUBATOR QUARANTINE] Requested asset(s) {quarantined_rejected} are locked in Lane 2 Incubator: "
                        f"{inc_mgr.get_lock_reason(quarantined_rejected[0])}. Live selection prohibited until certified."
                    )
                )
            raise HTTPException(status_code=400, detail="At least 1 valid asset must be provided")
        engine.set_asset(valid_assets)
        return {
            "status": "SUCCESS",
            "active_asset": engine.active_asset.value,
            "active_assets": [a.value for a in engine.active_assets],
            "active_asset_name": "All Assets (Omnichannel Basket)" if engine.asset_mode == "all" else (
                f"Basket ({', '.join(a.value for a in engine.active_assets)})" if engine.asset_mode == "basket" else engine.active_cfg.name
            ),
            "asset_mode": engine.asset_mode,
            "series_ticker": "MULTI" if engine.asset_mode != "single" else engine.active_cfg.series_ticker_15m,
            "max_concurrent_positions": engine.max_concurrent_positions,
            "quarantined_incubator_assets": quarantined_rejected,
        }

    # Fallback to single asset string
    if not req.asset:
        raise HTTPException(status_code=400, detail="Must provide 'asset' or 'assets'")

    asset_str = req.asset.upper().strip()
    if asset_str == "ALL":
        engine.set_asset("ALL")
        return {
            "status": "SUCCESS",
            "active_asset": "ALL",
            "active_assets": [a.value for a in engine.active_assets],
            "active_asset_name": "All Assets (Omnichannel Basket)",
            "asset_mode": "all",
            "series_ticker": "MULTI",
            "max_concurrent_positions": engine.max_concurrent_positions,
            "quarantined_incubator_assets": [a.value for a in CryptoAsset if inc_mgr.is_locked(a)] if engine.is_live else [],
        }
    try:
        new_asset = CryptoAsset(asset_str)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid asset: '{req.asset}'. Supported assets: {[a.value for a in CryptoAsset]} or 'ALL'"
        )

    if engine.is_live and inc_mgr.is_locked(new_asset):
        raise HTTPException(
            status_code=403,
            detail=(
                f"[INCUBATOR QUARANTINE] {new_asset.value} is quarantined in Lane 2 Incubator: "
                f"{inc_mgr.get_lock_reason(new_asset)}. Live selection is locked until certification."
            )
        )

    engine.set_asset(new_asset)
    return {
        "status": "SUCCESS",
        "active_asset": engine.active_asset.value,
        "active_assets": [a.value for a in engine.active_assets],
        "active_asset_name": engine.active_cfg.name,
        "asset_mode": engine.asset_mode,
        "series_ticker": engine.active_cfg.series_ticker_15m,
        "max_concurrent_positions": engine.max_concurrent_positions,
    }


# ---------------------------------------------------------------------------
# Agent POE & Incubator Status
# ---------------------------------------------------------------------------

@router.get("/api/poe/scorecards")
async def get_poe_scorecards() -> Dict[str, Any]:
    """Agent POE: Return empirical parameter scorecards across all evaluated and settled cycles."""
    engine = _require_engine()
    scorecards = engine.poe_recorder.compute_parameter_scorecards()
    cards_dict = {}
    for name, sc in scorecards.items():
        cards_dict[name] = {
            "parameter_name": sc.parameter_name,
            "current_threshold": sc.current_threshold,
            "total_evaluations": sc.total_evaluations,
            "veto_count": sc.veto_count,
            "quadrant_3_starved": sc.quadrant_3_starved,
            "quadrant_4_shielded": sc.quadrant_4_shielded,
            "vps_score_pct": sc.vps_score_pct,
            "asr_score_pct": sc.asr_score_pct,
            "dollar_contribution": float(sc.dollar_contribution),
            "fisher_p_value": sc.fisher_p_value,
            "status": sc.status,
            "evidence_summary": sc.evidence_summary,
        }
    settled = [r for r in engine.poe_recorder._records.values() if r.quadrant is not None]
    return {
        "status": "SUCCESS",
        "total_records": len(engine.poe_recorder._records),
        "settled_records": len(settled),
        "unsettled_records": len(engine.poe_recorder.get_unsettled_records()),
        "scorecards": cards_dict,
    }


@router.get("/api/poe/report")
async def get_poe_report() -> Dict[str, Any]:
    """Agent POE: Generate complete unvarnished empirical ground truth audit report."""
    engine = _require_engine()
    report_md = engine.poe_recorder.generate_poe_audit_report()
    return {
        "status": "SUCCESS",
        "report_markdown": report_md,
    }


@router.get("/api/incubator/status")
async def get_incubator_status() -> Dict[str, Any]:
    """Return live status of Lane 2 Incubator assets and auto-release certification progress."""
    inc_mgr = get_incubator_manager()
    return {
        "status": "SUCCESS",
        "incubator_assets": inc_mgr.get_status(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Bot Arm, Disarm, Panic, Arbitrage
# ---------------------------------------------------------------------------

@router.post("/api/bot/arm")
async def arm_bot() -> Dict[str, Any]:
    """Arm the bot for live execution."""
    engine = _require_engine()
    engine.is_armed = True
    engine.consecutive_losses = 0
    engine._persist_parameters()
    logger.info("🟢 [BOT ARMED] Live order execution activated by user. Loss streak reset.")
    return {"status": "ARMED", "armed": True, "consecutive_losses": 0}


@router.post("/api/arbitrage/toggle")
async def toggle_arbitrage() -> Dict[str, Any]:
    """Arbitrage scanner is permanently stopped by operator directive."""
    engine = _require_engine()
    if hasattr(engine, 'arb_scanner'):
        engine.arb_scanner.stop()
    logger.info("🛑 [ARBITRAGE RADAR] Arbitrage scanner remains permanently STOPPED by operator directive.")
    return {"status": "SUCCESS", "active": False, "message": "Arbitrage scanner is stopped by operator directive."}


@router.post("/api/bot/disarm")
async def disarm_bot() -> Dict[str, Any]:
    """Disarm the bot into standby mode."""
    engine = _require_engine()
    engine.is_armed = False
    engine._persist_parameters()
    logger.info("⏸️ [BOT DISARMED] Standby mode activated by user.")
    return {"status": "DISARMED", "armed": False}


@router.post("/api/bot/panic")
async def panic_halt() -> Dict[str, Any]:
    """Emergency halt: disarm bot and cancel all resting orders on exchange."""
    engine = _require_engine()
    cancelled = await engine.panic_cancel_all()
    logger.warning("🛑 [PANIC TRIGGERED] Bot disarmed and %d order(s) cancelled.", cancelled)
    return {"status": "PANIC_EXECUTED", "cancelled_orders": cancelled, "armed": False}


# ---------------------------------------------------------------------------
# Bot Parameters & Order Sweeping
# ---------------------------------------------------------------------------

@router.get("/api/bot/parameters")
async def get_bot_parameters(asset: Optional[str] = None) -> Dict[str, Any]:
    """Return live strategy parameters and guardrail thresholds for a given asset or active asset."""
    engine = _require_engine()
    return engine.get_parameters(asset=asset)


@router.post("/api/bot/parameters")
async def update_bot_parameters(req: ParametersUpdateRequest) -> Dict[str, Any]:
    """Dynamically update strategy parameters and guardrail caps for a specific asset (or active asset)."""
    engine = _require_engine()
    payload = req.model_dump(exclude_none=True)
    target_asset = payload.pop("asset", None)
    res = engine.update_parameters(asset=target_asset, **payload)
    logger.info("⚙️ [PARAMETERS UPDATED] Asset %s configuration: %s", target_asset or engine.active_asset.value, res)
    return {"status": "SUCCESS", "parameters": res}


@router.post("/api/bot/sweep-orders")
async def sweep_orders(force: bool = False) -> Dict[str, Any]:
    """Manually sweep and cancel all resting orders on finished or non-active events."""
    engine = _require_engine()
    cancelled = await engine.sweep_old_orders(keep_ticker=engine.active_ticker, force_all=force)
    t_rem = engine.get_time_to_expiry()
    logger.info("🧹 [MANUAL SWEEP] Cancelled %d order(s) for finished/expired events.", cancelled)
    return {
        "status": "SWEEP_COMPLETE",
        "cancelled_orders": cancelled,
        "active_ticker": engine.active_ticker,
        "time_to_expiry_s": round(t_rem, 1),
    }


# ---------------------------------------------------------------------------
# Preset Vault & Configuration Lifecycle Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/bot/presets")
async def get_bot_presets() -> Dict[str, Any]:
    """List all presets in the vault and return active preset metadata."""
    pm = get_preset_manager()
    return {
        "status": "SUCCESS",
        "presets": pm.list_presets(),
        "active_preset": pm.get_active_preset_metadata(),
    }


@router.post("/api/bot/presets/save")
async def save_bot_preset(req: SavePresetRequest) -> Dict[str, Any]:
    """Snapshot current live parameters into a new preset in the vault."""
    pm = get_preset_manager()
    success, msg, data = pm.save_preset(
        preset_name=req.preset_name,
        description=req.description or "",
        author=req.author or "Operator",
    )
    if not success:
        raise HTTPException(status_code=422, detail=msg)
    return {"status": "SUCCESS", "message": msg, "preset": data}


@router.post("/api/bot/presets/load")
async def load_bot_preset(req: LoadPresetRequest) -> Dict[str, Any]:
    """Atomically load and hot-swap parameters from a preset into the engine."""
    engine = _require_engine()
    pm = get_preset_manager()
    success, msg, data = pm.load_preset(req.preset_id)
    if not success:
        raise HTTPException(status_code=422, detail=msg)
    engine._load_persisted_parameters()
    engine._apply_asset_profile(engine.active_asset)
    logger.info("⚡ [HOT-SWAP APPLIED] Loaded preset '%s' into Standalone Engine.", req.preset_id)
    return {"status": "SUCCESS", "message": msg, "active_preset": pm.get_active_preset_metadata()}


@router.post("/api/bot/presets/unload")
async def unload_bot_preset() -> Dict[str, Any]:
    """Revert configuration back to the Council Certified Baseline."""
    engine = _require_engine()
    pm = get_preset_manager()
    success, msg, data = pm.unload_preset()
    if not success:
        raise HTTPException(status_code=422, detail=msg)
    engine._load_persisted_parameters()
    engine._apply_asset_profile(engine.active_asset)
    logger.info("🔄 [PRESET REVERT] Reset Standalone Engine to Council Baseline.")
    return {"status": "SUCCESS", "message": msg, "active_preset": pm.get_active_preset_metadata()}


@router.post("/api/bot/presets/upload")
async def upload_bot_preset(req: ImportPresetRequest) -> Dict[str, Any]:
    """Validate and import an uploaded preset JSON into the vault."""
    pm = get_preset_manager()
    raw_json = req.preset_json
    if not raw_json and req.preset_data:
        raw_json = json.dumps(req.preset_data)
    if not raw_json:
        raise HTTPException(status_code=400, detail="Missing preset_json or preset_data in request body")

    success, msg, data = pm.import_preset_json(raw_json)
    if not success:
        raise HTTPException(status_code=422, detail=msg)

    if _get_engine is not None:
        engine = _get_engine()
        if req.apply_immediately and engine:
            pm.load_preset(data["preset_id"])
            engine._load_persisted_parameters()
            engine._apply_asset_profile(engine.active_asset)

    return {"status": "SUCCESS", "message": msg, "preset": data}


@router.get("/api/bot/presets/export/{preset_id}")
async def export_bot_preset(preset_id: str) -> Response:
    """Export a preset as a downloadable JSON file."""
    pm = get_preset_manager()
    data = pm.export_preset(preset_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")
    content = json.dumps(data, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{preset_id}.json"'},
    )


@router.delete("/api/bot/presets/{preset_id}")
async def delete_bot_preset(preset_id: str) -> Dict[str, Any]:
    """Delete a custom preset from the vault."""
    pm = get_preset_manager()
    success, msg = pm.delete_preset(preset_id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "SUCCESS", "message": msg}


# ---------------------------------------------------------------------------
# Win32 Floating Widget & Window Management
# ---------------------------------------------------------------------------

@router.get("/api/window/status")
async def get_window_status() -> Dict[str, Any]:
    """Check if Cockpit window is found and pinned as Always on Top."""
    windows = _get_sb().find_cockpit_windows()
    if not windows:
        return {"available": False, "is_topmost": False, "windows_count": 0}
    hwnd, title = windows[0]
    topmost = _get_sb().is_always_on_top(hwnd)
    return {
        "available": True,
        "is_topmost": topmost,
        "hwnd": hwnd,
        "title": title,
        "windows_count": len(windows),
    }


@router.post("/api/window/pin")
async def pin_window(req: WindowPinRequest) -> Dict[str, Any]:
    """Toggle Always on Top (HWND_TOPMOST) for Cockpit window."""
    windows = _get_sb().find_cockpit_windows()
    if not windows:
        raise HTTPException(status_code=404, detail="No Pocket Cockpit window found")
    results = []
    for hwnd, title in windows:
        ok = _get_sb().set_always_on_top(hwnd, req.topmost)
        if req.width and req.height:
            _get_sb().resize_window(hwnd, req.width, req.height, topmost=req.topmost)
        results.append({"hwnd": hwnd, "title": title, "topmost": req.topmost, "success": ok})
    return {"status": "SUCCESS", "topmost": req.topmost, "windows": results}


@router.post("/api/window/resize")
async def resize_cockpit_window(req: WindowResizeRequest) -> Dict[str, Any]:
    """Resize Cockpit window (e.g. for Minimized widget or Expanded mode)."""
    windows = _get_sb().find_cockpit_windows()
    if not windows:
        raise HTTPException(status_code=404, detail="No Pocket Cockpit window found")
    results = []
    for hwnd, title in windows:
        ok = _get_sb().resize_window(hwnd, req.width, req.height, topmost=req.topmost)
        results.append({"hwnd": hwnd, "success": ok})
    return {"status": "SUCCESS", "width": req.width, "height": req.height, "windows": results}


@router.post("/api/window/launch-widget")
async def spawn_widget_window() -> Dict[str, Any]:
    """Launch Microsoft Edge or Chrome in chromeless app mode pinned as a floating desktop widget."""
    port = 8001
    ok = _get_sb().launch_widget_window(port=port, view="minimized")
    return {"status": "LAUNCHED" if ok else "FAILED", "success": ok}



# ---------------------------------------------------------------------------
# Remote Control Pairing Endpoints (Antigravity Style)
# ---------------------------------------------------------------------------

@router.get("/api/remote/info")
async def get_remote_info() -> Dict[str, Any]:
    """Get remote pairing state, device name, LAN IP, Tailscale IP, pairing URLs."""
    engine = _require_engine()
    if not hasattr(engine, "remote_manager"):
        raise HTTPException(status_code=503, detail="Remote control manager not ready")
    return engine.remote_manager.get_info(port=8001)


@router.post("/api/remote/toggle")
async def toggle_remote_control(req: RemoteToggleRequest) -> Dict[str, Any]:
    """Enable or disable remote control access."""
    engine = _require_engine()
    if not hasattr(engine, "remote_manager"):
        raise HTTPException(status_code=503, detail="Remote control manager not ready")
    engine.remote_manager.toggle(req.enabled)
    return {"status": "SUCCESS", "enabled": engine.remote_manager.enabled}


@router.post("/api/remote/regenerate")
async def regenerate_remote_token() -> Dict[str, Any]:
    """Regenerate pairing token, immediately revoking existing remote pairings."""
    engine = _require_engine()
    if not hasattr(engine, "remote_manager"):
        raise HTTPException(status_code=503, detail="Remote control manager not ready")
    new_token = engine.remote_manager.regenerate_token()
    info = engine.remote_manager.get_info(port=8001)
    return {"status": "SUCCESS", "token": new_token, "info": info}


@router.post("/api/remote/revoke")
async def revoke_remote_token() -> Dict[str, Any]:
    """Revoke pairing token and disable remote control access."""
    engine = _require_engine()
    if not hasattr(engine, "remote_manager"):
        raise HTTPException(status_code=503, detail="Remote control manager not ready")
    engine.remote_manager.revoke_token()
    return {"status": "SUCCESS", "enabled": False}

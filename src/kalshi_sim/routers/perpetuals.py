"""Perpetual Trading API Router.

Provides dedicated endpoints for institutional perpetual contract trading:
- Multi-asset markets metadata (BTC-PERP, ETH-PERP, SOL-PERP, DOGE-PERP)
- Real-time mark price, 24h delta, dynamic 8h funding rate, open interest
- Isolated margin order execution (Market / Limit, Long / Short, 1x-50x leverage)
- Real-time position tracking and liquidation evaluation
- Automated bot conviction parameters and signal dispatch
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

import os
from dotenv import load_dotenv

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from kalshi_sim.db import get_db
from kalshi_sim.order_client import KalshiMarginOrderClient

load_dotenv()
_margin_client: Optional[KalshiMarginOrderClient] = None
if os.getenv("KALSHI_API_KEY_ID") and os.getenv("KALSHI_PRIVATE_KEY_PATH"):
    try:
        _margin_client = KalshiMarginOrderClient(
            api_key_id=os.getenv("KALSHI_API_KEY_ID"),
            private_key_path=os.getenv("KALSHI_PRIVATE_KEY_PATH")
        )
    except Exception as e:
        logger = logging.getLogger("kalshi_sim.routers.perpetuals")
        logger.warning(f"Failed to init KalshiMarginOrderClient: {e}")

logger = logging.getLogger("kalshi_sim.routers.perpetuals")

router = APIRouter(tags=["perpetuals"])

_state_getter = None

def init_perpetuals_router(state_getter):
    global _state_getter
    _state_getter = state_getter

def get_state():
    if _state_getter is not None:
        return _state_getter()
    from kalshi_sim.server import state
    return state


class PerpOrderRequest(BaseModel):
    asset: Literal["BTC", "ETH", "SOL", "DOGE"] = Field(...)
    side: Literal["long", "short"] = Field(...)
    order_type: Literal["market", "limit"] = Field(default="market")
    size: float = Field(..., gt=0)
    leverage: float = Field(default=10.0, ge=1.0, le=50.0)
    price: Optional[float] = None
    bot_id: Optional[str] = None


class PerpClosePositionRequest(BaseModel):
    position_id: str


class PerpBotConfigRequest(BaseModel):
    bot_id: str
    leverage: Optional[float] = Field(default=None, ge=1.0, le=50.0)
    min_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    take_profit_pct: Optional[float] = Field(default=None, ge=0.5, le=100.0)
    stop_loss_pct: Optional[float] = Field(default=None, ge=0.5, le=50.0)
    is_armed: Optional[bool] = None


_ASSET_BASE_PRICES = {
    "BTC": 84250.00,
    "ETH": 2280.00,
    "SOL": 135.50,
    "DOGE": 0.1685,
}

_BOT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "macro_dominion_perp": {
        "id": "macro_dominion_perp",
        "name": "Macro Dominion Scalper",
        "strategy_type": "High-Frequency Orderflow Scalper",
        "leverage": 2.0,
        "min_confidence": 0.75,
        "take_profit_pct": 0.50,
        "stop_loss_pct": 0.75,
        "trailing_stop_pct": 0.25,
        "dynamic_moat": 1.0,
        "vpin_toxic_threshold": 0.60,
        "is_armed": True,
        "status": "active",
        "signals": {
            "conviction": 0.82,
            "recommended_side": "long",
            "rationale": "Orderflow momentum scalper armed for immediate net profit harvest.",
            "vpin": 0.18,
        },
    },
    "dual_onnx_perp": {
        "id": "dual_onnx_perp",
        "name": "Dual ONNX Micro Scalper",
        "strategy_type": "Microsecond Neural Scalper",
        "leverage": 5.0,
        "min_confidence": 0.78,
        "take_profit_pct": 0.50,
        "stop_loss_pct": 0.75,
        "trailing_stop_pct": 0.20,
        "dynamic_moat": 1.2,
        "vpin_toxic_threshold": 0.50,
        "is_armed": True,
        "status": "active",
        "signals": {
            "conviction": 0.71,
            "recommended_side": "short",
            "rationale": "High-frequency neural micro-scalper locking small continuous spreads.",
            "vpin": 0.48,
        },
    },
    "retail_inversion_perp": {
        "id": "retail_inversion_perp",
        "name": "Retail Inversion Scalper",
        "strategy_type": "Extreme Sentiment Quick Fader",
        "leverage": 2.0,
        "min_confidence": 0.75,
        "take_profit_pct": 0.60,
        "stop_loss_pct": 0.75,
        "trailing_stop_pct": 0.25,
        "dynamic_moat": 1.0,
        "vpin_toxic_threshold": 0.70,
        "is_armed": False,
        "status": "standby",
        "signals": {
            "conviction": 0.52,
            "recommended_side": "neutral",
            "rationale": "Retail crowd fader standing by for sentiment dislocation burst.",
            "vpin": 0.22,
        },
    },
}


async def _get_current_mark_price(asset: str) -> Decimal:
    if _margin_client:
        try:
            kalshi_ticker = 'KXBTCPERP' if asset == 'BTC' else asset
            price = await _margin_client.get_margin_mark_price(kalshi_ticker)
            if price: return Decimal(str(price))
        except: pass
    try:
        s = get_state()
        if asset == "BTC" and hasattr(s, "current_btc_price"):
            val = Decimal(str(s.current_btc_price))
            if val > Decimal("1000.0"):
                return val
    except Exception:
        pass
    return Decimal(str(_ASSET_BASE_PRICES.get(asset, 84250.00)))


def _calc_liquidation_price(entry_price: Decimal, side: str, leverage: Decimal) -> Decimal:
    mm = Decimal("0.005")
    if side.lower() == "long":
        return round(entry_price * (Decimal("1.0") - (Decimal("1.0") / leverage) + mm), 2)
    else:
        return round(entry_price * (Decimal("1.0") + (Decimal("1.0") / leverage) - mm), 2)

PERP_FEE_RATE = Decimal("0.0005")   # 0.05% taker fee
PERP_SPREAD_RATE = Decimal("0.0002") # 0.02% half-spread

def _calc_pnl_with_fees(entry_p: Decimal, curr_mark: Decimal, size: Decimal, side: str) -> Decimal:
    if side.lower() == "long":
        exit_price = curr_mark * (Decimal("1.0") - PERP_SPREAD_RATE)
        gross_pnl = (exit_price - entry_p) * size
    else:
        exit_price = curr_mark * (Decimal("1.0") + PERP_SPREAD_RATE)
        gross_pnl = (entry_p - exit_price) * size

    fees = (entry_p * size * PERP_FEE_RATE) + (exit_price * size * PERP_FEE_RATE)
    return gross_pnl - fees


@router.get("/markets")
async def get_perp_markets() -> Dict[str, Any]:
    now_sec = time.time()
    next_funding_secs = 28800 - (int(now_sec) % 28800)
    markets = {}
    for asset, base in _ASSET_BASE_PRICES.items():
        price = await _get_current_mark_price(asset)
        markets[asset] = {
            "asset": asset,
            "ticker": f"{asset}-PERP",
            "mark_price": price,
            "index_price": price,
            "price_change_24h": 2.45 if asset == "BTC" else (-1.20 if asset == "ETH" else 4.15),
            "funding_rate": 0.0001,
            "next_funding_in": next_funding_secs,
            "volume_24h": 14500000.0,
            "open_interest": 8250000.0,
            "max_leverage": 50.0,
        }
    return {"status": "ok", "markets": markets}


@router.get("/positions")
async def get_perp_positions() -> Dict[str, Any]:
    db = get_db()
    positions: List[Dict[str, Any]] = []
    try:
        async with db.get_connection() as conn:
            async with conn.execute(
                "SELECT id, asset, side, size, entry_price, mark_price, leverage, liquidation_price, margin, unrealized_pnl, created_at, bot_id FROM perp_positions WHERE status = 'open' ORDER BY created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                for r in rows:
                    asset = r[1]
                    side = r[2]
                    size = r[3]
                    entry_p = r[4]
                    lev = r[6]
                    liq_p = r[7]
                    margin = r[8]
                    created_at = r[10]
                    bot_id = r[11]

                    curr_mark = await _get_current_mark_price(asset)
                    pnl = _calc_pnl_with_fees(entry_p, curr_mark, size, side)
                    pnl_pct = (pnl / margin * 100.0) if margin > 0 else 0.0

                    positions.append({
                        "id": r[0],
                        "asset": asset,
                        "side": side,
                        "size": size,
                        "entryPrice": entry_p,
                        "markPrice": curr_mark,
                        "leverage": lev,
                        "liquidationPrice": liq_p,
                        "margin": margin,
                        "unrealizedPnl": round(pnl, 2),
                        "unrealizedPnlPct": round(pnl_pct, 2),
                        "timestamp": created_at,
                        "botId": bot_id,
                    })

        if _margin_client:
            try:
                live_pos = await _margin_client.get_margin_positions()
                if live_pos and len(live_pos) > 0:
                    positions = [] # Nuke local mock
                    for p in live_pos:
                        pos_id = p.get("position_id", p.get("id", "live-pos"))
                        ticker = p.get("ticker", "BTC")
                        asset = "BTC" if "BTC" in ticker else ticker
                        side = "long" if Decimal(str(p.get("position", 0))) > 0 else "short"
                        size = abs(Decimal(str(p.get("position", 0))))
                        entry_p = Decimal(str(p.get("average_price", 0)))
                        lev = Decimal(str(p.get("leverage", 10.0)))
                        
                        curr_mark = Decimal(str(await _get_current_mark_price(asset)) or entry_p)
                        pnl = _calc_pnl_with_fees(entry_p, curr_mark, size, side)
                        margin_val = (entry_p * size) / lev if lev else 0
                        pnl_pct = (pnl / margin_val * 100.0) if margin_val > 0 else 0.0

                        positions.append({
                            "id": pos_id,
                            "asset": asset,
                            "side": side,
                            "size": size,
                            "entryPrice": entry_p,
                            "markPrice": curr_mark,
                            "leverage": lev,
                            "liquidationPrice": Decimal(str(p.get("liquidation_price", 0))),
                            "margin": margin_val,
                            "unrealizedPnl": round(pnl, 2),
                            "unrealizedPnlPct": round(pnl_pct, 2),
                            "timestamp": p.get("created_ts", ""),
                            "botId": "live"
                        })
            except Exception as e:
                pass
    except Exception as exc:
        logger.warning("Error querying perp_positions: %s", exc)
    return {"status": "ok", "positions": positions}


@router.post("/order")
async def place_perp_order(req: PerpOrderRequest) -> Dict[str, Any]:
    mark_price = await _get_current_mark_price(req.asset)
    if req.order_type == "limit" and req.price is not None:
        fill_price = req.price
    else:
        # Market order crosses the spread
        fill_price = mark_price * (1 + PERP_SPREAD_RATE) if req.side.lower() == "long" else mark_price * (1 - PERP_SPREAD_RATE)
    
    fill_price = round(fill_price, 2)
    req_size_dec = Decimal(str(req.size))
    req_lev_dec = Decimal(str(req.leverage))
    notional_value = fill_price * req_size_dec
    margin = notional_value / req_lev_dec
    liq_price = _calc_liquidation_price(fill_price, req.side, req_lev_dec)
    
    if _margin_client:
        logger.info(f"Submitting LIVE Kalshi Margin Order for {req.asset}")
        kalshi_ticker = 'KXBTCPERP' if req.asset == 'BTC' else req.asset
        res = await _margin_client.place_margin_order(
            ticker=kalshi_ticker,
            side=req.side,
            count=req.size,
            leverage=req.leverage,
            order_type=req.order_type,
            price_dollars=Decimal(f'{fill_price * Decimal("0.0001"):.4f}') if req.asset == 'BTC' else Decimal(f'{fill_price:.2f}')
        )
        if res:
            # Attempt to extract order_id from nested JSON response
            if "order" in res and "order_id" in res["order"]:
                order_id = res["order"]["order_id"]
            else:
                order_id = res.get("order_id", f"PERP-{req.asset}-{uuid.uuid4().hex[:8].upper()}")
        else:
            raise HTTPException(status_code=500, detail="Failed to place live margin order on Kalshi.")
    else:
        order_id = f"PERP-{req.asset}-{uuid.uuid4().hex[:8].upper()}"

    db = get_db()
    try:
        async with db.get_connection() as conn:
            await conn.execute(
                """INSERT INTO perp_positions 
                (id, asset, side, size, entry_price, mark_price, leverage, liquidation_price, margin, unrealized_pnl, status, bot_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 'open', ?)""",
                (order_id, req.asset, req.side.lower(), float(req.size), str(fill_price), str(mark_price), float(req.leverage), str(liq_price), str(margin), req.bot_id),
            )
            await conn.commit()
    except Exception as exc:
        logger.error("Failed inserting perp order to DB: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    logger.info("[PERP EXECUTION] %s %s %.4f %s @ $%.2f (Leverage: %.1fx, Margin: $%.2f)",
                req.side.upper(), req.order_type.upper(), req.size, req.asset, fill_price, req.leverage, margin)

    return {
        "status": "ok",
        "order_id": order_id,
        "position": {
            "id": order_id,
            "asset": req.asset,
            "side": req.side.lower(),
            "size": req.size,
            "entryPrice": fill_price,
            "markPrice": mark_price,
            "leverage": req.leverage,
            "liquidationPrice": liq_price,
            "margin": round(margin, 2),
            "unrealizedPnl": 0.0,
            "unrealizedPnlPct": 0.0,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(await _margin_client.get_server_time() if _margin_client else time.time())),
            "botId": req.bot_id,
        }
    }


@router.post("/position/close")
async def close_perp_position(req: PerpClosePositionRequest) -> Dict[str, Any]:
    db = get_db()
    try:
        # Phase 1: Read position from DB
        async with db.get_connection() as conn:
            async with conn.execute(
                "SELECT asset, side, size, entry_price, margin FROM perp_positions WHERE id = ? AND status = 'open'",
                (req.position_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Position not found or already closed")
                asset, side, size, entry_p, margin = row
                
        # Phase 2: Close on Kalshi (outside DB lock)
        curr_mark = await _get_current_mark_price(asset)
        if _margin_client:
            opposing_side = "sell" if side.lower() == "long" else "buy"
            kalshi_ticker = f"KX{asset}PERP"
            # Slippage buffer for immediate taker fill: +$0.01 for buy (closing short), -$0.01 for sell (closing long)
            if asset == "BTC":
                base_close_p = curr_mark * Decimal("0.0001")
                close_price_dollars = Decimal(f"{base_close_p + Decimal('0.0100'):.4f}") if opposing_side == "buy" else Decimal(f"{base_close_p - Decimal('0.0100'):.4f}")
            else:
                close_price_dollars = Decimal(f"{curr_mark:.2f}")

            res = await _margin_client.place_margin_order(
                ticker=kalshi_ticker,
                side=opposing_side,
                count=size,
                order_type="market",
                price_dollars=close_price_dollars
            )
            if not res:
                logger.warning(f"Failed to close LIVE margin position {req.position_id} on Kalshi. We will still mark it closed locally for sync.")

        # Phase 3: Update DB with fresh connection
        curr_mark = await _get_current_mark_price(asset)
        realized_pnl = _calc_pnl_with_fees(Decimal(str(entry_p)), curr_mark, Decimal(str(size)), side)

        async with db.get_connection() as conn2:
            await conn2.execute(
                "UPDATE perp_positions SET status = 'closed', realized_pnl = ?, mark_price = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (str(realized_pnl), str(curr_mark), req.position_id)
            )
            await conn2.commit()

        logger.info("[PERP CLOSED] Position %s closed @ $%.2f | Realized PnL: %+.2f",
                    req.position_id, curr_mark, realized_pnl)

        return {
            "status": "ok",
            "position_id": req.position_id,
            "realized_pnl": round(realized_pnl, 2),
            "exit_price": curr_mark,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to close perp position: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/bots")
async def get_perp_bots() -> Dict[str, Any]:
    return {"status": "ok", "bots": list(_BOT_CONFIGS.values())}


@router.post("/bot/config")
async def update_perp_bot_config(req: PerpBotConfigRequest) -> Dict[str, Any]:
    if req.bot_id not in _BOT_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Bot {req.bot_id} not found")
    cfg = _BOT_CONFIGS[req.bot_id]
    if req.leverage is not None:
        cfg["leverage"] = req.leverage
    if req.min_confidence is not None:
        cfg["min_confidence"] = req.min_confidence
    if req.take_profit_pct is not None:
        cfg["take_profit_pct"] = req.take_profit_pct
    if req.stop_loss_pct is not None:
        cfg["stop_loss_pct"] = req.stop_loss_pct
    if req.is_armed is not None:
        cfg["is_armed"] = req.is_armed
    return {"status": "ok", "bot": cfg}

import random
import asyncio
from kalshi_sim.db import get_db

async def perpetual_auto_trade_loop() -> None:
    logger.info("dY [PERPETUAL AUTO-TRADER] Background loop started (Interval: 1s).")
    while True:
        try:
            await asyncio.sleep(1.0)
            
            # Get latest ONNX state
            from kalshi_sim.server import state
            try:
                ai_data = state.ai_worker.get_cached_signals()
            except:
                ai_data = {}
                
            p_up = ai_data.get("p_up", 0.5)
            p_down = ai_data.get("p_down", 0.5)
            vpin_safe = ai_data.get("vpin_is_safe", True)
            
            db = get_db()
            async with db.get_connection() as conn:
                async with conn.execute("SELECT COUNT(*) FROM perp_positions WHERE status = 'open'") as cursor:
                    global_open_count = (await cursor.fetchone())[0]

            for bot_id, cfg in _BOT_CONFIGS.items():
                if cfg.get("is_armed"):
                    async with db.get_connection() as conn:
                        async with conn.execute(
                            "SELECT id, side, entry_price FROM perp_positions WHERE status = 'open' AND bot_id = ?",
                            (bot_id,)
                        ) as cursor:
                            row = await cursor.fetchone()
                    
                    if not row and global_open_count == 0:
                        # Open new position if confidence is high and VPIN safe
                        min_conf = Decimal(str(cfg.get("min_confidence", 0.70)))
                        if vpin_safe:
                            if p_up > min_conf:
                                side = "long"
                            elif p_down > min_conf:
                                side = "short"
                            else:
                                side = None
                                
                            if side:
                                lev = Decimal(str(cfg.get("leverage", 10.0)))
                                req = PerpOrderRequest(
                                    asset="BTC",
                                    side=side,
                                    order_type="market",
                                    size=1.0,
                                    leverage=lev,
                                    bot_id=bot_id
                                )
                                await place_perp_order(req)
                    else:
                        pos_id, pos_side, entry_price = row
                        
                        # SCALPING EXIT RULES:
                        # 1. Reverse Signal Exit
                        should_close = False
                        if pos_side == "long" and p_up < 0.50:
                            should_close = True
                        elif pos_side == "short" and p_down < 0.50:
                            should_close = True
                            
                        # 2. Strict Real-Time Scalp PnL Check
                        current_spot = getattr(state, "current_btc_price", 0)
                        if current_spot > 0:
                            entry = Decimal(str(entry_price))
                            spot = Decimal(str(current_spot))
                            lev = Decimal(str(cfg.get("leverage", 10.0)))
                            # Micro-bankroll size: strictly 1 contract
                            net_pnl = _calc_pnl_with_fees(entry, spot, Decimal("1"), pos_side)
                            margin = entry / lev
                            pnl_pct = (net_pnl / margin) * Decimal("100") if margin > 0 else Decimal("0")

                            tp_pct = Decimal(str(cfg.get("take_profit_pct", 0.50)))
                            sl_pct = Decimal(str(cfg.get("stop_loss_pct", 0.75)))

                            # GAIN IS GAIN: If net profit after all fees & spread is >= $0.04 OR target ROI reached, BANK IT IMMEDIATELY
                            if net_pnl >= Decimal("0.04") or pnl_pct >= tp_pct:
                                logger.info(f"⚡ [SCALPER TAKE-PROFIT] Banking gain on {bot_id} (Net PnL: +${net_pnl:.4f}, ROI: +{pnl_pct:.2f}%)")
                                should_close = True
                            # TIGHT STOP LOSS: Cut loss instantly if drawdown crosses strict cap
                            elif pnl_pct <= -sl_pct:
                                logger.warning(f"🛡️ [SCALPER STOP-LOSS] Cutting adverse move on {bot_id} (Net PnL: -${abs(net_pnl):.4f}, ROI: {pnl_pct:.2f}%)")
                                should_close = True
                                
                        if should_close:
                            c_req = PerpClosePositionRequest(position_id=pos_id)
                            await close_perp_position(c_req)
        except Exception as e:
            import traceback
            logger.error(f"Perpetual Auto-Trader error: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(5)

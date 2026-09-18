"""Spot Price Feeds, Feed Lifecycle & Dynamic CLOB Ladder.

Extracted from server.py to reduce monolith size while maintaining
backward-compatible imports via re-exports in server.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Optional

import aiohttp

from kalshi_sim.auth import (
    DEMO_REST_BASE,
    DEMO_WS_URL,
    PROD_REST_BASE,
    PROD_WS_URL,
    create_aiohttp_connector,
)
from kalshi_sim.cfbenchmarks_sync import CFBenchmarksBRTISync, CFBenchmarksSync
from kalshi_sim.ingestion_agent import IngestionAgent, load_config
from kalshi_sim.mock_feed import MockKalshiFeed
from kalshi_sim.process_lock import get_active_lock_holder
from kalshi_sim.schemas import (
    CryptoAsset,
    L2BookState,
    MarketInfo,
    MarketStatus,
    Timeframe,
    get_asset_config,
)

logger = logging.getLogger("kalshi_sim.server_feeds")


# ---------------------------------------------------------------------------
# Module-Level Init (Dependency Injection)
# ---------------------------------------------------------------------------
_state_getter: Callable[[], Any] | None = None
_trigger_instant_broadcast_fn: Callable[[], Any] | None = None


def init_server_feeds(
    state_getter: Callable[[], Any],
    trigger_instant_broadcast_fn: Callable[[], Any],
) -> None:
    """Inject runtime dependencies from the main server module."""
    global _state_getter, _trigger_instant_broadcast_fn
    _state_getter = state_getter
    _trigger_instant_broadcast_fn = trigger_instant_broadcast_fn


def _get_state() -> Any:
    assert _state_getter is not None, "server_feeds not initialized"
    return _state_getter()


async def _trigger_broadcast() -> None:
    if _trigger_instant_broadcast_fn:
        await _trigger_instant_broadcast_fn()


async def start_live_feed() -> bool:
    """Initialize and run live Kalshi WebSocket feed for live paper trading."""
    state = _get_state()
    try:
        config = load_config()
        env = os.getenv("KALSHI_ENV", "live").lower()
        ws_url = PROD_WS_URL if env in ("prod", "live") else DEMO_WS_URL
        rest_base = PROD_REST_BASE if env in ("prod", "live") else DEMO_REST_BASE

        async def _on_live_trade(trade: Any) -> None:
            side_val = getattr(trade.taker_side, "value", str(trade.taker_side))
            p_val = trade.yes_price if str(side_val).lower() == "yes" else (Decimal("1.0") - trade.no_price if trade.no_price else Decimal("0.50"))
            p_cents = float(p_val * 100) if p_val else 50.0
            count = int(getattr(trade, "count", 1))
            val = p_cents / 100.0 * count
            val_str = f"+${val:,.0f}" if str(side_val).lower() == "yes" else f"-${val:,.0f}"
            t_str = trade.timestamp.strftime("%H:%M:%S") if getattr(trade, "timestamp", None) else datetime.now(timezone.utc).strftime("%H:%M:%S")
            trade_entry = {
                "ticker": trade.market_ticker,
                "side": side_val,
                "price_cents": f"{p_cents:.1f}¢",
                "contracts": count,
                "val_str": val_str,
                "time": t_str,
            }
            state.trade_tape.append(trade_entry)


        async def _on_live_ticker(update: Any) -> None:
            if getattr(update, "volume", None):
                vol_num = int(update.volume)
                state.volume_24h_str = f"${vol_num * 100:,.0f}" if vol_num < 100000 else f"${vol_num:,.0f}"

        state.ingestion_agent = IngestionAgent(
            api_key_id=config["api_key_id"],
            private_key_path=config["private_key_path"],
            timeframes=state.timeframes,
            data_dir=state.data_dir,
            enable_simulation=True,
            starting_capital=state.starting_capital,
            live_demo_orders=False,
            orderbook=state.orderbook,
            sim_agent=state.sim_agent,
            tick_writer=state.tick_writer,
            ws_url=ws_url,
            rest_base=rest_base,
            on_trade=_on_live_trade,
            on_ticker=_on_live_ticker,
        )
        state.feed_task = asyncio.create_task(state.ingestion_agent.run(), name="live_ingestion")
        state.mode = "live"
        logger.info("[LIVE PAPER TRADING] Connected to live Kalshi (%s) WebSocket stream.", env.upper())
        return True
    except (Exception, SystemExit) as exc:
        logger.info("[LIVE FEED] Live Kalshi credentials not in env (%s). Streaming 100%% real live Kalshi public market feeds.", exc)
        await start_live_public_feed()
        return True



async def live_kalshi_public_sync_loop() -> None:
    """Continuously ingest 100% REAL live Kalshi market contracts, strikes, timer, and orderbook."""
    state = _get_state()
    connector = create_aiohttp_connector()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
    }
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        last_market_poll = 0.0
        while True:
            try:
                now_mono = time.monotonic()
                now_utc = datetime.now(timezone.utc)

                # 1. Discover active live Kalshi 15M open markets every 2.0s
                active_cfg = get_asset_config(state.active_asset)
                if now_mono - last_market_poll >= 2.0:
                    last_market_poll = now_mono
                    url = f"{PROD_REST_BASE}/markets?series_ticker={active_cfg.series_ticker_15m}&status=open&limit=10"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3.0)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            raw_markets = data.get("markets", [])
                            open_m: list[tuple[datetime, dict[str, Any]]] = []
                            for m in raw_markets:
                                ticker = m.get("ticker")
                                if not ticker:
                                    continue
                                close_str = m.get("close_time")
                                open_str = m.get("open_time")
                                close_dt = datetime.fromisoformat(close_str.replace("Z", "+00:00")) if close_str else None
                                open_dt = datetime.fromisoformat(open_str.replace("Z", "+00:00")) if open_str else None
                                floor_str = m.get("floor_strike")
                                floor_dec = Decimal(str(floor_str)) if floor_str is not None else None
                                
                                minfo = MarketInfo(
                                    ticker=ticker,
                                    series_ticker=m.get("series_ticker", active_cfg.series_ticker_15m),
                                    title=m.get("title", ""),
                                    subtitle=m.get("subtitle", ""),
                                    status=MarketStatus.OPEN,
                                    open_time=open_dt,
                                    close_time=close_dt,
                                    expiration_time=close_dt,
                                    floor_strike=floor_dec,
                                    cap_strike=None,
                                    strike_type="greater",
                                )
                                if state.sim_agent:
                                    state.sim_agent._market_cache[ticker] = minfo
                                    state.sim_agent._ticker_timeframe_map[ticker] = Timeframe.FIFTEEN_MIN
                                if close_dt and close_dt > now_utc:
                                    open_m.append((close_dt, m))

                            if open_m:
                                open_m.sort(key=lambda x: x[0])
                                active_close, active_m = open_m[0]
                                new_ticker = active_m.get("ticker", "")
                                if new_ticker:
                                    state.active_ticker = new_ticker
                                    fl = active_m.get("floor_strike")
                                    if fl is not None:
                                        state.target_strike = Decimal(str(fl))

                # 2. Fetch live Level-2 Orderbook Snapshot from Kalshi public API every 500ms
                active_ticker = state.active_ticker
                if active_ticker and any(active_ticker.startswith(pfx) for pfx in ["KXBTC", "KXETH", "KXSOL", "KXDOGE"]):
                    ob_url = f"{PROD_REST_BASE}/markets/{active_ticker}/orderbook"
                    async with session.get(ob_url, timeout=aiohttp.ClientTimeout(total=2.0)) as resp2:
                        if resp2.status == 200:
                            ob_data = await resp2.json()
                            raw_book = ob_data.get("orderbook_fp") or ob_data.get("orderbook") or {}
                            bids = raw_book.get("yes_dollars") or raw_book.get("yes") or []
                            asks = raw_book.get("no_dollars") or raw_book.get("no") or []

                            book = state.orderbook.get_book(active_ticker)
                            if not book:
                                book = L2BookState(active_ticker)
                                state.orderbook._books[active_ticker] = book

                            # Parse real yes bids and no bids into Decimal CLOB
                            new_yes_book: dict[Decimal, Decimal] = {}
                            for pr_str, qty_str in bids:
                                new_yes_book[Decimal(str(pr_str))] = Decimal(str(qty_str))

                            new_no_book: dict[Decimal, Decimal] = {}
                            for pr_str, qty_str in asks:
                                new_no_book[Decimal(str(pr_str))] = Decimal(str(qty_str))

                            book.yes_book = new_yes_book
                            book.no_book = new_no_book

                            # Trigger bot evaluation against real live orderbook (suppressed only if sim_agent is in real live execution mode and standalone bot holds lock)
                            if state.sim_agent and state.ai_auto_trade:
                                is_live_exec = getattr(state.sim_agent, "execution_mode", "simulated") == "live"
                                if is_live_exec:
                                    holder = get_active_lock_holder()
                                    if not (holder and holder[1] != os.getpid()):
                                        asyncio.create_task(state.sim_agent._evaluate_market(active_ticker, book))
                                else:
                                    asyncio.create_task(state.sim_agent._evaluate_market(active_ticker, book))

                            state.is_dirty = True

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("[LIVE KALSHI SYNC] Poll error: %s", exc)

            await asyncio.sleep(0.5)



async def standalone_sync_loop() -> None:
    """Retired in Option C: Mother Server is the monolithic trading engine on Port 8000."""
    return



async def start_live_public_feed() -> None:
    """Run continuous live public Kalshi sync (Zero mock data)."""
    state = _get_state()
    state.mode = "live"
    state.feed_task = asyncio.create_task(live_kalshi_public_sync_loop(), name="live_public_sync")
    logger.info("[LIVE KALSHI SYNC] Connected to 100%% Real Live Kalshi Public Market & Orderbook stream.")



async def start_mock_feed() -> None:
    """Initialize and run interactive mock market feed for offline testing."""
    state = _get_state()
    state.mock_feed = MockKalshiFeed(
        state.orderbook,
        state.sim_agent,
        tick_writer=state.tick_writer,
    )
    state.feed_task = asyncio.create_task(state.mock_feed.run(), name="mock_feed")
    state.mode = "mock"
    logger.info("[MOCK SIMULATION] Interactive mock feed started for offline testing.")



async def stop_current_feed() -> None:
    """Stop active feed gracefully."""
    state = _get_state()
    if state.mock_feed:
        state.mock_feed.stop()
        state.mock_feed = None
    if state.ingestion_agent:
        await state.ingestion_agent._shutdown()
        state.ingestion_agent = None
    if state.feed_task and not state.feed_task.done():
        state.feed_task.cancel()
        try:
            await state.feed_task
        except asyncio.CancelledError:
            logger.debug("Feed task cancelled successfully.")
        except Exception as exc:
            logger.warning("Unexpected error awaiting feed task: %s", exc)
        state.feed_task = None



async def live_btc_spot_ws_loop() -> None:
    """Streams real-time crypto spot price ticks prioritizing official CF Benchmarks 5Hz feed."""
    state = _get_state()
    def _on_cf_asset(asset: CryptoAsset, price: Decimal, twap: Optional[Decimal], source: str) -> None:
        if asset == state.active_asset:
            if price != state.current_btc_price:
                state.current_btc_price = price
                if twap is not None:
                    state.twap_60s_price = twap
                state.coinbase_connected = True  # Marks spot feed healthy
                now_t = datetime.now(timezone.utc).strftime("%H:%M:%S")
                state.price_history.append({
                    "time": now_t,
                    "price": float(price),
                    "target": float(state.target_strike),
                })
                if state.mode != "live":
                    update_dynamic_clob_ladder(price, state.target_strike, state.active_ticker)
                state.is_dirty = True
                if state.connected_websockets:
                    asyncio.create_task(_trigger_broadcast())

    api_key_id = os.getenv("KALSHI_API_KEY_ID", "")
    priv_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")
    if api_key_id and priv_key_path:
        try:
            state.cf_sync = CFBenchmarksSync(
                api_key_id=api_key_id,
                private_key_path=priv_key_path,
                on_asset_price_update=_on_cf_asset,
            )
            await state.cf_sync.start()
            logger.info("[SPOT FEED] Official CF Benchmarks Multi-Asset 5Hz active on Mother server.")
        except Exception as e:
            logger.warning("[SPOT FEED] Could not start CF Benchmarks sync: %s", e)

    async def _coinbase_worker(session: aiohttp.ClientSession) -> None:
        while True:
            try:
                async with session.ws_connect("wss://ws-feed.exchange.coinbase.com", timeout=5.0) as ws:
                    sub_msg = {
                        "type": "subscribe",
                        "product_ids": ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"],
                        "channels": ["ticker"]
                    }
                    await ws.send_json(sub_msg)
                    logger.info("[SPOT FEED] Coinbase Pro WebSocket active as standby.")
                    product_map = {
                        "BTC-USD": CryptoAsset.BTC,
                        "ETH-USD": CryptoAsset.ETH,
                        "SOL-USD": CryptoAsset.SOL,
                        "DOGE-USD": CryptoAsset.DOGE,
                    }
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "ticker" and "price" in data:
                                pid = data.get("product_id")
                                matched_asset = product_map.get(pid)
                                if matched_asset == state.active_asset and not (state.cf_sync and state.cf_sync.is_connected):
                                    p = Decimal(str(data["price"]))
                                    if p != state.current_btc_price:
                                        state.current_btc_price = p
                                        now_t = datetime.now(timezone.utc).strftime("%H:%M:%S")
                                        state.price_history.append({
                                            "time": now_t,
                                            "price": float(p),
                                            "target": float(state.target_strike),
                                        })
                                        if state.mode != "live":
                                            update_dynamic_clob_ladder(p, state.target_strike, state.active_ticker)
                                        state.is_dirty = True
                                        if state.connected_websockets:
                                            asyncio.create_task(_trigger_broadcast())
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("[SPOT FEED] Coinbase WS retry in 2s: %s", exc)
            await asyncio.sleep(2.0)

    async def _binance_worker(session: aiohttp.ClientSession) -> None:
        while True:
            try:
                async with session.ws_connect("wss://stream.binance.com:9443/ws/btcusdt@ticker", timeout=5.0) as ws:
                    logger.info("[SPOT FEED] Binance WebSocket active as fallback standby for BTC-USDT.")
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if "c" in data and not (state.cf_sync and state.cf_sync.is_connected) and not state.coinbase_connected:
                                p = Decimal(str(data["c"]))
                                if p != state.current_btc_price:
                                    state.current_btc_price = p
                                    now_t = datetime.now(timezone.utc).strftime("%H:%M:%S")
                                    state.price_history.append({
                                        "time": now_t,
                                        "price": float(p),
                                        "target": float(state.target_strike),
                                    })
                                    if state.mode != "live":
                                        update_dynamic_clob_ladder(p, state.target_strike, state.active_ticker)
                                    state.is_dirty = True
                                    if state.connected_websockets:
                                        asyncio.create_task(_trigger_broadcast())

                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("[SPOT FEED] Binance WS retry in 2s: %s", exc)
            await asyncio.sleep(2.0)

    connector = create_aiohttp_connector()
    async with aiohttp.ClientSession(connector=connector) as session:
        cb_task = asyncio.create_task(_coinbase_worker(session), name="coinbase_spot_ws")
        bn_task = asyncio.create_task(_binance_worker(session), name="binance_spot_ws")
        try:
            await asyncio.gather(cb_task, bn_task)
        except asyncio.CancelledError:
            cb_task.cancel()
            bn_task.cancel()
            await asyncio.gather(cb_task, bn_task, return_exceptions=True)
        finally:
            if state.cf_sync:
                await state.cf_sync.stop()



async def live_btc_spot_sync_loop() -> None:
    """Fallback REST polling synchronizer for BTC spot price."""
    state = _get_state()
    connector = create_aiohttp_connector()
    async with aiohttp.ClientSession(connector=connector) as session:
        while True:
            try:
                if not (state.cf_sync and state.cf_sync.is_connected):
                    async with session.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            amt_str = data.get("data", {}).get("amount")
                            if amt_str:
                                state.current_btc_price = Decimal(str(amt_str))
            except Exception as exc:
                logger.debug("[SPOT SYNC] Coinbase REST sync error: %s", exc)
                try:
                    if not (state.cf_sync and state.cf_sync.is_connected):
                        async with session.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=aiohttp.ClientTimeout(total=2.0)) as resp2:
                            if resp2.status == 200:
                                data2 = await resp2.json()
                                if "price" in data2:
                                    state.current_btc_price = Decimal(str(data2["price"]))
                except Exception as exc2:
                    logger.debug("[SPOT SYNC] Binance REST fallback sync error: %s", exc2)
            await asyncio.sleep(0.5)



def update_dynamic_clob_ladder(spot_price: Decimal, strike_price: Decimal, ticker: str, remaining_secs: int = 900) -> None:
    """Maintain dynamic, high-frequency Level-2 CLOB order book reflecting live BTC spot price movements and time-to-expiry decay."""
    state = _get_state()
    book = state.orderbook.get_book(ticker)
    if not book:
        book = L2BookState(ticker)
        state.orderbook._books[ticker] = book

    diff = float(spot_price - strike_price)
    # Dynamic time-to-expiry fraction (tau in range [0, 1]) scaled to active timeframe
    tf_val = state.active_timeframe.value if hasattr(state.active_timeframe, "value") else str(state.active_timeframe)
    cycle_duration = 300.0 if tf_val == "5m" else (3600.0 if tf_val == "1h" else 900.0)
    tau_fraction = min(1.0, max(5, remaining_secs) / cycle_duration)
    # Volatility scale narrows with sqrt(tau):
    # For 5M, volatility scale starts tighter (~105.0 down to ~25.0 at expiry) reflecting smaller 5m dispersion
    if state.active_asset == CryptoAsset.BTC:
        if tf_val == "5m":
            scale = max(25.0, 105.0 * math.sqrt(tau_fraction))
        else:
            scale = max(35.0, 180.0 * math.sqrt(tau_fraction))
    else:
        active_cfg = get_asset_config(state.active_asset)
        base_diff = float(active_cfg.min_spot_diff)
        multiplier = (105.0 / 25.0) if tf_val == "5m" else (180.0 / 35.0)
        scale = max(base_diff, base_diff * multiplier * math.sqrt(tau_fraction))
    z = diff / scale if scale > 0 else 0.0
    try:
        prob = 1.0 / (1.0 + math.exp(-z))
    except OverflowError:
        prob = 1.0 if z > 0 else 0.0

    # Add realistic market-making micro-jitter
    noise = random.uniform(-0.008, 0.008)
    prob_mid = max(0.01, min(0.99, prob + noise))

    yes_bid_best = max(Decimal("0.01"), min(Decimal("0.98"), Decimal(str(round(prob_mid - 0.01, 2)))))
    no_bid_best = max(Decimal("0.01"), min(Decimal("0.98"), Decimal(str(round((1.00 - prob_mid) - 0.01, 2)))))

    # Strictly guarantee uncrossed book invariant: yes_bid + no_bid <= 1.00
    if yes_bid_best + no_bid_best >= Decimal("1.00"):
        no_bid_best = Decimal("1.00") - yes_bid_best - Decimal("0.01")
        if no_bid_best < Decimal("0.01"):
            no_bid_best = Decimal("0.01")
            yes_bid_best = Decimal("0.98")

    # Generate 10-12 active levels on YES and NO with realistic depth profiles
    yes_levels: dict[Decimal, Decimal] = {}
    no_levels: dict[Decimal, Decimal] = {}
    for i in range(10):
        p_yes = max(Decimal("0.01"), yes_bid_best - Decimal(str(round(i * 0.01, 2))))
        p_no = max(Decimal("0.01"), no_bid_best - Decimal(str(round(i * 0.01, 2))))
        base_qty = random.randint(150, 650) + (i * random.randint(100, 250))
        yes_levels[p_yes] = Decimal(str(base_qty))
        no_levels[p_no] = Decimal(str(base_qty + random.randint(-30, 30)))

    book.yes_book = yes_levels
    book.no_book = no_levels
    book.last_update = datetime.now(timezone.utc)
    book._stale = False
    state.is_dirty = True


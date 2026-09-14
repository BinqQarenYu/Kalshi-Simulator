import os
import time
import asyncio
import logging
import json
from decimal import Decimal
from typing import Dict, Any, List, Optional

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from kalshi_sim.polymarket_client import pm_client
from kalshi_sim.atomic_router import AtomicRouter

logger = logging.getLogger("kalshi_sim.arbitrage")


class CrossExchangeScanner:
    """
    Phase 1 & 2: Market Mapper & Spread Scanner.
    Finds exact matching markets between Kalshi and Polymarket.
    Polls the L2 orderbook for both to find net-positive arbitrage spreads.
    """

    def __init__(self, kalshi_engine):
        self.kalshi_engine = kalshi_engine
        self.router = AtomicRouter(kalshi_engine)
        self._running = False
        self.is_active = True  # Can be toggled from UI
        self.mapped_pairs = []  # List of dicts mapping Kalshi Ticker -> PM Token IDs
        self.latest_radar_scan = {"enabled": True, "status": "SCANNING (NO ARB)"}
        
        # Hardcoded Kalshi Taker fee approximation (dynamic based on price, but capped)
        self.kalshi_taker_fee_bps = 0.02  # $0.02 maximum per contract

    def start(self):
        self._running = True
        asyncio.create_task(self._scanner_loop(), name="arbitrage_scanner")

    def stop(self):
        self._running = False

    async def _discover_pm_markets(self):
        """Phase 1: Oracle Parity Mapper. Finds Polymarket BTC daily markets."""
        logger.info("📡 [ARBITRAGE SCANNER] Querying Polymarket Gamma API for active BTC markets...")
        url = "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=1000"
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None, lambda: requests.get(url, verify=False, timeout=10)
            )
            
            if resp.status_code == 200:
                events = resp.json()
                btc_events = [
                    e for e in events 
                    if ("Bitcoin" in e.get("title", "") or "BTC" in e.get("title", ""))
                ]
                
                btc_markets = []
                for e in btc_events:
                    for m in e.get("markets", []):
                        if m.get("clobTokenIds"):
                            tokens = json.loads(m.get("clobTokenIds")) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds")
                            if len(tokens) == 2:
                                btc_markets.append(m)
                
                logger.info(f"📡 [ARBITRAGE SCANNER] Found {len(btc_markets)} potential Polymarket BTC markets.")
                self.mapped_pairs = btc_markets
        except Exception as e:
            logger.error("📡 [ARBITRAGE SCANNER] Failed to map Polymarket markets: %s", e)

    async def _discover_binance_predictions(self):
        """Phase 1B: Binance Options / Prediction Market Mapper.
        Maps Kalshi binaries to Binance European Options (eapi.binance.com) or BSC Prediction endpoints.
        Note: Binance vanilla options have a linear payout (Spot - Strike), whereas Kalshi/Polymarket are fixed binary ($1.00).
        """
        logger.info("📡 [ARBITRAGE SCANNER] Probing Binance Options/Predictions for overlapping strikes...")
        # Stub for Binance Options API mapping
        # url = "https://eapi.binance.com/eapi/v1/exchangeInfo"
        self.binance_mapped_pairs = []
        logger.info("📡 [ARBITRAGE SCANNER] Binance mapping module initialized. (Awaiting strike parity filter)")

    async def _fetch_binance_orderbook(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch Binance L2 Orderbook for a specific prediction/option symbol."""
        # Stub for Binance WebSocket/REST L2 pull
        return None

    async def _fetch_pm_orderbook(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Fetch Polymarket L2 Orderbook for a specific token."""
        try:
            loop = asyncio.get_event_loop()
            book = await loop.run_in_executor(
                None, lambda: pm_client.client.get_order_book(token_id)
            )
            return book
        except Exception as e:
            logger.debug("Failed to fetch PM book for %s: %s", token_id, e)
            return None

    async def _scanner_loop(self):
        """Phase 2: Spread Scanner."""
        await self._discover_pm_markets()
        await self._discover_binance_predictions()
        
        while self._running:
            try:
                if not self.is_active:
                    self.latest_radar_scan = {"enabled": False, "status": "PAUSED"}
                    await asyncio.sleep(2.0)
                    continue

                # 1. Get current active Kalshi Market
                kalshi_active = self.kalshi_engine.active_ticker
                if not kalshi_active:
                    await asyncio.sleep(5.0)
                    continue

                # 2. Get Kalshi L2 Pricing
                k_yes_ask = self.kalshi_engine.best_yes_ask
                k_no_ask = self.kalshi_engine.best_no_ask
                
                if not k_yes_ask or not k_no_ask:
                    await asyncio.sleep(2.0)
                    continue
                
                radar_opportunities = []
                
                # 3. For each mapped Polymarket, poll the book (Shadow mode simulation)
                for pm_market in self.mapped_pairs[:1]:  # Just checking the top 1 for log brevity
                    tokens = json.loads(pm_market["clobTokenIds"]) if isinstance(pm_market["clobTokenIds"], str) else pm_market["clobTokenIds"]
                    yes_token, no_token = tokens[0], tokens[1]
                    
                    pm_book_yes = await self._fetch_pm_orderbook(yes_token)
                    pm_book_no = await self._fetch_pm_orderbook(no_token)
                    
                    if not pm_book_yes or not pm_book_no:
                        continue

                    try:
                        # Extract lowest ask from Polymarket
                        pm_yes_ask = Decimal(str(pm_book_yes.asks[0].price)) if hasattr(pm_book_yes, "asks") and pm_book_yes.asks else Decimal("1.00")
                        pm_no_ask = Decimal(str(pm_book_no.asks[0].price)) if hasattr(pm_book_no, "asks") and pm_book_no.asks else Decimal("1.00")
                    except Exception:
                        continue

                    arb_cost_k_yes = k_yes_ask + Decimal(str(self.kalshi_taker_fee_bps))
                    arb_cost_p_no = pm_no_ask 
                    
                    total_arb_cost_leg1 = arb_cost_k_yes + arb_cost_p_no
                    
                    if total_arb_cost_leg1 < Decimal("1.00"):
                        profit = Decimal("1.00") - total_arb_cost_leg1
                        logger.warning(
                            f"⚡ [ARB TARGET] Buy Kalshi YES ({k_yes_ask}) + PM NO ({pm_no_ask}) = {total_arb_cost_leg1}. Net Profit: {profit}"
                        )
                        opp_data = {
                            "type": "Kalshi YES / PM NO",
                            "kalshi_ticker": kalshi_active,
                            "kalshi_side": "yes",
                            "kalshi_leg": str(k_yes_ask),
                            "pm_token": no_token,
                            "pm_side": "buy",
                            "pm_leg": str(pm_no_ask),
                            "pm_price": str(pm_no_ask),
                            "total_cost": str(total_arb_cost_leg1),
                            "net_profit": str(profit)
                        }
                        radar_opportunities.append(opp_data)
                        
                        # Fire and forget router execution
                        asyncio.create_task(self.router.route_opportunity(opp_data))
                    else:
                        logger.info(
                            f"📡 [ARB WATCH] Kalshi YES ({k_yes_ask}) + PM NO ({pm_no_ask}) = {total_arb_cost_leg1} (No arb available)"
                        )
                    
            except Exception as e:
                logger.error("Scanner loop error: %s", e)
                
            try:
                # Quick Binance Spot probe for hedge parity context
                loop = asyncio.get_event_loop()
                bin_resp = await loop.run_in_executor(
                    None, lambda: requests.get("https://api.binance.com/api/v3/ticker/bookTicker?symbol=BTCUSDT", timeout=3)
                )
                if bin_resp.status_code == 200:
                    b_data = bin_resp.json()
                    bin_status = f"Active | BTC Spot: ${float(b_data['askPrice']):,.2f}"
                else:
                    bin_status = "Degraded"
            except Exception:
                bin_status = "Connection Error"
                
            self.latest_radar_scan = {
                "timestamp": time.time(),
                "enabled": True,
                "opportunities": radar_opportunities,
                "binance_status": bin_status,
                "markets_tracked": len(self.mapped_pairs)
            }
            
            await asyncio.sleep(5.0)

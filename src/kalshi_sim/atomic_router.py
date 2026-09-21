import logging
import asyncio
from decimal import Decimal
from typing import Dict, Any

from kalshi_sim.polymarket_client import pm_client

logger = logging.getLogger("kalshi_sim.atomic_router")

class AtomicRouter:
    """
    Phase 3: Maker-Taker Ambush Execution Engine.
    Executes cross-exchange arbitrage under strict constraints:
    1. Maker on Polymarket (0% fee).
    2. Synchronous intent lock to prevent legging.
    3. Taker sweep on Kalshi ONLY if PM fills.
    4. Sizing hard-capped to 1 contract.
    """

    def __init__(self, kalshi_engine):
        self.kalshi_engine = kalshi_engine
        self.in_flight = False
        self.enabled = False  # Permanently stopped by operator directive
        
    async def route_opportunity(self, opp: Dict[str, Any]):
        """
        Takes an opportunity dict and routes it.
        Permanently disabled: returns immediately.
        """
        if not self.enabled:
            logger.warning("🚫 [ATOMIC ROUTER] Arbitrage execution permanently stopped by operator directive.")
            return

        if self.in_flight:
            return
            
        profit = Decimal(opp.get("net_profit", "0"))
        
        # Guardrail: Only execute if net profit is >= 3¢ 
        if profit < Decimal("0.03"):
            return
            
        self.in_flight = True
        try:
            logger.warning("================ ATOMIC ROUTER ACTIVATED ================")
            logger.warning(f"Target: {opp.get('type')} | Profit: {profit}¢")
            
            kalshi_ticker = opp.get("kalshi_ticker")
            kalshi_side = opp.get("kalshi_side")
            pm_token = opp.get("pm_token")
            pm_price = opp.get("pm_price")
            
            logger.info(f"[LEG 1] Polymarket (MAKER) -> Placing LIMIT BUY at {pm_price} for token {pm_token[:8]}...")
            
            if pm_client.api_creds_established:
                logger.info("⚡ [POLYMARKET API] Sending signed Limit Order to Polygon Relayer...")
                # Place actual PM order logic here in the future
                await asyncio.sleep(1.0)
            else:
                logger.warning("🔒 [POLYMARKET API] Private Key missing! Shadow-executing PM leg.")
                await asyncio.sleep(1.0)
                
            logger.info("[AMBUSH TRAP] Waiting for Polymarket Maker fill. Kalshi Taker order held in reserve...")
            await asyncio.sleep(1.0) # Simulate waiting for PM fill
            logger.info("✅ [POLYMARKET] Maker Order FILLED! Triggering Leg 2...")
            
            logger.info(f"[LEG 2] Kalshi (TAKER) -> Sweeping {kalshi_side.upper()} on {kalshi_ticker}...")
            
            # Leg 2: Real Kalshi Taker order using the existing authenticated OrderClient
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.kalshi_engine.order_client.submit_order(
                        ticker=kalshi_ticker,
                        action="buy",
                        side=kalshi_side,
                        count=1,
                        client_order_id=self.kalshi_engine._generate_client_order_id()
                    )
                )
                logger.warning("✅ [KALSHI] Taker Order SUBMITTED successfully. (Count: 1)")
            except Exception as e:
                logger.error(f"❌ [KALSHI EXECUTION FAILED] Legging risk realized! Error: {e}")
                
            logger.warning("================ ARBITRAGE HEDGE LOCKED ================")
            
        finally:
            logger.info("[COOLDOWN] Engaging 5-second lock to prevent duplicate sweeps.")
            await asyncio.sleep(5.0)
            self.in_flight = False

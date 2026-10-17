"""Maker Limit Order Sweeper Module.

Continuously monitors open resting maker limit orders.
Sweeps (cancels) any order older than 90 seconds to eliminate
adverse selection sweep leaks without compromising trade execution.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger("MakerSweeper")


from datetime import datetime, timezone

async def maker_order_sweeper_loop(state: Any) -> None:
    """Continuously monitors open resting maker limit orders.
    Sweeps (cancels) any order older than 90 seconds or when time to expiry <= 240s (last 4 minutes)
    to eliminate adverse selection sweep leaks and late-cycle gamma/pin bleed.
    """
    logger.info("🛡️ [MAKER SWEEPER] 90s Stale & 4-Minute Late-Cycle Order Sweeper initialized.")
    while True:
        try:
            await asyncio.sleep(5.0)
            if state.mode == "live" and state.order_client and state.sim_agent:
                guardrails = getattr(state.sim_agent, "_guardrails", None)
                if guardrails and hasattr(guardrails, "_resting_order_details"):
                    now_mono = asyncio.get_event_loop().time()
                    for oid, order_info in list(guardrails._resting_order_details.items()):
                        ticker = order_info.get("ticker", "")
                        order_ts = order_info.get("ts", 0.0)
                        
                        # Condition 1: Stale order (>90s old)
                        import time
                        is_stale = (time.monotonic() - order_ts) >= 90.0

                        # Condition 2: Late-Cycle 4-Minute Quarantine (T <= 240s left)
                        is_late_cycle = False
                        if hasattr(state.sim_agent, "_market_cache"):
                            m_info = state.sim_agent._market_cache.get(ticker)
                            if m_info and getattr(m_info, "expiration_time", None):
                                rem_s = (m_info.expiration_time - datetime.now(timezone.utc)).total_seconds()
                                if rem_s <= 240.0:
                                    is_late_cycle = True

                        if is_stale or is_late_cycle:
                            reason = "Late-Cycle 4-Minute Cutoff (T<=240s)" if is_late_cycle else "Stale resting order (>90s)"
                            clean_oid = oid.replace("live_", "")
                            logger.info(
                                "🧹 [MAKER SWEEPER] %s detected: %s on %s. Cancelling immediately.",
                                reason, clean_oid, ticker,
                            )
                            success = await state.order_client.cancel_order(clean_oid)
                            if success:
                                guardrails.release_resting_order(oid)
                                logger.info("🧹 [MAKER SWEEPER] Order %s cancelled and cycle capacity released.", clean_oid)
        except Exception as exc:
            logger.debug("Maker sweeper loop error: %s", exc)

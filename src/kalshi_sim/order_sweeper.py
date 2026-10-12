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


async def maker_order_sweeper_loop(state: Any) -> None:
    """Continuously monitors open resting maker limit orders.
    Sweeps (cancels) any order older than 90 seconds to eliminate
    the adverse selection sweep leak without compromising trade execution.
    """
    logger.info("🛡️ [MAKER SWEEPER] 90s Stale Resting Order Sweeper initialized.")
    while True:
        try:
            await asyncio.sleep(5.0)
            if state.mode == "live" and state.order_client and state.sim_agent:
                guardrails = getattr(state.sim_agent, "_guardrails", None)
                if guardrails and hasattr(guardrails, "get_stale_resting_orders"):
                    stale_orders = guardrails.get_stale_resting_orders(max_age_seconds=90.0)
                    for order_info in stale_orders:
                        oid = order_info["order_id"]
                        ticker = order_info.get("ticker", "")
                        clean_oid = oid.replace("live_", "")
                        logger.info(
                            "🧹 [MAKER SWEEPER] Stale resting order (>90s) detected: %s on %s. Cancelling to eliminate adverse selection sweep.",
                            clean_oid, ticker
                        )
                        success = await state.order_client.cancel_order(clean_oid)
                        if success:
                            guardrails.release_resting_order(oid)
                            logger.info("🧹 [MAKER SWEEPER] Order %s cancelled and cycle capacity released.", clean_oid)
        except Exception as exc:
            logger.debug("Maker sweeper loop error: %s", exc)

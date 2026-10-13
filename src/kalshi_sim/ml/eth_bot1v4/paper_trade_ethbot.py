"""Paper‑trade script for the Ethereum‑specific Bot 1 V4 engine.

This utility runs the `EthBot1V4Engine` against Kalshi's **demo** (paper‑trading) sandbox.
It:
* Instantiates a `KalshiDemoOrderClient` (alias of `KalshiLiveOrderClient` with demo base URL).
* Connects the engine to the demo market data feed (via `KalshiDemoOrderClient`).
* Executes the engine's `run_cycle` loop at a configurable interval.
* Logs order actions and portfolio state using the existing logger.

The script is safe for production use because it never touches the live
`PROD_REST_BASE` endpoint – it forces the demo environment via the
environment variable `KALSHI_ENV=demo` (already set in `.env.example`).

Usage example (from the repository root)::

    python -m kalshi_sim.ml.eth_bot1v4.paper_trade_ethbot \
        --ticker KXETH15M-26AUG300215-15 \
        --cycle-interval 5

The script can be integrated into CI/ASVL tests by invoking the module
entry point.
"""

import os
import asyncio
import logging
from decimal import Decimal
from pathlib import Path
from typing import Optional

from kalshi_sim.auth import DEMO_REST_BASE, DEMO_WS_URL
from kalshi_sim.order_client import KalshiDemoOrderClient
from kalshi_sim.ml.eth_bot1v4.eth_bot1v4_engine import EthBot1V4Engine

logger = logging.getLogger("EthBotPaperTrade")
logger.setLevel(logging.INFO)

async def main(
    ticker: str,
    cycle_interval: int = 5,
    api_key_id: Optional[str] = None,
    private_key_path: Optional[str] = None,
) -> None:
    """Run the ETH bot in paper‑trade mode.

    Parameters
    ----------
    ticker: str
        The ETH contract ticker (e.g. ``KXETH15M-26AUG300215-15``).
    cycle_interval: int, default 5
        Seconds between engine cycles.
    api_key_id: str | None
        Kalshi demo API key ID; if omitted the env var ``KALSHI_API_KEY_ID``
        is used.
    private_key_path: str | None
        Path to the PEM private key; defaults to ``KALSHI_PRIVATE_KEY_PATH``.
    """
    # Resolve credentials from env or arguments
    api_key_id = api_key_id or os.getenv("KALSHI_API_KEY_ID")
    private_key_path = private_key_path or os.getenv("KALSHI_PRIVATE_KEY_PATH")
    if not api_key_id or not private_key_path:
        raise RuntimeError("Kalshi demo credentials not set in environment or arguments.")

    # Initialise demo order client (paper‑trading endpoint)
    order_client = KalshiDemoOrderClient(api_key_id, private_key_path, base_url=DEMO_REST_BASE)

    # Create the ETH‑specific engine – the constructor forces ticker/asset to ETH
    eth_engine = EthBot1V4Engine(order_client=order_client, ticker=ticker)

    logger.info("Starting ETH bot paper‑trade loop for ticker %s", ticker)
    try:
        while True:
            # The engine implements a ``run_cycle`` coroutine that performs
            # market data ingestion, signal evaluation and order placement.
            await eth_engine.run_cycle()
            await asyncio.sleep(cycle_interval)
    except asyncio.CancelledError:
        logger.info("Paper‑trade loop cancelled – shutting down.")
    finally:
        await order_client.close()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Paper‑trade ETH Bot 1 V4 on Kalshi demo.")
    parser.add_argument("--ticker", required=True, help="ETH market ticker (e.g. KXETH15M-…)")
    parser.add_argument("--cycle-interval", type=int, default=5, help="Seconds between cycles.")
    parser.add_argument("--api-key-id", help="Override KALSHI_API_KEY_ID env variable.")
    parser.add_argument("--private-key-path", help="Override KALSHI_PRIVATE_KEY_PATH env variable.")
    args = parser.parse_args()

    asyncio.run(
        main(
            ticker=args.ticker,
            cycle_interval=args.cycle_interval,
            api_key_id=args.api_key_id,
            private_key_path=args.private_key_path,
        )
    )

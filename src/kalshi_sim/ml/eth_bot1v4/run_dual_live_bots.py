# -*- coding: utf-8 -*-
"""
Dual‑bot live launcher – runs two independent Bot 1 V4 engines (ETH + another asset)
under the **same environment** and credentials that Bot 1 V4 already uses.

* Uses the live environment (`KALSHI_ENV=live`).
* Enforces the same guard‑rails as Bot 1 V4 (zero‑float Decimal, 1‑trade‑per‑cycle, seal check).
* Each engine gets its own `ContinuousExperienceBuffer` instance to keep histories separate.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# ----------------------------------------------------------------------
# 1️⃣  Environment validation – reuse the same checks as Bot 1 V4
# ----------------------------------------------------------------------
def _assert_live_environment() -> None:
    """Abort if the environment is not configured for live trading.
    The Bot 1 V4 codebase expects `KALSHI_ENV` to be "live" for production.
    """
    if os.getenv("KALSHI_ENV", "").lower() != "live":
        sys.exit("[FATAL] KALSHI_ENV must be set to \"live\" for live deployment.")

    required = ["KALSHI_API_KEY_ID", "KALSHI_PRIVATE_KEY_PATH"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        sys.exit(f"[FATAL] Missing required env vars: {', '.join(missing)}")

    seal_path = Path("seal.sha256")
    if not seal_path.is_file():
        sys.exit("[FATAL] Seal file (seal.sha256) not found – aborting live start.")

# ----------------------------------------------------------------------
# 2️⃣  Logging configuration – shared log file for both bots
# ----------------------------------------------------------------------
def _setup_logging() -> None:
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "live_dual_bots.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("kalshi_sim").setLevel(logging.DEBUG)

# ----------------------------------------------------------------------
# 3️⃣  Async driver – runs two engines concurrently
# ----------------------------------------------------------------------
async def _run_engine(engine, name: str, interval: float) -> None:
    """Execute a single engine in an endless loop.
    Args:
        engine: an instantiated Bot1V4DominationEngine (or subclass).
        name: friendly identifier used for log messages.
        interval: seconds to wait between cycles.
    """
    logger = logging.getLogger(name)
    logger.info("🚀 %s started", name)
    while True:
        try:
            await engine.run_cycle()
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("⚠️ Unhandled exception in %s: %s", name, exc)
        await asyncio.sleep(interval)

# ----------------------------------------------------------------------
# 4️⃣  Main entry point – parse CLI args and spin up both bots
# ----------------------------------------------------------------------
def main() -> None:
    _assert_live_environment()
    _setup_logging()

    parser = argparse.ArgumentParser(
        description="Run two live Bot 1 V4 engines (ETH + secondary asset) in the same process."
    )
    parser.add_argument(
        "--eth-interval",
        type=float,
        default=5.0,
        help="Seconds between ETH engine cycles (default 5s).",
    )
    parser.add_argument(
        "--secondary-asset",
        type=str,
        default="BTC",
        help="Crypto asset for the second bot (e.g., BTC, SOL).",
    )
    parser.add_argument(
        "--secondary-interval",
        type=float,
        default=5.0,
        help="Seconds between secondary engine cycles (default 5s).",
    )
    args = parser.parse_args()

    # Import inside main to keep startup fast and avoid circular imports.
    from kalshi_sim.ml.eth_bot1v4.eth_bot1v4_engine import EthBot1V4Engine
    from kalshi_sim.ml.bot1_v4_engine import Bot1V4DominationEngine
    from kalshi_sim.order_client import KalshiLiveOrderClient

    # Shared live order client – both bots will send orders through the same
    # authenticated session.  This mirrors the "single Kalshi account" requirement.
    client = KalshiLiveOrderClient()

    # ① ETH engine – wrapper forces asset/ticker to ETH.
    eth_engine = EthBot1V4Engine(order_client=client)

    # ② Secondary engine – can be BTC or any other supported asset.
    # We deliberately pass a fresh experience buffer to keep histories separate.
    secondary_engine = Bot1V4DominationEngine(
        order_client=client,
        asset=args.secondary_asset.upper(),
    )

    # Run both engines concurrently.
    loop = asyncio.get_event_loop()
    tasks = [
        _run_engine(eth_engine, "ETH_Bot", args.eth_interval),
        _run_engine(secondary_engine, f"{args.secondary_asset.upper()}_Bot", args.secondary_interval),
    ]
    loop.run_until_complete(asyncio.gather(*tasks))


if __name__ == "__main__":
    main()

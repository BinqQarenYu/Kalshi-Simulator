# -*- coding: utf-8 -*-
"""
Live‑mode entry point for the ETH‑specific Bot 1 V4 engine.
This script mirrors the one used for BTC but forces the asset to ETH.
It respects all guardrails defined in AGENTS.md (Decimal math, 1‑trade‑per‑cycle, seal check, etc.)
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    env_path = _ROOT / ".env"
    if env_path.is_file():
        load_dotenv(dotenv_path=env_path)
except Exception:
    pass

# ----------------------------------------------------------------------
# 1️⃣  Environment validation – same checks as Bot 1 V4
# ----------------------------------------------------------------------
def _assert_live_environment() -> None:
    if os.getenv("KALSHI_ENV", "").lower() != "live":
        sys.exit("[FATAL] KALSHI_ENV must be set to \"live\" for live deployment.")
    required = ["KALSHI_API_KEY_ID", "KALSHI_PRIVATE_KEY_PATH"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        sys.exit(f"[FATAL] Missing required env vars: {', '.join(missing)}")
    from kalshi_sim.bot_deployment_auditor import BotDeploymentAuditor
    auth_eth, reason_eth = BotDeploymentAuditor.check_live_authorization_on_disk("eth_bot1_v4")
    if not auth_eth:
        sys.exit(f"[FATAL] ETH bot seal verification failed: {reason_eth}")

# ----------------------------------------------------------------------
# 2️⃣  Logging configuration – shared with other bots
# ----------------------------------------------------------------------
def _setup_logging() -> None:
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "live_eth_bot.log"
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
# 3️⃣  Async driver – runs the ETH engine continuously
# ----------------------------------------------------------------------
async def _run_engine(engine, interval: float) -> None:
    logger = logging.getLogger("ETH_Bot")
    logger.info("🚀 ETH Bot started – entering main loop")
    while True:
        try:
            await engine.run_cycle()
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("⚠️ Unhandled exception in ETH bot: %s", exc)
        await asyncio.sleep(interval)

# ----------------------------------------------------------------------
# 4️⃣  Main entry point
# ----------------------------------------------------------------------
def main() -> None:
    _assert_live_environment()
    _setup_logging()

    parser = argparse.ArgumentParser(description="Run ETH Bot 1 V4 in live (real‑money) mode.")
    parser.add_argument(
        "--cycle-interval",
        type=float,
        default=5.0,
        help="Seconds to wait between engine cycles (default: 5s).",
    )
    args = parser.parse_args()

    # Import lazily to avoid circular imports.
    from kalshi_sim.ml.eth_bot1v4.eth_bot1v4_engine import EthBot1V4Engine
    from kalshi_sim.order_client import KalshiLiveOrderClient

    client = KalshiLiveOrderClient()
    engine = EthBot1V4Engine(order_client=client)  # asset forced to ETH inside wrapper

    asyncio.run(_run_engine(engine, args.cycle_interval))


if __name__ == "__main__":
    main()

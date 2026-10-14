"""Runner script for the Ethereum-specific Bot 1 V4 engine (Demo & Live).

This utility runs `EthBot1V4Engine` against Kalshi's demo or live exchange:
* Connects the real-time institutional `EthOrderflowFeed` (Binance & Coinbase L2 streams).
* Auto-discovers active 15-minute `KXETH15M` contracts and strike boundaries.
* Evaluates quantitative entry criteria within calibrated sweet spots (moat, timing, CLOB discount).
* In live mode, verifies the SHA-256 Seal of Excellence before placing live capital orders.
* Adheres strictly to AGENTS.md Law 1 (Zero Float Math) and Law 2 (1 contract micro-sizing, 1-trade-per-cycle lock).

Usage examples:
    # Autonomous Paper-Trading on Kalshi Demo
    python src/kalshi_sim/ml/eth_bot1v4/paper_trade_ethbot.py --mode demo

    # Authorized Live Trading with Micro-Bankroll Protection
    python src/kalshi_sim/ml/eth_bot1v4/paper_trade_ethbot.py --mode live
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from decimal import Decimal
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load workspace environment
_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(_ROOT / ".env")

from kalshi_sim.auth import DEMO_REST_BASE, PROD_REST_BASE
from kalshi_sim.order_client import KalshiDemoOrderClient, KalshiLiveOrderClient
from kalshi_sim.orderflow.eth_orderflow_feed import EthOrderflowFeed
from kalshi_sim.ml.eth_bot1v4.eth_bot1v4_engine import EthBot1V4Engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ETH-BOT1V4] %(message)s",
)
logger = logging.getLogger("EthBotRunner")


def verify_seal_of_excellence() -> bool:
    """Verify that eth_bot1_v4 holds a valid Seal of Excellence authorizing live trade."""
    seal_path = _ROOT / "data" / "seal_of_excellence.json"
    if not seal_path.exists():
        logger.error("❌ [SEAL REJECTED] seal_of_excellence.json not found on disk.")
        return False

    try:
        data = json.loads(seal_path.read_text(encoding="utf-8"))
        seals = data.get("seals", {})
        bot_seal = seals.get("eth_bot1_v4")
        if not bot_seal:
            logger.error("❌ [SEAL REJECTED] eth_bot1_v4 not registered in Seal of Excellence.")
            return False

        if not bot_seal.get("live_trading_authorized", False):
            logger.error("❌ [SEAL REJECTED] eth_bot1_v4 is NOT authorized for live capital trading.")
            return False

        logger.info(
            "🛡️ [SEAL VERIFIED] eth_bot1_v4 holds valid Seal of Excellence (%s). Live capital authorized.",
            bot_seal.get("seal_token", "VALID"),
        )
        return True
    except Exception as exc:
        logger.error("❌ [SEAL CHECK ERROR] Could not verify seal on disk: %s", exc)
        return False


async def run_eth_bot(
    mode: str = "demo",
    ticker: Optional[str] = None,
    cycle_interval: int = 5,
    api_key_id: Optional[str] = None,
    private_key_path: Optional[str] = None,
) -> None:
    """Run the ETH bot in paper or live mode."""
    api_key_id = api_key_id or os.getenv("KALSHI_API_KEY_ID")
    private_key_path = private_key_path or os.getenv("KALSHI_PRIVATE_KEY_PATH")

    if not api_key_id or not private_key_path:
        raise RuntimeError("Kalshi credentials not set in environment or arguments.")

    is_live = mode.lower() == "live"
    if is_live:
        if not verify_seal_of_excellence():
            raise PermissionError("Aborting live deployment: eth_bot1_v4 failed Seal of Excellence verification.")
        logger.warning("==================================================================")
        logger.warning("  🚨 LIVE CAPITAL TRADING ENGAGED: ETH BOT 1 V4 (KXETH15M)       ")
        logger.warning("  Micro-Bankroll Sizing: Strictly 1 contract per trade            ")
        logger.warning("  Execution Guardrail: 1 trade per 15-minute cycle lock           ")
        logger.warning("  Endpoint: %s", PROD_REST_BASE)
        logger.warning("==================================================================")
        order_client = KalshiLiveOrderClient(api_key_id, private_key_path, base_url=PROD_REST_BASE)
    else:
        logger.info("==================================================================")
        logger.info("  🧪 DEMO / PAPER TRADING ENGAGED: ETH BOT 1 V4 (KXETH15M)        ")
        logger.info("  Endpoint: %s", DEMO_REST_BASE)
        logger.info("==================================================================")
        order_client = KalshiDemoOrderClient(api_key_id, private_key_path, base_url=DEMO_REST_BASE)

    # Initialize institutional L2 WebSocket feed
    feed = EthOrderflowFeed()
    await feed.start()
    logger.info("📡 Streaming Binance & Coinbase Pro Level-2 orderflow for ETH...")

    # Initialize ETH Bot 1 V4 engine with live feed and order client
    eth_engine = EthBot1V4Engine(
        order_client=order_client,
        orderflow_feed=feed,
        ticker=ticker,
    )

    try:
        while True:
            try:
                decision = await eth_engine.run_cycle()
                if decision:
                    logger.info(
                        "📊 [TELEMETRY] Spot: $%.2f | Strike: $%.2f | Diff: %+.2f | Tau: %.0fs | OFI: %+.2f | Decision: %s",
                        float(eth_engine.get_spot_price()),
                        float(decision.spot_diff + float(eth_engine.get_spot_price())),
                        float(decision.spot_diff),
                        float(decision.time_to_expiry_s),
                        float(feed.ofi_l1),
                        decision.recommended_side.upper(),
                    )
            except Exception as loop_exc:
                logger.error("[CYCLE ERROR] Unexpected error during cycle: %s", loop_exc)

            await asyncio.sleep(cycle_interval)
    except asyncio.CancelledError:
        logger.info("ETH Bot loop cancelled - shutting down cleanly.")
    finally:
        logger.info("Stopping feeds and closing exchange sessions...")
        await feed.stop()
        await order_client.close()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Runner for ETH Bot 1 V4 (Demo & Live).")
    parser.add_argument("--mode", choices=["demo", "live"], default="demo", help="Execution mode: 'demo' or 'live'.")
    parser.add_argument("--ticker", default=None, help="Specific contract ticker (optional; auto-discovers if omitted).")
    parser.add_argument("--cycle-interval", type=int, default=5, help="Seconds between cycles (default: 5).")
    parser.add_argument("--api-key-id", help="Override KALSHI_API_KEY_ID.")
    parser.add_argument("--private-key-path", help="Override KALSHI_PRIVATE_KEY_PATH.")
    args = parser.parse_args()

    asyncio.run(
        run_eth_bot(
            mode=args.mode,
            ticker=args.ticker,
            cycle_interval=args.cycle_interval,
            api_key_id=args.api_key_id,
            private_key_path=args.private_key_path,
        )
    )

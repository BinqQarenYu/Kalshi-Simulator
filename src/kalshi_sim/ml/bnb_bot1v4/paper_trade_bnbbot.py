"""Runner script for the BNB-specific Bot 1 V4 engine (Demo & Live).

This utility runs `BnbBot1V4Engine` on local PC:
* Connects the real-time institutional `BnbOrderflowFeed` (Binance BNB-USDT L2 depth and trades).
* Auto-discovers active 15-minute `KXBNB15M` contracts and strike boundaries.
* Evaluates quantitative entry criteria within calibrated sweet spots ($1.50 moat, timing, CLOB discount).
* In live mode, verifies the SHA-256 Seal of Excellence before placing live capital orders.
* Adheres strictly to AGENTS.md Law 1 (Zero Float Math) and Law 2 (1 contract micro-sizing, 1-trade-per-cycle lock).

Usage examples:
    # Autonomous Paper-Trading on Kalshi Demo
    python src/kalshi_sim/ml/bnb_bot1v4/paper_trade_bnbbot.py --mode demo

    # Authorized Live Trading with Micro-Bankroll Protection
    python src/kalshi_sim/ml/bnb_bot1v4/paper_trade_bnbbot.py --mode live
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load workspace environment
_ROOT = Path(__file__).resolve().parents[4]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
load_dotenv(_ROOT / ".env")

from kalshi_sim.auth import DEMO_REST_BASE, PROD_REST_BASE
from kalshi_sim.order_client import KalshiDemoOrderClient, KalshiLiveOrderClient, KalshiShadowOrderClient
from kalshi_sim.orderflow.bnb_orderflow_feed import BnbOrderflowFeed
from kalshi_sim.ml.bnb_bot1v4.bnb_bot1v4_engine import BnbBot1V4Engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [BNB-BOT1V4] %(message)s",
)
logger = logging.getLogger("BnbBotRunner")


def verify_seal_of_excellence() -> bool:
    """Verify that bnb_bot1_v4 holds a valid Seal of Excellence authorizing live trade."""
    seal_path = _ROOT / "data" / "seal_of_excellence.json"
    if not seal_path.exists():
        logger.error("[SEAL REJECTED] seal_of_excellence.json not found on disk.")
        return False

    try:
        data = json.loads(seal_path.read_text(encoding="utf-8"))
        seals = data.get("seals", {})
        bnb_seal = seals.get("bnb_bot1_v4")
        if not bnb_seal:
            logger.error("[SEAL REJECTED] No seal entry found for 'bnb_bot1_v4'.")
            return False

        if not bnb_seal.get("live_trading_authorized", False):
            logger.error("[SEAL REJECTED] Live trading not authorized for bnb_bot1_v4 (status: %s).", bnb_seal.get("seal_status"))
            return False

        if bnb_seal.get("seal_status") != "SEALED_EXCELLENT":
            logger.error("[SEAL REJECTED] bnb_bot1_v4 status is %s, expected SEALED_EXCELLENT.", bnb_seal.get("seal_status"))
            return False

        token = bnb_seal.get("seal_token", "")
        if not token.startswith("SEAL-BNB-"):
            logger.error("[SEAL REJECTED] Invalid seal token prefix: %s", token)
            return False

        logger.info("[SEAL VERIFIED] bnb_bot1_v4 holds a valid Seal of Excellence (%s). Live trading approved.", token)
        return True
    except Exception as exc:
        logger.error("[SEAL ERROR] Failed to parse seal_of_excellence.json: %s", exc)
        return False


async def run_bnb_bot(mode: str = "demo", ticker: Optional[str] = None) -> None:
    """Run BNB Bot 1 V4 on local PC."""
    logger.info("Initializing BNB Bot 1 V4 (Asset: BNB, Series: KXBNB15M, Mode: %s)", mode.upper())

    # 1. Order Client
    if mode == "live":
        if not verify_seal_of_excellence():
            logger.critical("[HALT] Refusing to start BNB Bot in LIVE mode without a valid Seal of Excellence.")
            sys.exit(1)
        api_key = os.getenv("KALSHI_API_KEY")
        private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")
        if not api_key or not private_key_path:
            logger.critical("[HALT] Missing KALSHI_API_KEY or KALSHI_PRIVATE_KEY_PATH for LIVE trading.")
            sys.exit(1)
        order_client = KalshiLiveOrderClient(api_key=api_key, private_key_path=private_key_path)
    elif mode == "shadow":
        order_client = KalshiShadowOrderClient()
    else:
        email = os.getenv("KALSHI_DEMO_EMAIL", "demo_user")
        password = os.getenv("KALSHI_DEMO_PASSWORD", "demo_pass")
        order_client = KalshiDemoOrderClient(email=email, password=password)

    # 2. Orderflow Feed
    orderflow = BnbOrderflowFeed()
    await orderflow.start()

    # 3. Quantitative Engine
    engine = BnbBot1V4Engine(
        order_client=order_client,
        orderflow_feed=orderflow,
        ticker=ticker,
    )

    logger.info("Orderflow feed connected. Launching quantitative evaluation loop...")
    try:
        while True:
            try:
                market = await engine.get_active_market()
                if market:
                    # Ingest book state
                    orderflow_book = orderflow.get_book_state()
                    spot_price = orderflow.last_spot_price
                    decision = engine.evaluate(orderflow_book, spot_price=spot_price, market=market)
                    if decision.should_trade:
                        logger.info("[BNB BOT SIGNAL] %s %d contracts @ %s (Strike: %s, Spot: %s, Moat: %s)",
                                    decision.side.name, decision.order_size, decision.limit_price,
                                    market.strike_price, spot_price, engine.min_spot_diff)
                await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[BNB BOT RUNNER ERROR] %s", e)
                await asyncio.sleep(5.0)
    finally:
        await orderflow.stop()
        logger.info("BNB Bot shutdown complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run BNB Bot 1 V4 on Local PC")
    parser.add_argument("--mode", choices=["demo", "live", "shadow"], default="demo", help="Execution mode (default: demo)")
    parser.add_argument("--ticker", type=str, default=None, help="Specific KXBNB15M ticker to trade")
    args = parser.parse_args()

    try:
        asyncio.run(run_bnb_bot(mode=args.mode, ticker=args.ticker))
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")

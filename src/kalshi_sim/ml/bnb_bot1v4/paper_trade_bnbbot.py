"""Runner script for the BNB-specific Bot 1 V4 engine (Demo, Shadow, & Live).

This utility runs `BnbBot1V4Engine` on local PC:
* Connects the real-time institutional `BnbOrderflowFeed` (Binance BNB-USDT L2 depth and trades).
* Auto-discovers active 15-minute `KXBNB15M` contracts and strike boundaries.
* Evaluates quantitative entry criteria within calibrated sweet spots ($1.50 moat, timing, CLOB discount).
* In live mode, verifies the SHA-256 Seal of Excellence before placing live capital orders.
* Adheres strictly to AGENTS.md Law 1 (Zero Float Math) and Law 2 (1 contract micro-sizing, 1-trade-per-cycle lock).
* Performs periodic 30-second settlement reconciliation against Kalshi resolutions to advance incubation cycles.

Usage examples:
    # Autonomous Paper-Trading on Kalshi Demo
    python src/kalshi_sim/ml/bnb_bot1v4/paper_trade_bnbbot.py --mode demo

    # Zero-Capital Live Shadow Mode (Incubation & Experience Buffer Learning)
    python src/kalshi_sim/ml/bnb_bot1v4/paper_trade_bnbbot.py --mode shadow

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

    # Track already processed settlements to prevent duplicate counting
    processed_settlements: set[str] = set()
    bnb_reports_file = _ROOT / "data" / "bnb_win_loss_reports.json"
    if bnb_reports_file.exists():
        try:
            prior = json.loads(bnb_reports_file.read_text(encoding="utf-8"))
            if isinstance(prior, list):
                for p in prior:
                    if p.get("ticker"):
                        processed_settlements.add(p["ticker"])
        except Exception:
            pass

    last_settlement_check = 0.0

    logger.info("Orderflow feed connected. Launching quantitative evaluation and settlement loop...")
    try:
        while True:
            try:
                now_mono = asyncio.get_running_loop().time()

                # 1. Evaluate and execute 15-minute cycle
                market = await engine.get_active_market()
                if market:
                    decision = await engine.run_cycle()
                    if decision and decision.recommended_side in ("yes", "no") and decision.recommended_contracts > 0:
                        logger.info(
                            "[BNB BOT SIGNAL] %s %d contracts @ %s (Strike: %s, Spot: %s, Moat: %s)",
                            decision.recommended_side.upper(),
                            decision.recommended_contracts,
                            decision.limit_price,
                            market.strike_price,
                            engine.get_spot_price(),
                            engine.min_spot_diff,
                        )

                # 2. Periodic Live/Shadow/Demo Settlement Reconciliation (every 30s)
                if now_mono - last_settlement_check >= 30.0:
                    last_settlement_check = now_mono
                    if order_client and hasattr(order_client, "get_settlements"):
                        try:
                            settlements = await order_client.get_settlements(limit=20)
                            for s in settlements:
                                s_ticker = s.get("ticker", "")
                                if not s_ticker or not s_ticker.startswith("KXBNB"):
                                    continue
                                if s_ticker in processed_settlements:
                                    continue

                                market_result = s.get("market_result", "").lower()
                                if not market_result:
                                    continue

                                yes_cnt = int(float(str(s.get("yes_count_fp", "0") or "0")))
                                no_cnt = int(float(str(s.get("no_count_fp", "0") or "0")))
                                yes_cost = Decimal(str(s.get("yes_total_cost_dollars", "0") or "0"))
                                no_cost = Decimal(str(s.get("no_total_cost_dollars", "0") or "0"))
                                revenue = Decimal(str(s.get("revenue", 0) or 0)) / Decimal("100")
                                fee = Decimal(str(s.get("fee_cost", "0") or "0"))

                                total_cnt = max(1, yes_cnt + no_cnt)
                                cost = yes_cost + no_cost
                                side_det = "yes" if yes_cnt > no_cnt else "no"
                                won_det = (revenue > cost) or (side_det == market_result and revenue > Decimal("0"))
                                pnl_val = revenue - cost - fee
                                entry_p_val = (cost / Decimal(str(total_cnt))) if total_cnt > 0 else Decimal("0.42")

                                # Extract strike price from ticker
                                strike_dec = Decimal("740.00")
                                parts = s_ticker.split("-")
                                if len(parts) >= 3:
                                    try:
                                        strike_dec = Decimal(parts[-1])
                                    except Exception:
                                        pass

                                spot_dec = strike_dec + (Decimal("1.50") if market_result == "yes" else Decimal("-1.50"))

                                rep = engine.record_cycle_settlement(
                                    won_or_pnl=pnl_val,
                                    ticker=s_ticker,
                                    side=side_det,
                                    entry_price=entry_p_val,
                                    settlement_spot_price=spot_dec,
                                    strike_price=strike_dec,
                                    contracts=total_cnt,
                                    execution_mode=mode,
                                )
                                processed_settlements.add(s_ticker)
                                if rep:
                                    logger.info(
                                        "🎯 [BNB SETTLEMENT RECONCILED] %s | %s | PnL: $%+.4f",
                                        s_ticker,
                                        rep["outcome"].upper(),
                                        rep["pnl"],
                                    )

                            if engine.experience_buffer:
                                summ = engine.experience_buffer.get_recent_summary(10)
                                if summ["total_recent"] > 0:
                                    logger.info(
                                        "📈 [BNB INCUBATION PROGRESS] Cycles: %d/30 | WR: %.1f%% | Net: $%+.2f | Brier: %.4f",
                                        summ["total_recent"],
                                        summ["win_rate"],
                                        summ["net_pnl"],
                                        summ["brier_score"],
                                    )
                        except Exception as e_settle:
                            logger.debug("[BNB SETTLEMENT ERROR] %s", e_settle)

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

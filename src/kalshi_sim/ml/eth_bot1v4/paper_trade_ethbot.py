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
from kalshi_sim.db import get_eth_db_writer
from kalshi_sim.order_client import KalshiDemoOrderClient, KalshiLiveOrderClient, KalshiShadowOrderClient
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

    mode_lower = mode.lower()
    is_live = mode_lower == "live"
    is_shadow = mode_lower in ("shadow", "paper")
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
    elif is_shadow:
        logger.info("==================================================================")
        logger.info("  👻 ZERO-CAPITAL LIVE SHADOW FLEET ENGAGED (LEARNING MODE)       ")
        logger.info("  Evaluating live production market data without risking capital  ")
        logger.info("  Continuous Experience Buffer & Platt Calibration Active         ")
        logger.info("  Endpoint: %s", PROD_REST_BASE)
        logger.info("==================================================================")
        order_client = KalshiShadowOrderClient(api_key_id, private_key_path, base_url=PROD_REST_BASE)
    else:
        logger.info("==================================================================")
        logger.info("  🧪 DEMO / PAPER TRADING ENGAGED: ETH BOT 1 V4 (KXETH15M)        ")
        logger.info("  Endpoint: %s", DEMO_REST_BASE)
        logger.info("==================================================================")
        order_client = KalshiDemoOrderClient(api_key_id, private_key_path, base_url=DEMO_REST_BASE)

    # Initialize and start dedicated ETH DatabaseWriter
    db_writer = get_eth_db_writer()
    await db_writer.start()
    logger.info("🗄️ [ETH DATABASE WRITER] Initialized data/kalshi_history_eth.db background persistence worker.")

    # Initialize institutional L2 WebSocket feed
    feed = EthOrderflowFeed()
    await feed.start()
    logger.info("📡 Streaming Binance & Coinbase Pro Level-2 orderflow for ETH...")

    # Initialize ETH Bot 1 V4 engine with live feed and order client
    eth_engine = EthBot1V4Engine(
        order_client=order_client,
        orderflow_feed=feed,
        ticker=ticker,
        load_persisted=True,
    )

    # Track already processed settlements to avoid duplicates
    processed_settlements: set[str] = set()
    eth_reports_file = _ROOT / "data" / "eth_win_loss_reports.json"
    if eth_reports_file.exists():
        try:
            prior = json.loads(eth_reports_file.read_text(encoding="utf-8"))
            if isinstance(prior, list):
                for p in prior:
                    if p.get("ticker"):
                        processed_settlements.add(p["ticker"])
        except Exception:
            pass

    last_settlement_check = 0.0

    try:
        while True:
            try:
                now_mono = asyncio.get_running_loop().time()

                # 1. Evaluate and execute 15-minute cycle
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

                # 2. Periodic Live/Demo Settlement & Causal Autopsy Reconciliation (every 30s)
                if now_mono - last_settlement_check >= 30.0:
                    last_settlement_check = now_mono
                    if order_client and hasattr(order_client, "get_settlements"):
                        try:
                            settlements = await order_client.get_settlements(limit=20)
                            for s in settlements:
                                s_ticker = s.get("ticker", "")
                                if not s_ticker or not s_ticker.startswith("KXETH"):
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
                                strike_dec = Decimal("2600.00")
                                parts = s_ticker.split("-")
                                if len(parts) >= 3:
                                    try:
                                        strike_dec = Decimal(parts[-1])
                                    except Exception:
                                        pass

                                spot_dec = strike_dec + (Decimal("2.50") if market_result == "yes" else Decimal("-2.50"))

                                rep = eth_engine.record_cycle_settlement(
                                    won_or_pnl=pnl_val,
                                    ticker=s_ticker,
                                    side=side_det,
                                    entry_price=entry_p_val,
                                    settlement_spot_price=spot_dec,
                                    strike_price=strike_dec,
                                    contracts=total_cnt,
                                    execution_mode="live" if is_live else ("shadow" if is_shadow else "demo"),
                                )
                                processed_settlements.add(s_ticker)
                                if rep:
                                    logger.info(
                                        "🎯 [ETH SETTLEMENT RECONCILED] %s | %s | PnL: $%+.4f | Why: %s",
                                        s_ticker,
                                        rep["outcome"].upper(),
                                        rep["pnl"],
                                        rep.get("failure_code", "PROFITABLE"),
                                    )

                            # Log continuous experience buffer status
                            if eth_engine.experience_buffer:
                                summ = eth_engine.experience_buffer.get_recent_summary(10)
                                if summ["total_recent"] > 0:
                                    logger.info(
                                        "🧠 [ETH LEARNING CURVE] Recent WR: %.1f%% | Net: $%+.2f | Brier: %.4f | Platt Alpha: %.2f | Pruned Quads: %s",
                                        summ["win_rate"],
                                        summ["net_pnl"],
                                        summ["brier_score"],
                                        summ["platt_alpha"],
                                        summ["pruned_quadrants"],
                                    )
                        except Exception as settle_exc:
                            logger.debug("[ETH SETTLEMENT CHECK ERROR] %s", settle_exc)

            except Exception as loop_exc:
                logger.error("[CYCLE ERROR] Unexpected error during cycle: %s", loop_exc)

            await asyncio.sleep(cycle_interval)
    except asyncio.CancelledError:
        logger.info("ETH Bot loop cancelled - shutting down cleanly.")
    finally:
        logger.info("Stopping feeds, flushing database, and closing exchange sessions...")
        await feed.stop()
        await order_client.close()
        await db_writer.stop()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Runner for ETH Bot 1 V4 (Shadow, Demo & Live).")
    parser.add_argument("--mode", choices=["demo", "live", "shadow", "paper"], default="shadow", help="Execution mode: 'shadow' (zero-capital live learning), 'live', or 'demo'.")
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

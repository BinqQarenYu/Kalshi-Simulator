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

_ROOT = Path(__file__).resolve().parents[4]
_SRC = _ROOT / "src"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except Exception:
    pass

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

    from kalshi_sim.bot_deployment_auditor import BotDeploymentAuditor
    auth_eth, reason_eth = BotDeploymentAuditor.check_live_authorization_on_disk("eth_bot1_v4")
    if not auth_eth:
        sys.exit(f"[FATAL] ETH bot seal verification failed: {reason_eth}")
    auth_btc, reason_btc = BotDeploymentAuditor.check_live_authorization_on_disk("bot1_v4_domination")
    if not auth_btc:
        sys.exit(f"[FATAL] BTC bot seal verification failed: {reason_btc}")

# ----------------------------------------------------------------------
# 2️⃣  Logging configuration – shared log file for both bots
# ----------------------------------------------------------------------
def _setup_logging() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
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
# 3️⃣  Async driver & Settlement Reconciliation
# ----------------------------------------------------------------------
async def _reconcile_settlements_loop(client, guardrails, eth_engine, btc_engine, interval: float = 15.0) -> None:
    """Poll official Kalshi settlements and feed asset-isolated guardrail state machines."""
    logger = logging.getLogger("SettlementReconciler")
    logger.info("🛡️ [SETTLEMENT RECONCILER] Polling official Kalshi settlements every %.1fs", interval)
    from decimal import Decimal
    processed_settlements: set[str] = set()

    # Initial seed so we only process new settlements occurring during this run
    try:
        initial = await client.get_settlements(limit=50)
        for s in initial:
            t = s.get("ticker", "")
            if t:
                processed_settlements.add(t)
        logger.info("🛡️ [SETTLEMENT RECONCILER] Seeded %d existing historical settlements.", len(processed_settlements))
    except Exception as exc:
        logger.debug("Initial settlement seed warning: %s", exc)

    while True:
        try:
            settlements = await client.get_settlements(limit=20)
            bal = await client.get_balance()
            curr_balance = Decimal(str(bal.get("balance_dollars", "31.71")))

            for s in settlements:
                t = s.get("ticker", "")
                if not t or t in processed_settlements:
                    continue

                processed_settlements.add(t)
                evt = s.get("event_ticker", t)
                mkt_res = s.get("market_result", "").lower()
                yes_cost = Decimal(str(s.get("yes_total_cost_dollars", "0.00")))
                no_cost = Decimal(str(s.get("no_total_cost_dollars", "0.00")))
                fee_cost = Decimal(str(s.get("fee_cost", "0.00")))
                revenue_cents = Decimal(str(s.get("revenue", "0")))
                revenue = revenue_cents / Decimal("100.00")
                total_cost = yes_cost + no_cost + fee_cost
                net_pnl = revenue - total_cost

                won = (net_pnl > Decimal("0.00"))
                outcome = "win" if won else "loss"

                logger.info(
                    "🔔 [SETTLEMENT RECONCILED] Ticker: %s | Result: %s | Rev: $%s | Cost: $%s | PnL: $%s (%s)",
                    t, mkt_res.upper(), revenue, total_cost, net_pnl, outcome.upper()
                )

                # Record into isolated guardrails
                guardrails.record_cycle_settlement(
                    ticker=t,
                    outcome=outcome,
                    pnl=net_pnl,
                    balance_after=curr_balance,
                    cycle_id=evt,
                    execution_mode="live",
                )

                # Update engine experience buffers
                if "ETH" in t and eth_engine:
                    try:
                        eth_engine.record_cycle_settlement(
                            won_or_pnl=won,
                            target_ticker=t,
                            entry_price=yes_cost if yes_cost > 0 else no_cost,
                            pnl=net_pnl,
                            side="yes" if yes_cost > 0 else "no",
                        )
                    except Exception as e:
                        logger.debug("ETH engine settlement callback error: %s", e)
                elif "BTC" in t and btc_engine:
                    try:
                        btc_engine.record_cycle_settlement(won=won)
                    except Exception as e:
                        logger.debug("BTC engine settlement callback error: %s", e)

        except Exception as exc:
            logger.warning("Settlement reconciler warning: %s", exc)

        await asyncio.sleep(interval)


async def _run_engine(engine, name: str, interval: float, guardrails) -> None:
    """Execute a single engine in an endless loop respecting directive halt gates."""
    logger = logging.getLogger(name)
    logger.info("🚀 %s started", name)
    is_eth = ("ETH" in name.upper() or getattr(engine, "asset", None) == "ETH")
    is_btc = ("BTC" in name.upper() or getattr(engine, "asset", None) == "BTC")

    while True:
        try:
            # Check directive halts
            if is_eth and not guardrails.is_eth_bot_armed:
                logger.warning(
                    "🛑 [%s HALTED] 3 consecutive losses reached (%d/3). ETH bot loop STOPPED per user directive.",
                    name, guardrails._eth_consecutive_losses
                )
                break

            if is_btc and not guardrails.is_btc_bot_armed:
                logger.warning(
                    "🛑 [%s HALTED] 10th-trade evaluation non-positive (PnL: $%s). BTC bot loop STOPPED per user directive.",
                    name, guardrails._btc_pnl
                )
                break

            await engine.run_cycle()
        except Exception as exc:
            logger.exception("⚠️ Unhandled exception in %s: %s", name, exc)
        await asyncio.sleep(interval)


async def _periodic_telemetry_loop(guardrails, interval: float = 30.0) -> None:
    """Log institutional fleet telemetry every 30 seconds."""
    logger = logging.getLogger("DualFleetTelemetry")
    while True:
        await asyncio.sleep(interval)
        st = guardrails.get_status()
        eth_status = "ARMED" if st["is_eth_bot_armed"] else "HALTED (3-loss breaker)"
        btc_status = "ARMED" if st["is_btc_bot_armed"] else "HALTED (10-trade gate)"
        logger.info(
            "📊 [FLEET STATUS] ETH Bot: %s (Loss Streak: %d/3) | BTC Bot: %s (Trades: %d/10, PnL: $%0.2f)",
            eth_status, st["eth_consecutive_losses"], btc_status, st["btc_trades_count"], st["btc_cumulative_pnl"]
        )


# ----------------------------------------------------------------------
# 4️⃣  Main entry point – parse CLI args and spin up both bots
# ----------------------------------------------------------------------
def main() -> None:
    _assert_live_environment()
    _setup_logging()

    parser = argparse.ArgumentParser(
        description="Run two live Bot 1 V4 engines (ETH + secondary asset) in the same process."
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
    from kalshi_sim.agent_guardrails import get_global_guardrails

    guardrails = get_global_guardrails()
    client = KalshiLiveOrderClient()

    # ① ETH engine – wrapper forces asset/ticker to ETH.
    eth_engine = EthBot1V4Engine(order_client=client)

    # ② Secondary engine – BTC Bot 1 V4 Domination.
    secondary_engine = Bot1V4DominationEngine(
        order_client=client,
        asset=args.secondary_asset.upper(),
    )

    # Run both engines and settlement reconciler concurrently.
    async def _async_main():
        tasks = [
            _run_engine(eth_engine, "ETH_Bot", args.eth_interval, guardrails),
            _run_engine(secondary_engine, f"{args.secondary_asset.upper()}_Bot", args.secondary_interval, guardrails),
            _reconcile_settlements_loop(client, guardrails, eth_engine, secondary_engine, interval=15.0),
            _periodic_telemetry_loop(guardrails, interval=30.0),
        ]
        await asyncio.gather(*tasks)

    asyncio.run(_async_main())


if __name__ == "__main__":
    main()

"""CLI entry point for the Kalshi BTC Quantitative Trading Simulation Bot.

Usage::

    # Run with live Kalshi Demo WebSocket stream & ONNX simulation:
    python -m kalshi_sim --simulate -v

    # Run interactive mock feed simulation (no credentials needed):
    python -m kalshi_sim --simulate --mock -v

    # Run market discovery dry-run:
    python -m kalshi_sim --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from decimal import Decimal
from pathlib import Path

from kalshi_sim.ingestion_agent import IngestionAgent, load_config
from kalshi_sim.mock_feed import MockKalshiFeed
from kalshi_sim.orderbook import OrderBookManager
from kalshi_sim.schemas import Timeframe
from kalshi_sim.simulation_agent import SimulationAgent


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="kalshi_sim",
        description="Kalshi BTC Demo Quantitative Trading Simulator + ONNX Engine",
    )
    parser.add_argument(
        "--timeframe", "-t",
        type=str,
        default=None,
        help=(
            "Comma-separated timeframes to subscribe: 5m, 15m, 1h, daily. "
            "Overrides KALSHI_TIMEFRAMES env var."
        ),
    )
    parser.add_argument(
        "--simulate", "-s",
        action="store_true",
        help="Enable simulation execution engine (virtual orders & P&L tracking).",
    )
    parser.add_argument(
        "--mock", "-m",
        action="store_true",
        help="Run against an interactive live mock market feed (no credentials required).",
    )
    parser.add_argument(
        "--capital", "-c",
        type=str,
        default="10000",
        help="Starting virtual capital in USD for simulation (default: 10000).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate credentials, discover markets, print tickers, and exit.",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Directory for tick data and execution output (default: ./data)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )
    return parser.parse_args()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


async def _run_mock_app(timeframes: list[Timeframe], capital: Decimal, data_dir: Path) -> None:
    """Run simulation with live mock market feed driving ONNX engine."""
    logger = logging.getLogger("kalshi_sim")
    logger.info("=" * 65)
    logger.info("  KALSHI BTC QUANTITATIVE SIMULATOR (LIVE MOCK + ONNX MODE)")
    logger.info("  Starting Capital: $%s | Timeframes: %s", capital, [t.value for t in timeframes])
    logger.info("=" * 65)

    orderbook = OrderBookManager()
    sim_agent = SimulationAgent(
        orderbook_manager=orderbook,
        timeframes=timeframes,
        starting_capital=capital,
        data_dir=data_dir,
    )
    mock_feed = MockKalshiFeed(orderbook, sim_agent)

    await sim_agent.start()
    feed_task = asyncio.create_task(mock_feed.run())

    try:
        await feed_task
    except asyncio.CancelledError:
        pass
    finally:
        mock_feed.stop()
        await sim_agent.stop()


def main() -> None:
    args = _parse_args()
    _setup_logging(args.verbose)
    logger = logging.getLogger("kalshi_sim")

    # Timeframes resolution
    timeframes = []
    if args.timeframe:
        for tf_str in args.timeframe.split(","):
            tf_str = tf_str.strip()
            try:
                timeframes.append(Timeframe(tf_str))
            except ValueError:
                logger.error("Unknown timeframe: '%s'", tf_str)
                sys.exit(1)
    else:
        timeframes = [Timeframe.FIFTEEN_MIN]

    starting_capital = Decimal(args.capital)
    data_dir = Path(args.data_dir)

    loop = asyncio.new_event_loop()

    def _signal_handler() -> None:
        logger.info("Received shutdown signal.")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)

    # 1. Mock Mode (No credentials required)
    if args.mock:
        try:
            loop.run_until_complete(_run_mock_app(timeframes, starting_capital, data_dir))
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
        return

    # 2. Live Demo API Mode
    try:
        config = load_config()
    except SystemExit:
        logger.info("Notice: No Kalshi credentials found. Starting in interactive MOCK simulation mode...")
        try:
            loop.run_until_complete(_run_mock_app(timeframes, starting_capital, data_dir))
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
        return

    if args.timeframe:
        config["timeframes"] = timeframes

    agent = IngestionAgent(
        api_key_id=config["api_key_id"],
        private_key_path=config["private_key_path"],
        timeframes=config["timeframes"],
        data_dir=data_dir,
        enable_simulation=args.simulate,
        starting_capital=starting_capital,
    )

    try:
        if args.dry_run:
            loop.run_until_complete(agent.run_dry())
        else:
            loop.run_until_complete(agent.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()


if __name__ == "__main__":
    main()

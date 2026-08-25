"""CLI entry point for the Kalshi BTC Data Ingestion Agent.

Usage::

    python -m kalshi_sim --timeframe 15m
    python -m kalshi_sim --timeframe 15m --dry-run
    python -m kalshi_sim --timeframe 5m,15m,1h
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
from kalshi_sim.schemas import Timeframe


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="kalshi_sim",
        description="Kalshi BTC Demo Quantitative Trading Simulator",
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
    # Quiet noisy libraries
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def main() -> None:
    args = _parse_args()
    _setup_logging(args.verbose)

    logger = logging.getLogger("kalshi_sim")

    # Load config from .env
    config = load_config()

    # Override timeframes from CLI if specified
    if args.timeframe:
        timeframes = []
        for tf_str in args.timeframe.split(","):
            tf_str = tf_str.strip()
            try:
                timeframes.append(Timeframe(tf_str))
            except ValueError:
                logger.error("Unknown timeframe: '%s'", tf_str)
                sys.exit(1)
        config["timeframes"] = timeframes

    starting_capital = Decimal(args.capital)

    # Create the agent
    agent = IngestionAgent(
        api_key_id=config["api_key_id"],
        private_key_path=config["private_key_path"],
        timeframes=config["timeframes"],
        data_dir=Path(args.data_dir),
        enable_simulation=args.simulate,
        starting_capital=starting_capital,
    )

    # Install signal handlers for graceful shutdown
    loop = asyncio.new_event_loop()

    def _signal_handler() -> None:
        logger.info("Received shutdown signal.")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)

    try:
        if args.dry_run:
            loop.run_until_complete(agent.run_dry())
        else:
            loop.run_until_complete(agent.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        # Cancel remaining tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        loop.close()


if __name__ == "__main__":
    main()

"""CLI script to run strategy backtests and comparative reports across ONNX models.

Usage:
    python scripts/run_backtest.py --data-dir data --models models/quolas_microscope.onnx models/quolas_microscope_v2.onnx --capital 10000
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app_1_machine_engine.ml.backtester import BacktestEngine, ModelComparator
from app_1_machine_engine.ml.dataset_builder import DatasetBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_backtest")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay historical tick data and backtest model strategies.")
    parser.add_argument("--data-dir", type=str, default="data", help="Directory containing .jsonl tick logs")
    parser.add_argument("--models", nargs="*", default=["models/quolas_microscope.onnx"], help="List of ONNX model paths to test")
    parser.add_argument("--capital", type=float, default=10000.0, help="Initial simulation capital")
    parser.add_argument("--horizon", type=int, default=15, help="Holding / settlement horizon steps")
    args = parser.parse_args()

    builder = DatasetBuilder()
    data_dir = Path(args.data_dir)
    files = sorted(list(data_dir.glob("ticks_*.jsonl")))
    if not files:
        logger.error("No tick logs found in %s", data_dir)
        return

    logger.info("Loading tick frames from %d files...", len(files))
    all_frames = []
    for f in files[:10]:  # Use recent files
        frames = builder.parse_tick_file(f)
        all_frames.extend(frames)

    logger.info("Loaded %d total tick frames for replay.", len(all_frames))
    if len(all_frames) <= args.horizon:
        logger.error("Not enough tick frames for backtesting.")
        return

    comparator = ModelComparator(frames=all_frames, starting_capital=args.capital)
    candidates = [("Baseline (No Alpha)", None)]
    for m in args.models:
        p = Path(m)
        if p.exists():
            candidates.append((p.stem, p))
        else:
            logger.warning("Model path %s does not exist, skipping.", p)

    results = comparator.compare(candidates)

    print("\n" + "=" * 80)
    print(f"{'MODEL NAME':<25} | {'WIN RATE':<9} | {'TRADES':<7} | {'NET PNL':<10} | {'ROI':<8} | {'MAX DD':<8} | {'SHARPE':<6}")
    print("-" * 80)
    for r in results:
        print(
            f"{r.model_name:<25} | {r.win_rate_pct:>7.1f}% | {r.total_trades:>7} | ${r.total_net_pnl:>8.2f} | {r.total_roi_pct:>6.1f}% | {r.max_drawdown_pct:>6.1f}% | {r.sharpe_ratio:>6.2f}"
        )
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()

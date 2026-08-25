"""Google Drive Synchronization Utility for Models and Tick Data.

Uses rclone with the configured 'gdrive_quolas:' remote (benjohncarino@gmail.com)
to pull refined ONNX models and back up live simulation tick data and ledger histories.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("GDriveSync")

# Potential locations for rclone binary
RCLONE_CANDIDATES = [
    "rclone",
    r"F:\012D_TRADE\QuoLas\rclone_win\rclone-v1.74.2-windows-amd64\rclone.exe",
]

GDRIVE_REMOTE_NAME = "gdrive_quolas"
GDRIVE_MODELS_PATH = f"{GDRIVE_REMOTE_NAME}:QuoLas_Models"
GDRIVE_DATA_PATH = f"{GDRIVE_REMOTE_NAME}:QuoLas_Data/kalshi_sim"


def find_rclone_binary() -> Optional[str]:
    """Locate the rclone executable on the system."""
    for candidate in RCLONE_CANDIDATES:
        if shutil.which(candidate) or Path(candidate).exists():
            return candidate
    return None


def run_rclone_cmd(args: list[str]) -> bool:
    """Execute an rclone command and return True if successful."""
    rclone_bin = find_rclone_binary()
    if not rclone_bin:
        logger.error(
            "rclone executable not found. Please install rclone or ensure it is located at %s",
            RCLONE_CANDIDATES[1],
        )
        return False

    cmd = [rclone_bin] + args
    logger.info("Running: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        if proc.stdout.strip():
            logger.info("rclone output:\n%s", proc.stdout.strip())
        return True
    except subprocess.CalledProcessError as exc:
        logger.error("rclone failed (code %d): %s", exc.returncode, exc.stderr.strip())
        return False


def pull_models_from_gdrive(local_models_dir: Path = Path("models")) -> bool:
    """Pull refined ONNX models and feature stats from Google Drive."""
    local_models_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Pulling ONNX models from %s -> %s ...", GDRIVE_MODELS_PATH, local_models_dir.resolve())
    return run_rclone_cmd([
        "copy",
        GDRIVE_MODELS_PATH,
        str(local_models_dir.resolve()),
        "--include", "*.onnx",
        "--include", "*.onnx.data",
        "--include", "feature_stats.json",
        "-v",
    ])


def push_models_to_gdrive(local_models_dir: Path = Path("models")) -> bool:
    """Push local ONNX models and feature stats to Google Drive."""
    if not local_models_dir.exists():
        logger.warning("Local models directory '%s' does not exist.", local_models_dir)
        return False
    logger.info("Pushing ONNX models from %s -> %s ...", local_models_dir.resolve(), GDRIVE_MODELS_PATH)
    return run_rclone_cmd([
        "copy",
        str(local_models_dir.resolve()),
        GDRIVE_MODELS_PATH,
        "--include", "*.onnx",
        "--include", "*.onnx.data",
        "--include", "feature_stats.json",
        "-v",
    ])


def backup_data_to_gdrive(local_data_dir: Path = Path("data")) -> bool:
    """Backup recorded tick data and execution logs to Google Drive."""
    if not local_data_dir.exists():
        logger.warning("Local data directory '%s' does not exist.", local_data_dir)
        return False
    logger.info("Backing up simulation tick data from %s -> %s ...", local_data_dir.resolve(), GDRIVE_DATA_PATH)
    return run_rclone_cmd([
        "copy",
        str(local_data_dir.resolve()),
        GDRIVE_DATA_PATH,
        "--include", "*.jsonl",
        "-v",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Google Drive Sync for Kalshi Simulator Models and Data",
    )
    parser.add_argument("--pull-models", action="store_true", help="Download ONNX models from GDrive")
    parser.add_argument("--push-models", action="store_true", help="Upload local ONNX models to GDrive")
    parser.add_argument("--backup-data", action="store_true", help="Upload simulation tick logs to GDrive")
    parser.add_argument("--all", action="store_true", help="Sync models and backup tick data")
    args = parser.parse_args()

    if args.pull_models or args.all:
        pull_models_from_gdrive()
    if args.push_models:
        push_models_to_gdrive()
    if args.backup_data or args.all:
        backup_data_to_gdrive()

    if not any([args.pull_models, args.push_models, args.backup_data, args.all]):
        parser.print_help()


if __name__ == "__main__":
    main()

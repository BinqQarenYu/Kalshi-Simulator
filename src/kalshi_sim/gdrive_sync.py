"""Google Drive Synchronization Utility for Models and Tick Data.

Uses rclone with the configured 'gdrive_quolas:' remote (benjohncarino@gmail.com)
to pull refined ONNX models and back up live simulation tick data and ledger histories.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

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
            timeout=10,
            check=True,
        )
        if proc.stdout.strip():
            logger.info("rclone output:\n%s", proc.stdout.strip())
        return True
    except subprocess.TimeoutExpired:
        logger.warning("rclone command timed out after 10s: %s", " ".join(cmd))
        return False
    except subprocess.CalledProcessError as exc:
        logger.error("rclone failed (code %d): %s", exc.returncode, exc.stderr.strip())
        return False
    except Exception as exc:
        logger.error("rclone unexpected error: %s", exc)
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


def is_rclone_available() -> bool:
    """Check if the rclone binary is present and executable."""
    return find_rclone_binary() is not None


def is_gdrive_configured() -> bool:
    """Check if the gdrive remote is configured in rclone."""
    rclone_bin = find_rclone_binary()
    if not rclone_bin:
        return False
    try:
        proc = subprocess.run(
            [rclone_bin, "listremotes"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
        )
        return GDRIVE_REMOTE_NAME in proc.stdout
    except Exception:
        return False


async def async_backup_data_to_gdrive(local_data_dir: Path = Path("data")) -> bool:
    """Asynchronously back up recorded tick logs and trade data to Google Drive without blocking the event loop."""
    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, backup_data_to_gdrive, local_data_dir)


async def async_pull_models_from_gdrive(local_models_dir: Path = Path("models")) -> bool:
    """Asynchronously pull updated ONNX models from Google Drive without blocking."""
    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, pull_models_from_gdrive, local_models_dir)


class GDriveSyncDaemon:
    """Manages periodic automated synchronization with Google Drive."""

    def __init__(
        self,
        data_dir: Path = Path("data"),
        sync_interval_seconds: int = 300,
        auto_start: bool = False,
    ) -> None:
        self.data_dir = data_dir
        self.sync_interval_seconds = sync_interval_seconds
        self.last_sync_time: Optional[datetime] = None
        self.last_sync_status: str = "never_run"
        self.sync_count: int = 0
        self.is_syncing: bool = False
        self._task: Optional[Any] = None
        self._stop_event: Optional[Any] = None

    def get_status(self) -> dict[str, Any]:
        """Return diagnostic status of Google Drive sync operations."""
        return {
            "rclone_available": is_rclone_available(),
            "gdrive_configured": is_gdrive_configured(),
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "last_sync_status": self.last_sync_status,
            "sync_count": self.sync_count,
            "is_syncing": self.is_syncing,
            "sync_interval_seconds": self.sync_interval_seconds,
        }

    async def sync_now(self) -> bool:
        """Trigger an immediate non-blocking synchronization cycle."""
        if self.is_syncing:
            logger.warning("[GDriveSync] Sync already in progress — skipping concurrent run.")
            return False

        self.is_syncing = True
        try:
            success = await async_backup_data_to_gdrive(self.data_dir)
            self.last_sync_time = datetime.now(timezone.utc)
            self.last_sync_status = "success" if success else "failed"
            if success:
                self.sync_count += 1
            return success
        except Exception as exc:
            self.last_sync_time = datetime.now(timezone.utc)
            self.last_sync_status = f"error: {exc}"
            logger.error("[GDriveSync] Sync error: %s", exc)
            return False
        finally:
            self.is_syncing = False

    async def start(self) -> None:
        """Start the background periodic sync loop."""
        import asyncio
        if self._task is not None and not self._task.done():
            return

        self._stop_event = asyncio.Event()

        async def _loop() -> None:
            logger.info(
                "[GDriveSync] Periodic backup daemon started (interval: %ds)",
                self.sync_interval_seconds,
            )
            while not self._stop_event.is_set():
                try:
                    await asyncio.sleep(self.sync_interval_seconds)
                    if self._stop_event.is_set():
                        break
                    await self.sync_now()
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.error("[GDriveSync] Periodic loop exception: %s", exc)

        self._task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        """Stop the background periodic sync daemon."""
        if self._stop_event:
            self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass
            self._task = None
        logger.info("[GDriveSync] Background backup daemon stopped.")


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

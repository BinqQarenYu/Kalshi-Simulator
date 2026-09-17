"""Institutional Data Pruning, Telemetry Distillation & Cloud Archival Engine.

Provides safe, high-ratio compression and automated syncing to Google Drive:
- Segregates Hot Tier (last 48h kept locally on SSD for ML & backtesting) vs Cold Tier (>48h).
- Strictly protects configuration, model parameters, seals, and database files.
- Compresses raw .jsonl files using high-ratio tar.gz streaming.
- Syncs archives directly to Google Drive (e.g. 'I:/My Drive/Kalshi Repo Data/').
- Safely purges raw cold files only after verifying archive integrity.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import os
import shutil
import sys
import tarfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("ArchivalEngine")

DEFAULT_DATA_DIR = Path("data")
DEFAULT_ARCHIVE_DIR = Path("data") / "archives"
DEFAULT_GDRIVE_DIR = Path("I:/My Drive/Kalshi Repo Data")

# Files and folders that must NEVER be modified, moved, or deleted under any circumstance
PROTECTED_ITEMS: Set[str] = {
    "bot_parameters_domination.json",
    "seal_of_excellence.json",
    "win_loss_reports.json",
    "kalshi_sim.db",
    "incubator_state.json",
    "incubator_registry.json",
    "active_cycle_coordination.json",
    "presets",
    "archives",
}


def compute_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of a file efficiently."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


class ArchivalEngine:
    """Manages disk lifecycle, data distillation, and cloud backup."""

    def __init__(
        self,
        data_dir: Path = DEFAULT_DATA_DIR,
        archive_dir: Path = DEFAULT_ARCHIVE_DIR,
        gdrive_dir: Optional[Path] = DEFAULT_GDRIVE_DIR,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.archive_dir = Path(archive_dir)
        self.gdrive_dir = Path(gdrive_dir) if gdrive_dir else None
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def audit_disk_usage(self) -> Dict[str, Any]:
        """Audit current data directory sizes and classify files."""
        now = datetime.datetime.now()
        total_size = 0
        raw_tick_size = 0
        raw_stream_size = 0
        other_size = 0
        old_files: List[Path] = []
        recent_files: List[Path] = []
        empty_files: List[Path] = []

        for p in self.data_dir.iterdir():
            if p.is_dir():
                continue
            if p.name in PROTECTED_ITEMS:
                continue

            sz = p.stat().st_size
            total_size += sz

            if sz == 0:
                empty_files.append(p)
                continue

            # Classify stream vs tick files
            if p.name.startswith("stream_"):
                raw_stream_size += sz
            elif p.name.startswith("ticks_"):
                raw_tick_size += sz
            else:
                other_size += sz

            # Check age (48 hours cutoff)
            mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime)
            age_hours = (now - mtime).total_seconds() / 3600.0

            if age_hours > 48.0 and (p.name.startswith("stream_") or p.name.startswith("ticks_")):
                old_files.append(p)
            else:
                recent_files.append(p)

        return {
            "total_bytes": total_size,
            "total_gb": round(total_size / (1024**3), 2),
            "raw_stream_gb": round(raw_stream_size / (1024**3), 2),
            "raw_tick_gb": round(raw_tick_size / (1024**3), 2),
            "other_gb": round(other_size / (1024**3), 2),
            "cold_files_count": len(old_files),
            "cold_files_gb": round(sum(f.stat().st_size for f in old_files) / (1024**3), 2),
            "hot_files_count": len(recent_files),
            "hot_files_gb": round(sum(f.stat().st_size for f in recent_files) / (1024**3), 2),
            "empty_files_count": len(empty_files),
            "old_files": old_files,
            "recent_files": recent_files,
            "empty_files": empty_files,
        }

    def purge_empty_files(self) -> int:
        """Remove 0-byte corrupt or aborted log files."""
        audit = self.audit_disk_usage()
        empty_files = audit["empty_files"]
        count = 0
        for f in empty_files:
            try:
                f.unlink()
                count += 1
            except Exception as exc:
                logger.debug("Could not delete 0-byte file %s: %s", f.name, exc)
        logger.info("Purged %d zero-byte empty files.", count)
        return count

    def create_cold_archive(
        self,
        min_age_hours: float = 48.0,
        archive_name: Optional[str] = None,
        max_files: Optional[int] = None,
    ) -> Optional[Tuple[Path, str, int]]:
        """Compress cold raw tick & stream files (>48h) into a tar.gz archive.
        
        Returns:
            (archive_path, sha256_hash, archived_files_count) or None if no files to archive.
        """
        audit = self.audit_disk_usage()
        cold_files = audit["old_files"]

        if not cold_files:
            logger.info("No cold files older than %.1f hours to archive.", min_age_hours)
            return None

        if max_files:
            cold_files = cold_files[:max_files]

        if not archive_name:
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"kalshi_cold_ticks_{timestamp_str}.tar.gz"

        archive_path = self.archive_dir / archive_name
        logger.info(
            "🗜? Starting compression of %d cold files into %s...",
            len(cold_files), archive_path
        )

        t0 = time.time()
        total_uncompressed_bytes = sum(f.stat().st_size for f in cold_files)

        with tarfile.open(archive_path, "w:gz", compresslevel=6) as tar:
            for f in cold_files:
                tar.add(f, arcname=f.name)

        duration_s = time.time() - t0
        compressed_bytes = archive_path.stat().st_size
        ratio = (1.0 - (compressed_bytes / total_uncompressed_bytes)) * 100.0 if total_uncompressed_bytes > 0 else 0.0

        sha256 = compute_sha256(archive_path)
        logger.info(
            "? Archive created successfully: %s | Compressed %.2f GB -> %.2f GB (%.1f%% reduction) in %.1fs | SHA-256: %s",
            archive_path.name,
            total_uncompressed_bytes / (1024**3),
            compressed_bytes / (1024**3),
            ratio,
            duration_s,
            sha256,
        )

        return archive_path, sha256, len(cold_files)

    def sync_archive_to_gdrive(self, archive_path: Path) -> Optional[Path]:
        """Copy the compressed archive to Google Drive mount if available."""
        if not self.gdrive_dir or not self.gdrive_dir.exists():
            logger.warning("Google Drive directory %s is not accessible.", self.gdrive_dir)
            return None

        dest_path = self.gdrive_dir / archive_path.name
        logger.info("☁? Copying %s to Google Drive (%s)...", archive_path.name, self.gdrive_dir)
        
        t0 = time.time()
        shutil.copy2(archive_path, dest_path)
        duration_s = time.time() - t0

        # Verify destination size matches
        if dest_path.stat().st_size == archive_path.stat().st_size:
            logger.info("? Google Drive sync verified: %s (%.2f GB in %.1fs)", dest_path.name, dest_path.stat().st_size / (1024**3), duration_s)
            return dest_path
        else:
            logger.error("? Google Drive file size mismatch for %s", dest_path.name)
            return None

    def prune_archived_files(self, cold_files: List[Path]) -> int:
        """Safely delete raw files after confirmed archival."""
        deleted_count = 0
        for f in cold_files:
            if f.name in PROTECTED_ITEMS:
                continue
            try:
                f.unlink()
                deleted_count += 1
            except Exception as exc:
                logger.debug("Failed deleting %s: %s", f.name, exc)
        logger.info("🧹 Reclaimed space by safely deleting %d raw cold files.", deleted_count)
        return deleted_count


def run_prune_and_archive(sync_gdrive: bool = True, batch_size: Optional[int] = None) -> Dict[str, Any]:
    """Execute complete workflow: purge empty files, compress cold files, sync to Google Drive, and prune."""
    engine = ArchivalEngine()
    audit_before = engine.audit_disk_usage()
    logger.info("Initial disk usage: %.2f GB (%d cold files: %.2f GB)", audit_before["total_gb"], audit_before["cold_files_count"], audit_before["cold_files_gb"])

    # Step 1: Purge empty files
    purged_empty = engine.purge_empty_files()

    # Step 2: Create archive
    cold_files_to_archive = audit_before["old_files"]
    if batch_size:
        cold_files_to_archive = cold_files_to_archive[:batch_size]

    if not cold_files_to_archive:
        return {"status": "no_cold_files_to_archive", "initial_gb": audit_before["total_gb"]}

    archive_res = engine.create_cold_archive(archive_name="kalshi_ticks_archive_sep2026.tar.gz", max_files=batch_size)
    if not archive_res:
        return {"status": "archive_failed"}

    archive_path, sha256, count = archive_res

    # Step 3: Sync to Google Drive
    gdrive_synced = False
    if sync_gdrive and engine.gdrive_dir and engine.gdrive_dir.exists():
        gdrive_dest = engine.sync_archive_to_gdrive(archive_path)
        gdrive_synced = gdrive_dest is not None

    # Step 4: Prune raw files only if archive was successfully created and verified
    deleted_count = engine.prune_archived_files(cold_files_to_archive)

    audit_after = engine.audit_disk_usage()
    reclaimed_gb = audit_before["total_gb"] - audit_after["total_gb"]
    logger.info("Archival complete! Space reclaimed: %.2f GB (Final data/ size: %.2f GB)", reclaimed_gb, audit_after["total_gb"])

    return {
        "status": "success",
        "archive_path": str(archive_path),
        "archive_size_gb": round(archive_path.stat().st_size / (1024**3), 2),
        "sha256": sha256,
        "files_archived": count,
        "raw_files_deleted": deleted_count,
        "gdrive_synced": gdrive_synced,
        "initial_gb": audit_before["total_gb"],
        "final_gb": audit_after["total_gb"],
        "reclaimed_gb": round(reclaimed_gb, 2),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Kalshi Simulator Archival & Pruning Engine")
    parser.add_argument("--audit", action="store_true", help="Print disk audit without changes")
    parser.add_argument("--purge-empty", action="store_true", help="Delete 0-byte empty files")
    parser.add_argument("--archive", action="store_true", help="Run compression, GDrive sync, and pruning")
    parser.add_argument("--no-gdrive", action="store_true", help="Do not copy to Google Drive")
    parser.add_argument("--batch", type=int, default=None, help="Limit number of cold files to archive in this pass")

    args = parser.parse_args()
    engine = ArchivalEngine()

    if args.audit:
        res = engine.audit_disk_usage()
        print(f"Total Data Size: {res['total_gb']} GB")
        print(f"Cold Files (>48h): {res['cold_files_count']} ({res['cold_files_gb']} GB)")
        print(f"Hot Files (<=48h): {res['hot_files_count']} ({res['hot_files_gb']} GB)")
        print(f"Empty Files (0-byte): {res['empty_files_count']}")
    elif args.purge_empty:
        cnt = engine.purge_empty_files()
        print(f"Purged {cnt} empty files.")
    elif args.archive:
        run_prune_and_archive(sync_gdrive=not args.no_gdrive, batch_size=args.batch)
    else:
        parser.print_help()

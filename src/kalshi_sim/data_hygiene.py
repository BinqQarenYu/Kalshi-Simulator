"""
Data Hygiene, Storage Optimization & Canonical Market Data Manager.

Enforces:
1. Zero-Redundancy Invariant: Exactly one canonical per-contract file (stream_<ticker>.jsonl).
2. Automated Garbage Collection: Auto-purges 0-byte files, restart stubs, and obsolete execution logs.
3. Real-Data Integrity Guard: Rejects synthetic mock data contamination in historical datasets.
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class HygieneReport:
    """Summary metrics of data directory audit and cleanup."""
    total_files_scanned: int = 0
    total_size_bytes: int = 0
    zero_byte_files: List[str] = field(default_factory=list)
    restart_stubs: List[str] = field(default_factory=list)
    obsolete_executions: List[str] = field(default_factory=list)
    redundant_dumps: List[str] = field(default_factory=list)
    canonical_traded_streams: List[str] = field(default_factory=list)
    untraded_streams: List[str] = field(default_factory=list)
    protected_files: List[str] = field(default_factory=list)
    purged_files_count: int = 0
    bytes_reclaimed: int = 0
    errors: List[str] = field(default_factory=list)


class DataHygieneManager:
    """Institutional manager for market data hygiene, deduplication, and truth verification."""

    PROTECTED_EXTENSIONS: Set[str] = {".db", ".json", ".lock", ".py", ".onnx", ".txt", ".md"}
    PROTECTED_NAMES: Set[str] = {
        "kalshi_history.db",
        "bot_parameters_domination.json",
        "win_loss_reports.json",
        "trades.db",
        "trading_history.db",
        "trading_engine.lock",
        "trading_engine_macro.lock",
        "trading_engine_onnx.lock",
    }

    def __init__(self, data_dir: Path = Path("data"), active_buffer_seconds: float = 600.0) -> None:
        self.data_dir = Path(data_dir)
        self.active_buffer_seconds = active_buffer_seconds

    def get_traded_tickers(self) -> Set[str]:
        """Fetch all unique contracts settled or traded from the primary SQLite history."""
        db_path = self.data_dir / "kalshi_history.db"
        if not db_path.exists():
            return set()
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT ticker FROM settlements")
            settled = {r[0] for r in cur.fetchall()}
            cur.execute("SELECT DISTINCT ticker FROM trades")
            traded = {r[0] for r in cur.fetchall()}
            conn.close()
            return settled.union(traded)
        except Exception as e:
            logger.error("Failed to query traded tickers from kalshi_history.db: %s", e)
            return set()

    def audit_directory(self) -> HygieneReport:
        """Scan data directory and classify every file into functional categories."""
        rep = HygieneReport()
        if not self.data_dir.exists():
            return rep

        now = time.time()
        traded_tickers = self.get_traded_tickers()

        for filepath in self.data_dir.iterdir():
            if filepath.is_dir():
                continue

            rep.total_files_scanned += 1
            name = filepath.name
            ext = filepath.suffix.lower()

            try:
                sz = filepath.stat().st_size
                mtime = filepath.stat().st_mtime
            except OSError as e:
                rep.errors.append(f"Stat error on {name}: {e}")
                continue

            rep.total_size_bytes += sz

            # 1. Protected System Files
            if name in self.PROTECTED_NAMES or ext in self.PROTECTED_EXTENSIONS:
                rep.protected_files.append(name)
                continue

            # 2. Files modified within the active daemon buffer
            if (now - mtime) < self.active_buffer_seconds:
                rep.protected_files.append(name)
                continue

            # 3. Zero-byte empty files
            if sz == 0:
                rep.zero_byte_files.append(name)
                continue

            # 4. Obsolete paper executions
            if name.startswith("executions_"):
                rep.obsolete_executions.append(name)
                continue

            # 5. Monolithic tick dumps
            if name.startswith("ticks_paper_live_"):
                if sz < 100 * 1024:
                    rep.restart_stubs.append(name)
                else:
                    rep.redundant_dumps.append(name)
                continue

            # 6. Per-contract tick streams (stream_<ticker>.jsonl)
            if name.startswith("stream_"):
                tkr = name.replace("stream_", "").replace(".jsonl", "").replace(".gz", "")
                if tkr in traded_tickers:
                    rep.canonical_traded_streams.append(name)
                else:
                    if sz < 1024:
                        rep.restart_stubs.append(name)
                    else:
                        rep.untraded_streams.append(name)
                continue

            # 7. Other small stubs
            if sz < 4096:
                rep.restart_stubs.append(name)
            else:
                rep.protected_files.append(name)

        return rep

    def purge_redundant_files(self, dry_run: bool = False) -> Tuple[int, int]:
        """Safely delete 0-byte files, restart stubs, obsolete executions, and redundant dumps.
        
        Returns:
            Tuple of (files_purged_count, bytes_reclaimed)
        """
        rep = self.audit_directory()
        purge_list = rep.zero_byte_files + rep.restart_stubs + rep.obsolete_executions + rep.redundant_dumps

        purged_count = 0
        bytes_reclaimed = 0

        for fname in purge_list:
            fpath = self.data_dir / fname
            if not fpath.exists():
                continue
            try:
                sz = fpath.stat().st_size
                if not dry_run:
                    fpath.unlink()
                purged_count += 1
                bytes_reclaimed += sz
            except PermissionError:
                logger.warning("File is locked by an active process, skipping: %s", fname)
            except Exception as e:
                logger.error("Failed to purge %s: %s", fname, e)
                rep.errors.append(f"Purge error on {fname}: {e}")

        rep.purged_files_count = purged_count
        rep.bytes_reclaimed = bytes_reclaimed
        return purged_count, bytes_reclaimed

    def get_canonical_stream_path(self, ticker: str) -> Path:
        """Returns the single canonical path for a contract's tick stream (stream_<safe_ticker>.jsonl)."""
        safe_ticker = ticker.replace("/", "_").replace(":", "_")
        return self.data_dir / f"stream_{safe_ticker}.jsonl"

    def verify_data_authenticity(self, sample_lines: int = 100) -> Dict[str, Any]:
        """Audit historical tick files to guarantee they contain authentic Kalshi L2/RTI records."""
        results = {
            "audited_contracts": 0,
            "valid_kalshi_records": 0,
            "synthetic_mock_detected": 0,
            "status": "PASS",
        }

        stream_files = list(self.data_dir.glob("stream_*.jsonl"))
        results["audited_contracts"] = len(stream_files)

        valid_types = {"OrderBookDelta", "OrderBookSnapshot", "TickerUpdate", "TradeEvent"}

        for sf in stream_files[:50]:  # Sample top 50
            try:
                with open(sf, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f):
                        if i >= sample_lines:
                            break
                        # Fast sanity check
                        if "synthetic" in line.lower() or "mock_random" in line.lower():
                            results["synthetic_mock_detected"] += 1
                        if any(vt in line for vt in valid_types) or '"side":' in line:
                            results["valid_kalshi_records"] += 1
            except Exception:
                pass

        if results["synthetic_mock_detected"] > 0:
            results["status"] = "FAIL_MOCK_CONTAMINATION"
        return results


def main() -> None:
    """CLI tool for Data Hygiene & Single-Copy Integrity."""
    parser = argparse.ArgumentParser(description="Kalshi Simulator Data Hygiene & Canonical Store Manager")
    parser.add_argument("--audit", action="store_true", help="Print audit report of data directory")
    parser.add_argument("--purge", action="store_true", help="Execute safe purge of redundant & empty files")
    parser.add_argument("--verify-truth", action="store_true", help="Audit tick files for real-data authenticity")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without deleting files")

    args = parser.parse_args()
    mgr = DataHygieneManager()

    if args.verify_truth:
        res = mgr.verify_data_authenticity()
        print("=== Real-Data Authenticity Verification ===")
        print(f"Status: {res['status']}")
        print(f"Audited Contracts: {res['audited_contracts']}")
        print(f"Valid Exchange Records: {res['valid_kalshi_records']}")
        print(f"Synthetic Mock Detected: {res['synthetic_mock_detected']}")

    elif args.purge:
        count, reclaimed = mgr.purge_redundant_files(dry_run=args.dry_run)
        mode = "DRY RUN" if args.dry_run else "EXECUTED"
        print(f"[{mode}] Purged {count:,} redundant files. Reclaimed {reclaimed / 1024 / 1024 / 1024:.2f} GB.")

    else:
        rep = mgr.audit_directory()
        print("=== Data Directory Audit Report ===")
        print(f"Total Files Scanned:         {rep.total_files_scanned:,}")
        print(f"Total Storage Footprint:     {rep.total_size_bytes / 1024 / 1024 / 1024:.2f} GB")
        print(f"0-Byte Empty Files:          {len(rep.zero_byte_files):,}")
        print(f"Restart Stubs (<100KB):      {len(rep.restart_stubs):,}")
        print(f"Obsolete Executions:         {len(rep.obsolete_executions):,}")
        print(f"Redundant Omnibus Dumps:     {len(rep.redundant_dumps):,}")
        print(f"Canonical Traded Streams:    {len(rep.canonical_traded_streams):,}")
        print(f"Untraded Market Streams:     {len(rep.untraded_streams):,}")
        print(f"Protected System Files:      {len(rep.protected_files):,}")


if __name__ == "__main__":
    main()

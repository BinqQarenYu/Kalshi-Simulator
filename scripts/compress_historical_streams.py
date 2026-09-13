#!/usr/bin/env python3
"""Historical Stream Compactor — Pillar 3 of High-Throughput Data Memory Management.

Compresses existing uncompressed stream_*.jsonl files to .jsonl.gz with integrity
verification. Only removes the original .jsonl after confirming the .gz is valid.

Usage:
    python scripts/compress_historical_streams.py [--data-dir data/] [--dry-run]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Low CPU priority on Windows
try:
    import os
    os.nice(19)  # Unix
except (AttributeError, OSError):
    pass  # Windows: best-effort


def compute_line_count_and_hash(filepath: Path, compressed: bool = False) -> tuple[int, str]:
    """Count lines and compute SHA-256 of decompressed content."""
    h = hashlib.sha256()
    count = 0
    opener = gzip.open if compressed else open
    with opener(filepath, "rb") as f:
        for line in f:
            h.update(line)
            count += 1
    return count, h.hexdigest()


def compress_file(src: Path, dry_run: bool = False) -> tuple[bool, int, int]:
    """Compress a single .jsonl file to .jsonl.gz with integrity check.

    Returns:
        (success, original_bytes, compressed_bytes)
    """
    dst = src.with_suffix(".jsonl.gz")
    if dst.exists():
        logger.info("SKIP %s → .gz already exists", src.name)
        return True, 0, 0

    original_size = src.stat().st_size
    if original_size == 0:
        logger.info("SKIP %s → 0-byte file", src.name)
        return True, 0, 0

    if dry_run:
        logger.info("DRY RUN: would compress %s (%.2f MB)", src.name, original_size / 1024 / 1024)
        return True, original_size, 0

    # Phase 1: Compute source integrity hash
    src_lines, src_hash = compute_line_count_and_hash(src, compressed=False)

    # Phase 2: Compress with level 1 (fast, still ~5-8x ratio on JSON)
    try:
        with open(src, "rb") as fin, gzip.open(dst, "wb", compresslevel=1) as fout:
            while True:
                chunk = fin.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                fout.write(chunk)
    except Exception as e:
        logger.error("FAIL compression of %s: %s", src.name, e)
        if dst.exists():
            dst.unlink()
        return False, original_size, 0

    compressed_size = dst.stat().st_size

    # Phase 3: Verify integrity of compressed file
    gz_lines, gz_hash = compute_line_count_and_hash(dst, compressed=True)

    if gz_lines != src_lines or gz_hash != src_hash:
        logger.error(
            "INTEGRITY FAIL for %s: src=%d lines/%s, gz=%d lines/%s — keeping original",
            src.name, src_lines, src_hash[:12], gz_lines, gz_hash[:12],
        )
        dst.unlink()
        return False, original_size, 0

    # Phase 4: Remove original
    src.unlink()
    ratio = compressed_size / original_size if original_size > 0 else 0
    logger.info(
        "OK %s → %s (%.2f MB → %.2f MB, ratio %.1f%%)",
        src.name, dst.name,
        original_size / 1024 / 1024, compressed_size / 1024 / 1024,
        ratio * 100,
    )
    return True, original_size, compressed_size


def main() -> None:
    parser = argparse.ArgumentParser(description="Compress historical stream_*.jsonl to .jsonl.gz")
    parser.add_argument("--data-dir", type=str, default="data", help="Data directory (default: data/)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be compressed without acting")

    args = parser.parse_args()
    data_dir = Path(args.data_dir)

    if not data_dir.exists():
        logger.error("Data directory does not exist: %s", data_dir)
        sys.exit(1)

    jsonl_files = sorted(data_dir.glob("stream_*.jsonl"))
    # Exclude files that already have a .gz companion
    to_compress = [f for f in jsonl_files if not f.with_suffix(".jsonl.gz").exists()]

    if not to_compress:
        logger.info("No uncompressed stream files to process in %s", data_dir)
        return

    logger.info("Found %d uncompressed stream files to compress", len(to_compress))

    total_original = 0
    total_compressed = 0
    success_count = 0
    fail_count = 0
    t0 = time.monotonic()

    for f in to_compress:
        ok, orig, comp = compress_file(f, dry_run=args.dry_run)
        if ok:
            success_count += 1
            total_original += orig
            total_compressed += comp
        else:
            fail_count += 1

    elapsed = time.monotonic() - t0
    saved = total_original - total_compressed

    print(f"\n=== Historical Stream Compaction Report ===")
    print(f"Files processed:    {success_count:,}")
    print(f"Failures:           {fail_count:,}")
    if not args.dry_run and total_original > 0:
        print(f"Original size:      {total_original / 1024 / 1024 / 1024:.2f} GB")
        print(f"Compressed size:    {total_compressed / 1024 / 1024 / 1024:.2f} GB")
        print(f"Space saved:        {saved / 1024 / 1024 / 1024:.2f} GB ({saved / total_original * 100:.1f}%)")
    print(f"Elapsed time:       {elapsed:.1f}s")


if __name__ == "__main__":
    main()

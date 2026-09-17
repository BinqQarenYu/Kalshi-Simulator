"""Unit tests for ArchivalEngine (cold-tier segmentation, empty-file purging, protected-file invariants)."""

import os
import time
from pathlib import Path
import pytest

from kalshi_sim.archival_engine import ArchivalEngine, PROTECTED_ITEMS


def test_archival_engine_empty_file_purging(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    archive_dir = tmp_path / "archives"

    # Create empty files and non-empty files
    empty_file = data_dir / "stream_empty.jsonl"
    empty_file.write_text("")

    valid_file = data_dir / "ticks_valid.jsonl"
    valid_file.write_text('{"price": 100}\n')

    engine = ArchivalEngine(data_dir=data_dir, archive_dir=archive_dir)
    audit = engine.audit_disk_usage()
    assert audit["empty_files_count"] == 1

    purged = engine.purge_empty_files()
    assert purged == 1
    assert not empty_file.exists()
    assert valid_file.exists()


def test_archival_engine_protected_files_invariant(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    archive_dir = tmp_path / "archives"

    # Seed protected files
    seal_file = data_dir / "seal_of_excellence.json"
    seal_file.write_text('{"protected": true}')

    bot_params = data_dir / "bot_parameters_domination.json"
    bot_params.write_text('{"min_spot_diff": 14.0}')

    engine = ArchivalEngine(data_dir=data_dir, archive_dir=archive_dir)
    audit = engine.audit_disk_usage()

    # Protected items should not be classified in old_files or recent_files
    classified_names = [f.name for f in audit["old_files"] + audit["recent_files"]]
    assert "seal_of_excellence.json" not in classified_names
    assert "bot_parameters_domination.json" not in classified_names


def test_archival_engine_compression_and_gdrive_sync(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    archive_dir = tmp_path / "archives"
    gdrive_dir = tmp_path / "gdrive_repo"
    gdrive_dir.mkdir()

    # Create simulated old file (>48h)
    old_file = data_dir / "ticks_old_test.jsonl"
    old_file.write_text('{"sample": "market_data_tick"}\n' * 500)
    
    # Manually set mtime to 3 days ago
    three_days_ago = time.time() - (72 * 3600)
    os.utime(old_file, (three_days_ago, three_days_ago))

    engine = ArchivalEngine(data_dir=data_dir, archive_dir=archive_dir, gdrive_dir=gdrive_dir)
    audit = engine.audit_disk_usage()
    assert audit["cold_files_count"] == 1

    archive_res = engine.create_cold_archive(archive_name="test_archive.tar.gz")
    assert archive_res is not None
    arch_path, sha, count = archive_res
    assert arch_path.exists()
    assert count == 1

    # Sync to GDrive
    synced = engine.sync_archive_to_gdrive(arch_path)
    assert synced is not None
    assert (gdrive_dir / "test_archive.tar.gz").exists()

    # Prune
    deleted = engine.prune_archived_files([old_file])
    assert deleted == 1
    assert not old_file.exists()

"""
Unit tests for DataHygieneManager and single-copy canonical store.
"""

import tempfile
import time
from pathlib import Path
import pytest

from app_1_machine_engine.data_hygiene import DataHygieneManager, HygieneReport


def test_data_hygiene_classification_and_purge(tmp_path: Path):
    mgr = DataHygieneManager(data_dir=tmp_path, active_buffer_seconds=5.0)

    # 1. Create a 0-byte file
    zero_f = tmp_path / "zero_test.jsonl"
    zero_f.write_text("")

    # 2. Create an obsolete execution file
    exec_f = tmp_path / "executions_20260801_120000.jsonl"
    exec_f.write_text("{\"type\": \"paper_pnl\"}\n")

    # 3. Create a tiny restart stub
    stub_f = tmp_path / "ticks_paper_live_20260801_120000.jsonl"
    stub_f.write_text("{\"seq\": 1}\n")

    # 4. Create a protected database and parameter config
    db_f = tmp_path / "kalshi_history.db"
    db_f.write_text("sqlite-header-mock")
    cfg_f = tmp_path / "bot_parameters_domination.json"
    cfg_f.write_text("{\"active_asset\": \"BTC\"}")

    # 5. Create a canonical stream file for a contract
    stream_f = tmp_path / "stream_KXBTC15M-TEST.jsonl"
    stream_f.write_text("{\"side\": \"yes\", \"price\": 0.50}\n" * 100)

    # Fast forward time beyond 5.0s active buffer for created files
    old_time = time.time() - 10.0
    for p in [zero_f, exec_f, stub_f]:
        # adjust mtime
        import os
        os.utime(p, (old_time, old_time))

    # Audit
    rep = mgr.audit_directory()
    assert rep.total_files_scanned == 6
    assert "zero_test.jsonl" in rep.zero_byte_files
    assert "executions_20260801_120000.jsonl" in rep.obsolete_executions
    assert "ticks_paper_live_20260801_120000.jsonl" in rep.restart_stubs
    assert "kalshi_history.db" in rep.protected_files
    assert "bot_parameters_domination.json" in rep.protected_files

    # Purge
    purged, reclaimed = mgr.purge_redundant_files(dry_run=False)
    assert purged == 3
    assert not zero_f.exists()
    assert not exec_f.exists()
    assert not stub_f.exists()
    assert db_f.exists()
    assert cfg_f.exists()
    assert stream_f.exists()


def test_canonical_stream_path(tmp_path: Path):
    mgr = DataHygieneManager(data_dir=tmp_path)
    p = mgr.get_canonical_stream_path("KXBTC15M-26SEP111600-00")
    assert p == tmp_path / "stream_KXBTC15M-26SEP111600-00.jsonl"


def test_data_authenticity_checker(tmp_path: Path):
    mgr = DataHygieneManager(data_dir=tmp_path)

    # Valid Kalshi stream
    valid_f = tmp_path / "stream_KXBTC15M-TEST.jsonl"
    valid_f.write_text("{\"_type\": \"OrderBookDelta\", \"price\": 0.52, \"side\": \"yes\"}\n")

    res = mgr.verify_data_authenticity()
    assert res["status"] == "PASS"
    assert res["valid_kalshi_records"] >= 1
    assert res["synthetic_mock_detected"] == 0

    # Contaminated mock stream
    bad_f = tmp_path / "stream_MOCK_TEST.jsonl"
    bad_f.write_text("{\"synthetic\": true, \"mock_random\": 12345}\n")

    res2 = mgr.verify_data_authenticity()
    assert res2["status"] == "FAIL_MOCK_CONTAMINATION"
    assert res2["synthetic_mock_detected"] >= 1


def test_purge_aged_streams(tmp_path: Path):
    """Rolling retention: only untraded streams older than max_age_days are purged."""
    import os

    mgr = DataHygieneManager(data_dir=tmp_path, active_buffer_seconds=0.0)

    # Create an "old" untraded stream (20 days ago)
    old_stream = tmp_path / "stream_OLD-TICKER.jsonl"
    old_stream.write_text('{"side": "yes", "price": 0.50}\n' * 10)
    old_time = time.time() - (20 * 86400)
    os.utime(old_stream, (old_time, old_time))

    # Create an "old" compressed untraded stream
    old_gz = tmp_path / "stream_OLD-GZ-TICKER.jsonl.gz"
    import gzip
    with gzip.open(old_gz, "wt") as f:
        f.write('{"side": "no", "price": 0.48}\n' * 5)
    os.utime(old_gz, (old_time, old_time))

    # Create a "recent" untraded stream (2 days ago — should NOT be purged)
    recent_stream = tmp_path / "stream_RECENT-TICKER.jsonl"
    recent_stream.write_text('{"side": "yes", "price": 0.55}\n' * 10)
    recent_time = time.time() - (2 * 86400)
    os.utime(recent_stream, (recent_time, recent_time))

    # Dry run first
    count_dry, _ = mgr.purge_aged_streams(max_age_days=14, dry_run=True)
    assert count_dry == 2  # Both old files identified
    assert old_stream.exists()  # Not actually deleted
    assert old_gz.exists()

    # Real purge
    count, reclaimed = mgr.purge_aged_streams(max_age_days=14, dry_run=False)
    assert count == 2
    assert reclaimed > 0
    assert not old_stream.exists()
    assert not old_gz.exists()
    assert recent_stream.exists()  # Protected by age


def test_canonical_stream_path_prefers_gz(tmp_path: Path):
    """get_canonical_stream_path returns .jsonl.gz when it exists."""
    mgr = DataHygieneManager(data_dir=tmp_path)

    ticker = "KXBTC15M-26SEP111600-00"

    # When neither file exists, returns .jsonl
    p1 = mgr.get_canonical_stream_path(ticker)
    assert p1.name.endswith(".jsonl")
    assert not p1.name.endswith(".jsonl.gz")

    # Create .jsonl — should return .jsonl
    jsonl_path = tmp_path / "stream_KXBTC15M-26SEP111600-00.jsonl"
    jsonl_path.write_text("{}\n")
    p2 = mgr.get_canonical_stream_path(ticker)
    assert p2 == jsonl_path

    # Create .jsonl.gz — should now prefer .gz
    gz_path = tmp_path / "stream_KXBTC15M-26SEP111600-00.jsonl.gz"
    gz_path.write_bytes(b"\x1f\x8b" + b"\x00" * 8)  # minimal gzip header stub
    p3 = mgr.get_canonical_stream_path(ticker)
    assert p3 == gz_path


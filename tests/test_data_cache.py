"""
Unit tests for MarketDataCache (Simsim single-download & dual-reuse invariants).
"""

from pathlib import Path
import pytest
from kalshi_sim.data_cache import MarketDataCache


def test_market_data_cache_indexing_and_hit(tmp_path: Path):
    cache = MarketDataCache(data_dir=tmp_path)

    # Initially empty
    assert len(cache._cache_index) == 0
    assert not cache.is_cached("KXBTC15M-26SEP111530-30")

    # Create dummy contract stream (> 1KB)
    stream_f = tmp_path / "stream_KXBTC15M-26SEP111530-30.jsonl"
    stream_f.write_text("{\"price\": 0.50, \"delta\": 100, \"side\": \"yes\"}\n" * 50)

    # Refresh
    cache.refresh_index()
    assert cache.is_cached("KXBTC15M-26SEP111530-30")
    assert cache.get_stream("KXBTC15M-26SEP111530-30") == stream_f

    # Verify summary
    s = cache.get_summary()
    assert s["total_cached_contracts"] == 1
    assert s["contracts_by_asset"]["BTC"] == 1


def test_cache_first_avoids_redownload(tmp_path: Path):
    cache = MarketDataCache(data_dir=tmp_path)
    stream_f = tmp_path / "stream_KXETH15M-TEST.jsonl"
    stream_f.write_text("{\"price\": 0.40, \"delta\": 50}\n" * 60)
    cache.refresh_index()

    called = False

    def mock_fetcher(ticker: str):
        nonlocal called
        called = True

    # Should hit cache and NEVER call fetcher
    p = cache.get_stream("KXETH15M-TEST", fetch_if_missing=mock_fetcher)
    assert p == stream_f
    assert not called, "Fetcher should NOT be called when contract is already cached locally!"


def test_cache_miss_fetches_once(tmp_path: Path):
    cache = MarketDataCache(data_dir=tmp_path)
    called = False

    def mock_fetcher(ticker: str):
        nonlocal called
        called = True
        # Simulate saving to canonical stream
        target = tmp_path / f"stream_{ticker}.jsonl"
        target.write_text("{\"price\": 0.55, \"delta\": 100}\n" * 60)

    # Cache miss calls fetcher ONCE
    p = cache.get_stream("KXSOL15M-NEW", fetch_if_missing=mock_fetcher)
    assert called is True
    assert p == tmp_path / "stream_KXSOL15M-NEW.jsonl"
    assert cache.is_cached("KXSOL15M-NEW")

    # Second call hits cache (called remains True, not called again)
    called = False
    p2 = cache.get_stream("KXSOL15M-NEW", fetch_if_missing=mock_fetcher)
    assert p2 == p
    assert not called, "Second call must hit local cache without redownloading!"

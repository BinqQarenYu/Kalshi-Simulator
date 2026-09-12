"""
Market Data Cache & Deduplication Registry (Simsim Invariant).

Guarantees:
1. Single-Download Invariant: Market data is fetched at most ONCE per contract cycle.
2. Dual-Reuse Invariant: The exact same canonical stream (stream_<ticker>.jsonl) is
   reused seamlessly by BOTH ONNX Neural Training AND Future Strategy Simulations.
3. Cache-First Resolution: Always checks local canonical disk cache before triggering network I/O.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CachedContractInfo:
    """Metadata for a locally cached contract tick stream."""
    ticker: str
    asset: str
    file_path: Path
    file_size_bytes: int
    last_modified_utc: str
    is_settled: bool = False


class MarketDataCache:
    """Canonical fetch-cache manager for Kalshi order book tick data."""

    def __init__(self, data_dir: Path = Path("data")) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._cache_index: Dict[str, CachedContractInfo] = {}
        self.refresh_index()

    def refresh_index(self) -> None:
        """Scan data directory and build index of all locally available contract streams."""
        self._cache_index.clear()
        
        # Also check which contracts are settled in SQLite
        settled_tickers: Set[str] = set()
        db_path = self.data_dir / "kalshi_history.db"
        if db_path.exists():
            try:
                import sqlite3
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("SELECT DISTINCT ticker FROM settlements")
                settled_tickers = {r[0] for r in cur.fetchall()}
                conn.close()
            except Exception as e:
                logger.debug("Could not read settlements from db: %s", e)

        for f in self.data_dir.glob("stream_*.jsonl"):
            try:
                sz = f.stat().st_size
                # Only index non-empty streams (> 1 KB)
                if sz < 1024:
                    continue
                
                ticker = f.stem.replace("stream_", "")
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat()
                
                # Derive asset from ticker prefix
                asset = "BTC"
                if "ETH" in ticker:
                    asset = "ETH"
                elif "SOL" in ticker:
                    asset = "SOL"
                elif "DOGE" in ticker:
                    asset = "DOGE"
                elif "GOLD" in ticker:
                    asset = "GOLD"
                elif "HYPE" in ticker:
                    asset = "HYPER"

                self._cache_index[ticker] = CachedContractInfo(
                    ticker=ticker,
                    asset=asset,
                    file_path=f,
                    file_size_bytes=sz,
                    last_modified_utc=mtime,
                    is_settled=(ticker in settled_tickers),
                )
            except OSError:
                continue

        logger.info("MarketDataCache indexed %d cached contract streams (Total size: %.2f GB).",
                    len(self._cache_index),
                    sum(c.file_size_bytes for c in self._cache_index.values()) / 1024 / 1024 / 1024)

    def is_cached(self, ticker: str) -> bool:
        """Instant O(1) check if a contract's complete tick history is already saved locally."""
        safe_ticker = ticker.replace("/", "_").replace(":", "_")
        if safe_ticker in self._cache_index:
            return True
        # Check disk directly in case newly written
        p = self.data_dir / f"stream_{safe_ticker}.jsonl"
        return p.exists() and p.stat().st_size >= 1024

    def get_canonical_path(self, ticker: str) -> Path:
        """Returns the single canonical path for a contract (stream_<ticker>.jsonl)."""
        safe_ticker = ticker.replace("/", "_").replace(":", "_")
        return self.data_dir / f"stream_{safe_ticker}.jsonl"

    def get_stream(
        self,
        ticker: str,
        fetch_if_missing: Optional[Callable[[str], Any]] = None,
    ) -> Optional[Path]:
        """Cache-First Resolver.
        
        If contract is already downloaded locally:
            REUSES LOCAL FILE IMMEDIATELY. Zero network I/O, zero redownload.
        If missing and fetch_if_missing callback is provided:
            Fetches ONCE, saves to canonical path, indexes it, and returns path.
        """
        safe_ticker = ticker.replace("/", "_").replace(":", "_")
        canonical_path = self.get_canonical_path(safe_ticker)

        if self.is_cached(safe_ticker):
            logger.debug("🎯 [CACHE HIT] Reusing cached stream for %s (0 redownload).", ticker)
            return canonical_path

        if fetch_if_missing is not None:
            logger.info("⬇️ [CACHE MISS] Fetching fresh market data for %s...", ticker)
            fetch_if_missing(ticker)
            if canonical_path.exists() and canonical_path.stat().st_size > 0:
                self.refresh_index()
                return canonical_path

        return None

    def list_contracts(
        self,
        asset: Optional[str] = None,
        only_settled: bool = False,
    ) -> List[CachedContractInfo]:
        """Returns all locally cached contract streams available for ONNX training & bot simulation."""
        contracts = list(self._cache_index.values())
        if asset:
            contracts = [c for c in contracts if c.asset.upper() == asset.upper()]
        if only_settled:
            contracts = [c for c in contracts if c.is_settled]
        return sorted(contracts, key=lambda c: c.file_size_bytes, reverse=True)

    def get_summary(self) -> Dict[str, Any]:
        """Return cache health, storage footprint, and asset breakdown."""
        total_sz = sum(c.file_size_bytes for c in self._cache_index.values())
        by_asset: Dict[str, int] = {}
        for c in self._cache_index.values():
            by_asset[c.asset] = by_asset.get(c.asset, 0) + 1

        return {
            "total_cached_contracts": len(self._cache_index),
            "total_size_mb": round(total_sz / 1024 / 1024, 2),
            "total_size_gb": round(total_sz / 1024 / 1024 / 1024, 2),
            "contracts_by_asset": by_asset,
            "settled_contracts": sum(1 for c in self._cache_index.values() if c.is_settled),
        }

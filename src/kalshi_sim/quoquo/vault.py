"""Quoquo Institutional Vault & Storage Manager.

Manages canonical storage of polished, token-efficient telemetry digests in:
- reports/clean_telemetry/cycles.jsonl (line-delimited canonical records)
- reports/clean_telemetry/daily_digest.md (human and agent glanceable summary)
- In-memory rolling cache for sub-millisecond API queries (<300 tokens)
"""

from __future__ import annotations

import json
import logging
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from kalshi_sim.quoquo.schemas import CondensedCycleTelemetry

logger = logging.getLogger(__name__)

VAULT_DIR = Path("reports/clean_telemetry")
CYCLES_FILE = VAULT_DIR / "cycles.jsonl"
DIGEST_FILE = VAULT_DIR / "daily_digest.md"


class QuoquoVault:
    """Institutional storage custodian ensuring clean token storage."""

    def __init__(self, vault_dir: Optional[Path] = None, max_cache_size: int = 50) -> None:
        self.vault_dir = vault_dir or VAULT_DIR
        self.cycles_file = self.vault_dir / "cycles.jsonl"
        self.digest_file = self.vault_dir / "daily_digest.md"
        self._cache: deque[CondensedCycleTelemetry] = deque(maxlen=max_cache_size)
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self._load_recent_from_disk()

    def _load_recent_from_disk(self) -> None:
        """Warm in-memory cache with the latest records from disk."""
        if not self.cycles_file.exists():
            return
        try:
            with open(self.cycles_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines[-self._cache.maxlen:]:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    self._cache.append(CondensedCycleTelemetry(**data))
        except Exception as exc:
            logger.warning("QuoquoVault could not warm cache from disk: %s", exc)

    def store_cycle_digest(self, digest: CondensedCycleTelemetry) -> None:
        """Append a polished cycle digest to canonical disk storage and in-memory cache."""
        self._cache.append(digest)

        # 1. Append to cycles.jsonl
        try:
            with open(self.cycles_file, "a", encoding="utf-8") as f:
                f.write(digest.model_dump_json() + "\n")
        except Exception as exc:
            logger.error("Failed appending to %s: %s", self.cycles_file, exc)

        # 2. Update daily_digest.md
        self._rewrite_markdown_digest()

    def _rewrite_markdown_digest(self) -> None:
        """Generate a glanceable, low-token Markdown summary for human and AI agents."""
        try:
            lines = [
                "# Institutional Trading Telemetry - Clean Digest",
                "",
                f"> **Last Updated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | **Stored Cycles:** {len(self._cache)}",
                "",
                "| Cycle ET | Ticker | Outcome | Side | PnL | Dominant Veto | Deer Forensic Briefing |",
                "| :--- | :--- | :--- | :---: | :---: | :--- | :--- |",
            ]
            for item in reversed(self._cache):
                pnl_str = f"" if item.pnl else "-"
                side_str = (item.trade_side or "-").upper()
                lines.append(
                    f"| {item.cycle_time_et} | {item.cycle_ticker} | **{item.outcome.value}** | {side_str} | {pnl_str} | {item.dominant_veto.value} | {item.deer_briefing} |"
                )
            self.digest_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed rewriting daily markdown digest: %s", exc)

    def get_recent_digests(self, limit: int = 10) -> List[CondensedCycleTelemetry]:
        """Return the most recent polished digests."""
        return list(self._cache)[-limit:]


# Global Singleton
_global_vault: Optional[QuoquoVault] = None


def get_quoquo_vault() -> QuoquoVault:
    """Access the canonical Quoquo Vault singleton."""
    global _global_vault
    if _global_vault is None:
        _global_vault = QuoquoVault()
    return _global_vault

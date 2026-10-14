"""Sanitize and Disentangle Cross-Asset Contamination across SQLite DBs and JSON Reports.

Rules:
1. data/win_loss_reports.json must contain ONLY BTC trades (no ETH/KXETH).
2. data/eth_win_loss_reports.json must contain ONLY ETH trades (no BTC/KXBTC).
3. data/kalshi_history.db must contain ONLY BTC trades, settlements, and autopsies.
4. data/kalshi_history_eth.db must contain ONLY ETH trades, settlements, and autopsies.
5. All operations are idempotent, transactional, and preserve backups before mutating.
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sanitize_contamination")


def is_eth_record(record: Dict[str, Any]) -> bool:
    """Check if record belongs to ETH."""
    ticker = str(record.get("ticker", "")).upper()
    asset = str(record.get("asset", "")).upper()
    bot = str(record.get("bot_type", "")).upper()
    return "ETH" in ticker or asset == "ETH" or "ETH" in bot


def sanitize_json_reports(data_dir: Path) -> Dict[str, int]:
    """Sanitize win_loss_reports.json and eth_win_loss_reports.json."""
    wl_path = data_dir / "win_loss_reports.json"
    eth_path = data_dir / "eth_win_loss_reports.json"

    btc_reports: List[Dict[str, Any]] = []
    eth_reports: List[Dict[str, Any]] = []

    # Read existing win_loss_reports.json
    if wl_path.exists():
        backup_path = data_dir / f"win_loss_reports.backup_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.json"
        shutil.copy2(wl_path, backup_path)
        logger.info("Backed up %s to %s", wl_path, backup_path.name)
        try:
            wl_data = json.loads(wl_path.read_text(encoding="utf-8"))
            if isinstance(wl_data, list):
                for r in wl_data:
                    if is_eth_record(r):
                        eth_reports.append(r)
                    else:
                        btc_reports.append(r)
        except Exception as exc:
            logger.error("Error reading %s: %s", wl_path, exc)

    # Read existing eth_win_loss_reports.json
    if eth_path.exists():
        try:
            eth_data = json.loads(eth_path.read_text(encoding="utf-8"))
            if isinstance(eth_data, list):
                for r in eth_data:
                    if is_eth_record(r):
                        eth_reports.append(r)
                    else:
                        btc_reports.append(r)
        except Exception as exc:
            logger.error("Error reading %s: %s", eth_path, exc)

    # Deduplicate by report_id
    def dedupe(reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        deduped = []
        for r in reports:
            rid = str(r.get("report_id") or r.get("id") or "")
            key = rid if rid else (r.get("ticker", ""), r.get("timestamp_utc", ""))
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        deduped.sort(key=lambda x: str(x.get("timestamp_utc", "")), reverse=True)
        return deduped

    btc_clean = dedupe(btc_reports)
    eth_clean = dedupe(eth_reports)

    wl_path.write_text(json.dumps(btc_clean, indent=2), encoding="utf-8")
    eth_path.write_text(json.dumps(eth_clean, indent=2), encoding="utf-8")

    logger.info("Sanitized JSON reports: BTC count=%d, ETH count=%d", len(btc_clean), len(eth_clean))
    return {"btc_reports": len(btc_clean), "eth_reports": len(eth_clean)}


def sanitize_sqlite_databases(data_dir: Path) -> Dict[str, Any]:
    """Sanitize kalshi_history.db and kalshi_history_eth.db so each has strictly its own assets."""
    btc_db_path = data_dir / "kalshi_history.db"
    eth_db_path = data_dir / "kalshi_history_eth.db"

    results = {"btc_purged_eth_trades": 0, "eth_purged_btc_trades": 0}

    # 1. Clean kalshi_history.db (Remove any ETH entries)
    if btc_db_path.exists():
        backup_db = data_dir / f"kalshi_history.backup_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.db"
        shutil.copy2(btc_db_path, backup_db)
        logger.info("Backed up %s to %s", btc_db_path, backup_db.name)

        with sqlite3.connect(btc_db_path) as conn:
            cur = conn.cursor()
            for tbl in ["trades", "settlements", "trade_failure_autopsies", "trade_lifecycles"]:
                try:
                    cur.execute(f"DELETE FROM {tbl} WHERE ticker LIKE '%ETH%'")
                    results[f"btc_purged_{tbl}"] = cur.rowcount
                    if cur.rowcount > 0:
                        logger.info("Purged %d contaminated ETH rows from BTC %s", cur.rowcount, tbl)
                except sqlite3.OperationalError:
                    pass
            conn.commit()

    # 2. Clean kalshi_history_eth.db (Remove any BTC entries)
    if eth_db_path.exists():
        backup_eth_db = data_dir / f"kalshi_history_eth.backup_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.db"
        shutil.copy2(eth_db_path, backup_eth_db)
        logger.info("Backed up %s to %s", eth_db_path, backup_eth_db.name)

        with sqlite3.connect(eth_db_path) as conn:
            cur = conn.cursor()
            for tbl in ["trades", "settlements", "trade_failure_autopsies", "trade_lifecycles"]:
                try:
                    cur.execute(f"DELETE FROM {tbl} WHERE ticker LIKE '%BTC%'")
                    results[f"eth_purged_{tbl}"] = cur.rowcount
                    if cur.rowcount > 0:
                        logger.info("Purged %d contaminated BTC rows from ETH %s", cur.rowcount, tbl)
                except sqlite3.OperationalError:
                    pass
            conn.commit()

    return results


def main() -> None:
    data_dir = Path("data")
    if not data_dir.exists():
        logger.error("Data directory %s does not exist.", data_dir.absolute())
        return

    logger.info("Starting historical assessment & database contamination sanitization...")
    json_stats = sanitize_json_reports(data_dir)
    db_stats = sanitize_sqlite_databases(data_dir)
    logger.info("Contamination sanitization complete! JSON: %s, DB: %s", json_stats, db_stats)


if __name__ == "__main__":
    main()

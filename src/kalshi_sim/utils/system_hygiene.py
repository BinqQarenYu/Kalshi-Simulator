"""
src/kalshi_sim/utils/system_hygiene.py
Anti-bloat duty executed after every batch assessment.
Purges ephemeral dumps, vacuum old snapshots (>7d), rotates system logs,
and trims JSON reports while strictly preserving:
- All models, ONNX brains, PyTorch weights, and HMM scalers
- All trades, settlements, and batch assessments in SQLite
- All forensics records and failure autopsies (Lessons Learned)
- All audit seals, certificates of excellence, and strategy parameters
"""

import os
import gc
import gzip
import json
import logging
import sqlite3
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("kalshi_sim.utils.system_hygiene")

def run_assessment_hygiene_duty(
    repo_root: Optional[Path] = None,
    max_days_snapshots: int = 7,
    max_active_json_reports: int = 300,
) -> Dict[str, Any]:
    """
    Execute anti-bloat cleanup duty.
    Safe for autonomous invocation inside batch supervisors and daemon workers.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
    
    data_dir = repo_root / "data"
    results = {
        "snapshots_pruned": 0,
        "predictions_pruned": 0,
        "db_vacuumed": False,
        "reports_archived": 0,
        "tmp_purged": 0,
        "ram_reclaimed": False,
    }
    
    # 1. Vacuum & Prune SQLite Databases (kalshi_history.db & kalshi_history_eth.db)
    for db_name in ["kalshi_history.db", "kalshi_history_eth.db"]:
        db_path = data_dir / db_name
        if db_path.exists():
            try:
                con = sqlite3.connect(str(db_path))
                cur = con.cursor()
                
                # Check if tables exist
                existing_tables = {
                    row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
                }
                
                if "equity_snapshots" in existing_tables:
                    cur.execute(f"DELETE FROM equity_snapshots WHERE timestamp_utc < datetime('now', '-{max_days_snapshots} days')")
                    results["snapshots_pruned"] += cur.rowcount
                    
                if "ai_predictions" in existing_tables:
                    cur.execute(f"DELETE FROM ai_predictions WHERE timestamp_utc < datetime('now', '-{max_days_snapshots} days')")
                    results["predictions_pruned"] += cur.rowcount
                
                con.commit()
                cur.execute("VACUUM")
                con.close()
                results["db_vacuumed"] = True
                logger.info("🧹 [HYGIENE] Database %s vacuumed and pruned (>%dd snapshots purged).", db_name, max_days_snapshots)
            except Exception as e:
                logger.warning("[HYGIENE] Database prune error on %s: %s", db_name, e)

    # 2. Compress Large JSON Reports if they exceed threshold
    for rep_name in ["eth_win_loss_reports.json", "win_loss_reports.json"]:
        rep_path = data_dir / rep_name
        archive_path = data_dir / f"{rep_name.replace('.json', '')}_archive.json.gz"
        if rep_path.exists():
            try:
                with open(rep_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                if isinstance(data, list) and len(data) > (max_active_json_reports + 100):
                    archive_slice = data[:-max_active_json_reports]
                    active_slice = data[-max_active_json_reports:]
                    
                    # Append or create gzip archive
                    existing_archived = []
                    if archive_path.exists():
                        try:
                            with gzip.open(archive_path, "rt", encoding="utf-8") as az:
                                existing_archived = json.load(az)
                        except Exception:
                            existing_archived = []
                    
                    existing_archived.extend(archive_slice)
                    with gzip.open(archive_path, "wt", encoding="utf-8") as az:
                        json.dump(existing_archived, az)
                    
                    with open(rep_path, "w", encoding="utf-8") as f:
                        json.dump(active_slice, f, indent=2)
                    
                    results["reports_archived"] += len(archive_slice)
                    logger.info("📦 [HYGIENE] Archived %d entries from %s to %s.", len(archive_slice), rep_name, archive_path.name)
            except Exception as e:
                logger.warning("[HYGIENE] Report compression error on %s: %s", rep_name, e)

    # 3. Purge Ephemeral OS / Temporary Files
    if os.name != "nt":
        # Vacuum Linux journalctl logs if permissions allow
        try:
            subprocess.run(["sudo", "journalctl", "--vacuum-size=50M"], capture_output=True, timeout=5)
            subprocess.run(["sudo", "journalctl", "--vacuum-time=3d"], capture_output=True, timeout=5)
        except Exception:
            pass

        # Clean /tmp orphaned temporary files
        tmp_dir = Path("/tmp")
        if tmp_dir.exists():
            for p in tmp_dir.glob("tmp*"):
                try:
                    if p.is_dir():
                        import shutil
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        p.unlink(missing_ok=True)
                    results["tmp_purged"] += 1
                except Exception:
                    pass

    # 4. Trigger Full Python Garbage Collection
    gc.collect()
    results["ram_reclaimed"] = True
    logger.info("✨ [HYGIENE COMPLETED] Anti-bloat duty successfully performed: %s", results)
    return results

import os
import sqlite3
import json
import pytest
from pathlib import Path
from kalshi_sim.utils.system_hygiene import run_assessment_hygiene_duty

def test_system_hygiene_preserves_brains_and_prunes_bloat(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    # Setup mock SQLite database
    db_path = data_dir / "kalshi_history.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("CREATE TABLE equity_snapshots (id INTEGER PRIMARY KEY, timestamp_utc TEXT)")
    cur.execute("CREATE TABLE ai_predictions (id INTEGER PRIMARY KEY, timestamp_utc TEXT)")
    cur.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY, details TEXT)")
    
    # Old records (> 10 days ago)
    cur.execute("INSERT INTO equity_snapshots VALUES (1, '2026-10-01T00:00:00')")
    cur.execute("INSERT INTO ai_predictions VALUES (1, '2026-10-01T00:00:00')")
    
    # Fresh records (< 2 days ago)
    cur.execute("INSERT INTO equity_snapshots VALUES (2, '2026-11-06T00:00:00')")
    cur.execute("INSERT INTO ai_predictions VALUES (2, '2026-11-06T00:00:00')")
    
    # Trade record (must NEVER be deleted)
    cur.execute("INSERT INTO trades VALUES (100, 'trade_lesson_brain')")
    conn.commit()
    conn.close()
    
    # Setup oversized json report (> 400 entries)
    rep_path = data_dir / "eth_win_loss_reports.json"
    dummy_reports = [{"report_id": f"REP_{i}"} for i in range(450)]
    rep_path.write_text(json.dumps(dummy_reports), encoding="utf-8")
    
    # Execute hygiene routine
    results = run_assessment_hygiene_duty(repo_root=tmp_path, max_days_snapshots=7, max_active_json_reports=300)
    
    assert results["db_vacuumed"] is True
    assert results["snapshots_pruned"] == 1
    assert results["predictions_pruned"] == 1
    assert results["reports_archived"] == 150
    
    # Verify DB content
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    remaining_snaps = cur.execute("SELECT count(*) FROM equity_snapshots").fetchone()[0]
    remaining_preds = cur.execute("SELECT count(*) FROM ai_predictions").fetchone()[0]
    trades_intact = cur.execute("SELECT count(*) FROM trades").fetchone()[0]
    conn.close()
    
    assert remaining_snaps == 1
    assert remaining_preds == 1
    assert trades_intact == 1
    
    # Verify JSON trimmed and archive created
    with open(rep_path, "r", encoding="utf-8") as f:
        active_reps = json.load(f)
    assert len(active_reps) == 300
    
    archive_path = data_dir / "eth_win_loss_reports_archive.json.gz"
    assert archive_path.exists()

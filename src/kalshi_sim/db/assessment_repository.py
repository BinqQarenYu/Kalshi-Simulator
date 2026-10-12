"""
src/kalshi_sim/db/assessment_repository.py

Institutional Assessment Repository & SQL Ingestion Engine.
Manages persistent storage, parsing, backfilling, and querying
of 6-trade quantitative batch assessments within SQLite (SCHEMA_V4_SQL).
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from kalshi_sim.db.schema import CURRENT_SCHEMA_VERSION, SCHEMA_V4_SQL

logger = logging.getLogger("kalshi_sim.db.assessment_repository")

DEFAULT_DB_PATH = Path("data/kalshi_history.db")


def ensure_assessment_schema(conn: sqlite3.Connection) -> None:
    """Ensure batch_assessments and related tables exist in the database."""
    conn.executescript(SCHEMA_V4_SQL)
    conn.commit()


def parse_markdown_assessment(md_text: str, filename: str = "") -> Dict[str, Any]:
    """Parse a 6-trade evaluation markdown document into structured SQL fields."""
    data: Dict[str, Any] = {
        "raw_markdown": md_text,
        "target_asset": "KXBTC15M",
    }

    # Extract Batch Number from title or filename
    batch_match = re.search(r"Batch\s*#(\d+)", md_text, re.IGNORECASE)
    if not batch_match and filename:
        batch_match = re.search(r"#(\d+)", filename)
    data["batch_number"] = int(batch_match.group(1)) if batch_match else 0

    # Document ID
    doc_match = re.search(r"\*\*Document ID:\*\*\s*`?([^`\n]+)`?", md_text)
    if doc_match:
        data["document_id"] = doc_match.group(1).strip()
    elif filename:
        data["document_id"] = Path(filename).stem
    else:
        data["document_id"] = f"batch_{data['batch_number']}"

    # Evaluation Date
    date_match = re.search(r"\*\*Evaluation Date:\*\*\s*([^\n\r]+)", md_text)
    if date_match:
        data["evaluation_date"] = date_match.group(1).strip()
    else:
        # Fallback to date from filename or current
        fn_date = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
        data["evaluation_date"] = fn_date.group(1) if fn_date else "2026-10-12"

    # Time Window
    tw_match = re.search(r"\*\*Time Window:\*\*\s*`?([^`\n]+)`?", md_text)
    data["time_window"] = tw_match.group(1).strip() if tw_match else None

    # Market Session
    ms_match = re.search(r"\*\*Market Session:\*\*\s*([^\n\r]+)", md_text)
    data["market_session"] = ms_match.group(1).strip() if ms_match else None

    # Target Asset
    asset_match = re.search(r"\*\*Target Asset:\*\*\s*([^\n\r]+)", md_text)
    if asset_match:
        data["target_asset"] = asset_match.group(1).strip()

    # Execution Vessel
    vessel_match = re.search(r"\*\*Execution Vessel:\*\*\s*`?([^`\n]+)`?", md_text)
    data["vessel"] = vessel_match.group(1).strip() if vessel_match else "Bot 1 V4"

    # Active Playbook
    pb_match = re.search(r"\*\*Active Playbook[^:]*:\*\*\s*`?([^`\n]+)`?", md_text)
    data["active_playbook"] = pb_match.group(1).strip() if pb_match else None

    # Verdict
    verdict_match = re.search(r"\*\*Gate Evaluation Verdict:\*\*\s*\*\*([^\*]+)\*\*", md_text)
    if verdict_match:
        data["verdict"] = verdict_match.group(1).strip()
    else:
        data["verdict"] = "PASSED" if "PASSED" in md_text else "EVALUATED"

    # Batch Record (Wins - Losses)
    rec_match = re.search(r"\*\*Batch Record\*\*\s*\|\s*\*\*(\d+)\s*Wins?\s*[–\-]\s*(\d+)\s*Losses?\*\*", md_text)
    if rec_match:
        data["wins"] = int(rec_match.group(1))
        data["losses"] = int(rec_match.group(2))
        data["total_trades"] = data["wins"] + data["losses"]
    else:
        data["wins"] = 0
        data["losses"] = 0
        data["total_trades"] = 6

    # Win Rate
    wr_match = re.search(r"\*\*Win Rate\*\*\s*\|\s*\*\*([\d\.]+)%\*\*", md_text)
    if wr_match:
        data["win_rate"] = float(wr_match.group(1))
    else:
        data["win_rate"] = round((data["wins"] / max(1, data["total_trades"])) * 100.0, 2)

    # Net Batch PnL
    pnl_match = re.search(r"\*\*Net Batch PnL\*\*\s*\|\s*\*\*([^\*\|]+)\*\*", md_text)
    if pnl_match:
        clean_pnl = pnl_match.group(1).replace("$", "").replace("+", "").strip()
        try:
            data["net_pnl"] = float(clean_pnl)
        except ValueError:
            data["net_pnl"] = 0.0
    else:
        data["net_pnl"] = 0.0

    # Pre-Batch Balance
    pre_match = re.search(r"\*\*Pre-Batch Balance\*\*\s*\|\s*\*\*([^\*\|]+)\*\*", md_text)
    if pre_match:
        clean_pre = pre_match.group(1).replace("$", "").strip()
        try:
            data["pre_batch_balance"] = float(clean_pre)
        except ValueError:
            data["pre_batch_balance"] = None
    else:
        data["pre_batch_balance"] = None

    # Post-Batch Balance
    post_match = re.search(r"\*\*Post-Batch Balance\*\*\s*\|\s*\*\*([^\*\|]+)\*\*", md_text)
    if post_match:
        clean_post = post_match.group(1).replace("$", "").strip()
        try:
            data["post_batch_balance"] = float(clean_post)
        except ValueError:
            data["post_batch_balance"] = None
    else:
        data["post_batch_balance"] = None

    # Market Regime
    regime_match = re.search(r"\*\*Regime State\*\*\s*\|\s*\*\*([^\*\|]+)\*\*", md_text)
    data["market_regime"] = regime_match.group(1).strip() if regime_match else None

    # Microstructure Context
    micro_match = re.search(r"### Market Microstructure Context:(.*?)(?=###|$)", md_text, re.DOTALL)
    data["microstructure_context"] = micro_match.group(1).strip() if micro_match else None

    # Winning Trades Autopsy
    win_auto_match = re.search(r"### Winning Trades Autopsy:(.*?)(?=###|##|$)", md_text, re.DOTALL)
    data["winning_autopsy"] = win_auto_match.group(1).strip() if win_auto_match else None

    # Losing Trades Autopsy
    loss_auto_match = re.search(r"### Losing Trades Autopsy.*?:(.*?)(?=###|##|$)", md_text, re.DOTALL)
    data["losing_autopsy"] = loss_auto_match.group(1).strip() if loss_auto_match else None

    # What Changes Triggered / Root Cause / Council Directives
    changes_match = re.search(r"## 4\. What Changes Triggered:(.*?)(?=## 5\.|$)", md_text, re.DOTALL)
    data["changes_triggered"] = changes_match.group(1).strip() if changes_match else None

    council_match = re.search(r"## 5\. Council Directives.*?:(.*?)(?=$)", md_text, re.DOTALL)
    data["council_directives"] = council_match.group(1).strip() if council_match else None

    # Parse individual trade rows from Table 2
    trades_list: List[Dict[str, Any]] = []
    trade_rows = re.findall(
        r"\|\s*\*\*T(\d+)\*\*\s*\|\s*`?([^`\|]+)`?\s*\|\s*\*\*([A-Z]+)\*\*\s*\|\s*(\d+)\s*\|\s*`?([^\`\|]+)`?\s*\|\s*`?([^\`\|]+)`?\s*\|\s*([^\`\|]+)\|\s*([^\`\|]+)\|\s*`?([^\`\|\n]+)`?",
        md_text,
    )
    for row in trade_rows:
        trades_list.append({
            "trade_index": int(row[0]),
            "ticker": row[1].strip(),
            "side": row[2].strip(),
            "size": int(row[3]),
            "entry_price": row[4].strip(),
            "settlement_price": row[5].strip(),
            "outcome": row[6].strip(),
            "net_pnl": row[7].strip(),
            "post_trade_balance": row[8].strip(),
        })
    data["trades_json"] = json.dumps(trades_list) if trades_list else None

    return data


def backfill_assessments_from_docs(
    docs_dir: Optional[Path] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Read all assessment markdown files in docs/ and persist into SQLite."""
    target_docs = docs_dir or Path("docs")
    target_db = db_path or DEFAULT_DB_PATH
    target_db.parent.mkdir(parents=True, exist_ok=True)

    if not target_docs.exists():
        logger.warning("Docs directory %s does not exist.", target_docs)
        return 0

    files = sorted(target_docs.glob("assessment_*.md"))
    if not files:
        logger.info("No assessment files found in %s.", target_docs)
        return 0

    conn = sqlite3.connect(str(target_db))
    ensure_assessment_schema(conn)

    count = 0
    cursor = conn.cursor()

    columns = [
        "batch_number", "document_id", "evaluation_date", "time_window",
        "market_session", "target_asset", "vessel", "active_playbook",
        "verdict", "wins", "losses", "total_trades", "win_rate", "net_pnl",
        "pre_batch_balance", "post_batch_balance", "market_regime",
        "microstructure_context", "winning_autopsy", "losing_autopsy",
        "root_cause_why", "changes_triggered", "council_directives",
        "lessons_learned", "trades_json", "raw_markdown"
    ]
    placeholders = ", ".join(["?"] * len(columns))
    sql = f"INSERT OR REPLACE INTO batch_assessments ({', '.join(columns)}) VALUES ({placeholders})"

    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8")
            parsed = parse_markdown_assessment(content, filename=file_path.name)
            if not parsed.get("batch_number"):
                continue

            values = [parsed.get(col) for col in columns]
            cursor.execute(sql, values)
            count += 1
        except Exception as e:
            logger.error("Error parsing/ingesting %s: %s", file_path.name, e)

    conn.commit()
    conn.close()
    logger.info("✅ Successfully ingested %d batch assessments into %s", count, target_db)
    return count


def get_assessment_by_batch(batch_number: int, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieve an assessment by batch number."""
    target_db = db_path or DEFAULT_DB_PATH
    if not target_db.exists():
        return None

    conn = sqlite3.connect(str(target_db))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM batch_assessments WHERE batch_number = ?", (batch_number,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_recent_assessments(limit: int = 10, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Retrieve recent batch assessments sorted by batch_number descending."""
    target_db = db_path or DEFAULT_DB_PATH
    if not target_db.exists():
        return []

    conn = sqlite3.connect(str(target_db))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM batch_assessments ORDER BY batch_number DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [dict(r) for r in rows]


def get_assessment_summary_stats(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Retrieve aggregated macro statistics across all recorded batch assessments."""
    target_db = db_path or DEFAULT_DB_PATH
    if not target_db.exists():
        return {
            "total_batches": 0,
            "total_trades": 0,
            "total_wins": 0,
            "total_losses": 0,
            "cumulative_pnl": 0.0,
            "win_rate": 0.0,
        }

    conn = sqlite3.connect(str(target_db))
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COUNT(*) as total_batches,
            COALESCE(SUM(total_trades), 0) as total_trades,
            COALESCE(SUM(wins), 0) as total_wins,
            COALESCE(SUM(losses), 0) as total_losses,
            COALESCE(SUM(net_pnl), 0.0) as cumulative_pnl
        FROM batch_assessments
    """)
    row = cursor.fetchone()
    conn.close()

    if not row or row[0] == 0:
        return {
            "total_batches": 0,
            "total_trades": 0,
            "total_wins": 0,
            "total_losses": 0,
            "cumulative_pnl": 0.0,
            "win_rate": 0.0,
        }

    total_batches, total_trades, total_wins, total_losses, cumulative_pnl = row
    win_rate = round((total_wins / max(1, total_trades)) * 100.0, 2)

    return {
        "total_batches": total_batches,
        "total_trades": total_trades,
        "total_wins": total_wins,
        "total_losses": total_losses,
        "cumulative_pnl": round(cumulative_pnl, 2),
        "win_rate": win_rate,
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    ingested = backfill_assessments_from_docs()
    stats = get_assessment_summary_stats()
    print(f"Ingested {ingested} assessments.")
    print("Assessment Summary Stats:", stats)

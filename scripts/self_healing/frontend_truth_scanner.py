"""
frontend_truth_scanner.py — Offline Frontend Ergonomics & UI Invariants Scanner
Zero-token, 100% offline static scanner for React/TypeScript frontend.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any

FRONTEND_SRC = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"

class UIReviewFinding:
    def __init__(self, file_path: str, line_no: int, category: str, message: str, snippet: str = ""):
        self.file_path = file_path
        self.line_no = line_no
        self.category = category
        self.message = message
        self.snippet = snippet

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": str(self.file_path),
            "line": self.line_no,
            "category": self.category,
            "message": self.message,
            "snippet": self.snippet
        }

def scan_frontend_file(file_path: Path) -> List[UIReviewFinding]:
    findings = []
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return findings

    for idx, line in enumerate(lines):
        line_no = idx + 1
        stripped = line.strip()

        # Check 1: Financial metric / price rendered without tabular-nums
        if any(term in stripped.lower() for term in ["price", "pnl", "balance", "strike", "spot"]) and "$" in stripped:
            if "tabular-nums" not in stripped and "<span" in stripped and "className" in stripped:
                findings.append(UIReviewFinding(
                    str(file_path), line_no, "MISSING_TABULAR_NUMS",
                    "Financial metric rendered without 'font-mono tabular-nums' causing tick jitter.",
                    stripped
                ))

        # Check 2: Raw parseFloat on prices
        if "parseFloat(" in stripped and any(term in stripped.lower() for term in ["price", "cost", "strike", "diff"]):
            findings.append(UIReviewFinding(
                str(file_path), line_no, "RAW_FLOAT_PARSING",
                "Raw parseFloat on monetary price risks IEEE-754 precision drift in frontend display.",
                stripped
            ))

    return findings

def scan_all_frontend_components() -> List[UIReviewFinding]:
    findings = []
    # STRICT BOUNDARY: Perpetual Trading Components Only
    comp_dir = FRONTEND_SRC / "components" / "perpetual"
    if not comp_dir.exists():
        return findings
    for ext in ["*.tsx", "*.ts"]:
        for file_path in comp_dir.glob(ext):
            findings.extend(scan_frontend_file(file_path))
    return findings

if __name__ == "__main__":
    findings = scan_all_frontend_components()
    print(f"[*] Frontend Truth Scanner found {len(findings)} ergonomic findings.")
    for f in findings[:5]:
        print(f"  - {Path(f.file_path).name}:{f.line_no} [{f.category}] -> {f.message}")

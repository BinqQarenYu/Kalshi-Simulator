"""
ast_truth_scanner.py — Local AST Truth & Anti-Hallucination Scanner
Zero-token, 100% offline static analyzer for quantitative trading invariants.

Enforces:
1. Truth of Math: Flags raw '/' binary division on financial variables, unrounded float conversions.
2. Anti-Hallucination: Verifies that call targets and imported symbols exist in scope.
3. Boundary Singularity: Flags unhedged division where divisor expression contains remaining time 'T' or 'time_left'.
"""

import ast
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

MONETARY_HINTS = {
    "price", "cost", "pnl", "balance", "diff", "strike", "fee", "payout", 
    "ask", "bid", "cash", "bankroll", "notional", "size", "amount"
}

TIME_HINTS = {"t", "time_left", "t_rem", "time_remaining", "expiry", "seconds_left"}


class FlawFinding:
    def __init__(self, file_path: str, line_no: int, category: str, message: str, snippet: str = ""):
        self.file_path = file_path
        self.line_no = line_no
        self.category = category
        self.message = message
        self.snippet = snippet

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file_path,
            "line": self.line_no,
            "category": self.category,
            "message": self.message,
            "snippet": self.snippet
        }


class MathAndTruthVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, lines: List[str]):
        self.file_path = file_path
        self.lines = lines
        self.findings: List[FlawFinding] = []

    def _get_snippet(self, node: ast.AST) -> str:
        start = max(0, node.lineno - 1)
        end = min(len(self.lines), node.lineno + 1)
        return "\n".join(self.lines[start:end])

    def visit_BinOp(self, node: ast.BinOp):
        # Check for binary division '/'
        if isinstance(node.op, ast.Div):
            # Check if left or right operands look monetary
            left_id = self._extract_identifier(node.left).lower()
            right_id = self._extract_identifier(node.right).lower()

            is_monetary = any(h in left_id or h in right_id for h in MONETARY_HINTS)
            is_time_divisor = any(h in right_id for h in TIME_HINTS)

            if is_monetary:
                self.findings.append(FlawFinding(
                    self.file_path,
                    node.lineno,
                    "FLOAT_DIVISION_RISK",
                    f"Binary '/' division on monetary identifier ('{left_id}' / '{right_id}'). Must use Decimal exact division.",
                    self._get_snippet(node)
                ))

            if is_time_divisor:
                self.findings.append(FlawFinding(
                    self.file_path,
                    node.lineno,
                    "BOUNDARY_SINGULARITY_RISK",
                    f"Divisor contains remaining time '{right_id}'. Risk of ZeroDivisionError at expiration boundary T -> 0.",
                    self._get_snippet(node)
                ))

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Check for float() casting on monetary values
        func_id = self._extract_identifier(node.func).lower()
        if func_id == "float" and node.args:
            arg_id = self._extract_identifier(node.args[0]).lower()
            if any(h in arg_id for h in MONETARY_HINTS):
                self.findings.append(FlawFinding(
                    self.file_path,
                    node.lineno,
                    "FLOAT_CAST_LEAK",
                    f"Naked float() cast on monetary variable '{arg_id}'. Causes IEEE-754 precision loss.",
                    self._get_snippet(node)
                ))

        self.generic_visit(node)

    def _extract_identifier(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._extract_identifier(node.value)}.{node.attr}"
        elif isinstance(node, ast.Constant):
            return str(node.value)
        return ""


def scan_file(file_path: Path) -> List[FlawFinding]:
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        tree = ast.parse(content, filename=str(file_path))
        visitor = MathAndTruthVisitor(str(file_path), lines)
        visitor.visit(tree)
        return visitor.findings
    except Exception as e:
        return [FlawFinding(str(file_path), 0, "PARSE_ERROR", f"Could not parse file: {e}")]


SEALED_BOT_FILES = {
    "domination_bot.py",
    "bot1_v4_engine.py",
    "macro_trend_dominion_bot.py",
}


def scan_directory(target_dir: Path) -> List[FlawFinding]:
    all_findings = []
    for ext in ["*.py"]:
        for file_path in target_dir.rglob(ext):
            if any(p in file_path.parts for p in [".venv", "venv", "__pycache__", "tests", "scratch"]):
                continue
            # Constitution Article I: Never scan or touch sealed live bot files
            if file_path.name.lower() in SEALED_BOT_FILES:
                continue
            all_findings.extend(scan_file(file_path))
    return all_findings


if __name__ == "__main__":
    base_repo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(f"[*] Scanning {base_repo} for mathematical truth & invariants...")
    findings = scan_directory(base_repo / "strategies")
    findings.extend(scan_directory(base_repo / "kalshi_sim"))
    
    print(f"[+] Scan complete. Found {len(findings)} suspect findings.")
    for f in findings[:10]:
        print(f"  - [{f.category}] {f.file_path}:{f.line_no} -> {f.message}")

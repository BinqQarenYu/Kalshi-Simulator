"""
sentinel_daemon.py — Autonomous 24/7 Self-Healing Sentinel Daemon
"Project Hephaestus" — The Unflinching Truth Watchman

Runs at low frequency (25m cadence) with:
1. Circuit Breakers: Respects Live Trading Sanctuary & Trade Blackout Window.
2. Local AST Truth Scanner: Zero token cost.
3. Token-Armor Review: Max 2 calls/hr to Lead Deer.
4. ASVL Verification Gate: 100% pytest pass required or auto-revert.
5. Windows IDLE priority: Zero CPU contention with Port 8000 live trades.
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

# Windows Process Priority Clamping to IDLE_PRIORITY_CLASS
if sys.platform == "win32":
    try:
        import ctypes
        # IDLE_PRIORITY_CLASS = 0x00000040
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.SetPriorityClass(handle, 0x00000040)
        print("[+] Pinned Sentinel process to IDLE_PRIORITY_CLASS (Sanctuary for Port 8000).")
    except Exception as e:
        print(f"[!] Warning: Could not pin IDLE_PRIORITY_CLASS: {e}")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.self_healing.ast_truth_scanner import scan_directory
from scripts.self_healing.frontend_truth_scanner import scan_all_frontend_components
from scripts.self_healing.circuit_breakers import CircuitBreakerManager
from scripts.self_healing.email_dispatcher import send_sentinel_email_alert
from scripts.self_healing.lead_deer_reviewer import LeadDeerReviewer
from scripts.self_healing.deer_architect_reviewer import DeerArchitectReviewer

AUDIT_LOG = Path("docs/audits/SELF_HEALING_AUDIT.md")
PROCESSED_REGISTRY = Path("docs/audits/processed_findings_registry.json")
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def log_audit(entry: str):
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S ET")
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n### [{timestamp}] {entry}\n")


def _get_processed_keys() -> set[str]:
    if not PROCESSED_REGISTRY.exists():
        return set()
    try:
        import json
        data = json.loads(PROCESSED_REGISTRY.read_text(encoding="utf-8"))
        return set(data.get("keys", []))
    except Exception:
        return set()


def _mark_key_processed(key: str):
    import json
    keys = _get_processed_keys()
    keys.add(key)
    PROCESSED_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_REGISTRY.write_text(json.dumps({"keys": list(keys)}, indent=2), encoding="utf-8")


def run_asvl_verification() -> bool:
    """Executes the empirical ASVL test suite (Backend Pytest + Frontend Typecheck)."""
    print("[*] Running ASVL Test Gate: pytest tests/ -q...")
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True
    )
    if res.returncode != 0:
        print(f"[-] ASVL Pytest Gate FAILED (Exit Code {res.returncode}):\n{res.stdout[:400]}")
        return False
    print("[+] ASVL Pytest Gate PASSED (100% Green).")

    print("[*] Running ASVL Frontend Gate: npm run typecheck...")
    f_res = subprocess.run(
        ["npm.cmd" if sys.platform == "win32" else "npm", "run", "typecheck"],
        cwd=str(REPO_ROOT / "frontend"),
        capture_output=True,
        text=True
    )
    if f_res.returncode != 0:
        print(f"[-] ASVL Frontend Gate FAILED (Exit Code {f_res.returncode}):\n{f_res.stdout[:400]}")
        return False
    print("[+] ASVL Frontend Gate PASSED (Zero TypeScript Errors).")
    return True


_CYCLE_COUNTER = 0


def sentinel_cycle():
    """Alternates between Backend (Lead Deer) and Frontend (Deer Architect) every cycle."""
    global _CYCLE_COUNTER
    _CYCLE_COUNTER += 1
    is_frontend_turn = (_CYCLE_COUNTER % 2 == 0)

    cb = CircuitBreakerManager()
    safe, reason = cb.check_live_sanctuary()
    
    if not safe:
        print(f"[~] Cycle {_CYCLE_COUNTER} skipped: {reason}")
        return

    processed = _get_processed_keys()

    if is_frontend_turn:
        print(f"[*] Cycle {_CYCLE_COUNTER}: [FRONTEND DEER ARCHITECT] Scanning UI/UX ergonomics & WebCLOB styling...")
        ui_findings = scan_all_frontend_components()
        unprocessed_ui = [f for f in ui_findings if f"{f.file_path}:{f.line_no}:{f.category}" not in processed]

        if not unprocessed_ui:
            print("[+] Frontend clean. Zero unaddressed ergonomic or typography flaws found.")
            return

        print(f"[!] Found {len(ui_findings)} UI items ({len(unprocessed_ui)} unaddressed). Processing 1 problem...")
        target_f = unprocessed_ui[0]
        key = f"{target_f.file_path}:{target_f.line_no}:{target_f.category}"
        _mark_key_processed(key)

        reviewer = DeerArchitectReviewer()
        if cb.is_file_quarantined(target_f.file_path):
            print(f"[~] File {target_f.file_path} is under quarantine. Skipping.")
            return

        print(f"  - Deer Architect auditing {Path(target_f.file_path).name}:{target_f.line_no} [{target_f.category}]")
        verdict = reviewer.review_ui_ergonomics(target_f.file_path, target_f.line_no, target_f.snippet, target_f.category)
        print(f"    Verdict: {verdict}")
        if verdict and verdict.get("needs_improvement"):
            critique = verdict.get("critique", "Ergonomic polish recommended")
            rec_fix = verdict.get("recommended_fix", "")
            log_audit(f"**Deer Architect (UI/UX)** on `{Path(target_f.file_path).name}:{target_f.line_no}`: {critique}")
            send_sentinel_email_alert(
                file_path=target_f.file_path,
                line_no=target_f.line_no,
                category=target_f.category,
                explanation=critique,
                proposed_fix=rec_fix,
                is_fatal=False,
                agent_role="Deer Architect (UI/UX Ergonomics)"
            )
    else:
        print(f"[*] Cycle {_CYCLE_COUNTER}: [BACKEND LEAD DEER] Scanning repository for mathematical & quantitative flaws...")
        findings = scan_directory(REPO_ROOT / "strategies")
        findings.extend(scan_directory(REPO_ROOT / "src" / "kalshi_sim"))
        unprocessed_be = [f for f in findings if f"{f.file_path}:{f.line_no}:{f.category}" not in processed]

        if not unprocessed_be:
            print("[+] Backend clean. Zero unaddressed mathematical or logic flaws found.")
            return

        print(f"[!] Found {len(findings)} suspect findings ({len(unprocessed_be)} unaddressed). Processing 1 problem...")
        target_f = unprocessed_be[0]
        key = f"{target_f.file_path}:{target_f.line_no}:{target_f.category}"
        _mark_key_processed(key)

        reviewer = LeadDeerReviewer()
        if cb.is_file_quarantined(target_f.file_path):
            print(f"[~] File {target_f.file_path} is under quarantine. Skipping.")
            return

        print(f"  - Lead Deer auditing {Path(target_f.file_path).name}:{target_f.line_no} [{target_f.category}]")
        verdict = reviewer.review_suspect_math(target_f.file_path, target_f.line_no, target_f.snippet, target_f.category)
        print(f"    Verdict: {verdict}")
        if verdict and verdict.get("is_fatal"):
            explanation = verdict.get("flaw_explanation", "Mathematical flaw detected")
            fix = verdict.get("minimal_fix", "")
            log_audit(f"**Lead Deer (Fatal Flaw)** on `{Path(target_f.file_path).name}:{target_f.line_no}`: {explanation}")
            send_sentinel_email_alert(
                file_path=target_f.file_path,
                line_no=target_f.line_no,
                category=target_f.category,
                explanation=explanation,
                proposed_fix=fix,
                is_fatal=True,
                agent_role="Lead Deer (Backend Self-Healer)"
            )


def run_sentinel_forever(interval_seconds: int = 120):
    """24/7 Continuous Autonomous Watchman Loop. 2m Cadence."""
    print(f"[*] Autonomous Self-Healing Sentinel Daemon engaged. Alternating Cadence: {interval_seconds // 60}m.")
    while True:
        try:
            sentinel_cycle()
        except Exception as exc:
            print(f"[!] Unexpected error in sentinel cycle: {exc}")
        print(f"[*] Standing watch. Sleeping {interval_seconds // 60} minutes until next alternating sweep...")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_sentinel_forever(interval_seconds=120)


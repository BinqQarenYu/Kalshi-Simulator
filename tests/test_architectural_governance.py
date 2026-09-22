"""Architectural Governance & Anti-Monolith Expansion Test Suite.

Ensures that refactored core files (server.py, standalone_bot.py, simulation_agent.py,
ParentHub.tsx, ClobTerminalView.tsx, etc.) do NOT expand back into convoluted monoliths.
"""

from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Enforce strict line budget ceilings on all 11 refactored files
REFACTORED_FILE_LIMITS = {
    # Backend Core Monoliths
    "src/kalshi_sim/server.py": 1500,
    "src/kalshi_sim/standalone_bot.py": 1100,
    "src/kalshi_sim/simulation_agent.py": 700,
    "src/kalshi_sim/ml/domination_bot.py": 1350,
    "src/kalshi_sim/routers/strategies.py": 1250,
    
    # Frontend Component Monoliths
    "frontend/src/components/ParentHub.tsx": 1550,
    "frontend/src/components/ClobTerminalView.tsx": 1400,
    "frontend/src/components/HistoricalAnalyticsTab.tsx": 800,
    "frontend/src/components/baby_bot/BabyBotParametersDrawer.tsx": 300,
    "frontend/src/components/ONNXSettingsPanel.tsx": 350,
    "frontend/src/components/BabyBotConsole.tsx": 1000,
}


@pytest.mark.parametrize("rel_path, max_lines", REFACTORED_FILE_LIMITS.items())
def test_refactored_file_line_budget_ceiling(rel_path: str, max_lines: int):
    """Verify that refactored monoliths remain clean and do not exceed their line budget ceilings."""
    target_path = REPO_ROOT / rel_path
    assert target_path.exists(), f"Refactored target file does not exist: {rel_path}"

    content = target_path.read_text(encoding="utf-8", errors="ignore")
    actual_lines = len(content.splitlines())

    assert actual_lines <= max_lines, (
        f"🚨 [MONOLITH EXPANSION VETO] File '{rel_path}' has expanded to {actual_lines} lines, "
        f"exceeding its strict budget ceiling of {max_lines} lines! "
        f"Extract new logic into a dedicated submodule instead of appending to this file."
    )


def test_no_super_monoliths_in_codebase():
    """Verify that no Python file in src/kalshi_sim exceeds 1,600 lines."""
    sim_dir = REPO_ROOT / "src" / "kalshi_sim"
    oversized = []

    for py_file in sim_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        line_count = len(py_file.read_text(encoding="utf-8", errors="ignore").splitlines())
        if line_count > 1600:
            oversized.append((py_file.relative_to(REPO_ROOT), line_count))

    assert not oversized, f"Found Python files exceeding 1,600 lines: {oversized}"

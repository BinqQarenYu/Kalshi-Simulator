"""tests/test_seal_immutability.py
Verifies the Constitutional Seal Immutability Shield and that automated tools
cannot touch or modify sealed live bots.
"""

from pathlib import Path
import pytest
from scripts.self_healing.circuit_breakers import CircuitBreakerManager, SEALED_BOT_FILES
from scripts.self_healing.ast_truth_scanner import scan_directory

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_constitution_seal_immutability_clause():
    """Verify that CONSTITUTION.md contains the ratified Seal Immutability Shield."""
    const_file = REPO_ROOT / "CONSTITUTION.md"
    assert const_file.exists(), "CONSTITUTION.md must exist."
    content = const_file.read_text(encoding="utf-8")
    
    assert "The Absolute Sealed Bot Protection Law (NEVER TOUCH SEALED LIVE BOTS)" in content
    assert "domination_bot.py" in content
    assert "macro_trend_dominion_bot.py" in content
    assert "strictly confined to Lane 2 Incubator" in content


def test_circuit_breaker_quarantine_sealed_bots():
    """Verify that CircuitBreakerManager considers sealed bot files quarantined by default."""
    cb = CircuitBreakerManager()
    
    sealed_examples = [
        "src/kalshi_sim/ml/domination_bot.py",
        "domination_bot.py",
        "src/kalshi_sim/bot1_v4_engine.py",
        "bot1_v4_engine.py",
        "strategies/macro_trend_dominion_bot.py",
        "macro_trend_dominion_bot.py",
        "data/seal_of_excellence.json",
    ]
    
    for file_path in sealed_examples:
        assert cb.is_sealed_bot_file(file_path) is True, f"Expected {file_path} to be recognized as sealed"
        assert cb.is_file_quarantined(file_path) is True, f"Expected {file_path} to be quarantined from touch"

    # Verify unsealed/paper files are not falsely marked as sealed
    assert cb.is_sealed_bot_file("src/kalshi_sim/incubator_agent.py") is False
    assert cb.is_sealed_bot_file("src/kalshi_sim/base_engine.py") is False


def test_ast_truth_scanner_skips_sealed_files(tmp_path):
    """Verify that scan_directory will never scan sealed files."""
    test_dir = tmp_path / "strategies"
    test_dir.mkdir()
    
    # Create a dummy sealed file with bad division that would normally be flagged
    sealed_file = test_dir / "domination_bot.py"
    sealed_file.write_text("x = price / 2\n", encoding="utf-8")
    
    # Create an unsealed file with bad division
    unsealed_file = test_dir / "candidate_bot.py"
    unsealed_file.write_text("x = price / 2\n", encoding="utf-8")
    
    findings = scan_directory(test_dir)
    flagged_files = [Path(f.file_path).name for f in findings]
    
    assert "domination_bot.py" not in flagged_files, "Sealed bot file must NEVER be flagged or touched"
    assert "candidate_bot.py" in flagged_files, "Unsealed candidate bot file should be processed in Lane 2"

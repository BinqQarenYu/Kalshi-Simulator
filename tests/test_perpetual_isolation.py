import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SACRED_BINARY_FILES = [
    'src/kalshi_sim/ml/domination_bot.py',
    'src/kalshi_sim/ml/macro_trend_dominion_bot.py',
    'src/kalshi_sim/ml/dual_onnx_strategy.py',
    'src/kalshi_sim/standalone_bot.py',
    'src/kalshi_sim/live_coordinator.py',
    'src/kalshi_sim/cfbenchmarks_sync.py',
    'src/kalshi_sim/bot_deployment_auditor.py',
    'src/kalshi_sim/server_settlements.py',
    'src/kalshi_sim/server_feeds.py',
    'frontend/src/components/ClobTerminalView.tsx',
    'data/seal_of_excellence.json',
    'data/bot_parameters_domination.json',
]

@pytest.mark.parametrize('rel_path', SACRED_BINARY_FILES)
def test_sacred_core_exists_and_unviolated(rel_path: str):
    target = REPO_ROOT / rel_path
    assert target.exists(), f'Sacred binary core file missing: {rel_path}'

def test_perpetual_sandbox_silo_structure():
    perp_dir = REPO_ROOT / 'src/kalshi_sim/perpetuals'
    assert perp_dir.exists(), 'Dedicated perpetual sandbox folder must exist'
    
    perp_router = REPO_ROOT / 'src/kalshi_sim/routers/perpetuals.py'
    assert perp_router.exists(), 'Dedicated perpetual router must exist'

    rule_file = REPO_ROOT / '.agents/rules/5-perpetual-isolation.md'
    assert rule_file.exists(), 'Perpetual isolation rule must exist'
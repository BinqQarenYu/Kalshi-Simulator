import os, sys
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path('/home/ec2-user/kalshi-bot')
os.chdir(_ROOT)
load_dotenv(_ROOT / '.env')
sys.path.insert(0, str(_ROOT / 'src'))

from kalshi_sim.ml.quolas_core.hmm_brain import HMMBrain

hmm = HMMBrain()
print(f"HMM model path: {hmm.model_path}")
print(f"HMM model exists: {hmm.model_path.exists()}")
print(f"HMM is_trained: {hmm.is_trained}")
print(f"HMM current_regime: {hmm.current_regime}")
print(f"HMM regime_probabilities: {hmm.regime_probabilities}")

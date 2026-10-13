import os, sys
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path('/home/ec2-user/kalshi-bot')
os.chdir(_ROOT)
load_dotenv(_ROOT / '.env')
sys.path.insert(0, str(_ROOT / 'src'))

from kalshi_sim.ml.onnx_engine import KalshiONNXEngine
from kalshi_sim.ml.quolas_core.hmm_brain import HMMBrain

print("=== CHECKING ONNX MODELS ON DISK ===")
models_dir = _ROOT / 'models'
if models_dir.exists():
    for f in models_dir.iterdir():
        print(f"  {f.name} ({f.stat().st_size} bytes)")
else:
    print("models_dir DOES NOT EXIST!")

print("\n=== TESTING KalshiONNXEngine() DEFAULT ===")
eng = KalshiONNXEngine()
print(f"Default model_path: {eng.model_path}")
print(f"Model exists: {eng.model_path.exists()}")
print(f"Session loaded: {eng.session is not None}")

print("\n=== TESTING KalshiONNXEngine(model_path='models/quolas.onnx') ===")
eng_quolas = KalshiONNXEngine(model_path="models/quolas.onnx")
print(f"Model exists: {eng_quolas.model_path.exists()}")
print(f"Session loaded: {eng_quolas.session is not None}")

print("\n=== TESTING HMM Brain ===")
hmm = HMMBrain()
print(f"HMM model exists: {hmm.model_path.exists()}")
print(f"HMM is trained/loaded: {hmm.is_trained}")

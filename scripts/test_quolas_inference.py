import os, sys
from pathlib import Path
from dotenv import load_dotenv
import numpy as np

_ROOT = Path('/home/ec2-user/kalshi-bot')
os.chdir(_ROOT)
load_dotenv(_ROOT / '.env')
sys.path.insert(0, str(_ROOT / 'src'))

from kalshi_sim.ml.onnx_engine import KalshiONNXEngine

eng = KalshiONNXEngine(model_path="models/quolas.onnx")
print(f"Session: {eng.session}")

# Test with dummy 28-D vector with realistic non-zero variance
dummy_raw = np.array([
    0.01, 10.0, 10.0, 1.0, 0.5, 0.5, 0.15, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0
], dtype=np.float32)

res = eng.process_feature_vector(dummy_raw)
print("Inference result on quolas.onnx:")
for k, v in res.items():
    print(f"  {k}: {v}")

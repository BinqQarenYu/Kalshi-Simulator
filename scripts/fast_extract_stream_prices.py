import time
from pathlib import Path
import json

data_dir = Path("data")

with open(data_dir / "win_loss_reports.json", "r", encoding="utf-8") as f:
    reports = json.load(f)

tickers = set(r.get("ticker") for r in reports if r.get("ticker"))

print(f"Finding stream files for {len(tickers)} report tickers...")
t0 = time.time()
stream_min_prices = {}

for ticker in tickers:
    sf = data_dir / f"stream_{ticker}.jsonl"
    if not sf.exists():
        continue
    min_yes = 1.0
    min_no = 1.0
    # Read binary mode and search fast
    with open(sf, "rb") as f:
        for line in f:
            # Fast byte check
            if b'"price":' not in line:
                continue
            try:
                # Fast slice
                p_idx = line.find(b'"price":') + 8
                p_end = line.find(b',', p_idx)
                p_val = float(line[p_idx:p_end])
                if 0.01 <= p_val <= 0.99:
                    if b'"yes"' in line and p_val < min_yes:
                        min_yes = p_val
                    elif b'"no"' in line and p_val < min_no:
                        min_no = p_val
            except Exception:
                continue
    stream_min_prices[ticker] = {"min_yes": min_yes, "min_no": min_no}

dt = time.time() - t0
print(f"Scanned {len(stream_min_prices)} stream files in {dt:.2f} seconds!")
with open("data/stream_min_prices_cache.json", "w") as f:
    json.dump(stream_min_prices, f, indent=2)
print("Saved to data/stream_min_prices_cache.json")

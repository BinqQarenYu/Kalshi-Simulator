import json
import time
from pathlib import Path
from datetime import datetime

data_dir = Path("data")
stream_files = sorted(list(data_dir.glob("stream_KXBTC15M-*.jsonl")), key=lambda x: x.stat().st_mtime)

recent_streams = []
for sf in stream_files:
    mtime = datetime.fromtimestamp(sf.stat().st_mtime)
    if mtime.strftime("%Y-%m-%d") in ("2026-09-04", "2026-09-05"):
        recent_streams.append(sf)

print(f"Testing price extraction on {len(recent_streams)} recent stream files...")
t0 = time.time()

stream_stats = {}
for sf in recent_streams[:10]:
    min_yes = 1.0
    min_no = 1.0
    with open(sf, "r", encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
                p = d.get("price")
                s = d.get("side")
                if p is not None and 0.01 <= p <= 0.99:
                    if s == "yes" and p < min_yes:
                        min_yes = p
                    elif s == "no" and p < min_no:
                        min_no = p
            except Exception:
                continue
    ticker = sf.stem.replace("stream_", "")
    stream_stats[ticker] = {"min_yes": min_yes, "min_no": min_no}

dt = time.time() - t0
print(f"Processed 10 stream files in {dt:.2f}s ({dt/10:.2f}s per file)")
for k, v in stream_stats.items():
    print(f"  {k}: min_yes={v['min_yes']:.2f}, min_no={v['min_no']:.2f}")

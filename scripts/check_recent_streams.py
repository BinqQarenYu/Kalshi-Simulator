from pathlib import Path
from datetime import datetime
import json

data_dir = Path("data")
stream_files = sorted(list(data_dir.glob("stream_KXBTC15M-*.jsonl")), key=lambda x: x.stat().st_mtime)

print(f"Total 15M stream files: {len(stream_files)}")
recent_streams = []
for sf in stream_files:
    mtime = datetime.fromtimestamp(sf.stat().st_mtime)
    if mtime.strftime("%Y-%m-%d") in ("2026-09-04", "2026-09-05"):
        recent_streams.append((sf, mtime))

print(f"15M stream files from past 2 days (Sept 4-5): {len(recent_streams)}")
for sf, mtime in recent_streams[-10:]:
    print(f"  {sf.name} ({sf.stat().st_size / (1024*1024):.1f} MB) - {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

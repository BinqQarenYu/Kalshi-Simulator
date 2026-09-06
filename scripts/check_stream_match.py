import json
from pathlib import Path

data_dir = Path("data")

with open(data_dir / "win_loss_reports.json", "r", encoding="utf-8") as f:
    reports = json.load(f)

matched = 0
for r in reports:
    ticker = r.get("ticker")
    sf = data_dir / f"stream_{ticker}.jsonl"
    if sf.exists():
        matched += 1

print(f"Total reports: {len(reports)}, Matched with exact stream file: {matched}")

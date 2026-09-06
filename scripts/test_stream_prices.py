import json
from pathlib import Path

sf = Path("data/stream_KXBTC15M-26SEP050845-45.jsonl")

prices_yes = []
prices_no = []

with open(sf, "r", encoding="utf-8") as f:
    for line in f:
        try:
            d = json.loads(line)
            side = d.get("side")
            price = d.get("price")
            if price is not None and 0.01 <= price <= 0.99:
                if side == "yes":
                    prices_yes.append(price)
                elif side == "no":
                    prices_no.append(price)
        except Exception:
            continue

print(f"Stream: {sf.name}")
print(f"YES prices count: {len(prices_yes)}, min={min(prices_yes):.2f}, max={max(prices_yes):.2f}")
print(f"NO prices count: {len(prices_no)}, min={min(prices_no):.2f}, max={max(prices_no):.2f}")

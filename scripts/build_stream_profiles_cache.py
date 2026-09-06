import json
import time
from pathlib import Path

data_dir = Path("data")
with open(data_dir / "win_loss_reports.json", "r", encoding="utf-8") as f:
    reports = json.load(f)

tickers = sorted(set(r.get("ticker") for r in reports if r.get("ticker")))
print(f"Building cache for {len(tickers)} unique tickers...")

t0 = time.time()
profiles = {}

for ticker in tickers:
    sf = data_dir / f"stream_{ticker}.jsonl"
    if not sf.exists():
        continue
    
    min_trade_yes = 1.0
    max_trade_yes = 0.0
    min_trade_no = 1.0
    max_trade_no = 0.0
    min_yes_ask = 1.0
    min_no_ask = 1.0
    max_yes_bid = 0.0
    max_no_bid = 0.0
    trade_count = 0

    with open(sf, "r", encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
                if d.get("ticker") and d.get("price_cents"):
                    trade_count += 1
                    raw_p = str(d.get("price_cents", "")).replace("¢", "").replace("c", "").strip()
                    side = d.get("side", "").lower()
                    if raw_p:
                        p = float(raw_p) / 100.0 if float(raw_p) > 1.0 else float(raw_p)
                        if 0.01 <= p <= 0.99:
                            if side == "yes":
                                min_trade_yes = min(min_trade_yes, p)
                                max_trade_yes = max(max_trade_yes, p)
                            elif side == "no":
                                min_trade_no = min(min_trade_no, p)
                                max_trade_no = max(max_trade_no, p)
                elif "price" in d and "side" in d:
                    p = float(d["price"])
                    side = d["side"].lower()
                    delta = float(d.get("delta", 0.0))
                    if 0.01 <= p <= 0.99 and delta > 0:
                        if side == "yes":
                            max_yes_bid = max(max_yes_bid, p)
                        elif side == "no":
                            max_no_bid = max(max_no_bid, p)
            except Exception:
                continue

    if max_no_bid > 0:
        min_yes_ask = min(min_yes_ask, round(1.0 - max_no_bid, 2))
    if max_yes_bid > 0:
        min_no_ask = min(min_no_ask, round(1.0 - max_yes_bid, 2))

    profiles[ticker] = {
        "trade_count": trade_count,
        "min_trade_yes": min_trade_yes if min_trade_yes < 1.0 else None,
        "max_trade_yes": max_trade_yes if max_trade_yes > 0.0 else None,
        "min_trade_no": min_trade_no if min_trade_no < 1.0 else None,
        "max_trade_no": max_trade_no if max_trade_no > 0.0 else None,
        "min_yes_ask": min_yes_ask if min_yes_ask < 1.0 else None,
        "min_no_ask": min_no_ask if min_no_ask < 1.0 else None,
        "max_yes_bid": max_yes_bid if max_yes_bid > 0.0 else None,
        "max_no_bid": max_no_bid if max_no_bid > 0.0 else None,
    }

dt = time.time() - t0
print(f"Extracted {len(profiles)} stream profiles in {dt:.2f}s")
with open("data/stream_profiles_cache.json", "w", encoding="utf-8") as f:
    json.dump(profiles, f, indent=2)
print("Saved cache to data/stream_profiles_cache.json")

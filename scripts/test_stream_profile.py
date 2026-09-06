import json
from pathlib import Path

def extract_stream_profile(stream_path: Path):
    min_trade_yes = 1.0
    max_trade_yes = 0.0
    min_trade_no = 1.0
    max_trade_no = 0.0
    min_yes_ask = 1.0
    min_no_ask = 1.0
    max_yes_bid = 0.0
    max_no_bid = 0.0
    trade_count = 0

    with open(stream_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
                # Trade event
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
                # Order book delta or snapshot
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

    # Note: On Kalshi, YES Ask = 1.00 - NO Bid, and NO Ask = 1.00 - YES Bid!
    if max_no_bid > 0:
        min_yes_ask = min(min_yes_ask, round(1.0 - max_no_bid, 2))
    if max_yes_bid > 0:
        min_no_ask = min(min_no_ask, round(1.0 - max_yes_bid, 2))

    return {
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

# Test on a file
sf = Path("data/stream_KXBTC15M-26SEP041200-00.jsonl")
if sf.exists():
    profile = extract_stream_profile(sf)
    print("Profile for", sf.name)
    print(json.dumps(profile, indent=2))

import json
from pathlib import Path
from decimal import Decimal

# Test a few stream files
data_dir = Path("data")
stream_files = sorted(data_dir.glob("stream_KXBTC15M-26SEP04*.jsonl")) + sorted(data_dir.glob("stream_KXBTC15M-26SEP05*.jsonl"))
print(f"Found {len(stream_files)} stream files for Sept 4 & 5")

for sf in stream_files[:5]:
    trades = []
    yes_bids = []
    no_bids = []
    yes_asks = []
    no_asks = []

    with open(sf, "r", encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
                # Check for trade
                if d.get("ticker") and d.get("price_cents"):
                    raw_p = str(d.get("price_cents", "")).replace("¢", "").replace("c", "").strip()
                    side = d.get("side", "").lower()
                    if raw_p:
                        p_flt = float(raw_p) / 100.0 if float(raw_p) > 1.0 else float(raw_p)
                        trades.append((side, p_flt))
                # Check for book update
                elif "price" in d and "side" in d:
                    p = float(d["price"])
                    s = d["side"].lower()
                    if s == "yes":
                        yes_bids.append(p)
                    elif s == "no":
                        no_bids.append(p)
            except Exception:
                continue

    trade_yes = [p for s, p in trades if s == "yes"]
    trade_no = [p for s, p in trades if s == "no"]

    print(f"\n--- {sf.name} ---")
    print(f"  Total Trades: {len(trades)} (YES trades: {len(trade_yes)}, NO trades: {len(trade_no)})")
    if trade_yes:
        print(f"  YES Trade Price Range: min=${min(trade_yes):.2f}, max=${max(trade_yes):.2f}")
    if trade_no:
        print(f"  NO Trade Price Range: min=${min(trade_no):.2f}, max=${max(trade_no):.2f}")
    if yes_bids:
        print(f"  YES Book Price Updates: min=${min(yes_bids):.2f}, max=${max(yes_bids):.2f}")
    if no_bids:
        print(f"  NO Book Price Updates: min=${min(no_bids):.2f}, max=${max(no_bids):.2f}")

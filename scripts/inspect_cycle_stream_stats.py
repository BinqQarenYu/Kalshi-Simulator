import json
from pathlib import Path
from decimal import Decimal

data_dir = Path("data")
with open(data_dir / "win_loss_reports.json", "r", encoding="utf-8") as f:
    reports = json.load(f)

# Reverse to chronological order
chronological_reports = list(reversed(reports))

print(f"Total reports: {len(chronological_reports)}")

cycle_stats = []

for idx, r in enumerate(chronological_reports):
    ticker = r.get("ticker", "")
    strike = float(r.get("strike_price", 0))
    settle = float(r.get("settlement_btc_price", 0))
    spot_diff = settle - strike
    side = r.get("bot_side", "yes").lower()
    actual_entry = float(r.get("entry_price", 0.50))
    outcome = r.get("outcome", "loss").lower()
    vpin = float(r.get("vpin_score", 0.15))
    cycle_time = r.get("cycle_time", "")

    # Check for stream file
    sf = data_dir / f"stream_{ticker}.jsonl"
    has_stream = sf.exists()
    min_yes_trade = None
    min_no_trade = None
    min_yes_book = None
    min_no_book = None

    if has_stream:
        with open(sf, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                    if d.get("ticker") and d.get("price_cents"):
                        raw_p = str(d.get("price_cents", "")).replace("¢", "").replace("c", "").strip()
                        s = d.get("side", "").lower()
                        if raw_p:
                            p_flt = float(raw_p) / 100.0 if float(raw_p) > 1.0 else float(raw_p)
                            if 0.01 <= p_flt <= 0.99:
                                if s == "yes":
                                    min_yes_trade = min(min_yes_trade or 1.0, p_flt)
                                elif s == "no":
                                    min_no_trade = min(min_no_trade or 1.0, p_flt)
                    elif "price" in d and "side" in d:
                        p = float(d["price"])
                        s = d["side"].lower()
                        if 0.01 <= p <= 0.99:
                            if s == "yes":
                                min_yes_book = min(min_yes_book or 1.0, p)
                            elif s == "no":
                                min_no_book = min(min_no_book or 1.0, p)
                except Exception:
                    continue

    cycle_stats.append({
        "idx": idx,
        "ticker": ticker,
        "cycle_time": cycle_time,
        "strike": strike,
        "settle": settle,
        "spot_diff": spot_diff,
        "side": side,
        "actual_entry": actual_entry,
        "actual_outcome": outcome,
        "vpin": vpin,
        "has_stream": has_stream,
        "min_yes_trade": min_yes_trade,
        "min_no_trade": min_no_trade,
    })

print("Sample cycle stream stats:")
for cs in cycle_stats[:10]:
    print(f"Cycle {cs['idx']}: {cs['ticker']} | diff={cs['spot_diff']:+.1f} | side={cs['side']} | actual_entry={cs['actual_entry']:.2f} | has_stream={cs['has_stream']} | min_yes={cs['min_yes_trade']} | min_no={cs['min_no_trade']}")

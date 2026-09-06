import json
from pathlib import Path

sf = Path("data/stream_KXBTC15M-26SEP050845-45.jsonl")
print("File:", sf.name, "Size:", sf.stat().st_size / (1024*1024), "MB")

orderbook_msgs = 0
trade_msgs = 0
min_yes_ask = 1.0
max_yes_bid = 0.0
min_no_ask = 1.0
max_no_bid = 0.0

with open(sf, "r", encoding="utf-8") as f:
    for line in f:
        try:
            d = json.loads(line)
            m_type = d.get("type") or d.get("channel")
            if "orderbook" in str(m_type) or "snapshot" in str(m_type) or "delta" in str(m_type):
                orderbook_msgs += 1
                msg = d.get("msg") or d
                yes_book = msg.get("yes") or []
                no_book = msg.get("no") or []
                for p, q in yes_book:
                    p = float(p)
                    if 0 < p < 1:
                        max_yes_bid = max(max_yes_bid, p)
                for p, q in no_book:
                    p = float(p)
                    if 0 < p < 1:
                        max_no_bid = max(max_no_bid, p)
            elif "trade" in str(m_type):
                trade_msgs += 1
        except Exception:
            continue

print(f"Orderbook msgs: {orderbook_msgs}, Trade msgs: {trade_msgs}")
print(f"Max YES bid seen: {max_yes_bid:.2f}, Max NO bid seen: {max_no_bid:.2f}")

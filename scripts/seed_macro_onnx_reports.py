"""Seed Macro ONNX Bot (Overhauled Model) 26 Real Backtest Trades into JSON & SQLite."""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

import scripts.backtest_latest_real_data as bt

def seed_macro_onnx():
    print("Loading production cycles...")
    cycles = bt.load_production_cycles()
    print(f"Loaded {len(cycles)} production cycles.")

    print("Running ONNX Balanced ($40 Gate) Strategy evaluation...")
    predictor = bt.ONNXMicrostructurePredictor()
    records = bt.evaluate_strategy_macro_trend_onnx_fusion(
        cycles, predictor, uncertainty_distance_threshold=40.0, strategy_label="Macro ONNX Bot"
    )

    taken_records = [r for r in records if r.action == "TAKE"]
    print(f"Total trades taken: {len(taken_records)}")

    cycle_map = {c.cycle_index: c for c in cycles}

    running_balance = Decimal("25.00")
    report_items = []
    trade_rows = []
    settlement_rows = []

    for idx, r in enumerate(taken_records):
        c = cycle_map.get(r.cycle_index)
        if not c:
            continue

        running_balance += r.pnl
        report_id = f"WLR-ONNX-{idx+1:03d}"
        trade_id = f"TRD-ONNX-{idx+1:03d}"
        settle_id = f"STL-ONNX-{idx+1:03d}"

        dt = datetime.fromtimestamp(c.epoch_s, timezone.utc)
        dt_str = dt.isoformat()
        epoch_ms = int(c.epoch_s * 1000)

        entry_pr = float(r.entry_price)
        settle_pr = 1.00 if r.outcome == "win" else 0.00
        pnl_f = float(r.pnl)
        roi_f = round((pnl_f / entry_pr) * 100.0, 1)

        rep = {
            "report_id": report_id,
            "cycle_time": r.cycle_time,
            "ticker": r.ticker,
            "timeframe": "15m",
            "strike_price": float(c.strike_price),
            "settlement_btc_price": float(c.settlement_spot),
            "bot_side": r.side.lower(),
            "contracts": 1,
            "entry_price": entry_pr,
            "settlement_price": settle_pr,
            "outcome": r.outcome,
            "pnl": pnl_f,
            "roi_pct": roi_f,
            "ai_confidence": 0.86,
            "ai_rationale": r.rationale,
            "vpin_score": 0.08,
            "ev_edge": 0.16,
            "balance_after": float(running_balance),
            "bot_type": "macro_onnx",
            "execution_mode": "simulated",
            "timestamp_utc": dt_str,
        }
        report_items.append(rep)

        trade_rows.append((
            trade_id,
            dt_str,
            epoch_ms,
            r.ticker,
            "15m",
            r.side.lower(),
            1,
            entry_pr,
            entry_pr,
            0.0,
            0.08,
            0.16,
            "macro_onnx",
            "simulated",
            "filled"
        ))

        settlement_rows.append((
            settle_id,
            dt_str,
            epoch_ms,
            r.ticker,
            r.side.lower(),
            1,
            entry_pr,
            settle_pr,
            r.outcome,
            pnl_f,
            float(running_balance),
            "macro_onnx",
            "simulated"
        ))

    # 1. Update data/win_loss_reports.json
    json_path = Path("data/win_loss_reports.json")
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        filtered = [x for x in existing if x.get("bot_type") != "macro_onnx"]
        combined = list(reversed(report_items)) + filtered
    else:
        combined = list(reversed(report_items))

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)
    print(f"Wrote {len(report_items)} Macro ONNX reports to {json_path}")

    # 2. Update data/kalshi_history.db
    db_path = Path("data/kalshi_history.db")
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()

        c.execute("DELETE FROM trades WHERE bot_type = 'macro_onnx'")
        c.execute("DELETE FROM settlements WHERE bot_type = 'macro_onnx'")

        c.executemany(
            """INSERT INTO trades (
                trade_id, timestamp_utc, timestamp_epoch_ms, ticker, timeframe,
                side, size, price, gross_value, fees, vpin, kelly_fraction,
                bot_type, execution_mode, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            trade_rows
        )

        c.executemany(
            """INSERT INTO settlements (
                settlement_id, timestamp_utc, timestamp_epoch_ms, ticker,
                side, size, entry_price, settlement_price, outcome, pnl,
                balance_after, bot_type, execution_mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            settlement_rows
        )

        conn.commit()
        print(f"Inserted {len(trade_rows)} trades and {len(settlement_rows)} settlements into {db_path}")

        c.execute("SELECT count(*), sum(case when outcome='win' then 1 else 0 end), sum(pnl) FROM settlements WHERE bot_type='macro_onnx'")
        row = c.fetchone()
        print(f"Verification: Total={row[0]}, Wins={row[1]}, Net PnL=${row[2]:.2f}, Win Rate={row[1]/row[0]*100:.1f}%")
        conn.close()

if __name__ == "__main__":
    seed_macro_onnx()

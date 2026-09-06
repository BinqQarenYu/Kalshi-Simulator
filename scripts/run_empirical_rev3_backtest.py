import json
from decimal import Decimal
from pathlib import Path
from scripts.backtest_latest_real_data import (
    load_production_cycles,
    compute_metrics,
    StrategyTradeRecord,
)

with open("data/stream_profiles_cache.json", "r", encoding="utf-8") as f:
    profiles = json.load(f)

cycles = load_production_cycles()

def evaluate_rev3_actual_side(cycles, discount_price, contracts=1):
    disc_dec = Decimal(str(discount_price))
    fee = Decimal("0.00")  # Maker orders pay $0.00 fee
    records = []

    for c in cycles:
        side = c.actual_side

        # 1. Pre-trade guardrails
        # VPIN Toxicity Gate
        if c.vpin_score > 0.40:
            records.append(StrategyTradeRecord(
                cycle_index=c.cycle_index, cycle_time=c.cycle_time, ticker=c.ticker,
                strategy_name=f"Domination Rev 3 (${discount_price:.2f})", action="VETO",
                side=side, entry_price=c.actual_entry, contracts=0, outcome="vetoed",
                pnl=Decimal("0.00"), gross_win=Decimal("0.00"), gross_loss=Decimal("0.00"),
                rationale=f"VPIN Toxicity Veto ({c.vpin_score:.2f} > 0.40)",
                macro_regime=c.macro_regime, spot_diff=c.spot_diff
            ))
            continue

        # Spot-Strike Distance Gate ($35 threshold)
        if abs(c.spot_diff) < Decimal("35.0"):
            records.append(StrategyTradeRecord(
                cycle_index=c.cycle_index, cycle_time=c.cycle_time, ticker=c.ticker,
                strategy_name=f"Domination Rev 3 (${discount_price:.2f})", action="VETO",
                side=side, entry_price=c.actual_entry, contracts=0, outcome="vetoed",
                pnl=Decimal("0.00"), gross_win=Decimal("0.00"), gross_loss=Decimal("0.00"),
                rationale=f"Spot-Strike Proximity Veto (|Diff|=${abs(c.spot_diff):.1f} < $35)",
                macro_regime=c.macro_regime, spot_diff=c.spot_diff
            ))
            continue

        # 2. Maker Resting Fill check against real L2 orderbook / trade tape
        prof = profiles.get(c.ticker)
        filled = False
        if prof:
            if side == "yes":
                min_p = prof.get("min_trade_yes") or prof.get("min_yes_ask")
            else:
                min_p = prof.get("min_trade_no") or prof.get("min_no_ask")

            if min_p is not None and Decimal(str(round(min_p, 2))) <= disc_dec:
                filled = True
        else:
            # Fallback for cycles without exact stream file:
            # Only filled if actual ask at entry was already <= discount limit price
            if c.actual_entry <= disc_dec:
                filled = True

        if not filled:
            records.append(StrategyTradeRecord(
                cycle_index=c.cycle_index, cycle_time=c.cycle_time, ticker=c.ticker,
                strategy_name=f"Domination Rev 3 (${discount_price:.2f})", action="UNFILLED",
                side=side, entry_price=disc_dec, contracts=0, outcome="unfilled",
                pnl=Decimal("0.00"), gross_win=Decimal("0.00"), gross_loss=Decimal("0.00"),
                rationale=f"Maker Resting Order @ ${discount_price:.2f} never reached (Auto-cancelled @ 45s)",
                macro_regime=c.macro_regime, spot_diff=c.spot_diff
            ))
            continue

        # 3. Settlement evaluation
        cycle_yes_won = c.settlement_spot >= c.strike_price
        bot_won = (side == "yes" and cycle_yes_won) or (side == "no" and not cycle_yes_won)

        if bot_won:
            outcome = "win"
            pnl = (Decimal("1.00") - disc_dec - fee) * Decimal(contracts)
            gross_w = pnl
            gross_l = Decimal("0.00")
        else:
            outcome = "loss"
            pnl = (-disc_dec - fee) * Decimal(contracts)
            gross_w = Decimal("0.00")
            gross_l = abs(pnl)

        records.append(StrategyTradeRecord(
            cycle_index=c.cycle_index, cycle_time=c.cycle_time, ticker=c.ticker,
            strategy_name=f"Domination Rev 3 (${discount_price:.2f})", action="TAKE",
            side=side, entry_price=disc_dec, contracts=contracts, outcome=outcome,
            pnl=pnl, gross_win=gross_w, gross_loss=gross_l,
            rationale=f"Maker Discount Fill @ ${discount_price:.2f} ($0.00 fee) | Diff: {c.spot_diff:+.1f}",
            macro_regime=c.macro_regime, spot_diff=c.spot_diff
        ))

    return records

print("=" * 115)
print("DOMINATION REV 3 EMPIRICAL BACKTEST (NO LOOKAHEAD BIAS - USING REAL-TIME BOT SIDE)")
print("=" * 115)
header = "{:<12} | {:<18} | {:<16} | {:<12} | {:<12} | {:<12} | {:<12} | {:<12}"
print(header.format("DISCOUNT", "FILLED/VETO/UNFILL", "WIN RATE", "NET PNL", "PROFIT FACT", "AVG WIN/LOSS", "EXPECTANCY", "MAX DRAWDOWN"))
print("-" * 115)

for disc in [0.48, 0.45, 0.40, 0.35, 0.30]:
    recs = evaluate_rev3_actual_side(cycles, disc, contracts=1)
    m = compute_metrics(f"Rev 3 (${disc:.2f})", recs)
    unfilled = sum(1 for r in recs if r.action == "UNFILLED")
    vetoed = sum(1 for r in recs if r.action == "VETO")
    ratio_str = f"{m.trades_taken}/{vetoed}/{unfilled}"
    wr_str = f"{m.win_rate_pct:.1f}% ({m.wins}W/{m.losses}L)"
    wl_str = f"${m.avg_win:.2f}/${m.avg_loss:.2f}"
    dd_str = f"${m.max_drawdown_dollars:.2f} ({m.max_drawdown_pct:.1f}%)"
    print(header.format(
        f"${disc:.2f}",
        ratio_str,
        wr_str,
        f"${m.net_pnl:+.2f}",
        f"{m.profit_factor:.2f}",
        wl_str,
        f"${m.expectancy_per_trade:+.2f}",
        dd_str
    ))
print("=" * 115)

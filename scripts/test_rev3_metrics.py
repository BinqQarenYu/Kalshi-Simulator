import json
from decimal import Decimal
from pathlib import Path
from scripts.backtest_latest_real_data import (
    load_production_cycles,
    evaluate_strategy_baseline,
    evaluate_strategy_domination_1,
    evaluate_strategy_domination_2,
    evaluate_strategy_macro_trend,
    evaluate_strategy_macro_trend_onnx_fusion,
    compute_metrics,
    ONNXMicrostructurePredictor,
    StrategyTradeRecord,
)

# Load cache
with open("data/stream_profiles_cache.json", "r", encoding="utf-8") as f:
    profiles = json.load(f)

cycles = load_production_cycles()

def evaluate_rev3(cycles, discount_price, contracts=1):
    disc_dec = Decimal(str(discount_price))
    fee = Decimal("0.00")
    records = []

    for c in cycles:
        # 1. Pre-trade guardrails
        if c.vpin_score > 0.40:
            records.append(StrategyTradeRecord(
                cycle_index=c.cycle_index, cycle_time=c.cycle_time, ticker=c.ticker,
                strategy_name=f"Domination Rev 3 (${discount_price:.2f})", action="VETO",
                side=c.actual_side, entry_price=c.actual_entry, contracts=0, outcome="vetoed",
                pnl=Decimal("0.00"), gross_win=Decimal("0.00"), gross_loss=Decimal("0.00"),
                rationale=f"VPIN Toxicity Veto ({c.vpin_score:.2f} > 0.40)",
                macro_regime=c.macro_regime, spot_diff=c.spot_diff
            ))
            continue

        if abs(c.spot_diff) < Decimal("35.0"):
            records.append(StrategyTradeRecord(
                cycle_index=c.cycle_index, cycle_time=c.cycle_time, ticker=c.ticker,
                strategy_name=f"Domination Rev 3 (${discount_price:.2f})", action="VETO",
                side=c.actual_side, entry_price=c.actual_entry, contracts=0, outcome="vetoed",
                pnl=Decimal("0.00"), gross_win=Decimal("0.00"), gross_loss=Decimal("0.00"),
                rationale=f"Spot-Strike Proximity Veto (|Diff|=${abs(c.spot_diff):.1f} < $35)",
                macro_regime=c.macro_regime, spot_diff=c.spot_diff
            ))
            continue

        # 2. Direction
        side = "yes" if c.spot_diff > Decimal("0.0") else "no"

        # 3. Fill check
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
            if c.actual_entry <= disc_dec or abs(c.spot_diff) > Decimal("100.0"):
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

        # 4. Settlement
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
            rationale=f"Maker Discount Sniper Fill @ ${discount_price:.2f} ($0.00 fee) | Diff: {c.spot_diff:+.1f}",
            macro_regime=c.macro_regime, spot_diff=c.spot_diff
        ))

    return records

for disc in [0.48, 0.45, 0.40, 0.35, 0.30]:
    recs = evaluate_rev3(cycles, disc, contracts=1)
    m = compute_metrics(f"Rev 3 (${disc:.2f})", recs)
    unfilled = sum(1 for r in recs if r.action == "UNFILLED")
    print(f"\n--- Rev 3 @ ${disc:.2f} ---")
    print(f"  Filled / Vetoed / Unfilled: {m.trades_taken} / {m.trades_vetoed - unfilled} / {unfilled}")
    print(f"  Win Rate: {m.win_rate_pct:.1f}% ({m.wins}W / {m.losses}L)")
    print(f"  Net PnL: ${m.net_pnl} | Profit Factor: {m.profit_factor:.2f}")
    print(f"  Avg Win: ${m.avg_win} | Avg Loss: ${m.avg_loss} | Payoff Ratio: {m.payoff_ratio:.2f}")
    print(f"  Expectancy: ${m.expectancy_per_trade}/trade")
    print(f"  Max Drawdown: ${m.max_drawdown_dollars} ({m.max_drawdown_pct:.1f}%) | Sharpe: {m.sharpe_ratio:.2f}")

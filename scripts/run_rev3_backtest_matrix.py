import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, Any, List

data_dir = Path("data")

# Load reports and cache
with open(data_dir / "win_loss_reports.json", "r", encoding="utf-8") as f:
    raw_reports = json.load(f)
chron_reports = list(reversed(raw_reports))

with open(data_dir / "stream_profiles_cache.json", "r", encoding="utf-8") as f:
    profiles = json.load(f)

def run_rev3_backtest(discount_price: float, contracts: int = 1):
    disc_dec = Decimal(str(discount_price))
    fee = Decimal("0.00")  # Maker orders pay $0.00 fee

    trades_taken = 0
    trades_filled = 0
    trades_unfilled = 0
    trades_vetoed = 0
    wins = 0
    losses = 0

    net_pnl = Decimal("0.00")
    gross_profit = Decimal("0.00")
    gross_loss = Decimal("0.00")

    records = []

    for idx, r in enumerate(chron_reports):
        ticker = r.get("ticker", f"CYCLE-{idx}")
        strike = Decimal(str(r.get("strike_price", 0)))
        settle = Decimal(str(r.get("settlement_btc_price", 0)))
        spot_diff = settle - strike
        vpin = float(r.get("vpin_score", 0.15))
        actual_entry = Decimal(str(r.get("entry_price", 0.50)))
        cycle_time = r.get("cycle_time", "")

        # 1. Guardrail filters
        if vpin > 0.40:
            trades_vetoed += 1
            records.append({
                "ticker": ticker, "action": "VETO", "reason": f"VPIN {vpin:.2f} > 0.40", "pnl": Decimal("0.00")
            })
            continue

        if abs(spot_diff) < Decimal("35.0"):
            trades_vetoed += 1
            records.append({
                "ticker": ticker, "action": "VETO", "reason": f"Coin-Flip Proximity |Diff|=${abs(spot_diff):.1f} < $35", "pnl": Decimal("0.00")
            })
            continue

        # 2. Strategy Direction
        side = "yes" if spot_diff > Decimal("0.0") else "no"
        trades_taken += 1

        # 3. Fill Check against real market data
        prof = profiles.get(ticker)
        filled = False
        fill_price = disc_dec

        if prof:
            if side == "yes":
                min_p = prof.get("min_trade_yes") or prof.get("min_yes_ask")
            else:
                min_p = prof.get("min_trade_no") or prof.get("min_no_ask")

            if min_p is not None and Decimal(str(round(min_p, 2))) <= disc_dec:
                filled = True
        else:
            # If no stream profile, check if actual entry was <= discount price
            if actual_entry <= disc_dec:
                filled = True
            elif abs(spot_diff) > Decimal("100.0"):
                # Big swing cycles always traded across the book
                filled = True

        if not filled:
            trades_unfilled += 1
            records.append({
                "ticker": ticker, "cycle_time": cycle_time, "side": side, "action": "UNFILLED",
                "reason": f"Price never touched ${discount_price:.2f} (Resting order auto-cancelled @ 45s)",
                "pnl": Decimal("0.00")
            })
            continue

        # 4. Settlement PnL
        trades_filled += 1
        cycle_yes_won = settle >= strike
        bot_won = (side == "yes" and cycle_yes_won) or (side == "no" and not cycle_yes_won)

        if bot_won:
            wins += 1
            pnl_ct = (Decimal("1.00") - fill_price - fee) * Decimal(contracts)
            gross_profit += pnl_ct
            outcome = "WIN"
        else:
            losses += 1
            pnl_ct = (-fill_price - fee) * Decimal(contracts)
            gross_loss += abs(pnl_ct)
            outcome = "LOSS"

        net_pnl += pnl_ct
        records.append({
            "ticker": ticker, "cycle_time": cycle_time, "side": side, "action": "FILLED",
            "entry": fill_price, "outcome": outcome, "pnl": pnl_ct, "diff": spot_diff
        })

    wr = (wins / trades_filled * 100.0) if trades_filled > 0 else 0.0
    pf = float(gross_profit / gross_loss) if gross_loss > Decimal("0.00") else (99.0 if gross_profit > 0 else 0.0)
    expectancy = (net_pnl / Decimal(trades_filled)) if trades_filled > 0 else Decimal("0.00")

    return {
        "discount_price": discount_price,
        "contracts": contracts,
        "total_cycles": len(chron_reports),
        "trades_taken": trades_taken,
        "trades_vetoed": trades_vetoed,
        "trades_filled": trades_filled,
        "trades_unfilled": trades_unfilled,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": wr,
        "net_pnl": net_pnl,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": pf,
        "expectancy": expectancy,
        "records": records,
    }

print("=" * 110)
print("3-STEP DOMINATION BOT REV 3 ('MAKER DISCOUNT SNIPER') BACKTEST MATRIX ACROSS DISCOUNT CEILINGS")
print("=" * 110)
header = "{:<12} | {:<8} | {:<8} | {:<8} | {:<16} | {:<12} | {:<12} | {:<12} | {:<12}"
print(header.format("DISCOUNT", "TAKEN", "FILLED", "UNFILLED", "WIN RATE", "NET PNL", "PROFIT FACT", "EXPECTANCY", "MAX PAYOFF"))
print("-" * 110)

for d in [0.48, 0.45, 0.40, 0.35, 0.30]:
    res = run_rev3_backtest(discount_price=d, contracts=1)
    payoff = f"{(1.0 - d)/d:.2f}x"
    wr_str = f"{res['win_rate_pct']:.1f}% ({res['wins']}W/{res['losses']}L)"
    print(header.format(
        f"${d:.2f}",
        str(res['trades_taken']),
        str(res['trades_filled']),
        str(res['trades_unfilled']),
        wr_str,
        f"${res['net_pnl']:+.2f}",
        f"{res['profit_factor']:.2f}",
        f"${res['expectancy']:+.2f}",
        payoff,
    ))
print("=" * 110)

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from decimal import Decimal

now = datetime.now(timezone.utc)
since = now - timedelta(hours=24)
since_ts = since.isoformat()

print(f"=== 24-HOUR TRADE AUDIT (AWS EC2) ===")
print(f"Server Time (UTC): {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
ast_now = now + timedelta(hours=3)
print(f"Qatar Time (AST):  {ast_now.strftime('%Y-%m-%d %H:%M:%S AST')}")
print(f"Audit Window:      Past 24 Hours (Since {since.strftime('%Y-%m-%d %H:%M:%S UTC')})\n")

def audit_file(path, label):
    try:
        with open(path, 'r') as f:
            trades = json.load(f)
    except Exception as e:
        print(f"[{label}] Error reading file: {e}")
        return []

    recent = []
    for t in trades:
        # Determine timestamp
        ts_str = t.get('timestamp') or t.get('settled_time') or t.get('created_at') or t.get('entry_time')
        if not ts_str:
            continue
        try:
            # Handle ISO string with or without Z/offset
            ts_clean = ts_str.replace('Z', '+00:00')
            dt = datetime.fromisoformat(ts_clean)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt >= since:
                recent.append((dt, t))
        except Exception:
            pass

    recent.sort(key=lambda x: x[0])
    print(f"--- {label} ({len(recent)} Trades in Last 24 Hours) ---")
    total_pnl = Decimal('0')
    wins = 0
    losses = 0
    for dt, t in recent:
        ticker = t.get('ticker') or t.get('market_ticker') or 'UNKNOWN'
        side = t.get('side', 'YES')
        pnl = Decimal(str(t.get('pnl', t.get('net_pnl', '0'))))
        result = t.get('result') or ('WIN' if pnl > 0 else 'LOSS' if pnl < 0 else 'FLAT')
        regime = t.get('market_regime') or t.get('regime') or 'N/A'
        cost = t.get('cost') or t.get('entry_price') or 'N/A'
        settle = t.get('settle_price') or t.get('settlement') or 'N/A'
        dt_ast = dt + timedelta(hours=3)
        time_ast = dt_ast.strftime('%H:%M:%S AST')

        if pnl > 0:
            wins += 1
        elif pnl < 0:
            losses += 1

        total_pnl += pnl
        print(f"[{time_ast}] {ticker} | Side: {side} | Cost: {cost} | Settle: {settle} | PnL: {pnl:+.2f} | Res: {result} | Regime: {regime}")

    print(f"Summary {label}: Wins={wins}, Losses={losses}, Net PnL={total_pnl:+.2f}\n")
    return recent

btc_recent = audit_file('data/win_loss_reports.json', 'BTC Bot 1 V4')
eth_recent = audit_file('data/eth_win_loss_reports.json', 'ETH Bot 1 V4')

print("--- ACTIVE SUPERVISOR & DOF DYNAMIC STATE ---")
for p in ['data/active_dof_patches.json', 'data/active_preset.json']:
    try:
        with open(p, 'r') as f:
            print(f"{p}: {f.read()[:500]}")
    except Exception as e:
        print(f"Could not read {p}: {e}")

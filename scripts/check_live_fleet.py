"""Check live fleet status, portfolio balance, and active positions on Kalshi."""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
load_dotenv(_ROOT / ".env")

from kalshi_sim.order_client import KalshiLiveOrderClient
from kalshi_sim.auth import PROD_REST_BASE

async def main():
    client = KalshiLiveOrderClient(os.getenv("KALSHI_API_KEY_ID"), os.getenv("KALSHI_PRIVATE_KEY_PATH"), base_url=PROD_REST_BASE)
    state = await client.get_live_portfolio_state()
    print("==================================================")
    print("KALSHI LIVE FLEET PORTFOLIO STATUS")
    print("==================================================")
    print(f"Total Balance     : ${state.balance_dollars:.4f}")
    print(f"Available Margin  : ${state.available_margin:.4f}")
    print(f"Payout Pending    : ${state.payout_pending:.4f}")
    print(f"Active Positions  : {len(state.positions)}")
    for p in state.positions:
        print(f"  * {p.ticker:<28} | {p.side.value.upper():<3} | {p.position} contract(s) | Fees: ${p.fees_paid:.4f} | Realized PnL: ${p.realized_pnl:.4f}")
    print("==================================================")
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())

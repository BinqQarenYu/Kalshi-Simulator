# Quantitative Trader & Operations Guide

This guide details daily operation, live trading guardrails, realistic micro-bankroll sizing, and emergency procedures across both the **Mother Server (Port 8000)** and **24/7 Standalone Engine (Port 8001)**.

---

## 🎯 Realistic Micro-Bankroll Management ($15.00 Model)

When trading ultra-short binary event contracts with micro-bankrolls ($15.00 – $25.00), capital preservation and mathematical discipline are non-negotiable:

| Parameter | Setting | Quantitative Rationale |
| :--- | :--- | :--- |
| **Contract Sizing / Trade** | **Strictly 1 Contract** | Hard-coded invariant. Eliminates single-trade ruin risk. |
| **Max Contracts / Cycle** | **Strictly 2 Contracts** | Caps maximum cycle risk to $0.96 (under 6.5% of $15.00 bankroll). |
| **Maker Order Ceiling** | **$0.48 / Contract** | Enforces resting limit orders at or below $0.48, qualifying for **$0.00 maker fees** on Kalshi. |
| **Target Profit / Win** | **+$0.52 / Contract** | Favorable asymmetric risk-to-reward ratio. |
| **Loss Streak Breaker** | **3 Consecutive Losses** | Automatic disarm into STANDBY mode. Protects capital during choppy regimes. |
| **Minimum Statistical Edge** | **6.0%** | Rejects trades where AI/CDF probability does not sufficiently exceed market ask. |
| **Minimum Net Expected Value**| **+$0.02 / Contract** | Guarantees positive expectancy after all hypothetical slippage. |
| **Minimum Spot Distance** | **$35.00 (BTC)** | Avoids coin-flip chop near the strike line. |

---

## ⚡ Daily Live Trading Workflow

### Step 1: Pre-Flight Verification
1. Ensure your Kalshi API private key is present in `keys/` and `.env` has `KALSHI_ENV=live`.
2. Confirm no orphaned trading processes are holding the process lock:
   ```powershell
   python -c "from kalshi_sim.process_lock import get_active_lock_holder; print(get_active_lock_holder())"
   ```
3. Run the automated test suite to certify system integrity:
   ```powershell
   $env:PYTHONPATH="src"
   python -m pytest tests/ -v
   ```

### Step 2: Launch the 24/7 Standalone Baby Bot
For dedicated live execution with zero distraction and zero chart lag, launch the Standalone Engine on Port 8001:
```powershell
.\run_standalone_bot.bat

# Or via Python CLI:
$env:PYTHONPATH="src"
python -m kalshi_sim.standalone_bot --port 8001 --live --asset BTC
```
The browser opens automatically to **`http://localhost:8001`**.

### Step 3: Operating the Pocket Cockpit
1. **Minimized Desktop View**:
   - By default, the Cockpit loads in **Minimized Mode** (fitting cleanly in a compact ~500px window).
   - Check the asset selector (`BTC`, `ETH`, `SOL`, `DOGE`) to confirm your target asset.
   - Click `[● ARMED / EXECUTE LIVE ORDERS]` to arm the bot.
   - The status pill turns green: `[ARMED / LIVE]`.
2. **Expanding Details**:
   - Click `[⤢ Expand]` in the header or `[▾ Show Institutional Telemetry & Parameters]` at the bottom.
   - Inspect live balance, today's PnL, target strike vs spot price, countdown, and active playbook.
   - Tweak strategy parameters if market volatility shifts, then click `[💾 Apply & Save]`.

---

## 🛑 Emergency Controls & Panic Procedures

### 1. 1-Click Emergency Panic (Port 8001)
If the market experiences extreme abnormal turbulence or you wish to cease trading immediately:
- Click `[🔴 EMERGENCY PANIC: CANCEL ALL ORDERS & STOP]` on the Cockpit.
- The engine instantly:
  1. Sets `is_armed = False` (disarming all future trade evaluations).
  2. Issues authenticated HTTP requests to Kalshi's V2 cancellation endpoint (`/trade-api/v2/portfolio/events/orders/{order_id}`) for every active resting order.
  3. Reconciles local position state and logs the incident.

### 2. Standby / Disarm Mode
- If you wish to pause order routing without cancelling resting orders:
  - Click `[○ DISARMED / STANDBY / SAFE MODE]`.
  - The bot continues streaming market feeds and calculating EV, but will not submit orders.

### 3. Automatic 3-Loss Streak Circuit Breaker
- If 3 consecutive trades in a session result in losses:
  - The bot automatically trips its internal circuit breaker and enters `STANDBY`.
  - To resume, the operator must manually review the market regime and click `[● ARMED]`, which resets the loss counter to 0.

---

## 🧹 Order Garbage Collection & Rollover Dead Zones

Binary prediction options experience sharp volatility spikes right around expiration boundaries:
- **Pre-Expiry Freeze ($T_{\text{rem}} \le 45\text{s}$)**:
  - No new orders are placed during the final 45 seconds of a cycle. Gamma risk is excessive and exchange matching slows down.
- **Post-Expiry Cooldown ($T_{\text{rem}} \ge 855\text{s}$)**:
  - The first 45 seconds of a fresh cycle are reserved for market makers to establish tight spreads.
- **Automated Watchdog Sweeper**:
  - Every 30 seconds, the engine compares resting order tickers against the active event. Any order belonging to an expired or non-active ticker is automatically swept and cancelled.
  - You can trigger an instant manual sweep at any time by clicking `[🧹 Sweep Expired Event Orders]`.

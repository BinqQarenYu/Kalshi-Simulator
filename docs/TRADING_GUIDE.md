# Quantitative Trader & Operations Guide

This guide details daily operation, bot selection, realistic bankroll management, and the Dual-Bot forward validation tournament.

---

## 🚀 Quick Start & Launch Commands

### 1. Launching the Platform
Run the all-in-one launcher or launch the backend and frontend separately:

```powershell
# Option A: One-click launcher
./launch_simulator.bat

# Option B: Manual Launch (Terminal 1 - Backend)
$env:PYTHONPATH="src"
python -m kalshi_sim.server

# Manual Launch (Terminal 2 - Frontend)
cd frontend
npm run dev
```

The WebCLOB Terminal will be accessible at `http://localhost:5173`.

---

## 🎯 Realistic Bankroll Management ($15.00 Model)

When trading with small account balances ($15.00), capital preservation is paramount:

| Account Metric | Setting | Rationale |
| :--- | :--- | :--- |
| **Starting Balance** | `$15.00` | Aligned 1:1 with real-world demo exchange balance ($15.28). |
| **Max Allocation / Trade** | `$0.50 – $1.50` | Micro-contract sizing (1–4 contracts) preventing ruin. |
| **Fractional Kelly Scale** | `0.25 (Quarter-Kelly)` | Smooths equity curve and guards against estimation variance. |
| **Max Portfolio Drawdown** | `15.0% ($2.25)` | Automatic circuit breaker protection. |

---

## ⚔️ The Dual-Bot Forward-Validation Tournament

The simulator runs both the **3-Step Domination Bot** and **ONNX Neural Net Bot** simultaneously on every live tick.

### How to Evaluate Performance
1. In the top navigation bar or drawer, open the **📊 Analytics & Journal** tab.
2. Select your desired strategy from the **Strategy Filter** dropdown:
   - **All Bots**: Aggregate multi-strategy performance.
   - **3-Step Domination Bot**: Cycle playbook alpha.
   - **ONNX Microstructure Bot**: 28-D tensor deep learning alpha.
3. Compare:
   - **Win Rate %** (Target $\ge 60\%$)
   - **Profit Factor / ROI**
   - **Max Drawdown %** (Target $\le 10\%$)
   - **Execution Latency** (Sub-2ms)

---

## 🛑 Emergency Controls & Position Liquidation

1. **1-Click Emergency Kill Switch**:
   Click the **KILL SWITCH** button in the header to instantly trip the circuit breaker, cancel all open orders, and prevent automated entries.
2. **Resume Trading**:
   Click **RESUME** to reset the circuit breaker and resume AI auto-trading.
3. **1-Click Close / Clear Position**:
   In the **Active Positions** table, click **Close** to market-liquidate open positions on the exchange, or **Clear** to remove finalized 0-contract records.

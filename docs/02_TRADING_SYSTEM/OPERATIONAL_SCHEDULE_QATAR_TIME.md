# Operational Trading Schedule & Golden Sessions (Qatar Local Time / AST)

**Time Zone Reference:** Qatar Local Time (`AST` = UTC+3) | Eastern Time (`ET` = UTC-4 EDT)  
**Dataset Ground Truth:** 2,350 Settled Event Cycles (Empirical Truth Protocol)  
**Fleet Status:** Active Live Capital on AWS EC2 (`13.63.158.94`)

---

## 1. Quick Reference: 24-Hour Visual Schedule (Qatar Time)

```text
========================================================================================
QATAR TIME (AST)      ET HOUR      SESSION STATUS     EMPIRICAL WIN RATE & PnL ACTION
========================================================================================
00:00 - 01:00         17:00 ET     [OFF] STANDBY      Inter-Session Deadband (Auto-Off)
01:00 - 02:00         18:00 ET     🟢 TRADE           59.9% WR | +$14.39 US Close Flow
02:00 - 03:00         19:00 ET     [OFF] AUTO-OFF     27.1% WR | -$12.72 Post-Market Thin Lull
03:00 - 05:00         20:00-21:59  🏆 GOLDEN #1       74.1% WR | +$53.20 #1 Best Session (84.4% @ 03:00)
05:00 - 09:00         22:00-01:59  🛑 TOXIC DEADZONE  31.5% WR | -$30.24 Asian Graveyard Drift (Shadow Mode)
09:00 - 10:00         02:00 ET     🟢 TRADE           56.8% WR | +$22.64 London Cash Open Surge
10:00 - 11:00         03:00 ET     [OFF] STANDBY      49.0% WR | Whipsaw Pruned (Shadow Mode)
11:00 - 12:00         04:00 ET     🟢 TRADE           68.1% WR | +$17.25 European Mid-Morning Flow
12:00 - 15:00         05:00-07:59  🛑 TOXIC DEADZONE  21.4% WR | -$62.65 Pre-Market Bleed Trap (Worst)
15:00 - 16:00         08:00 ET     🟢 TRADE           64.0% WR | +$9.95  Pre-NY Economic Flow
16:00 - 18:00         09:00-10:59  🛑 TOXIC DEADZONE  26.7% WR | -$32.97 Wall Street Opening Whipsaw
18:00 - 20:00         11:00-12:59  🟢 TRADE (TREND)   80.7% WR | +$32.34 US Midday Trend (100% @ 18:00)
20:00 - 23:00         13:00-15:59  🛑 TOXIC DEADZONE  32.4% WR | -$10.74 US Afternoon Lull (Shadow Mode)
23:00 - 00:00         16:00 ET     🟢 TRADE           59.2% WR | +$13.52 US Cash Market Close (MOC)
========================================================================================
```

---

## 2. Approved Golden Trading Windows (Qatar Time)

Trading is strictly authorized **ONLY** during these verified high-conviction windows:

### 1. 🏆 **The Asian Prime Session: 03:00 – 05:00 Qatar Time** (`20:00 – 21:59 ET`)
- **Combined Performance:** **`+$53.20 Realized PnL`**, **`74.1% Win Rate`**, **`4.82 Profit Factor`** across 224 trades.
- **Peak Hour (03:00 Qatar / 20:00 ET):** **`84.4% Win Rate`**, **`+$44.35 PnL`**, **`6.21 Profit Factor`**.
- **Quant Dynamic:** Asian market opening momentum creates clean, persistent directional orderflow with minimal counter-trend wicks.

### 2. 🌟 **The US Midday Institutional Trend: 18:00 – 20:00 Qatar Time** (`11:00 – 12:59 ET`)
- **Combined Performance:** **`+$32.34 Realized PnL`**, **`80.7% Win Rate`**, **`9.80 Profit Factor`** across 109 trades.
- **Peak Hour (18:00 Qatar / 11:00 ET):** **`100.0% Win Rate`** (56/56 wins), **`+$27.05 PnL`**, **`99.00 Profit Factor`**.
- **Quant Dynamic:** After the chaotic opening sweeps settle, institutional algorithmic order execution provides steady, predictable trend continuation.

### 3. 🌟 **The London Cash Open Expansion: 09:00 – 12:00 Qatar Time** (`02:00 – 04:59 ET`)
- **Combined Performance:** **`+$47.67 Realized PnL`**, **`57.9% Win Rate`**, **`1.74 Profit Factor`** across 484 trades.
- **Quant Dynamic:** European bank liquidity arrives, expanding market depth and driving strong momentum breakouts from overnight ranges.

### 4. 🌟 **The US Cash Market Close (MOC): 23:00 – 00:00 Qatar Time** (`16:00 – 16:59 ET`)
- **Combined Performance:** **`+$13.52 Realized PnL`**, **`59.2% Win Rate`**, **`1.57 Profit Factor`** across 130 trades.
- **Quant Dynamic:** S&P / Nasdaq Market-On-Close institutional rebalancing drives decisive terminal delta on BTC & ETH.

### 5. 🌟 **The Asian Open Flow: 01:00 – 02:00 Qatar Time** (`18:00 – 18:59 ET`)
- **Combined Performance:** **`+$14.39 Realized PnL`**, **`59.9% Win Rate`**, **`1.48 Profit Factor`** across 147 trades.

### 6. 🌟 **Pre-NY Economic Flow: 15:00 – 16:00 Qatar Time** (`08:00 – 08:59 ET`)
- **Combined Performance:** **`+$9.95 Realized PnL`**, **`64.0% Win Rate`**, **`2.40 Profit Factor`** across 50 trades.
- **Quant Dynamic:** US macro releases (CPI, Non-Farm Payrolls, PPI) create immediate directional velocity.

---

## 3. The Auto-Off Toxic Dead Zones (Qatar Time)

The system automatically switches to `WAIT` state during these windows to eliminate **`-$150.01`** in cumulative loss drag:

| Qatar Time (AST) | ET Equivalent | Win Rate | Loss Eliminated | Toxic Market Dynamic |
| :--- | :--- | :--- | :--- | :--- |
| **12:00 – 15:00** | 05:00 – 07:59 ET | **21.4%** *(07:00 ET is 7.7%)* | **`-$62.65`** | **Pre-Market Bleed Trap:** European lunch lull / US pre-dawn illiquid book; 78% of breakouts reverse. |
| **16:00 – 18:00** | 09:00 – 10:59 ET | **26.7%** | **`-$32.97`** | **Wall Street Opening Storm:** 10:00 AM economic whipsaws sweep both bids and asks. |
| **05:00 – 09:00** | 22:00 – 01:59 ET | **31.5%** | **`-$30.24`** | **Overnight Graveyard:** Thin books and low-conviction Brownian drift. |
| **20:00 – 23:00** | 13:00 – 15:59 ET | **32.4%** | **`-$10.74`** | **US Afternoon Lull:** Algorithmic liquidity dries up until the final cash hour. |

---

## 4. Winning Market Regimes & Calibrated Settings

### A. Market Regimes
- **`STORM` (Velocity Breakouts):** **`82.5% Win Rate`**, **`+$15.83`**, **`6.12 PF`** — Highest conviction taker entry.
- **`BLEED` (Orderflow Imbalance):**
  - Inside Golden Sessions: **`78.4% Win Rate`**, **`+$128.30 PnL`**.
  - Inside Toxic Sessions: **`26.1% Win Rate`**, **`-$125.27 PnL`** (Auto-vetoed by SessionTimingGuard).
- **`CHOP`:** **`30.0% Win Rate`**, **`-$5.87 PnL`** — **Strictly Disabled** (`enable_chop_trading: false`).

### B. The Anti-Bargain Trap Floor
- **Disproven:** Buying cheap contracts at **`$0.35 - $0.39`** had an **`86.5% loss rate`** (**`-$46.83 Net PnL`**).
- **Calibrated Rule:** `min_viable_ask_floor = 0.40`. The bot refuses to buy contracts below $\$0.40$.
- **Sweet Spot Corridor:** Contracts priced between **`$0.45` and `$0.62`** produced **`71.3% - 100% Win Rate`** and **`+$102.39 Net PnL`**.

### C. Execution Horizon
- `entry_window_open_minutes = 5.0` ($\tau \le 300\text{s}$): Confined to the high-certainty late-cycle window to eliminate early Brownian noise ($\tau > 600\text{s}$).

---

## 5. System Health & Infrastructure

- **AWS Production Server:** `13.63.158.94` (`/home/ec2-user/kalshi-bot`)
- **Systemd Daemons:**
  - `kalshi-bot.service` (Headless Server / Pocket Cockpit)
  - `kalshi-btc-bot.service` (Bitcoin Live Trader)
  - `kalshi-eth-bot.service` (Ethereum Live Trader)
- **Local PC Workstation:** Fully synced on branch `zero_hallucination_mode` with 65/65 unit tests passing.

---

## 6. Pre-Session Warm-Up, Auto-Off Shadow Mode & Anti-Paper Clutter Policy

### A. 15-Minute Pre-Session Warm-Up (`WARM_UP` Mode)
- **Trigger:** Exactly at minute $\ge 45$ of the preceding hour before any approved Golden Session (e.g., `14:45 AST` before the `15:00 AST` Pre-NY window; `17:45 AST` before the `18:00 AST` US Midday Trend; `02:45 AST` before the `03:00 AST` Asian Prime window).
- **Engine State:**
  - Connects and primes Binance L2 WebSocket feeds and Kalshi orderbook state.
  - Warms up rolling orderflow metrics: Order Flow Imbalance (OFI L1), Volume-Synchronized Probability of Toxicity (VPIN), 1m rolling volatility, and macro slope cache.
  - Runs ONNX neural inference and Kev Decision Oracle forward passes to hot-cache weights and model latency.
  - **Live Order Execution Gate:** Live order submission is held until `:00` at top-of-the-hour.

### B. Auto-Off & Shift to Shadow Mode (`SHADOW` Mode)
- **Trigger:** Immediately upon the conclusion of each approved Golden Session (e.g., at `13:00 ET` / `20:00 AST` after the US Midday window closes).
- **Engine State:**
  - Auto-off live order submission.
  - Shifts engine into shadow evaluation mode to continuously track market regimes, test ONNX predictions against market outcomes, and adapt continuous experience buffers.
  - In-memory Platt calibration alpha ($\alpha$) and Brier calibration scores continue to update in real-time.

### C. Zero Paper-Trade Persistence Protocol (Empirical Data Purity)
- **User Directive:** "dont save its paper trade, i dont need fake report like that papertrading."
- **Enforcement:**
  - `data/win_loss_reports.json` and `data/eth_win_loss_reports.json` strictly accept records where `execution_mode.lower() == "live"`.
  - Non-live (shadow, demo, paper) settlements update the in-memory learning models and continuous experience buffers only, and are **NEVER** written to disk reports.
  - This guarantees 100% data integrity for historical auditing, PnL tracking, and executive review.

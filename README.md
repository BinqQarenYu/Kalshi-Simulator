# Kalshi Quantitative Trading Terminal & Institutional Multi-Bot Ecosystem

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-262%20passed-brightgreen.svg)]()
[![Throughput](https://img.shields.io/badge/L2%20Throughput-135k%20deltas%2Fs-orange.svg)]()
[![Inference Latency](https://img.shields.io/badge/ONNX%20Latency-0.38ms-blue.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

An institutional-grade quantitative trading platform, market data ingestion pipeline, and real-time execution engine for **Kalshi Binary Prediction Event Contracts** across ultra-short **5-minute** and **15-minute** cycles for **Bitcoin (`KXBTC`)**, **Ethereum (`KXETH`)**, **Solana (`KXSOL`)**, and **Dogecoin (`KXDOGE`)**.

---

## 📚 Complete Documentation Index

- [🏛 System Architecture & Infrastructure](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/ARCHITECTURE.md)
- [⚡ 24/7 Standalone Engine & Pocket Cockpit Runbook](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/STANDALONE_BOT_RUNBOOK.md)
- [🤖 Quantitative Strategy Bots & Playbooks](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/STRATEGY_BOTS.md)
- [🔌 REST & WebSocket API Reference (Port 8000 & 8001)](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/API_REFERENCE.md)
- [🚀 Trader Operations & Bankroll Guide](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/TRADING_GUIDE.md)
- [🛡️ Data Integrity & Continuous Audit Rules](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/DATA_INTEGRITY.md)

---

## 🏛 Core Two-Tier Architecture & Workflow

The platform operates as an institutional two-tier system designed to completely isolate research/backtesting from production execution:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              TIER 1: MOTHER SERVER & PARENT HUB (PORT 8000)                │
│                         The Research Lab & Multi-Bot Arena                  │
│                                                                             │
│  • Full WebCLOB Terminal (React 18 + TypeScript + Canvas Depth Ladder)      │
│  • Multi-Bot Forward Validation Tournament (Dominion, ONNX, Scalper, Trend) │
│  • 28-Dimensional Microstructure Feature Extraction & Model Continuous Lab │
│  • Paper/Shadow trading on live exchange order flow without real capital    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Promotion Gate: BotDeploymentAuditor
                                       ▼ (Passes 4 Pillars: Math, Risk, API, DB)
┌─────────────────────────────────────────────────────────────────────────────┐
│             TIER 2: 24/7 STANDALONE BABY BOT DAEMON (PORT 8001)             │
│                         The Dedicated Execution Engine                      │
│                                                                             │
│  • Ultra-Lean Python Daemon (`standalone_bot.py`) trading 24/7 autonomously │
│  • Pocket Cockpit UI with Minimized Mode & Full Institutional View          │
│  • Sole Live Trading Authorization: 3-Step Dominion only                   │
│  • Hard Micro-Bankroll Invariants: 1 ct/trade, max 2 cts/cycle @ $0.48      │
│  • Anti-Burst Concurrency Mutex (`_eval_lock`) & Pre-Flight Intent Lock     │
│  • Windows 24/7 Away-Mode (`SetThreadExecutionState`) with Sleep Prevention │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Critical Quantitative & Architectural Invariants

1. **Micro-Bankroll Sizing Invariant**:
   - Sizing is strictly hard-capped to **1 contract per trade** and **maximum 2 contracts total exposure per cycle** across any active asset (`BTC`, `ETH`, `SOL`, `DOGE`).
   - Limit orders are placed as passive maker resting orders with a price ceiling of **$0.48** (maker orders enjoy **$0.00 taker fee** on Kalshi).
2. **Sole Execution Authorization**:
   - Only **3-Step Dominion** (`ThreeStepDominationBot`) is authorized to execute live money trades.
   - All other simulation/paper bots (Dominion 2, ONNX Microstructure, Macro Trend, Scalpers) are strictly locked out of live capital.
3. **Anti-Burst Concurrency Mutex & Pre-Flight Intent Reservation**:
   - An `asyncio.Lock()` serializes market evaluation per tick.
   - Synchronous reservation locks (`_in_flight_locks`) register pre-trade intents before sending network requests, completely eliminating duplicate burst fills caused by rapid WebSocket delta arrivals.
4. **3-Consecutive Loss Circuit Breaker**:
   - The engine continuously audits session settlements. If 3 consecutive losses occur, the bot automatically disarms into standby mode, logs the incident, and cancels all active resting orders.
5. **Exact Kalshi V2 API Endpoints**:
   - Live order placement uses `/trade-api/v2/portfolio/orders`.
   - Live order cancellation uses `/trade-api/v2/portfolio/events/orders/{order_id}` with authenticated RSA-PSS SHA-256 headers.
6. **CF Benchmarks BRTI 5Hz & 60s TWAP Parity**:
   - Spot prices stream from Kalshi's authenticated CME CF Bitcoin Real-Time Index feed (`cfbenchmarks_value_5hz` at 200ms) with official trailing 60s TWAP (`avg_60s_data`) for exact settlement parity.
7. **Strict Decimal Financial Arithmetic**:
   - Zero floating-point calculations. Python's `decimal.Decimal` and TypeScript's string-wrapped types govern all balances, PnL, order prices, fees, and strike differences.
8. **Process Mutual Exclusion Lock**:
   - File-based locking (`data/trading_engine.lock`) prevents dual-process execution between Mother Server and Standalone Bot.
9. **Windows 24/7 Away Mode**:
   - The standalone engine calls `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED)` to guarantee zero interruption when monitors turn off.

---

## 🌐 Multi-Asset & Multi-Timeframe Matrix

| Asset Symbol | Asset Name | 15-Minute Series | 5-Minute Series | CF Benchmarks Index | Min Spot Distance | Price Decimals |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BTC** | Bitcoin | `KXBTC15M` | `KXBTC5M` | `BRTI` | $35.00 | 2 |
| **ETH** | Ethereum | `KXETH15M` | `KXETH5M` | `ETHUSD_RTI` | $2.50 | 2 |
| **SOL** | Solana | `KXSOL15M` | `KXSOL5M` | `SOLUSD_RTI` | $0.50 | 2 |
| **DOGE** | Dogecoin | `KXDOGE15M` | `KXDOGE5M` | `DOGEUSD_RTI` | $0.0005 | 4 |

---

## 🎮 Dual Terminal UI Ecosystem

### 1. Standalone Pocket Cockpit (`http://localhost:8001`)
Served by `standalone_bot.py` on port `8001`:
* **Minimized Mode (Compact Desktop View)**:
  - Header with live engine status pill (`[ARMED / LIVE]` vs `[STANDBY / SAFE]`) and view toggle `[⤢ Expand / ⤡ Minimize]`.
  - Multi-asset switcher bar (`[₿ BTC] [Ξ ETH] [● SOL] [Ð DOGE]`).
  - Master controls: `[● ARMED / EXECUTE LIVE ORDERS]` and `[○ DISARMED / STANDBY / SAFE MODE]`.
  - Emergency Panic: `[🔴 EMERGENCY PANIC: CANCEL ALL ORDERS & STOP]`.
  - Sleek collapsible drawer toggle at the bottom.
* **Expanded Institutional Mode**:
  - 5 primary KPI cards (Kalshi Live Balance, Today's Realized PnL, Target Strike TO BEAT, Spot Index NOW, Active Countdown).
  - Dynamic parameter tuning & guardrail controls.
  - Microstructure telemetry (Inside Touch, BRTI Spot, Moneyness Diff, Statistical Edge, VPIN Toxicity Score, Playbook state).
  - Today's settled cycles journal.
  - Live execution log console.

### 2. Mother Server WebCLOB Terminal (`http://localhost:8000`)
Served by `server.py` on port `8000`:
* Full institutional WebCLOB interface with interactive depth ladder.
* TradingView-style spot price chart with real-time target strike line and 15-minute countdown.
* Dual-Bot Arena analytics, backtesting laboratory, and 28-D feature visualization.

---

## 🚀 Quick Launch Guide

### Prerequisites
* **Python 3.11+** installed (`pip install -e .` and `pip install -e ".[dev]"`).
* **Node.js 18+** & `npm` (for frontend terminal in `frontend/`).
* Valid Kalshi API credentials in `.env` (`KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH`, `KALSHI_ENV=live`).

### 1. Run 24/7 Standalone Engine (Production Live Trading)
```powershell
# Launch Standalone Engine on Port 8001
.\run_standalone_bot.bat

# Or via Python CLI:
$env:PYTHONPATH="src"
python -m kalshi_sim.standalone_bot --port 8001 --live --asset BTC
```
* Access the Pocket Cockpit at: `http://localhost:8001`

### 2. Run Mother Server (Parent Hub / Strategy Lab)
```powershell
# Launch Mother Server on Port 8000
.\run_dashboard.bat

# Or via Python CLI:
$env:PYTHONPATH="src"
python -m kalshi_sim.server
```
* Access the WebCLOB Terminal at: `http://localhost:8000`

---

## 🧪 Verification & Testing

Every quantitative component, order fill simulator, guardrail, and API endpoint is verified by an automated test suite:

```powershell
# Run backend pytest suite (all 262 tests must pass)
$env:PYTHONPATH="src"
python -m pytest tests/ -v

# Run frontend typecheck and production build
cd frontend
npm run typecheck
npm run build
```

---

## 📜 License & Compliance

This software is for institutional algorithmic research, quantitative simulation, and approved live execution on Kalshi under CFTC regulation. Distributed under the MIT License.

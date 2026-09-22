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

## 🏛 Core Unified Architecture & Workflow
 
 The platform operates as an institutional unified algorithmic trading platform converging multi-engine strategy execution, 1 Quant University, multi-paper incubation, and multi-live trading into **One Unified Terminal on Port 8000**:
 
 ```
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                 UNIFIED PORT 8000 MOTHER APPLICATION                       │
 │      Mother Server (`server.py`) + WebCLOB Terminal + Docked Cockpit       │
 │                                                                             │
 │  • Full WebCLOB Terminal (React 18 + TypeScript + Canvas Depth Ladder)      │
 │  • Docked Baby Bot Cockpit (Live Sizing, Presets 35¢/48¢/51¢/52¢, Panic)    │
 │  • Multi-Engine Execution Hub (Bot 1 Domination, Bot 2 ONNX, Bot 3 Trend)  │
 │  • Monolithic Lock: TradingEngineLock(owner_name="mother_server")          │
 └──────────────────────┬───────────────────────────────┬──────────────────────┘
                        │                               │
                        ▼                               ▼
 ┌──────────────────────────────────────┐ ┌────────────────────────────────────┐
 │  LANE 1: MULTI-LIVE EXECUTION        │ │  LANE 2: THE 1 QUANT UNIVERSITY    │
 │  (Real Money Kalshi API Execution)   │ │  (Multi-Paper Strategy Incubator)  │
 │                                      │ │                                    │
 │  • Authorized Sealed Bots:           │ │  • Academic Curriculum Tiers:      │
 │    - Bot 1: 3-Step Domination Bot    │ │    - Freshman (0-9 cycles)         │
 │    - Bot 3: Macro Trend Dominion     │ │    - Sophomore (10-19 cycles)      │
 │  • Micro-Bankroll Armor: 1 ct/asset  │ │    - Junior (20-29 cycles)         │
 │  • Combined Cap: 2 cts max/cycle     │ │    - Senior / Candidate (30+ cyc)  │
 │  • LiveCoordinator Anti-Wash Shield  │ │  • Real-Time Paper Execution       │
 └──────────────────────────────────────┘ └─────────────────┬──────────────────┘
                                                            │
                                  Passage of Seal of Excellence Gate
                                  (5-Pillar Audit: Math, Risk, Truth, CFTC, Edge)
                                                            ▼
                                           SHA-256 Seal Minted on Disk
                                           (`data/seal_of_excellence.json`)
 ```
 
 ---
 
 ## 🛡️ Critical Quantitative & Architectural Invariants
 
 1. **Micro-Bankroll Sizing Invariant**:
    - Sizing is strictly hard-capped to **1 contract per trade** and **maximum 2 contracts total exposure per cycle** across any active asset (`BTC`, `ETH`, `SOL`, `DOGE`).
    - Limit orders are placed as passive maker resting orders with a price ceiling of **$0.48** (maker orders enjoy **$0.00 taker fee** on Kalshi).
 2. **Multi-Bot Live Authorization & The Seal of Excellence**:
    - Only bots possessing a verified automated SHA-256 Seal of Excellence on disk (**Bot 1 `3_step_domination_bot`** and **Bot 3 `macro_trend_dominion`**) are authorized to execute live real-money trades.
    - All other simulation and paper bots remain safely enrolled in the **Lane 2 Quant University** until 5-pillar graduation.
 3. **Multi-Bot Anti-Cannibalism & Wash-Trading Shield**:
    - Multiple bots on the same account/ticker must **NEVER** hold opposing positions (YES vs NO) on the same contract cycle.
    - Synchronously arbitrated by `LiveCoordinator` (`live_coordinator.py`) with absolute CFTC anti-wash trading veto power. Cooperative same-direction execution permitted up to 2 contracts total.
 4. **Anti-Burst Concurrency Mutex & Pre-Flight Intent Reservation**:
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

## 🎮 The Unified Terminal UI Ecosystem
 
 ### 1. Unified Mother Application (`http://localhost:8000`)
 Served by `server.py` on port `8000`:
 * **Full Institutional WebCLOB Terminal**:
   - Interactive L2 canvas order book ladder with live depth profile.
   - Real-time TradingView-style price chart, 5Hz CME CF BRTI spot sync, and 15-minute countdown.
   - Live trade tape, micro-fill animations, and adverse selection alerts.
 * **Integrated Docked Baby Bot Console (Right Rail)**:
   - Live Micro-Bankroll Sizing ($15-$75 equity armor capped to 1 ct/asset).
   - Fast-action preset pills: `35¢`, `48¢`, `51¢`, `52¢`.
   - Dedicated strategy dials for sealed live bots (**Bot 1** & **Bot 3**).
   - Instant failsafe controls: `ARMED / LIVE` vs `DISARMED / STANDBY` and `EMERGENCY PANIC`.
 * **The 1 Quant University & Strategy Incubator**:
   - Lane 2 Paper trading tournament tracking candidate algorithms.
   - Academic standings (Freshman -> Sophomore -> Junior -> Senior).
   - Automated 5-Pillar Seal of Excellence examination and promotion audit.
 
 ### 2. Standalone Lightweight Daemon (Headless / Win32 Widget)
 * Runs headless via `standalone_bot.py` or with ultra-compact native Win32 HUD (`win32_window.py`).
 * Fully synchronized with `LiveCoordinator` and disk seals.
 
 ---
 
 ## 🚀 Quick Launch Guide
 
 ### Prerequisites
 * **Python 3.11+** installed (`pip install -e .` and `pip install -e ".[dev]"`).
 * **Node.js 18+** & `npm` (for frontend terminal in `frontend/`).
 * Valid Kalshi API credentials in `.env` (`KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH`, `KALSHI_ENV=live`).
 
 ### Run Unified Institutional Terminal (Port 8000)
 ```powershell
 # Launch Unified Mother Server (Engine + UI + University)
 .\run_dashboard.bat
 
 # Or via Python CLI:
 $env:PYTHONPATH="src"
 python -m kalshi_sim.server
 ```
 * Access the Unified Terminal at: `http://localhost:8000`

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

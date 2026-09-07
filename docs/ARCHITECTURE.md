# System Architecture & Infrastructure

The **Kalshi Quantitative Trading Simulator & Live Execution Terminal** is an institutional-grade algorithmic platform for trading Kalshi prediction event contracts across 5-minute and 15-minute cycles on **Bitcoin (`KXBTC`)**, **Ethereum (`KXETH`)**, **Solana (`KXSOL`)**, and **Dogecoin (`KXDOGE`)**.

---

## 🏛 High-Level System Topology

The platform is architected into two completely decoupled operational tiers, preventing research and testing overhead from contaminating live exchange execution:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   AUTHENTICATED MARKET DATA INGESTION                                   │
│                                                                                                         │
│  • Kalshi WebSocket Feed (`wss://api.elections.kalshi.com/trade-api/ws/v2`): L2 Book Deltas, Trades     │
│  • CME CF Benchmarks 5Hz Feed (`cfbenchmarks_value_5hz`): Real-time Spot Index (200ms tick resolution)  │
│  • Trailing 60s TWAP (`avg_60s_data`): Official settlement index parity                                 │
│  • Coinbase / Binance Fallback Streams: High-throughput redundancy                                      │
└────────────────────────────────────────────────────┬────────────────────────────────────────────────────┘
                                                     │
                                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    ORDER BOOK & DATA NORMALIZATION LAYER                                │
│                                                                                                         │
│  • OrderBookManager: Local L2 Central Limit Order Book (CLOB) with sequence continuity validation       │
│  • TickWriter / DBWriter: Asynchronous write-behind queues to SQLite (`data/kalshi_history.db`)         │
│  • OHLCVAggregator: Multi-timeframe bar formation & rolling microstructure indicators                   │
│  • Strict Decimal Precision: Zero IEEE 754 float drift across all pricing and strike calculations       │
└────────────────────────────────────────────────────┬────────────────────────────────────────────────────┘
                                                     │
                         ┌───────────────────────────┴───────────────────────────┐
                         ▼                                                       ▼
┌─────────────────────────────────────────────────┐   ┌─────────────────────────────────────────────────┐
│      TIER 1: MOTHER SERVER & STRATEGY LAB       │   │   TIER 2: 24/7 STANDALONE ENGINE (BABY BOT)     │
│             (Port 8000: `server.py`)            │   │         (Port 8001: `standalone_bot.py`)        │
│                                                 │   │                                                 │
│  • Multi-Bot Forward Validation Tournament:     │   │  • Dedicated Live Capital Execution Daemon      │
│    - 3-Step Domination Bot (Moneyness CDF)      │   │  • Sole Authorized Bot: 3-Step Dominion         │
│    - ONNX Microstructure Neural Net (28-D)      │   │  • Pocket Cockpit UI (Minimized & Full Modes)   │
│    - Dominion 2 Bot (Kalshi Odds Inversion)     │   │  • Hard Micro-Sizing Invariant:                 │
│    - Macro Trend & Scalping Engines             │   │    Strictly 1 ct/trade, max 2 cts/cycle @ $0.48 │
│  • Institutional WebCLOB Terminal (React/Vite)  │   │  • Anti-Burst Mutex (`_eval_lock`)              │
│  • 28-D Microstructure Feature Extraction Lab   │   │  • Pre-Flight Intent Reservation Lock           │
│  • Virtual Paper Trading & Backtesting Arena    │   │  • 3-Consecutive Loss Circuit Breaker           │
│  • Lane 2 (Shadow Paper) & Lane 3 (Sim)         │   │  • Windows 24/7 Away Mode (Sleep Prevention)    │
│  • Certifies bots via BotDeploymentAuditor      │   │  • Lane 1 (Production Real Money Trading)       │
└─────────────────────────────────────────────────┘   └─────────────────────────────────────────────────┘
                         │                                                       │
                         └───────────────────────────┬───────────────────────────┘
                                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   EXECUTION & RISK GUARDRAILS LAYER                                     │
│                                                                                                         │
│  • AgentGuardrails: Sizing validation, 1-2 contract cycle locks, pre-flight intent reservation           │
│  • AgentIntegrityCheck: Background invariant auditor (CLOB continuity, uncrossed books, clock parity)   │
│  • Mutual Exclusion Lock: `data/trading_engine.lock` prevents dual-process live trading collisions       │
│  • VPIN Toxicity Gate: Volume-Synchronized Probability of Toxicity vetoes trades during toxic bursts    │
│  • 30-Second Order Sweeper: Periodic watchdog cancels stale resting orders from expired cycles          │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ The Three Operational Execution Lanes

The platform segregates capital, data streams, and algorithms across three distinct operational regimes:

### Lane 1: LIVE (Real Money Production)
- Exactly **ONE** strategy holds the active Live Execution Token at any time (default: `ThreeStepDominion`).
- Runs in Tier 2 (`standalone_bot.py`) on port `8001`.
- Sizing strictly hard-capped to 1 contract per trade, maximum 2 contracts exposure per cycle at maker limit ceiling $0.48.
- Routes signed orders directly to Kalshi production endpoints (`https://api.elections.kalshi.com/trade-api/v2`).
- Never runs paper simulations or virtual order book walks when live mode is engaged.

### Lane 2: SHADOW / INCUBATOR (Paper on Live Market Microstructure)
- Ingests the **exact same live exchange tick feeds** (BRTI 5Hz + Kalshi L2 CLOB) concurrently with Lane 1.
- Allows candidate bots (e.g. Dominion 2, ONNX Microstructure, Macro Trend) to generate hypothetical orders, virtual fills, and track shadow PnL without risking real capital.
- Runs inside Tier 1 (`server.py`) on port `8000`.

### Lane 3: SIMULATION / BACKTESTING (Offline Data & Jump-Diffusion)
- Offline quantitative research using historical DuckDB/CSV data or synthetic jump-diffusion BTC spot price paths.
- Used for machine learning training, feature ablation studies, and hyperparameter sweeps.

---

## 🔒 Concurrency Control & Anti-Burst Protection

High-frequency WebSocket delta bursts can deliver multiple book updates within milliseconds. Without concurrency synchronization, an algorithm could evaluate the same signal multiple times before the first order finishes routing over the network.

To eliminate this vulnerability:
1. **Evaluation Mutex (`asyncio.Lock`)**:
   - Market evaluations in `standalone_bot.py` are serialized under `self._eval_lock`.
2. **Synchronous Intent Reservation (`_in_flight_locks`)**:
   - Before dispatching an HTTP POST to Kalshi, `validate_pre_trade_intent()` synchronously records an in-flight intent reservation for that specific market cycle:
     ```python
     self._in_flight_locks[market_ticker] = True
     self._cycle_contracts_count[cycle_key] = current_count + requested_contracts
     ```
   - Subsequent ticks arriving while the network request is in flight are immediately rejected with `Pre-trade intent already in-flight`.
3. **Intent Release & Final Settlement**:
   - Once the order placement finishes (or errors out), `release_in_flight_intent()` clears the reservation, ensuring perfect cycle accounting.

---

## 🔄 The 4-Stage Strategy Promotion Lifecycle

Every algorithmic trading model must graduate through four sequential gates before deployment to live capital:

```
┌──────────────┐      ┌───────────────┐      ┌───────────────┐      ┌──────────────┐
│  1. COOK     │ ───► │  2. BACKTEST  │ ───► │   3. SHADOW   │ ───► │  4. PROMOTE  │
│ Strategy file│      │ Historical    │      │ Live feeds,   │      │ Production   │
│ in Python    │      │ test battery  │      │ virtual fills │      │ Standalone   │
└──────────────┘      └───────────────┘      └───────────────┘      └──────────────┘
```

1. **Cook**: Implement strategy as an isolated class implementing `evaluate()`, `get_parameters()`, and `update_parameters()`.
2. **Backtest**: Verify quantitative edge across historical DuckDB event cycles; write unit tests in `tests/`.
3. **Shadow**: Incubate in Lane 2 for 24–48 hours to assess fill probability, slippage, and adverse selection under live microstructure conditions.
4. **Promote**: Pass the 4-pillar pre-flight certification audit (`BotDeploymentAuditor`). Once certified, promote to Tier 2 Standalone Engine.

---

## 🛡️ Guardian Daemons & Invariant Protections

1. **`AgentIntegrityCheck` (`src/kalshi_sim/integrity_agent.py`)**:
   - Runs in the background every 5 seconds to audit mathematical invariants:
     - $\text{Equity} = \text{Balance} + \sum \text{Unrealized PnL}$
     - $\text{Best YES Bid} + \text{Best NO Bid} \le 1.00$ (Uncrossed CLOB)
     - Countdown monotonicity and Eastern Time offset compliance.
2. **`AgentLawOrder` (`src/kalshi_sim/law_order_agent.py`)**:
   - Enforces CFTC market conduct rules, wash-sale protection, anti-spoofing limits, and token-bucket API rate limiting (20 requests/sec).
3. **`TradingEngineLock` (`src/kalshi_sim/process_lock.py`)**:
   - Cross-platform process mutex stored at `data/trading_engine.lock`.
   - Validates PID liveness. Reclaims stale locks cleanly upon abnormal terminations.

---

## 🕒 Eastern Time (`America/New_York`) Standard

All event schedules, target strikes, and cycle intervals adhere strictly to Eastern Time:
- Contract expiration boundary: `:00`, `:15`, `:30`, `:45` ET.
- Market duration banner format: `September 7, 3:45 – 4:00 PM ET`.
- Pre-expiry trading freeze: $T_{\text{rem}} \le 45\text{s}$.
- Post-expiry spread settlement: $T_{\text{rem}} \ge 855\text{s}$.

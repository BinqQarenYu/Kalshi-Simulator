# System Architecture & Infrastructure

The **Kalshi Bitcoin Quantitative Trading Simulator & Live Execution Terminal** is designed as a low-latency, institutional-grade quantitative platform for trading Kalshi 15-minute Bitcoin Prediction Binary Contracts (`KXBTC15M`).

---

## 🏛 High-Level Architecture

```
                                  [ Kalshi Exchange WebSocket & REST API ]
                                  [ Coinbase / Binance BTC Spot Index Feed ]
                                                      │
                                                      ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                   INGESTION & DATA NORMALIZATION LAYER                                 │
 │                                                                                                        │
 │  • OrderBookManager: Local L2 Central Limit Order Book (CLOB) with sequence gap auto-resync            │
 │  • TickWriter / MarketDataMemoryManager: Zero-copy ring buffers & append-only disk logging             │
 │  • OHLCVAggregator: High-frequency rolling multi-timeframe candle aggregations                        │
 │  • Synchronous Spot Feed: Sub-second BTC Index sync ($S_t$) with zero IEEE-754 floating point drift     │
 └────────────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                      │
                                                      ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                  DUAL QUANTITATIVE STRATEGY ARENA                                      │
 │                                                                                                        │
 │  ┌─────────────────────────────────────────────────┐   ┌────────────────────────────────────────────┐  │
 │  │        BOT 1: 3-STEP DOMINATION ENGINE          │   │      BOT 2: ONNX NEURAL NETWORK BOT        │  │
 │  │  • Playbook 1: Early Momentum Breakout (10-15m) │   │  • 28-D Order Flow Microstructure Tensor   │  │
 │  │  • Playbook 2: Mid-Cycle Trend Drift (4-10m)    │   │  • ONNX CPU Runtime Thread-Pool (<1.5ms)   │  │
 │  │  • Playbook 3: Late Gamma Snub (45s-4m)         │   │  • Directional Probabilities (Up/Down/Wait)│  │
 │  │  • Digital Option Moneyness CDF Math            │   │  • Statistical Expected Value Engine (EV)  │  │
 │  │  • Isolated Virtual Bankroll ($15.00)           │   │  • Isolated Virtual Bankroll ($15.00)      │  │
 │  └─────────────────────────────────────────────────┘   └────────────────────────────────────────────┘  │
 └────────────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                      │
                                                      ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                   EXECUTION & RISK GUARDRAIL LAYER                                     │
 │                                                                                                        │
 │  • OrderSimulator: Multi-level L2 depth walking with realistic market impact and VWAP fills            │
 │  • Live Demo Order Client: RSA-signed Kalshi API orders with rate limits and slippage bounds           │
 │  • AgentLawOrder: CFTC compliance, wash-trading prevention, anti-spoofing, position limits             │
 │  • AgentIntegrityCheck: Invariant auditor (CLOB continuity, uncrossed books, Decimal math)             │
 │  • SystemResourceGovernor: CPU & memory pressure throttling, GC pacing, and latency protection         │
 └────────────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                      │
                                                      ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                 PERSISTENCE & REAL-TIME STREAMING                                      │
 │                                                                                                        │
 │  • FastAPI Server: High-throughput async REST endpoints & WebSocket broadcasting                       │
 │  • SQLite Database (kalshi_history.db): Trades, settlements, predictions, equity snapshots             │
 │  • React / Vite Frontend Terminal: Depth ladder, live WebCLOB, win/loss reports journal, guardrails    │
 └────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Component Breakdown

### 1. Ingestion Agent (`src/kalshi_sim/ingestion_agent.py`)
- Maintains persistent WebSocket connections to Kalshi (`wss://api.elections.kalshi.com/trade-api/ws/v2`).
- Handles channel subscriptions: `orderbook_delta`, `trade`, `market_ticker`.
- Implements automated reconnection with exponential backoff and instant snapshot recovery upon sequence anomalies.

### 2. CLOB Order Book Manager (`src/kalshi_sim/orderbook.py`)
- Maintains full in-memory Limit Order Books (Bids & Asks) for active contracts.
- Provides thread-safe snapshot generation, inside-touch best bid/ask calculations, and multi-level depth slicing ($10$–$15$ levels).

### 3. Simulation Agent (`src/kalshi_sim/simulation_agent.py`)
- Coordinates the Dual-Bot forward validation arena.
- Executes trades across isolated portfolios (`_portfolio_domination` and `_portfolio_onnx`), ensuring zero capital cross-talk.
- Dispatches executions to the SQLite database queue and triggers automated settlement at cycle boundaries (`:00`, `:15`, `:30`, `:45`).

### 4. Background Guardian Daemons
- **`AgentIntegrityCheck` (`src/kalshi_sim/integrity_agent.py`)**: Runs continuous invariant verification (unrealized P&L consistency, uncrossed books, clock alignment).
- **`AgentLawOrder` (`src/kalshi_sim/law_order_agent.py`)**: Enforces CFTC and Kalshi exchange compliance rules (pre-trade checks, position size caps, self-trade prevention).
- **`SystemResourceGovernor` (`src/kalshi_sim/system_governor.py`)**: Monitors CPU and memory utilization to prevent event loop starvation under high tick rates.

---

## 🕒 Eastern Time & Countdown Parity

The platform strictly operates under **Eastern Time (`America/New_York`)**:
- All cycle headers adhere to official Kalshi format (e.g. `August 30, 1:15 – 1:30 PM ET`).
- The 15-minute countdown timer is synchronized with sub-second accuracy to Kalshi's official market close boundaries.

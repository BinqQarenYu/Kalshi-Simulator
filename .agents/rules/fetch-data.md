---
trigger: always_on
glob: "**/*"
description: Market data ingestion, WebSocket synchronization, and execution mode data rules for Kalshi Simulator.
---

# Market Data Ingestion & Live Synchronization Rules

## 1. Execution Mode Data Segregation
- **`MOCK_SIMULATION` Mode**:
  - Uses realistic synthetic Level-2 order flow, multi-level depth walks, and geometric Brownian motion / jump-diffusion BTC spot price paths.
  - Payoffs and binary contract pricing must strictly adhere to digital option fair value formulations.
- **`PAPER_TRADING` & `LIVE_TRADING` Modes**:
  - **Zero Placeholder/Mock Data**: When running in paper or live demo mode, all market feeds, order books, taker trades, and strikes must originate strictly from the live Kalshi WebSocket/REST API.
  - If live exchange connectivity is interrupted, the system must enter a reconnection/graceful pause state with explicit logging rather than silently falling back to mock data.

## 2. Kalshi WebSocket Ingestion & Book Synchronization
- **L2 Order Book Integrity**:
  - Maintain a strict local Central Limit Order Book (CLOB) constructed from initial full snapshots (`orderbook_snapshot`) and incremental delta streams (`orderbook_delta`).
  - **Sequence Number Validation**: Continuously track `seq` numbers. If any sequence gap or out-of-order delta is detected, immediately invalidate the local book and trigger an automated full snapshot resync.
- **Real-Time Stream Prioritization**:
  - Prioritize real-time WebSocket streams (`orderbook_delta`, `trade`, `market_ticker`) over polled REST endpoints to minimize microstructure latency.
  - Underlying Bitcoin Spot Index prices must be synchronized concurrently to compute exact moneyness, time-to-expiry decay, and automated settlement.

## 3. Microstructure Data Persistence
- **High-Throughput Tick & Depth Logging**:
  - All inside-touch updates, L2 depth transitions, trade prints, and 28-dimensional feature extractions must be streamed to append-only disk storage (`TickWriter` / CSV / DuckDB).
  - Ensure disk I/O operations are offloaded to asynchronous worker tasks to prevent event loop blocking in high-frequency regimes.

## 4. Kalshi ET Clock, 15-Minute Countdown Timer & Spot Price Absolute Parity
- **Eastern Time (`America/New_York`) Exclusivity**:
  - All event timestamps, target strike expiry times (e.g. `5:30am ET`), and market duration headers (e.g. `August 29, 5:15 - 5:30 AM ET`) must strictly reflect Eastern Time (ET).
  - Never display raw UTC or unlocalized local machine time on trading headers or market banners.
- **Identical 15-Minute Cycle Countdown Timer**:
  - The countdown timer (e.g. `09:19`) represents the exact time remaining in the active 15-minute cycle to the next expiration boundary (:00, :15, :30, :45 ET) or the active Kalshi contract's `close_time`.
  - The timer in our application must be **identical** to the official Kalshi web timer at all times with sub-second synchronization.
- **Identical "TO BEAT" Target Strike & "NOW" Spot Price Parity**:
  - **"TO BEAT" Target Strike ($K$)**: Must strictly reflect the active 15-minute event target strike (e.g. `$77,453.12`).
  - **"NOW" Bitcoin Spot Price ($S_t$)**: Must stream the live institutional Bitcoin Spot Index price (Coinbase/Binance BTC-USD feed) with sub-second latency, matching the official settlement index.
  - **Price Diff & Delta Accuracy**: The live price difference ($\text{Diff} = S_t - K$) and percentage ($\text{Diff \%} = \frac{S_t - K}{K} \times 100\%$) must be calculated with `Decimal` precision on every tick and update the UI in real time.
- **Continuous Guardian Audit**:
  - The `AgentIntegrityCheck` auditor validates timer monotonicity, ET string compliance, and price parity continuously in the background.



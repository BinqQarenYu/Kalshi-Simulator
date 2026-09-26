# Kalshi Simulator: The 7-Stage End-to-End Trading Pipeline

This document outlines the authoritative, unvarnished data workflow of the Kalshi Simulator—from raw network bytes to settled PnL. It establishes the "Physics of the Trade," governed by the agents and strict architecture invariants.

## Phase 1: Ingestion & Purification (The Front Door)
1. **Raw Fetch**: WebSockets to Coinbase, Binance, and CF Benchmarks broadcast hundreds of raw JSON ticks per second.
2. **Quoquo's Pet (The Scrubber)**: Before the execution engine registers a tick, the Scrubber middleware intercepts it. It drops floating-point poison, forcefully converts strings to `Decimal`, checks timestamps against local UTC to prevent NTP drift (dropping ticks lagging >3s), and enforces absolute sanity bounds to prevent flash-crash hallucinations.
3. **State Memory**: Only perfectly sanitized ticks are written to the live `price_history` buffer and the L2 Orderbook state.

## Phase 2: Feature Extraction (Preparing the Meal)
1. **The Aggregator**: The core engine aggregates the clean tick stream into structured timeframes (1M, 5M, 15M candles).
2. **Microstructure Calculation**: The engine computes complex physical variables: **VPIN** (Volume-Synchronized Probability of Informed Trading), bid-ask imbalance, order book momentum, and spot velocity. These are formatted into a strict mathematical tensor.

## Phase 3: The ONNX Oracle (The Brain)
1. **Inference**: The feature tensor is instantly passed into the **ONNX Machine Learning Model** (e.g., Dual ONNX or Macro Dominion). 
2. **The Verdict**: The ONNX model executes its matrix multiplications in milliseconds and outputs a probability float (e.g., "82.4% confidence that BTC will settle above Strike `$83,000` at 16:15 UTC").

## Phase 4: Risk Guardrails (The Shield)
Even if the ONNX Oracle says "BUY", the system does not blindly obey. The signal is audited by the **Risk Guardrail Subagent**:
1. **The Dead-Zone Check**: Are we too close to the strike price (e.g., ±$35)? If yes, it's a pure coin-flip. **VETO**.
2. **Toxicity Check**: Is VPIN spiking beyond 0.65? **VETO**.
3. **Exposure & Streak Limit**: Are we already holding maximum exposure (2 contracts)? Did we just lose 3 consecutive cycles? **VETO**.

## Phase 5: The Sniper Trigger (Execution)
If the Guardrails grant clearance:
1. **In-Flight Intent Lock**: The engine synchronously reserves an `in_flight_lock` for the market cycle. This guarantees no other concurrent tick can trigger a duplicate entry (Lesson 1 & 17).
2. **Order Dispatch**: A Maker Limit Order (capped at 1 contract micro-sizing) is fired to the Kalshi V2 API.
3. **Lock Release**: Once the Kalshi REST API responds confirming the order is resting on the exchange book, the in-flight lock is released.

## Phase 6: Harvest vs. Settlement (The Exit)
1. The engine continually monitors the open position.
2. **Take-Profit (Harvest)**: If the contract price surges to `$0.92` before expiry, the engine fires a limit sell to instantly harvest the profit and avoid last-second directional reversal risk.
3. **Expiry Settlement**: If it does not reach the harvest threshold, the contract is held until the Kalshi clock runs out, settling at `$1.00` (Win) or `$0.00` (Loss).

## Phase 7: Accounting & POE Audit (The Post-Mortem)
1. **The Ledger**: The SQLite database records the final fill price and settlement results.
2. **The UI Dashboard**: The React WebCLOB interface instantly reads the WebSocket updates, pushing new totals for PnL, Win Rate, and Daily Streak.
3. **Agent POE**: Agent POE (Post-Occupancy Evaluator) wakes up to evaluate the cold math. It compares the actual PnL against vetoed counterfactuals to determine if the active parameters generated true alpha or starved the portfolio.

---

**Summary Pipeline**:
`Raw Data` ➔ `Scrubber` ➔ `Feature Extractor` ➔ `ONNX Model` ➔ `Risk Guardrails` ➔ `Execution API` ➔ `Harvest` ➔ `SQLite / UI PnL Report`

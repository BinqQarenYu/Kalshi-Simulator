---
name: lessons-learned
description: Institutional trading lessons learned, incident post-mortems, anti-regression patterns, and hard-coded invariants for Kalshi quantitative trading.
---

# Lessons Learned & Post-Mortem Hardening Guide

This document is the authoritative institutional repository of all quantitative trading post-mortems, operational incident forensics, bug mitigations, and hard-coded architectural invariants for the Kalshi algorithmic trading platform.

**Rule for all AI Agents**: Before modifying any bot strategy, execution engine, risk guardrail, or API client, you **MUST** consult this skill to prevent regression of past failures.

---

## Index of Lessons Learned

- [Lesson 1: Async Concurrency Race Conditions & Pre-Flight In-Flight Intent Locks](#lesson-1-async-concurrency-race-conditions--pre-flight-in-flight-intent-locks)
- [Lesson 2: Micro-Bankroll Sizing Invariants (1 Contract per Trade, Max 2 Shares per Cycle)](#lesson-2-micro-bankroll-sizing-invariants-1-contract-per-trade-max-2-shares-per-cycle)
- [Lesson 3: Kalshi API V2 vs Deprecated V1 Endpoints (HTTP 410 Fix)](#lesson-3-kalshi-api-v2-vs-deprecated-v1-endpoints-http-410-fix)
- [Lesson 4: The Razor-Tight Coin-Flip Dead Zone (|Spot - Strike| < Noise Threshold)](#lesson-4-the-razor-tight-coin-flip-dead-zone-spot---strike--noise-threshold)
- [Lesson 5: Execution Authority Isolation & Single-Process Locking](#lesson-5-execution-authority-isolation--single-process-locking)
- [Lesson 6: Consecutive Loss Streak Breaker (Overnight Hemorrhage Defense)](#lesson-6-consecutive-loss-streak-breaker-overnight-hemorrhage-defense)
- [Lesson 7: Deterministic Polling vs Fragile Sleeps in Async Testing](#lesson-7-deterministic-polling-vs-fragile-sleeps-in-async-testing)
- [Lesson 8: Strict IEEE-754 Floating-Point Disallowance](#lesson-8-strict-ieee-754-floating-point-disallowance)
- [Lesson 9: Multi-Asset Context Switching Isolation](#lesson-9-multi-asset-context-switching-isolation)
- [Lesson 10: Multi-Asset Order Sweep & Take-Profit Fill Isolation (The 12-Order Auto-Cancel Loop)](#lesson-10-multi-asset-order-sweep--take-profit-fill-isolation-the-12-order-auto-cancel-loop)
- [Lesson 11: Zero Static Mock Data & Anti-Hallucination Dashboard Invariant (Single Source of Truth)](#lesson-11-zero-static-mock-data--anti-hallucination-dashboard-invariant-single-source-of-truth)

---

### Lesson 1: Async Concurrency Race Conditions & Pre-Flight In-Flight Intent Locks

#### The Incident (2026-09-07)
* **Symptom**: During live trading on `KXDOGE15M`, the bot fired **5 consecutive orders in 2 seconds** instead of the maximum 2 contracts exposure limit.
* **Forensic Root Cause**:
  1. Placing an order over HTTP takes 200ms – 500ms (`await self.order_client.place_order(...)`), yielding control to the asyncio event loop.
  2. The cycle lock (`record_resting_order`) was previously written only *after* the HTTP response returned.
  3. While Order #1 was in flight, 4 subsequent WebSocket market ticks triggered `evaluate_and_execute()`.
  4. Each incoming tick saw `_cycle_locks` as empty, approved the trade, and launched concurrent HTTP order placements.
* **Hardened Architecture**:
  1. **Async Mutex (`_eval_lock`)**: An `asyncio.Lock()` guards `evaluate_and_execute()`. If an evaluation or dispatch is in flight (`if self._eval_lock.locked(): return`), incoming ticks are immediately dropped.
  2. **Synchronous In-Flight Intent Lock**: `validate_pre_trade_intent()` immediately reserves `self._in_flight_locks.add(cycle_key)` and advances `_last_order_ts` synchronously *before* initiating network I/O. Any concurrent check is rejected with `IN-FLIGHT ORDER LOCKOUT`.
  3. **Safe Release on Failure**: If the HTTP call raises an exception or returns `None`, `release_in_flight_intent(cycle_key)` safely unblocks the cycle.

---

### Lesson 2: Micro-Bankroll Sizing Invariants (1 Contract per Trade, Max 2 Shares per Cycle)

#### The Rule
$$\begin{aligned}
\mathbf{\text{Per-Trade Sizing:}} &\quad \mathbf{1\text{ contract}} \times \mathbf{\$0.48} = \mathbf{\$0.48\text{ max risk per order}} \\
\mathbf{\text{Cycle Exposure Cap:}} &\quad \mathbf{\text{Max } 2\text{ contracts}} \times \mathbf{\$0.48} = \mathbf{\$0.96\text{ max risk per cycle}} \\
\mathbf{\text{Order Style:}} &\quad \mathbf{\text{Maker Resting Limit @ \$0.48}}\text{ (\$0.00 exchange fee)}
\end{aligned}$$

#### Implementation Guardrails
1. Individual order sizing is strictly clamped to 1: `approved_size = min(requested_size, 1)`.
2. Cumulative cycle tracking: `self._cycle_contracts_count[cycle_key]`.
3. If `self._cycle_contracts_count >= 2`, all further entries in that cycle are permanently blocked until settlement:
   `CYCLE EXPOSURE CAP: Cycle '{cycle_key}' reached max 2 contracts exposure (2/2 active).`
4. Sole Strategy Authorization: Only `ThreeStepDominationBot` is authorized to place live trades. All other candidate bots (Dominion 2, ONNX Microstructure, Scalp) receive `approved_size = 0`.

---

### Lesson 3: Kalshi API V2 vs Deprecated V1 Endpoints (HTTP 410 Fix)

#### The Incident
* **Symptom**: Sweeping expired or obsolete resting orders failed with `HTTP 410: {"error":{"code":"deprecated_v1_order_endpoint","message":"Please switch to the V2 endpoints"}}`.
* **Root Cause**: The order cancellation endpoint was pointing to legacy `/trade-api/v2/portfolio/orders/{order_id}`.
* **Correction**:
  - Event contract cancellation endpoint in Kalshi V2 is:
    ```
    DELETE https://api.elections.kalshi.com/trade-api/v2/portfolio/events/orders/{order_id}
    ```
  - Implemented automatic fallback to `/portfolio/orders/{order_id}` if a non-event market is encountered.

---

### Lesson 4: The Razor-Tight Coin-Flip Dead Zone (|Spot - Strike| < Noise Threshold)

#### The Principle
* Kalshi binary contracts settle to $1.00 or $0.00.
* When Bitcoin spot price ($S_t$) is within $\pm\$15$ to $\pm\$70$ of the strike price ($K$) with $>5$ minutes remaining, price movement is dominated by Brownian motion noise (typical 1-minute BTC volatility is \$14–\$25).
* Entering near the strike is a pure 50/50 coin flip that bleeds the bid-ask spread.
* **Rule**: Require $|\Delta \text{Spot}| \ge \text{Threshold}$ ($S_t - K \ge \$35$ to $\$70$ on BTC, asset-scaled for ETH/SOL/DOGE) before edge is considered valid.
* When inside the dead zone, the bot outputs `Razor-Tight Proximity Veto: Skipping`.

---

### Lesson 5: Execution Authority Isolation & Single-Process Locking

#### The Principle
* **Anti-Pattern**: Multiple server processes or development instances routing live orders concurrently.
* **Invariant**:
  - Exactly **ONE** process holds the live execution token via file-based mutual exclusion (`TradingEngineLock` on `data/trading_engine.lock`).
  - Standalone Bot on port `8001` is the dedicated 24/7 production execution authority.
  - Mother Server on port `8000` is locked into read-only simulation/monitoring mode when the standalone lock is held (`HTTP 409 Conflict` on live order attempts).

---

### Lesson 6: Consecutive Loss Streak Breaker (Overnight Hemorrhage Defense)

#### The Principle
* Repeated consecutive losses indicate an adverse microstructure regime shift (e.g. strong macro trend overriding local mean-reversion).
* **Hard Stop**: After **3 consecutive losses** (`max_consecutive_losses = 3`), the engine triggers an automatic **Emergency Disarm**:
  `🛑 [STREAK BREAKER] 3 consecutive losses reached. Bot AUTO-DISARMED to prevent further hemorrhaging.`
* Re-arming requires manual user action via `/api/bot/arm` or UI kill switch toggle.

---

### Lesson 7: Deterministic Polling vs Fragile Sleeps in Async Testing

#### The Anti-Pattern
* Using arbitrary sleep durations in tests (e.g. `await asyncio.sleep(0.05)`).
* Under high CPU load or Windows NTFS file locking, background tasks may take 60ms, causing random test race conditions.
* **Standard Pattern**:
  ```python
  for _ in range(30):
      if condition_met():
          break
      await asyncio.sleep(0.05)
  assert condition_met() is True
  ```

---

### Lesson 8: Strict IEEE-754 Floating-Point Disallowance

#### The Invariant
* Binary financial calculations must never use native Python `float` or native JavaScript `number`.
* Float rounding errors (e.g. `0.1 + 0.2 = 0.30000000000000004`) distort strike differences, profit factors, equity tracking, and fee calculations.
* **Mandatory Stack**:
  - Python: `decimal.Decimal`
  - Frontend: `decimal.js` and string-wrapped values.

---

### Lesson 9: Multi-Asset Context Switching Isolation

#### The Principle
* When switching active asset (e.g. from DOGE to BTC via `/api/assets/select`):
  1. Capture `target_ticker = self.active_ticker` as a local variable within the evaluation frame.
  2. Release any pending in-flight locks for the previous asset.
  3. Sweep and cancel resting orders from the previous asset to prevent cross-asset order accumulation.

---

### Lesson 10: Multi-Asset Order Sweep & Take-Profit Fill Isolation (The 12-Order Auto-Cancel Loop)

#### The Incident (2026-09-11)
* **Symptom**: During live trading on `KXBTC15M-26SEP110615-15`, the user observed the engine submit and cancel **12 limit sell orders in 66 seconds**, spamming the Kalshi exchange order activity tab and SQLite trade log.
* **Forensic Root Cause**:
  1. The bot was long 1 BTC contract. While the trade was maturing, the engine focus switched to evaluate Gold (`KXGOLD...`).
  2. At $T=119\text{s}$, the BTC position triggered Late-Cycle Harvest (Take Profit) and dispatched a limit sell order @ $0.9040.
  3. Meanwhile, the background `_resting_order_watchdog_loop` ran a continuous finished event sweep checking:
     `if oid and self.active_ticker and t != self.active_ticker: cancel_order(oid)`
  4. Because `self.active_ticker` was currently `KXGOLD...`, the watchdog saw the resting sell on `KXBTC...`, mistakenly deemed it an obsolete finished event, and auto-cancelled it within 2 seconds.
  5. Because the sell order was cancelled before filling, Kalshi still held the 1 BTC position. On the next tick, Take-Profit fired again, placed another sell, and the sweep cancelled it again—repeating **12 times**.
  6. Furthermore, Take-Profit was enqueuing `take_profit_exit` records to SQLite immediately upon order dispatch rather than awaiting verified fill confirmation.
* **Hardened Architecture & Invariants**:
  1. **Multi-Asset Protected Ticker Shield**: Any background sweep or watchdog routine must dynamically aggregate a `protected_tickers` set:
     - All tickers in `self.active_positions` (never sweep orders on open positions being actively managed or exited).
     - All tickers in `self.active_resting_orders` (never sweep unexpired limit orders).
     - All unexpired market cycles across all assets in `self.asset_markets` ($T_{\text{rem}} > 45\text{s}$).
     - `self.active_ticker` if $T_{\text{rem}} > 45\text{s}$.
     Resting orders are ONLY cancelled if their ticker is strictly outside `protected_tickers` and the contract is truly finished.
  2. **Take-Profit De-duplication**: Before dispatching a take-profit order, the engine checks `any(o.get('ticker') == pos_ticker and o.get('action') == 'sell' for o in self.active_resting_orders.values())` to prevent duplicate exits while one is resting.
  3. **Fill-Gated DB & PnL Accounting**: Take-profit limit orders placed on the book are registered in `self.active_resting_orders`. PnL updates and SQLite `take_profit_exit` entries are ONLY committed once the exchange confirms the fill (`open_orders` sweep or WebSocket fill event).

---

### Lesson 11: Zero Static Mock Data & Anti-Hallucination Dashboard Invariant (Single Source of Truth)

#### The Incident (2026-09-12)
* **Symptom**: The user observed a sharp contradiction on the institutional dashboard: Mother Dash Factory Matrix displayed Bot 3 (Macro Trend Dominion) with a **67.8% win rate across 310 events**, while the council report and live running daemon on Port 8003 (`standalone_macro.py`) reported 5 losses, 1 win (16.7% win rate, -$0.67 PnL). The user understandably perceived this as an AI hallucination.
* **Forensic Root Cause**:
  1. During frontend prototyping of `ParentHub.tsx`, hardcoded static placeholder numbers (`events: 310, winRate: '67.8%', profitFactor: '1.52'`) were written into `benchmarkingModels` with an empty `useMemo` dependency array (`[]`).
  2. Mother server (`server.py` on Port 8000) only polled Port 8001 (`standalone_bot.py`), while Port 8002 (`standalone_onnx.py`) and Port 8003 (`standalone_macro.py`) ran isolated daemons without upstream telemetry aggregation.
  3. Consequently, static mock numbers masqueraded as live metrics on the user's primary decision dashboard.
* **Hardened Architecture & Invariants**:
  1. **Strict Zero Mock Data in Production UI**: No static placeholder percentages, simulated event counts, or mock trade records are ever permitted in trading dashboards.
  2. **Multi-Port Telemetry Aggregator**: Mother server (`server.py` on Port 8000) continuously synchronizes with all active bot daemons (Port 8001 Live, Port 8002 Dual ONNX Shadow, Port 8003 Macro Dominion Shadow) via `standalone_sync_loop` and broadcasts live empirical statistics (`settled_cycles`, `today_wins`, `today_losses`, `today_win_rate`, `today_pnl`) down the WebSocket.
  3. **Honest Empty State (`—` / `AWAITING TELEMETRY`)**: If a bot daemon is starting up or has zero settled cycles, the UI must render `—` (dash) or `AWAITING TELEMETRY`, never a fabricated percentage.
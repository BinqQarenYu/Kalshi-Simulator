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
- [Lesson 12: Live Bot Promotion & Execution Engine API Coupling](#lesson-12-live-bot-promotion--execution-engine-api-coupling)
- [Lesson 13: The NTP Clock Drift Vulnerability & Sync-to-Source Invariant](#lesson-13-the-ntp-clock-drift-vulnerability--sync-to-source-invariant)
- [Lesson 14: Decoupled State Desynchronization (The Dashboard Mirage)](#lesson-14-decoupled-state-desynchronization-the-dashboard-mirage)
- [Lesson 15: The 6-Stage Seal of Excellence Gauntlet & Zero-Exemption Interlock](#lesson-15-the-6-stage-seal-of-excellence-gauntlet--zero-exemption-interlock)
- [Lesson 16: The Multi-Port Microservice Trap (Port Sprawl & Localhost Bridge Collapse)](#lesson-16-the-multi-port-microservice-trap-port-sprawl--localhost-bridge-collapse)
- [Lesson 17: The Zombie In-Flight Intent Lockout & Monotonic 15-Second TTL Circuit Breaker](#lesson-17-the-zombie-in-flight-intent-lockout--monotonic-15-second-ttl-circuit-breaker)
- [Lesson 18: Human Cognitive Fatigue & The Anti-Complexity Doctrine ("Simple is More")](#lesson-18-human-cognitive-fatigue--the-anti-complexity-doctrine-simple-is-more)

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
---

### Lesson 12: Live Bot Promotion & Execution Engine API Coupling

#### The Incident (2026-09-14)
* **Symptom**: Promoting a heavily backtested strategy (`MacroTrendDominionBot`) to Live execution (Lane 1) caused an immediate background crash during the `BotDeploymentAuditor` pre-flight check, followed by continuous `AttributeError` and `TypeError` exceptions within `evaluate()` and `evaluate_exit()`.
* **Forensic Root Cause**:
  1. **Strict Zero-Float Math Rule Violation**: The new strategy's `__init__` hardcoded `self.discount_limit_price = 0.52` as a native float. The `BotDeploymentAuditor` immediately aborted the process due to non-Decimal monetary representation.
  2. **Seal of Excellence Bypass**: The new bot had 0 recorded live settled cycles in `seal_of_excellence.json` and failed the "Statistical Edge" pillar (which requires >= 30 verified cycles).
  3. **Tightly-Coupled Execution API**: The Standalone execution engine (`standalone_bot.py`) expects the loaded strategy to expose specific configuration flags (e.g., `enable_take_profit_ceiling`, `reverse_indicator_threshold`) for frontend UI telemetry, and passes specific advanced kwargs (like `twap_60s`) into `evaluate()`. The new bot was written in isolation and did not implement these expected fields.
* **Hardened Architecture & Invariants**:
  1. **Consistent Strategy Interface**: All new strategy classes must inherit from a unified base interface or unconditionally accept `**kwargs` in both `evaluate()` and `evaluate_exit()` to gracefully swallow unexpected runtime arguments passed by the engine.
  2. **Zero-Float Pre-Flight Scrub**: All monetary parameters (e.g., limit prices, ceilings, edge offsets) must be strictly typed as `Decimal("...")` inside the strategy constructor.
  3. **Formal Graduation Mechanics**: A backtested bot cannot be forced into live execution solely by changing the imported class. It must be granted a verified entry in `data/seal_of_excellence.json` (via the Council-Sanctioned Override or by fulfilling the 30-cycle minimum hurdle in Lane 2 Incubator) so it survives the `BotDeploymentAuditor` runtime gate.

## Lesson 14: Decoupled State Desynchronization (The Dashboard Mirage)
**Context**: The user identified a critical UI-to-Execution mismatch where the Mother Dashboard (Port 8000) reported 3_step_domination_bot as the active live strategy, while the Live Execution Engine (Port 8001) was actively trading macro_trend_dominion_bot.
**Root Cause**: The ecosystem utilizes a multi-port decoupled architecture. However, the Mother Server (server.py) initialized its ServerState.active_strategy_bot with a *hardcoded string literal* on startup, rather than pulling the single source of truth from seal_of_excellence.json or querying the live executor. When the backend code was swapped to promote a new bot, the UI remained statically hardcoded.
**Why It's Dangerous**: UI/Execution desynchronization is catastrophic in quantitative trading. If a trader or risk manager looks at the Mother Dash and sees the wrong bot, they are managing imaginary risk while real capital is deployed by an invisible engine. It creates a 'Dashboard Mirage'.
**The Invariant Fix**: 
1. **Zero Hardcoded State**: Monitoring servers must never hardcode the active strategy identifier. The active strategy must always be resolved dynamically from the execution layer or the unified seal_of_excellence.json database.
2. **Absolute Source of Truth**: The active live bot must hold the single source of truth across all ports. If Port 8001 is trading it, Port 8000 must reflect it.

---

### Lesson 15: The 6-Stage Seal of Excellence Gauntlet & Zero-Exemption Interlock

#### The Context & Incident
* **Symptom**: Strategy promotion historically relied on manual JSON edits or verbal "Council Exemptions" (`COUNCIL-SANCTIONED-BASELINE-V3.2`). In reality, backtested bots with 88% win rates in optimistic simulation failed on live ticks due to fee drag, queue priority, and instantaneous spot vs. 60s TWAP mismatches.
* **The Hardened Invariant**:
  1. **Zero Live Orders Without Verified Seal**: No bot may route real capital without an automated SHA-256 Seal of Excellence token on disk (`data/seal_of_excellence.json`).
  2. **On-Demand User Trigger**: The gauntlet is only activated when the user explicitly requests to *"check bot if it's time to test for excellence"*.
  3. **The 6-Stage Gauntlet**:
     - *Stage 1 (AST Integrity)*: Strict Decimal typing, zero native floats, `evaluate(**kwargs)` interface.
     - *Stage 2 (Adversarial SimSim)*: 100 historical cycles, CME CF 60s TWAP settlement parity, 250ms latency, Net $EV \ge +\$0.0400$/ct after fees.
     - *Stage 3 (Anti-Kamikaze & Harakiri)*: 1-contract clamp, max 2 shares/cycle, 3-loss streak auto-disarm in $<100$ms, panic sweep in $<300$ms.
     - *Stage 4 (Multi-Regime Incubator)*: $\ge 30$ settled cycles in Lane 2 Shadow (15 Low-Vol $\sigma \le \$80$ + 15 High-Vol $\sigma > \$200$), Win Rate $\ge 55\%$, PF $\ge 1.25$, Drawdown $\ge 12\%$. Dead-zone trades ($|S_t - K| < \$25$) invalidated.
     - *Stage 5 (5-Pillar Audit)*: 100% automated PASS across Guardrail, Math, Truths, Law, and Statistical Edge pillars.
     - *Stage 6 (Cryptographic Minting)*: SHA-256 token generated and written to disk; Port 8001 engine lock interlocked.

---

### Lesson 16: The Multi-Port Microservice Trap (Port Sprawl & Localhost Bridge Collapse)

#### The Incident (2026-09-14 to 2026-09-15)
* **Symptom**: A 24-hour debug spiral unfolded where Mother Server (Port 8000), Standalone Bot (Port 8001), Dual ONNX (Port 8002), and Macro Dominion (Port 8003) ran as disjoint processes. Mother Dash experienced:
  1. Flickering market parameters (spot price and timer constantly overwriting every 500ms).
  2. Persistent `HTTP 409 Conflict` errors: dead processes held `data/trading_engine.lock` on disk, preventing live execution.
  3. Complicated localhost proxy tunnels between Port 8000 and Ports 8001/8002/8003.
  4. Silent bot crashes due to unhandled `AttributeError: 'HMMBrain' object has no attribute 'is_trained'`.
* **Forensic Root Cause**:
  - **The Microservice Anti-Pattern**: Separating trading strategies into individual background HTTP servers on separate ports created unnecessary process boundaries, uncoordinated file lock fighting, state desynchronization, and localhost network latency.
  - **State Stomping**: Mother Server's `standalone_sync_loop` continuously overwrote its local truth with whatever Port 8001 returned, causing desync when Port 8001 stalled or restarted.
* **Hardened Invariant (Rule 9 — Unified Single-Port Engine)**:
  1. **Port 8000 Monolith**: All strategies (`3_step_domination_bot`, `dual_onnx`, `macro_trend_dominion`, `dominion_2_bot`) execute within a single monolithic engine on Port 8000 (`server.py`).
  2. **Retirement of Port Sprawl**: Ports 8001, 8002, 8003 and external `.bat` subprocess wrappers are permanently retired.
  3. **Direct Memory Ownership**: Mother Server acquires `TradingEngineLock(owner_name="mother_server", force=True)` on startup. All strategy switching occurs in-process via `resolve_bot_instance()` without HTTP proxy loops.

---

### Lesson 17: The Zombie In-Flight Intent Lockout & Monotonic 15-Second TTL Circuit Breaker

#### The Incident (2026-09-15)
* **Symptom**: After a transient network timeout or unexpected exception during order dispatch, the bot entered a silent coma: it remained armed, but rejected 100% of subsequent market ticks with:
  `IN-FLIGHT ORDER LOCKOUT: Order dispatch currently in flight for cycle... Concurrent order placement blocked.`
  The bot never traded again until the server was killed and restarted.
* **Forensic Root Cause**:
  - `validate_pre_trade_intent()` synchronously acquires an in-flight lock (`self._in_flight_locks.add(cycle_key)`) to eliminate 200ms async race conditions.
  - If the outbound HTTP call failed, dropped a socket, or raised an exception outside the try/finally block before calling `release_in_flight_intent()`, the cycle key was trapped forever in `_in_flight_locks`.
  - The lock lacked a temporal expiration mechanism (deadline).
* **Hardened Invariant**:
  1. **Monotonic High-Resolution Timestamping**: When an in-flight lock is acquired, its monotonic creation time is recorded: `self._in_flight_lock_ts[cycle_key] = time.monotonic()`.
  2. **15-Second Invariant TTL Auto-Release**: If an in-flight lock persists for $\ge 15.0$ seconds:
     - The guardrail automatically purges the lock: `self._in_flight_locks.discard(cycle_key)`.
     - An audit warning is logged: `⏱️ [IN-FLIGHT TIMEOUT] Lock for cycle expired after 15s TTL. Auto-releasing.`
     - Execution heals autonomously on the very next tick without human intervention or server restarts.

---

### Lesson 18: Human Cognitive Fatigue & The Anti-Complexity Doctrine ("Simple is More")

#### The Incident (2026-09-14 to 2026-09-15)
* **Symptom**: 24 hours of continuous coding produced exhaustion, leading to fragmented instructions, hasty band-aid fixes on symptoms rather than root causes, and severe operational frustration.
* **Root Causes & Cognitive Fallacies**:
  1. **Mental Fatigue & Decision Deterioration**: Operating algorithmic trading systems while exhausted degrades risk perception. Small visual anomalies (e.g. 10s countdown timer offset) triggered disproportionate panic, causing agents to add hasty calculation hacks that exacerbated clock desync.
  2. **The "Band-Aid on Band-Aid" Trap**: When multi-port polling failed, rather than eliminating the multi-port architecture, more shims were added (shell launchers, reverse proxies, retry loops, manual lock cleaners).
  3. **Premature Multi-Vector Complexity**: Attempting to trade 4 assets (`BTC`, `ETH`, `SOL`, `DOGE`) across 3 different bots on 3 different ports simultaneously before a single engine on BTC was rock-solid.
* **Institutional Principles ("Simple is More")**:
  1. **Halt & Rest Doctrine**: When cognitive fatigue sets in, trading systems must be placed on automated conservative hold (1 contract cap, strict streak breaker) rather than undergoing live refactoring during late hours.
  2. **Root Cause Over Surface Patching**: When an offset or mismatch appears, trace the physics (e.g. OS NTP clock drift vs. API calculation) before modifying production math.
  3. **The Law of Parsimony**: If an algorithmic architecture requires external background servers, inter-port bridges, and file-lock handoffs, it is fundamentally flawed. The simplest architecture (single process, single port, modular classes, strict Decimal math) is always the most profitable, maintainable, and resilient.

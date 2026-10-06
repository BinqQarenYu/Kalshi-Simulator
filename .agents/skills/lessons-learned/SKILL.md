---
name: lessons-learned
description: Institutional trading lessons learned, incident post-mortems, anti-regression patterns, and hard-coded invariants for Kalshi quantitative trading.
---

# Institutional Lessons Learned & Post-Mortem Hardening Repository

This document is the authoritative institutional repository of all quantitative trading post-mortems, operational incident forensics, bug mitigations, and hard-coded architectural invariants for the Kalshi algorithmic trading platform.

**Mandatory Rule for All Agents & Engineers**: Before modifying any bot strategy, execution engine, risk guardrail, mathematical model, or API client, you **MUST** consult this document to prevent regression of past failures.

---

## Master Taxonomy of Lessons Learned

```
                        [ THE THREE PILLARS OF INSTITUTIONAL MEMORY ]
                                              |
        +-------------------------------------+-------------------------------------+
        |                                     |                                     |
[ PILLAR I: CODING & ASYNC ]       [ PILLAR II: TRADING & CLOB ]      [ PILLAR III: QUANT & MATH ]
• Concurrency Race Locks           • Micro-Bankroll Sizing Caps       • Gaussian erf Normalization
• Zero-Float IEEE-754 Math         • Kalshi V2 API Specifics          • Proximity Moat Dead Zone
• Monolithic Port 8000 Engine      • Protected Ticker Shields         • Macro Trend Overrides
• Monotonic 15s TTL Deadlock       • Harakiri Streak Breakers         • Dynamic Volatility Scaling
• Live Memory State Sync           • 6-Trade Evaluation Circuit       • Anti-Overfitting 30-Trade
• Watchdog Process Resiliency      • Seal of Excellence Gauntlet      • Zero-Mock Single Truth
• The Anti-Complexity Doctrine     • Maker vs Taker Fee Geometry      • Time-of-Day Regime Filter
```

---

# 💻 PILLAR I: CODING & ASYNC SYSTEMS ENGINEERING

### Lesson C1: Async Concurrency Race Conditions & Monotonic 15s TTL Deadlock Breaker
* **Incident (2026-09-07 & 2026-09-15)**:
  1. During live trading, network latency (200–500ms per HTTP call) allowed multiple incoming WebSocket ticks to enter `evaluate_and_execute()` simultaneously, firing 5 duplicate orders in 2 seconds.
  2. A later patch added in-flight locks, but an unhandled network timeout trapped the cycle key in `_in_flight_locks` forever, causing the bot to reject 100% of subsequent ticks ("Zombie Lockout").
* **Hardened Architectural Invariants**:
  1. **Async Mutex (`_eval_lock`)**: An `asyncio.Lock()` guards entry evaluation. If a dispatch is in flight, new ticks are immediately discarded.
  2. **Pre-Flight In-Flight Intent Lock**: `validate_pre_trade_intent()` synchronously records `self._in_flight_locks.add(cycle_key)` and monotonic timestamp `self._in_flight_lock_ts[cycle_key] = time.monotonic()` *before* awaiting network I/O.
  3. **15-Second Monotonic TTL Auto-Purge**: If a lock exceeds 15.0 seconds without resolution, the guardrail automatically purges the lock, logs a timeout audit, and heals execution on the next tick.

---

### Lesson C2: Strict Zero IEEE-754 Float Financial Math
* **The Invariant Law**: Native Python `float` and native JavaScript `number` are **strictly forbidden** for monetary calculations, order balances, strike differentials, fee calculations, and PnL tracking.
* **Why**: IEEE-754 precision artifacts (e.g., `0.1 + 0.2 = 0.30000000000000004`) create phantom fractional cent discrepancies, trigger incorrect limit clamp evaluations, and corrupt database settlement accounting.
* **Mandatory Stack**:
  * Python: `decimal.Decimal` with string-initialized constants (`Decimal("0.48")`).
  * TypeScript / Frontend: `decimal.js` with exact string serialization across WebSocket and REST payloads.

---

### Lesson C3: Monolithic Single-Port Architecture (Port 8000) vs. The Multi-Port Trap
* **Incident (2026-09-14 to 2026-09-25)**:
  * Attempting to split bots across isolated ports (Port 8000 Mother Server, Port 8001 Standalone Live, Port 8002 Dual ONNX, Port 8003 Macro) created fatal process lock fighting (`data/trading_engine.lock` `HTTP 409 Conflict`), state stomping, port sprawl, and localhost proxy latency.
* **Hardened Architectural Invariants**:
  1. **Single Monolithic Process**: All bots, background supervisors, continuous trainers, and WebSocket broadcasts execute within a single monolithic engine on Port 8000 (`server.py`).
  2. **In-Memory Memory Manager**: Bot switching occurs in-process via `resolve_bot_instance()` with zero inter-process HTTP proxy overhead.
  3. **Exclusive Mutex Lock**: Exactly one OS-level process holds `TradingEngineLock(owner_name="mother_server", force=True)` on startup.

---

### Lesson C4: Deterministic Polling vs. Fragile Sleeps in Async Testing
* **The Anti-Pattern**: Using fixed time sleeps (`await asyncio.sleep(0.05)`) in test suites. Under high CPU load or Windows NTFS file locking, tasks take variable time, causing intermittent test failures.
* **Standard Test Invariant**:
  ```python
  for _ in range(50):
      if condition_met():
          break
      await asyncio.sleep(0.02)
  assert condition_met() is True
  ```

---

### Lesson C5: OS NTP Clock Drift vs. Exchange Expiration Alignment
* **Incident (2026-09-14)**:
  * A 3–7 second Windows OS clock drift caused the engine to miscalculate contract expiration countdowns ($T_{\text{rem}}$), either submitting orders into expired markets or rejecting valid early-cycle entries.
* **Hardened Invariant**:
  * Server initializes `ClockSync` on startup, continuously syncing against authoritative external time sources and CF Benchmarks index timestamps to maintain sub-millisecond expiration synchronization.

---

### Lesson C6: Live In-Memory State & Portfolio Position Tracking Synchronization
* **Incident (2026-10-05)**:
  * Live fills on Kalshi were recorded to SQLite and guardrails, but failed to call `portfolio.open_position()`. Consequently, the strategy evaluator saw 0 active positions, skipping all Take-Profit, Trailing Ratchet, and Doubt Harvest early exits.
* **Hardened Invariant**:
  * Every confirmed live fill **MUST** immediately instantiate a `SimulatedFill` and register with `active_p.open_position()` so real-time position monitoring, early liquidation, and profit harvesting remain active.

---

### Lesson C7: Event-Loop Subprocess Deadlocks & 24/7 Watchdog Recovery
* **Incident (2026-09-29)**:
  * A blocking background cloud sync subprocess (`rclone copy`) timed out after 60s and froze Python's `asyncio` event loop. The socket stayed open, but the server became completely deaf to market ticks.
* **Hardened Invariant**:
  1. All external disk and subprocess I/O must run with explicit non-blocking timeouts or inside background executor threads.
  2. If the event loop stalls or API health checks take $>5$ seconds, the watchdog triggers an automated, clean restart.

---

### Lesson C8: The Anti-Complexity Doctrine ("Simple is More") & The Clean Slate Protocol
* **Incident (2026-09-25)**:
  * Premature UI over-engineering (massive React components, 5 overlapping validation layers, 4 tiers of pseudo-database JSON files) resulted in tech debt spirals and wasted developer tokens.
* **Hardened Invariant**:
  * **Core Over Chrome**: The mathematical execution loop is the sole engine of profitability. Zero complex UI abstractions until the terminal trading loop is 100% mathematically proven and rock-solid.

---

# 📈 PILLAR II: TRADING MICROSTRUCTURE & LIVE EXECUTION

### Lesson T1: Micro-Bankroll Anti-Kamikaze Sizing Caps
* **The Invariant Law**:
  $$\begin{aligned}
  \mathbf{\text{Per-Order Sizing:}} &\quad \mathbf{1\text{ contract}} \times \mathbf{\$0.48} = \mathbf{\$0.48\text{ max risk per order}} \\
  \mathbf{\text{Cycle Sizing Cap:}} &\quad \mathbf{\text{Max } 2\text{ contracts}} \times \mathbf{\$0.48} = \mathbf{\$0.96\text{ max risk per cycle}} \\
  \mathbf{\text{Order Style:}} &\quad \mathbf{\text{Maker Resting Limit @ \$0.48}}\text{ (\$0.00 exchange fee)}
  \end{aligned}$$
* **Implementation Guardrail**: `approved_size = min(requested_size, 1)`. If `_cycle_contracts_count >= 2`, further orders in that cycle are hard-blocked until expiration.

---

### Lesson T2: Kalshi V2 REST/WebSocket Endpoint Compliance (HTTP 410 Fix)
* **Incident**: Sweeping expired resting orders failed with `HTTP 410 Deprecated V1 Endpoint`.
* **Correction**: Event contract order cancellations must strictly target:
  ```http
  DELETE https://api.elections.kalshi.com/trade-api/v2/portfolio/events/orders/{order_id}
  ```

---

### Lesson T3: Multi-Asset Order Sweep & Take-Profit Fill Isolation (Protected Ticker Shield)
* **Incident (2026-09-11)**:
  * When asset focus shifted to Gold, the background order watchdog saw a resting BTC take-profit sell order, misidentified it as an obsolete foreign-asset order, and cancelled it 12 times in 66 seconds.
* **Hardened Invariant (Protected Ticker Shield)**:
  * Background order sweeps must never cancel orders on tickers present in:
    1. `active_positions` (open positions being actively managed).
    2. `active_resting_orders` (active unexpired limit bids/asks).
    3. Unexpired market cycles across any asset ($T_{\text{rem}} > 45\text{s}$).

---

### Lesson T4: Harakiri Streak Breaker (Adverse Regime Emergency Disarm)
* **The Rule**: Consecutive losses indicate an adverse microstructure regime (e.g., violent macro squeeze fighting local mean-reversion).
* **Hard Stop**: After **3 consecutive losses** (`_consecutive_losses >= 3`), the bot is automatically **DISARMED** (`is_bot_armed = False`). Re-arming requires manual user action via `/api/guardrails/rearm`.

---

### Lesson T5: The 6-Stage Cryptographic Seal of Excellence Gauntlet
* **The Invariant**: No bot may route live capital without a verified SHA-256 cryptographic Seal of Excellence token written on disk (`data/seal_of_excellence.json`).
* **The 6 Gauntlet Pillars**:
  1. *AST Integrity*: Strict Decimal typing, zero native floats.
  2. *Adversarial Simulation*: 100 historical cycles, CF 60s TWAP parity, Net $EV \ge +\$0.0400$/ct.
  3. *Anti-Kamikaze*: 1-contract clamp, max 2 shares/cycle, 3-loss streak auto-disarm.
  4. *Multi-Regime Incubator*: $\ge 30$ settled cycles in Lane 2 Shadow, Win Rate $\ge 55\%$, PF $\ge 1.25$.
  5. *5-Pillar Audit*: Guardrail, Math, Truths, Law, and Statistical Edge compliance.
  6. *Cryptographic Minting*: SHA-256 token generated and verified by `BotDeploymentAuditor`.

---

### Lesson T6: Limit Clamp Floor Inversion in Choppy Regimes (The 51c Floor Bug)
* **Incident (2026-10-05)**:
  * In chop regimes requiring a $\$0.48$ maximum discount ceiling, `clamped_price = max(base_floor, min(dynamic_price, max_cap))` evaluated to `0.51` because `base_floor` was statically set to `0.51`.
* **Hardened Invariant**:
  * Price floors must never exceed risk ceilings:
    `base_floor = min(float(self.discount_limit_price), max_cap)`

---

### Lesson T7: Autonomous 6-Trade Evaluation Batch Gate & Dual-Layer Execution Breaker
* **The Architecture**:
  * All active trading runs in discrete **6-trade evaluation batches** (`batch_trades_quota = 6`).
  * **Dual-Layer Circuit Breaker**:
    1. *Synchronous In-Memory Layer*: The millisecond Trade #6 settles, if Batch Net PnL $\le \$0.00$, `is_bot_armed = False` is set instantly. Trade #7 is blocked at the gate (`veto 0e`).
    2. *Parallel Background Daemon (`batch_supervisor.py`)*: Audits the batch, updates cumulative history, logs Quant Council analytics, and enforces the 30-trade macro calibration gate.
  * **Auto-Extension**: Only profitable batches ($> \$0.00$ PnL) automatically reset counters and extend for another 6 trades.

---

# 🧠 PILLAR III: QUANTITATIVE LOGIC, MATHEMATICAL RIGOR & ALPHA

### Lesson Q1: The Razor-Tight Dead Zone & Proximity Moat ($|\Delta \text{Spot}| < \text{Threshold}$)
* **The Principle**: When Bitcoin spot price ($S_t$) is within $\pm\$15$ to $\pm\$70$ of strike price ($K$) with $>5$ minutes remaining, outcome variance is dominated by Brownian motion noise.
* **Rule**: Require $|\Delta \text{Spot}| \ge \text{Dynamic Moat Threshold}$ before entering. If spot is inside the dead zone, output `Razor-Tight Proximity Veto: Skipping`.

---

### Lesson Q2: Gaussian Error Function ($\text{erf}$) Normalization ($\sqrt{2}$ Invariant)
* **Incident (2026-10-05)**:
  * The Gaussian spot probability was calculated as `p_up = 0.5 * (1 + erf(z))`, missing the standard normal divisor $\sqrt{2}$. This artificially magnified the z-score by $\approx 1.414$, generating false $86\%$ confidence spikes on minor $\$35$ spot fluctuations right before reversals.
* **Hardened Invariant**:
  * All analytical Gaussian CDF calculations must strictly include $\sqrt{2}$:
    $$z = \frac{S_t - K}{\sigma \sqrt{\tau}}, \quad \Phi(z) = \frac{1}{2}\left[1 + \text{erf}\left(\frac{z}{\sqrt{2}}\right)\right]$$

---

### Lesson Q3: Zero Static Mock Data & Anti-Hallucination Single Source of Truth
* **Incident (2026-09-12)**:
  * Hardcoded placeholder statistics (`winRate: '67.8%', events: 310`) in UI prototypes misled operators into believing an unproven bot was winning live.
* **Hardened Invariant**:
  * Production dashboards must render strictly verified live data from `kalshi_history.db` or display `—` / `AWAITING TELEMETRY`. Static mock metrics are permanently banned.

---

### Lesson Q4: Time-of-Day Regime Filtering (US Institutional Flow vs. Asian Chop)
* **Empirical Forensic Truth (883 Trades Analyzed)**:
  * During US daytime trading hours (9 AM – 10 PM EST / 13:00 – 02:00 UTC), Bitcoin is dominated by high-volume directional institutional flow, rendering short-term mean-reversion bots unprofitable (33%–45% win rate).
  * During Asian / US Overnight hours (10 PM – 9 AM EST / 02:00 – 13:00 UTC), volatility compresses into predictable ranges, boosting mean-reversion win rates to $>60\%$.
* **Rule**: Filter or tighten entry thresholds during high-impact US macro economic release windows.

---

### Lesson Q5: Macro Trend Directional Filter (Never Bet Against Institutional 1H Momentum)
* **Forensic Audit (October 5 Streak Analysis)**:
  * 5 consecutive losses occurred because the micro Gaussian drift model bet **NO** simply because spot was currently below strike, ignoring a powerful 1-hour bullish macro trend.
* **Hardened Invariant**:
  * If the 1-hour EMA / 15-minute macro trend slope is strongly positive, the engine **strictly vetoes NO bets** even if micro Gaussian drift suggests mean-reversion.

---

### Lesson Q6: Dynamic Realized Volatility Scaling vs. Fixed $\sigma = \$14/\text{min}$ Fallacy
* **The Flaw**: Assuming a constant baseline volatility ($\sigma = \$14/\text{min}$) causes the proximity moat to severely underestimate risk when volatility expands to $\$50-\$80/\text{min}$ during active sessions.
* **Hardened Invariant**:
  * The Proximity Moat must dynamically scale using the live 15-minute Parkinson / ATR realized volatility:
    $$\text{Threshold}_{\text{dynamic}} = z_{\text{asset}} \times \sigma_{\text{realized}} \times \sqrt{\tau_{\text{mins}}}$$

---

### Lesson Q7: Anti-Overfitting Sample Size Rule (30-Trade Macro Threshold vs. 6-Trade Micro Noise)
* **The Principle**: A sample of $n=6$ trades has a $11.88\%$ probability of producing $\le 2$ wins purely by binomial variance on an edge-positive strategy.
* **The Invariant Law**:
  1. **6-Trade Boundary**: Used **strictly as a capital-preservation circuit breaker** (halt execution).
  2. **$\ge 30$-Trade Boundary**: Used **strictly for model parameter evolution and weight recalibration**.
  3. **The Anti-Overfitting Lock**: The system **refuses** to curve-fit parameters to short-term 6-trade noise until at least 30 verified trades are logged in the macro sample database.

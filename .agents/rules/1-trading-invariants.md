---
trigger: always_on
glob: "**/*"
description: Core quantitative trading invariants, capital preservation rules, and execution isolation standards.
---

# 1. Quantitative Trading Invariants & Execution Isolation

## 1. Strict Decimal Financial Math (Zero Float Tolerance)
- **NEVER** use IEEE-754 floating-point math (`float` in Python / native `number` in JS) for financial calculations (balances, order amounts, prices, PnL, fees, strike differences).
- All monetary arithmetic must use Python `decimal.Decimal` and TypeScript `decimal.js` / string-wrapped allocations.

## 2. Micro-Bankroll Sizing Armor
- For bankrolls under $75, sizing is strictly hard-capped to **1 contract per trade** for each asset (`BTC`, `ETH`, `SOL`, `DOGE`).
- Sole Live Strategy: Only the certified active strategy (default `ThreeStepDominationBot`) is authorized to route live orders.

## 3. 1-Trade-Per-Cycle & In-Flight Intent Lock
- Once an automated bot submits an order for the active 15M/5M cycle, **no further orders or additions may be submitted for that ticker/cycle**.
- In-flight intent locks MUST be reserved synchronously *before* awaiting network I/O to eliminate race conditions.

## 4. Execution Mode Segregation (Zero Simulation in Live)
- In Live Mode (`Lane 1`), 100% of resources are dedicated exclusively to live execution.
- Paper trades, virtual books, and simulated routines MUST NEVER contaminate live balances, real positions, or live win/loss records.

## 5. Single-Process Execution Authority
- Exactly **ONE** process holds the live execution token via `trading_engine.lock` on port `8001` (`StandaloneBotEngine`).
- The Mother Server on port `8000` is strictly restricted to read-only monitoring and simulation when the standalone lock is active.

## 6. Zero Git-Branching for Bots
- Never create git branches or worktrees to run different bots. All bots exist as modular Python classes in `strategies/`.

## 7. Mandatory Live Promotion Lifecycle & 4-Pillar Certification
- **Zero Direct Live Deployment**: No bot may ever be deployed directly to Live Trading (`Lane 1`).
- **4-Stage Promotion Lifecycle**: Every strategy must graduate sequentially: `COOK` (isolated module) $\to$ `BACKTEST` (historical cycles & unit tests) $\to$ `SHADOW` (Lane 2 incubator on live ticks, zero capital risk) $\to$ `PROMOTE` (Live Lane 1).
- **Mandatory 4-Pillar Pre-Flight Audit**: A bot MUST achieve 100% PASS on all 4 pillars of `BotDeploymentAuditor` (Invariant Compliance, Micro-Bankroll Sizing, Guardrail Wiring, and Decimal Math) before it can be authorized for live order routing.

## 8. Multi-Bot Anti-Cannibalism & Directional Coherence
- **Zero Opposing Position Cannibalism**: Multiple bots operating on the same account/ticker must **NEVER** take opposing positions (e.g. Bot 1 BUY YES while Bot 3 BUY NO) on the same 15M contract cycle.
- **Negative-Arbitrage Trap**: Holding opposing binary positions at or near 52¢ creates a guaranteed negative-payout loss ($1.00 payout on $1.04 cost = -$0.04 guaranteed loss) and destroys risk/reward asymmetry.
- **Enforcement**: All trade intents must resolve synchronously through `LiveCoordinator` (`live_coordinator.py`). Any order proposal whose side opposes an existing active or resting position on that ticker is strictly vetoed with `CFTC ANTI-WASH TRADING VETO`.

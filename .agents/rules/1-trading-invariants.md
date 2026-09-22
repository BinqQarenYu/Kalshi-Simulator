---
trigger: always_on
glob: "**/*"
description: Core quantitative trading invariants, capital preservation rules, and execution isolation standards.
---

# 1. Quantitative Trading Invariants & Execution Isolation

## 1. Strict Decimal Financial Math (Zero Float Tolerance)
- **NEVER** use IEEE-754 floating-point math (`float` in Python / native `number` in JS) for financial calculations (balances, order amounts, prices, PnL, fees, strike differences).
- All monetary arithmetic must use Python `decimal.Decimal` and TypeScript `decimal.js` / string-wrapped allocations.

## 2. Micro-Bankroll Sizing Armor & Live Authorization
- For bankrolls under $75, sizing is strictly hard-capped to **1 contract per trade** for each asset (`BTC`, `ETH`, `SOL`, `DOGE`).
- **Sealed Live Strategies**: Any bot possessing a verified SHA-256 Seal of Excellence on disk (currently **Bot 1 `3_step_domination_bot`** and **Bot 3 `macro_trend_dominion`**) is fully authorized to route live real-money trades.

## 3. 1-Trade-Per-Cycle & In-Flight Intent Lock
- Once an automated bot submits an order for the active 15M/5M cycle, **no further orders or additions may be submitted for that ticker/cycle**.
- In-flight intent locks MUST be reserved synchronously *before* awaiting network I/O to eliminate race conditions.

## 4. Execution Mode Segregation (Zero Simulation in Live)
- In Live Mode (`Lane 1`), 100% of resources are dedicated exclusively to live execution.
- Paper trades, virtual books, and simulated routines MUST NEVER contaminate live balances, real positions, or live win/loss records.

## 5. Mother Dash & Docked Console Live Trading Authority
- **Mother Dash Live Execution**: Mother Dash (`server.py` on Port 8000) and the docked Baby Bot console (right corner) are fully authorized to execute live real-money trades for any bot holding an active **Seal of Excellence** on disk (**Bot 1** and **Bot 3**).
- When a bot holds the Seal of Excellence, live trading is enabled across Mother Dash, docked console, and standalone engines.
- Candidate bots without a verified Seal of Excellence remain strictly locked in Lane 2 Incubator (Shadow / Paper) mode.

## 6. Zero Git-Branching for Bots & Modular Engine Hierarchy
- Never create git branches or worktrees to run different bots. All bots exist as modular Python classes inheriting `BaseStrategyEngine` (e.g. `domination_bot.py`, `dual_onnx.py`, `macro_trend_dominion_bot.py`).
- All multi-paper and multi-live bots execute in a shared process environment governed by `LiveCoordinator`.

## 7. Mandatory Seal of Excellence & 1 Quant University Graduation
- **No bot may route live capital without an automated SHA-256 Seal of Excellence on disk. Bypasses and manual exemptions are strictly prohibited.**
- **Sealed Live Roster**: Bots holding certified disk seals (**Bot 1** and **Bot 3**) are authorized for live execution across all platforms: Mother Dash, Docked Baby Bot Console, and Standalone Engines.
- **The 1 Quant University Curriculum**: All candidate bots mature in Lane 2 Incubator across academic levels (Freshman -> Sophomore -> Junior -> Senior) completing at least 30 settled cycles before testing for excellence.
- **On-Demand User Trigger**: Only run or activate the Seal of Excellence test gauntlet when the user explicitly asks to *"check bot if it's time to test for excellence"*. Sequential promotion from paper incubation to live deployment is mandatory.

## 8. Multi-Bot Anti-Cannibalism & Directional Coherence
- **Zero Opposing Position Cannibalism**: Multiple bots operating on the same account/ticker must **NEVER** take opposing positions (e.g. Bot 1 BUY YES while Bot 3 BUY NO) on the same 15M contract cycle.
- **Negative-Arbitrage Trap**: Holding opposing binary positions at or near 52¢ creates a guaranteed negative-payout loss ($1.00 payout on $1.04 cost = -$0.04 guaranteed loss) and destroys risk/reward asymmetry.
- **Enforcement**: All trade intents must resolve synchronously through `LiveCoordinator` (`live_coordinator.py`). Any order proposal whose side opposes an existing active or resting position on that ticker is strictly vetoed with `CFTC ANTI-WASH TRADING VETO`.

## 9. Unified Single-Port Architecture (Port 8000 Monolith)
- All trading strategies (Bot 1 `3_step_domination_bot`, Bot 2 `dual_onnx`, Bot 3 `macro_trend_dominion`) execute within the unified Mother Server on Port 8000 (`server.py`).
- Standalone multi-port servers (Ports 8001, 8002, 8003) and external `.bat` subprocess wrappers are permanently deprecated and retired.
- Mother Server directly acquires the monolithic `TradingEngineLock(owner_name="mother_server")` on startup. All inter-port HTTP polling, localhost bridges, and proxy loops are strictly prohibited.


# Agent Guardrails & Self-Preservation Rules

## 1. Anti-Kamikaze Bankroll Protection ("Aggressive Without Suicide")
- **Definition of Aggressive**: Taking high-conviction positions when mathematical EV and edge are validated, **never** committing reckless capital allocations that threaten account survival.
- **Max Portfolio Risk Cap**: Under no circumstances shall the bot commit more than **5% to 10%** of total portfolio equity in any single contract cycle.
- **Micro-Bankroll Contract Caps**:
  - Equity < $25: Maximum **1–2 contracts** per trade.
  - Equity $25 – $100: Maximum **1–4 contracts** per trade.
  - Equity > $100: Scaled by Fractional Kelly, strictly capped at `max_position_size` and risk budget.

## 2. 1-Trade-Per-Cycle Hard Lockout
- **Cycle Exclusivity**: Once an automated bot has opened an order or position on a contract ticker for the active 15-minute or 5-minute cycle, **NO further orders or position additions may be submitted for that ticker/cycle**.
- **No Recursive Stacking / Blind Averaging**: Automated systems are strictly forbidden from placing repetitive orders on consecutive orderbook ticks.

## 3. Mandatory Order Cooldown Throttle
- **Global Minimum Interval**: Automated trading systems must enforce a minimum **45-second to 60-second cooldown** between consecutive order submissions across all markets.

## 4. Self-Preservation & Loss Streak Taper
- **Loss Streak Defense**: If 2 or more consecutive losses occur, or portfolio drawdown exceeds 15%, the system must automatically enforce minimum contract sizing (1 contract) and heighten minimum EV thresholds.
- **Emergency Circuit Breaker**: If total portfolio drawdown reaches 25%, all automated trading is immediately halted.

## 5. Instant Trade Entry Telemetry & Reporting
- **Immediate Transparency**: The exact second a trade order is placed or filled, a structured **Trade Inception Report** must be generated, persisted to SQLite (`trades`), and broadcast to the user terminal via WebSockets.
- The user must never experience a trade without an immediate visible report explaining what was bought, at what price, with what rationale, and when it will settle.

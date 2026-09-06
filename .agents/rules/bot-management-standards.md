---
trigger: always_on
glob: "**/*"
description: Standard institutional rules for bot management, multi-strategy architecture, execution lanes (Live, Shadow/Incubator, Simulation), and safe promotion lifecycle.
---

# Bot Management & Multi-Strategy Architecture Standards

## 1. The Anti-Pattern Ban
- **Zero Git-Branching or Worktrees for Process Orchestration**:
  - Git branches and git worktrees are strictly for source code versioning, feature branches, and Pull Requests.
  - **NEVER** create a Git branch, worktree, or duplicate folder simply to run a specific bot, separate live execution from development, or isolate testing.
- **Zero Server Fragmentation**:
  - Do not create disjoint, parallel server entrypoints or split dashboard ports (e.g. running one bot on 8000 and another on 8001 with conflicting process locks).
  - All bot execution lanes, live feeds, and UI controls must be managed through a single, unified institutional engine and dashboard.

## 2. Pluggable Strategy Architecture (The Registry Pattern)
- **Shared Infrastructure**:
  - All bots share the same production-grade data ingestion and risk infrastructure:
    - Authenticated Kalshi CF Benchmarks BRTI 5Hz stream (`cfbenchmarks_value_5hz`) and official 60s settlement TWAP (`avg_60s_data`).
    - Local L2 Central Limit Order Book (CLOB) with sequence continuity validation.
    - Pre-trade risk guardrails: micro-bankroll sizing (1–2 contracts, max 4), 1-trade-per-cycle lock, VPIN toxicity cutoff, and cooldown buffers.
    - Deterministic `decimal.Decimal` arithmetic for all monetary values.
- **Isolated Strategy Modules**:
  - Each trading strategy lives in its own dedicated file (e.g., `src/kalshi_sim/strategies/`).
  - Strategies must be modular classes implementing a standardized interface:
    - `evaluate(market_state) -> Optional[OrderProposal]`
    - `get_parameters() -> Dict[str, Any]`
    - `update_parameters(**kwargs) -> Dict[str, Any]`
  - Editing or adding a new bot file must never alter or risk existing certified strategies.

## 3. The Three Execution Lanes
The system maintains strict segregation between three concurrent operational regimes:

1. **Lane 1: LIVE (Real Money Production)**
   - Exactly **ONE** strategy holds the active "Live Execution Token" per contract cycle (default: `ThreeStepDominion`).
   - Routes authenticated orders directly to the Kalshi exchange.
   - Enforces the 1-trade-per-cycle lock, emergency panic kill switch, and automated pre-expiry / post-rollover order sweeps.
2. **Lane 2: SHADOW / INCUBATOR (Paper on Live Market Microstructure)**
   - Ingests the **exact same real-time live market feed** (BRTI 5Hz + Kalshi L2 CLOB) concurrently with Lane 1.
   - New or experimental bots run here to generate hypothetical orders, virtual fills, and shadow PnL.
   - **Zero Live Execution Risk**: Orders never touch real money or the live order book. Allows continuous real-world evaluation without risking bankroll.
3. **Lane 3: SIMULATION / BACKTESTING**
   - Offline testing using historical DuckDB/CSV data, jump-diffusion spot paths, or synthetic order book walks.
   - Used for rapid iterative research, machine learning training, and hyperparameter optimization.

## 4. The Safe Promotion Lifecycle (Cook -> Backtest -> Shadow -> Promote)
Every algorithmic trading strategy must graduate through a rigorous 4-stage lifecycle before handling live capital:

```
┌─────────────┐      ┌───────────────┐      ┌─────────────────┐      ┌─────────────┐
│  1. COOK    │ ───► │  2. BACKTEST  │ ───► │   3. SHADOW     │ ───► │  4. PROMOTE │
│  Code bot   │      │  Historical   │      │   Live feed,    │      │  Certified  │
│  module     │      │  data & tests │      │   paper fills   │      │  Live trade │
└─────────────┘      └───────────────┘      └─────────────────┘      └─────────────┘
```

1. **Cook**: Build the strategy in an isolated module (e.g., `strategies/new_bot.py`).
2. **Backtest**: Verify quantitative edge across historical 15-minute cycles; write comprehensive unit tests in `tests/`.
3. **Shadow Test (Incubator)**: Deploy to Lane 2 alongside the active live bot for 24–48 hours to measure real-world fill probability, slippage, and adverse selection under live microstructure conditions.
4. **Certify & Promote**: Pass the 4-pillar pre-flight certification audit (`BotDeploymentAuditor`). Once certified, switch the strategy selector to promote the bot to Lane 1 (Live).

## 5. Invariant Protections & Zero Regression
- Never disable or bypass the 1-trade-per-cycle lock or VPIN toxicity veto in Lane 1.
- Never use IEEE-754 floats for monetary calculations in any lane.
- Always run the full verification battery before committing:
  ```bash
  python -m pytest tests/ -v
  cd frontend && npm run typecheck && npm run build
  ```

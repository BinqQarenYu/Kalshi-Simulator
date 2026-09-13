# AGENTS.md — Kalshi Simulator AI Agent Guidance

Welcome! This repository is an institutional algorithmic trading platform and simulation terminal for Kalshi 15-minute Bitcoin (`KXBTC15M`) binary options contracts.

---

## 1. Tech Stack & Environment
- **Backend**: Python 3.11+, FastAPI, WebSockets, Asyncio, ONNX Runtime (CPU Provider), SQLite.
- **Frontend**: React 18, Vite, TypeScript, TailwindCSS, Canvas (Dark institutional WebCLOB theme).
- **Package Managers**: `pip` (Python with `pyproject.toml`), `npm` (Frontend in `frontend/`).

---

## 2. Verification & Test Commands
Always run these verification commands before committing or opening a PR:

### Backend Tests
```bash
python -m pytest tests/ -v
```
All 174+ unit and integration tests must pass without failures.

### Frontend Typecheck & Build
```bash
cd frontend
npm run typecheck   # tsc --noEmit
npm run build       # vite build
```
Zero TypeScript compilation errors and a clean build in `frontend/dist/`.

---

## 3. Critical Quantitative & Architectural Rules
1. **Strict Decimal Financial Math**:
   - **NEVER** use IEEE 754 floating-point math (`float` in Python / native `number` in JS) for financial calculations (balances, order amounts, entry/exit prices, PnL, fees, strike diffs).
   - Use Python's `decimal.Decimal` and TypeScript's `decimal.js` / string-wrapped allocations.
2. **Execution Mode Isolation**:
   - `MOCK_SIMULATION`: Uses realistic Level-2 synthetic book walks, partial fills, and jump-diffusion spot paths.
   - `LIVE_TRADING`: 100% to real exchange execution via Kalshi API. Never paper trade during live mode.
3. **Micro-Bankroll Sizing & Sole Authorization**:
   - Only 3-Step Dominion is authorized to trade; all other paper/simulation bots are prohibited from trading.
   - Sizing is strictly hard-capped to **1 contract for each asset** (`BTC`, `ETH`, `SOL`, `DOGE`).
4. **Kalshi Taker Fees**:
   - Taker fee: `ceil(0.07 * C * P * (1 - P))` with $0.01 floor and $0.02 cap per contract. Maker resting orders receive $0.00 fee.
5. **Adverse Selection Guard & Dynamic Spot Velocity Front-Run ($\Delta^*$)**:
   - Spot Velocity Front-Run operates via 4-regime fading mathematics: Macro Drift ($T > 240$s, $|Z_v| \ge 2.50\sigma$), Transition ($60\text{s} < T \le 240$s, adaptive $\Delta^*(T)$ with $2.0\sigma$ winning sweetspot \$28.00 BTC), Silas TWAP Gravity ($15\text{s} < T \le 60$s, quadratic decay $\sim (T/60)^2$ vetoing exits where $v < v_{\text{crit}}$), and Expiration Quarantine ($T \le 15$s, strict hold for \$1.00 settlement).
   - In simulation, fast market adverse drift (+$0.01) is triggered when spot velocity exceeds calibrated asset thresholds.
6. **CF Benchmarks BRTI 5Hz & Settlement TWAP Parity**:
   - Spot price ($S_t$) and moneyness ($S_t - K$) must stream from Kalshi's authenticated CME CF Bitcoin Real-Time Index feed (`cfbenchmarks_value_5hz` at 200ms) with official trailing 60s TWAP (`avg_60s_data`) for exact settlement parity.
7. **Pluggable Strategy Architecture & Multi-Lane Execution**:
   - Follow [.agents/rules/bot-management-standards.md](file:///.agents/rules/bot-management-standards.md).
   - **Zero Branch-per-Bot Anti-Pattern**: Never branch the repo or spawn git worktrees to run different bots. All bots exist as modular Python classes in `strategies/`.
   - **Three Distinct Lanes**: Lane 1 (Live Real Money, 1 bot at a time), Lane 2 (Shadow / Incubator, paper trading on live ticks for cooking new bots), Lane 3 (Offline Simulation & Backtesting).
   - **Unified Dashboard**: Single port and unified server manage all lanes without process lock collisions.
8. **Multi-Bot Anti-Cannibalism & Wash-Trading Shield**:
   - Multiple bots on the same account must **NEVER** hold opposing positions (YES vs NO) on the same contract cycle.
   - Any opposing submission is blocked synchronously by `LiveCoordinator` to eliminate guaranteed negative-arbitrage loss (-4¢/pair) and CFTC wash-trading violations.

---

## 4. PR & Workflow Standards
- Make minimal, targeted diffs. Do not refactor unrelated modules.
- Ensure any added trading logic includes corresponding pytest unit tests in `tests/`.
- Provide a clear PR description detailing motivation, changes, and verification results.

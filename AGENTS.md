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
3. **Micro-Bankroll Sizing & Live Trading Authorization**:
   - Any bot possessing an automated SHA-256 **Seal of Excellence** on disk (currently **Bot 1 `3_step_domination_bot`** and **Bot 3 `macro_trend_dominion`**) is authorized to execute live real-money trades directly from **Mother Dash**, the **docked Baby Bot console (right corner)**, or Standalone engines.
   - Sizing is strictly hard-capped to **1 contract for each asset** (`BTC`, `ETH`, `SOL`, `DOGE`). All unsealed bots remain in Lane 2 Incubator (paper mode).
4. **Kalshi Taker Fees**:
   - Taker fee: `ceil(0.07 * C * P * (1 - P))` with $0.01 floor and $0.02 cap per contract. Maker resting orders receive $0.00 fee.
5. **Adverse Selection Guard & Dynamic Spot Velocity Front-Run ($\Delta^*$)**:
   - Spot Velocity Front-Run operates via 4-regime fading mathematics: Macro Drift ($T > 240$s, $|Z_v| \ge 2.50\sigma$), Transition ($60\text{s} < T \le 240$s, adaptive $\Delta^*(T)$ with $2.0\sigma$ winning sweetspot \$28.00 BTC), Silas TWAP Gravity ($15\text{s} < T \le 60$s, quadratic decay $\sim (T/60)^2$ vetoing exits where $v < v_{\text{crit}}$), and Expiration Quarantine ($T \le 15$s, strict hold for \$1.00 settlement).
   - In simulation, fast market adverse drift (+$0.01) is triggered when spot velocity exceeds calibrated asset thresholds.
6. **CF Benchmarks BRTI 5Hz & Settlement TWAP Parity**:
   - Spot price ($S_t$) and moneyness ($S_t - K$) must stream from Kalshi's authenticated CME CF Bitcoin Real-Time Index feed (`cfbenchmarks_value_5hz` at 200ms) with official trailing 60s TWAP (`avg_60s_data`) for exact settlement parity.
7. **Pluggable Multi-Engine Strategy Architecture & Execution Lanes**:
   - **Zero Branch-per-Bot Anti-Pattern**: Never branch the repo or spawn git worktrees to run different bots. All bots exist as modular Python classes inheriting `BaseStrategyEngine` (`domination_bot.py`, `dual_onnx.py`, `macro_trend_dominion_bot.py`).
   - **Three Execution Lanes**:
     - *Lane 1 (Live Real Money)*: Authorized live trading bots holding certified SHA-256 Seals of Excellence (**Bot 1** and **Bot 3**).
     - *Lane 2 (Shadow / Incubator — The 1 Quant University)*: Multi-paper trading on live tick feeds to evaluate candidate bots through Freshman -> Sophomore -> Junior -> Senior curriculum tiers.
     - *Lane 3 (Offline Simulation & Backtesting)*: High-throughput L2 synthetic book walks and jump-diffusion stress testing.
   - **Unified Port 8000 Dashboard Monolith**: A single master server (`server.py` on Port 8000) orchestrates all engines, Mother Dashboard WebCLOB, docked Baby Bot Console, and university telemetry simultaneously.
8. **Multi-Bot Live & Paper Execution with Anti-Cannibalism Shield**:
   - Multiple bots on the same account/ticker must **NEVER** hold opposing positions (YES vs NO) on the same contract cycle.
   - Synchronously arbitrated by `LiveCoordinator` (`live_coordinator.py`) with absolute CFTC anti-wash trading veto power.
   - Cooperative same-direction execution permitted up to the multi-bot micro-bankroll cap (max 2 contracts combined).
9. **The 1 Quant University & Passage of the Seal of Excellence**:
   - Every algorithmic candidate must graduate from the Lane 2 Incubator University by completing at least 30 settled cycles with $\ge 52\%$ win rate and $\ge 1.10$ profit factor.
   - Pre-flight passage requires passing the 5-Pillar Gauntlet audited by `BotDeploymentAuditor` (Guardrails, Mathematical Decimal Integrity, Data Truths/CF Benchmarks, Regulatory Wash-Trading, and Empirical Statistical Edge).

---

## 4. PR & Workflow Standards
- **Backend & Quantitative Precision**: Make minimal, targeted diffs. Do not refactor unrelated backend modules. Ensure any added trading logic includes unit tests in `tests/`.
- **Frontend UI/UX & Design Sweeps**: When tasked with visual/ergonomic work, execute comprehensive component-wide sweeps ("Scoop More Sand" Standard) rather than fragmented micro-patches.
- Provide a clear PR description detailing motivation, changes, and verification results (`pytest`, `npm run typecheck`, `npm run build`).

---

## 5. Google Jules Autonomous Agent Protocols (`jules.google`)
Jules operates under three specialized engineering personas. When running in this repository, Jules must adhere to these scope standards:

### ⚡ Bolt (Microstructure & Low-Latency Systems)
- Focus: Order book delta processing, feature extraction speed, Decimal pre-allocation, ring buffer zero-copy slicing, and eliminating GC allocations.
- **The Sweet Spot Mandate**: Target 1 self-contained hot-path pipeline per PR (e.g. depth memoization, ring buffer slicing, or VPIN sum-of-squares). Never sprawl across multiple unrelated engines simultaneously. Always benchmark (<1ms budget) and append learnings to `.jules/bolt.md`.

### 🎨 Palette (Institutional FinTech UI/UX & WebCLOB Ergonomics)
- Focus: Modernizing visual hierarchy, terminal aesthetics, glanceable telemetry, and high-density Bloomberg-grade layouts across the React frontend.
- **The Sweet Spot Mandate: "Goldilocks Scoop" (Neither Teaspoon Nor Bulldozer)**:
  - **Floor: Zero Teaspoon Anti-Pattern**: Forbidden from opening PRs that merely add a single `aria-label` or one focus ring to a single button. Micro-patches create PR clutter and fragment component design.
  - **Ceiling: Zero Bulldozer Anti-Pattern**: Forbidden from opening sprawling PRs that touch 6+ files, refactor global state hooks (`useState`, `useEffect`, `useRef`), or rewrite cross-component layout contracts. No massive refactors that invite regressions, UI breakage, or unmergeable conflict states.
  - **The Sweet Spot (Target Scope: 1 Cohesive Component or View Slice, ~150–350 lines net diff)**:
    1. Institutional dark WebCLOB container styling (`bg-slate-950`, `bg-slate-900/80`, `border-slate-800`).
    2. Glanceable typography (`font-mono tabular-nums` for all financial metrics, prices, and timers).
    3. Status badge & gauge contrast (Emerald YES/Win, Crimson NO/Loss, Amber Wait/Quarantine, Cyan ONNX).
    4. Cohesive interactive states (`hover:border-slate-700`, `focus-visible:ring-2 focus-visible:ring-cyan-500/50`, active press, disabled) across **all** interactive elements in the file.
    5. Additive Accessibility: Retain and harmonize all ARIA roles, `role="switch"`, `onKeyDown` listeners, and screen reader labels.
  - **Zero Logic Tampering**: Never modify React state hooks (`useState`, `useEffect`, `useRef`), event handlers, API payloads, or delete TypeScript interface props.

### 🛡️ Sentinel (Security, CFTC Compliance & Rate Limits)
- Focus: CFTC anti-wash trading arbitration, token-bucket rate limit compliance, HTTP security headers, and credential isolation.
- Scope: Security middleware, audit trails, and defensive API validation. Always append learnings to `.jules/sentinel.md`.

---

## 6. Supreme Constitution (Governing Law)
- **All autonomous agents, background daemons, and self-healing processes are bound by [`CONSTITUTION.md`](file:///CONSTITUTION.md)** — the supreme governing document of this repository.
- The Constitution supersedes all other agent rules and skill files in cases of conflict.
- Key constitutional mandates: Human Sovereignty & Seal Immutability (Art. I), Deterministic Quantitative Integrity (Art. II), Sacred Core Isolation (Art. III), 25% Quota Sweetspot (Art. IV), ASVL Self-Healing Covenant (Art. V), Modern Slick UI Standards (Art. VI).

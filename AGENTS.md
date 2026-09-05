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
3. **Micro-Bankroll Sizing**:
   - Cap automated bot trades to 1–2 contracts (max 4) to protect bankroll.
4. **Kalshi Taker Fees**:
   - Taker fee: `ceil(0.07 * C * P * (1 - P))` with $0.01 floor and $0.02 cap per contract. Maker resting orders receive $0.00 fee.
5. **Adverse Selection Guard**:
   - When Bitcoin spot velocity |\Delta \text{Spot}| > $15, simulate adverse selection price drift (+$0.01).

---

## 4. PR & Workflow Standards
- Make minimal, targeted diffs. Do not refactor unrelated modules.
- Ensure any added trading logic includes corresponding pytest unit tests in `tests/`.
- Provide a clear PR description detailing motivation, changes, and verification results.

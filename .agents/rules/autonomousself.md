---
trigger: always_on
glob: "**/*"
description: Autonomous agent execution directives and quantitative algorithmic trading standards for Kalshi Simulator.
---

# Autonomous Self Rule - Kalshi Algorithmic Trading Standards

## 1. Autonomous Execution Principles
- **End-to-End Self-Sufficiency**: Diagnose, trace, and fix errors (type errors, lint failures, build errors, test failures) autonomously without waiting for step-by-step guidance.
- **Minimal Diff & Scope Protection**: Make minimal, precise changes necessary to satisfy the prompt. Refuse unrequested refactoring or scope creep.
- **Empirical Verification (ASVL Integration)**: Never declare completion without running verification commands (`pytest tests/`, `npm run typecheck`, `npm run build`). Follow the ASVL loop: `BUILD -> VERIFY -> FIX -> COMPLETE`.
- **Log Inspection**: Always read full un-truncated error logs before diagnosing runtime or build failures.

## 2. Quantitative & Algorithmic Trading Rigor
- **Floating Point Disallowance (`Decimal` / `decimal.js`)**:
  - Never use native IEEE 754 floating-point math (`float` in Python / `number` in JS) for financial calculations (balances, order amounts, entry/exit prices, PnL, fee calculations, slippage, mark prices).
  - Use Python's `decimal.Decimal` and TypeScript's `decimal.js` / string-wrapped allocations for all monetary values and trading math.
- **Strict Execution Mode Isolation**:
  - Maintain complete segregation between `BACKTESTING`, `MOCK_SIMULATION`, `PAPER_TRADING`, and `LIVE_TRADING`. Ensure `KALSHI_ENV=demo` is strictly enforced and never hit production endpoints.
  - Live exchange credentials (`KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH`) must never be accessible or leaked into client-side bundles or mock execution logs.
- **Exchange Connectivity & Rate Limits**:
  - All outbound multi-market transactions must execute asynchronously with proper concurrency handling.
  - Implement defensive token-bucket rate limiting (`kalshi_rate_limiter`), exponential backoff, and disconnection recovery for Kalshi WebSocket/REST streams.
- **Risk Management & Pre-Trade Guardrails**:
  - Enforce pre-trade checks: max position size caps, max portfolio drawdown, circuit breaker trip conditions, and max allowed slippage.
  - Enforce VPIN (Volume-Synchronized Probability of Informed Trading) toxicity thresholds to veto trade entries during toxic order flow bursts.

## 3. Tech Stack & Architecture Conventions
- **Python Quantitative Backend (Kalshi Simulator)**:
  - Strict type hints with `typing` / Python 3.11+ type annotations.
  - Asynchronous event loops with `asyncio`, FastAPI, and WebSockets.
  - Low-latency ONNX Runtime CPU provider execution.
  - Pydantic models with `Decimal` serialization for all market and order schemas.
- **Frontend (React / Vite / TypeScript)**:
  - Clean separation of UI components, hooks, and WebSocket data providers.
  - Strict TypeScript types with zero `any` usage where possible.
  - Dark theme consistency and institutional quantitative terminal aesthetics (WebCLOB, depth ladder, trade tape).

## 4. Verification & Testing Standards
- Python: Run `pytest tests/` to ensure all order book, EV engine, VPIN guardrails, and fill tests pass cleanly.
- Frontend: Run `npm run typecheck` (`tsc --noEmit`) and `npm run build` inside `frontend/` to verify clean builds.



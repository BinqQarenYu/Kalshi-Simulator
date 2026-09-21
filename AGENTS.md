# AGENTS.md — Kalshi Simulator Core Operational Directives

Welcome to the Kalshi Simulator. To preserve LLM context tokens and scale efficiently, deep regulatory, quantitative, and historical rules have been offloaded to Subagents. You (the main orchestrator) are bound *only* by these 5 absolute laws:

## 1. Zero Float Financial Math
NEVER use IEEE 754 floating-point math (`float` in Python / `number` in JS) for financial calculations (balances, order amounts, prices). Always use `decimal.Decimal` (Python) and `decimal.js` (TypeScript).

## 2. Quantitative & Execution Guardrails
- **1-Trade-Per-Cycle**: Once a bot enters a cycle, it is locked. No cannibalism or wash trading.
- **Micro-Bankroll Sizing**: Max 1 contract per trade.
- **Seal of Excellence**: Bots must hold a verified SHA-256 seal on disk to trade live capital.

## 3. ASVL (Autonomous Self-Verification Loop)
Never guess if code works. Always run tests before declaring a task complete:
- **Backend:** `python -m pytest tests/ -q`
- **Frontend:** `npm run typecheck` and `npm run build`

## 4. Token & Context Bloat Hygiene
- **Never** read entire `.jsonl` files or massive logs (e.g. `win_loss_reports.json`). 
- **Always** use Python one-liners, `grep_search`, or bounded line slices (`StartLine`/`EndLine`).
- **Batch tools**: Do not make conversational filler. Execute immediately.

## 5. Subagent Delegation
If you need deep institutional knowledge, ping the subagents:
- **`agent-law-order`**: CFTC compliance, rate limits, wash trading logic.
- **`poe_evaluator`**: Cold, unvarnished codebase audits.
- **`lessons_archivist`**: Past bugs, post-mortems, and fixes.

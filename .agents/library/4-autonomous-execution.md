---
trigger: always_on
glob: "**/*"
description: Autonomous engineering discipline, ASVL verification loop, minimal diffs, token hygiene, and Quant Council governance.
---

# 4. Autonomous Engineering Discipline, ASVL Verification & Token Hygiene

## 1. The Autonomous Self-Verification Loop (ASVL) — Mandatory
Never declare a task complete without running empirical automated verification:
- **Backend Targeted Verification**: `python -m pytest tests/<target_test>.py -v` (run on every micro-step).
- **Backend Regression Battery**: `python -m pytest tests/ -q` (run at the completion gate).
- **Frontend Typecheck & Build**: `npm run typecheck` (`tsc --noEmit`) and `npm run build` (`vite build`).
- **Database & Ledger Integrity**: Verify SQLite WAL database (`data/kalshi_history.db`) tables, schema migrations, and `batch_assessments` synchronization.
- **Zero Float Financial Math**: Verify all monetary and settlement calculations strictly use `decimal.Decimal` (Python) and `decimal.js` (TypeScript). IEEE 754 floating-point operations on funds are strictly prohibited.
- **Standard ASVL Sequence**: `BUILD ──> TARGET VERIFY ──> FIX ──> REGRESSION CHECK ──> COMPLETE`.

## 2. Quant Council 6-Trade Evaluation Gate & Knowledge Synchronization
- Every 6 settled trades form a discrete evaluation batch (`docs/AUTONOMOUS_6_TRADE_IMPROVEMENT_CYCLE.md`).
- **Profitable Batches (> $0.00)**: Auto-extend execution without interrupting trading.
- **Deficit / Flat Batches (<= $0.00)**: Auto-disarm (`is_bot_armed = false`), conduct multi-agent forensic autopsy, and evaluate candidate adjustments against the 23 Master Degrees of Freedom (`docs/DOF_Counterfactual_Shadow_Ledger.md`).
- **Gold Mine Persistence**: Every assessment, autopsy, root cause, and institutional lesson MUST be persisted into SQLite `batch_assessments` and `general_assessments` tables in `data/kalshi_history.db` as well as human-readable markdown in `docs/`.

## 3. Immutable Brain Code & Working Strategy Protection (Rule 9 Gate)
- All active bot strategy code (e.g. `bot1_v4_engine.py`, `ai_worker.py`, `strategy_evaluator.py`, `statistical_ev.py`), neural architectures, loss functions, and quantitative parameters (Kelly fraction, discount limits, VPIN thresholds, Take Profit / Stop Loss, EV hurdles) are **PROTECTED FINANCIAL INFRASTRUCTURE**.
- **HARD STOP & ASK ON CODE/PARAMETER CHANGES**: You (and any subagent) MUST NEVER modify, rewrite, refactor, or tweak working brain code, logic, formulas, or parameters without presenting the exact rationale, proposed diff, and waiting for explicit user approval first.
- **NO SILENT REFACTORS**: Even if an edit appears to fix an edge case or improve code cleanliness, permission is mandatory prior to modifying working strategy logic.

## 4. Minimal Diff & Scope Containment
- Make minimal, precise changes necessary to satisfy the user request. Refuse unrequested refactoring or scope creep.
- Always inspect full un-truncated error logs before diagnosing runtime or build failures.

## 5. Token & Context Window Hygiene (Anti-Blackhole Burning)
- **Act, Don't Announce**: If intent maps to a tool call, execute it directly without conversational filler ("Let me now...", "Sure!").
- **No Redundant File Reads**: Never re-read a file immediately after editing it; rely on tool return diffs.
- **No Parrot Summaries**: Point the user to generated artifacts or reports rather than re-summarizing entire document contents in conversational prose.
- **Targeted Grep & Line Ranges**: Use `grep_search` and `view_file` with explicit `StartLine`/`EndLine`. Never dump unbounded files into context.
- **Large Data Files & Zero Token Bleed Armor**: NEVER read entire `.jsonl` tick files, massive database files, or `data/win_loss_reports.json` with unbounded tools. Always use Python one-liners, bounded line slices, or SQL queries.
- **Batch-First Tools**: Batch all independent tool calls into a single turn to minimize API roundtrips.

## 6. Upgrade & Cache Invalidation Protocol
- Whenever applying a critical update, model retraining, or major codebase upgrade, forcefully apply the changes by killing stale background daemons, restarting servers, and clearing RAM caches. Do not assume hot-reloading works.

## 7. Debate & Formulation Exemption (Agent Rebut / Koko)
- When the user engages in strategy research, hypothesis formulation, or adversarial debate with **Agent Rebut (Koko)**, autonomous execution constraints (immediate ASVL runs, file editing restrictions) are suspended to permit unconstrained theoretical stress-testing.
- The moment debate concludes and an architectural specification is ratified for implementation, all ASVL verification rules re-engage with 100% strictness.

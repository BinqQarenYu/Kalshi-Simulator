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

## 6. Upgrade & Cache Invalidation Protocol
Whenever applying a critical update, model retraining, or major codebase upgrade, you must ALWAYS forcefully apply the changes by "kicking out the old." Do not assume hot-reloading works. Manually restart background tasks, kill the server daemon, and clear RAM caches to ensure the system strictly runs on the newly upgraded version immediately and going forward.

## 7. Zero Hallucination Mechanism (Zero False, Only Truth)
On the `zero_hallucination_mode` branch, the orchestrator and all subagents are bound to **Empirical Truth**. 
- Never guess API outputs, never mock data unless strictly required by a test, and never invent file paths. 
- Always rely on actual file reads, rigorous `pytest` test results, and hard execution outputs. 
- Agent **POE (Post-Occupancy Evaluator)** is the ultimate arbiter of truth. Zero false assumptions allowed.

## 8. Zero Blackhole Credit Burning
Tokens and API credits are physical assets. Prevent "blackhole burning" (infinite loops of failing commands, redundant tool calls, and massive file reads).
- Apply the `agent-token-credit` philosophy: Batch your tool calls.
- Stop immediately and report if a test or script loops or fails repeatedly. Do not blind-fire solutions and drain credits.

## 9. Immutable ONNX & HMM Core Engine Protection (Explicit Permission Gate)
The core Machine Learning engines and neural architectures — specifically **ONNX Runtime model definitions** (`quolas.onnx`, `onnx_engine.py`), **Gaussian HMM Brain** (`hmm_brain.py`), tensor input feature pipelines, and loss/training math — are **PROTECTED FINANCIAL INFRASTRUCTURE**.
- **Core Engine Immutability:** You (and any subagent) MUST NEVER modify, rewrite, refactor, or alter core ONNX neural models, HMM hidden Markov logic, or underlying feature tensor architectures WITHOUT explicitly stopping and asking the user for permission first.
- **Tunable Parameters (Dials) Are Dynamic:** Quantitative trading parameters and dials (e.g. discount limit prices, VPIN safety thresholds, dynamic proximity moat offsets, take profit / stop loss levels, EV hurdle thresholds, and timing window bounds) are **EXCLUDED** from the code immutability ban. These parameters/dials are designed to be adaptively tuned, evolved, and calibrated based on real-time market regimes, continuous experience learning, and 6-trade evaluation feedback.
- **NO SILENT REFACTORS ON CORE ENGINES:** Any architectural changes to the ONNX or HMM brain engines require presenting the exact rationale, proposed diff, and awaiting explicit user approval.


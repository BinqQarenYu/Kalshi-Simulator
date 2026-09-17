---
name: Autonomous Self-Verification Loop Skill (ASVL) - Antigravity Edition
description: Autonomous end-to-end self-verification loop skill for goal-based task execution, automated testing, continuous evaluation, and definitive completion gates.
---

# Autonomous Self-Verification Loop Skill (ASVL) - Antigravity Edition

## 1. Goal-Oriented Execution & Codeflow Integration
ASVL is the execution and verification engine of Antigravity. It takes the **Granular Task Contract** from **Agent Codeflow** and anchors it into a structured, goal-based execution run:
- **Goal**: A clear, high-level description of the ultimate outcome.
- **Success Criteria**: A checklist of 3–5 specific, quantifiable, and testable outcomes required to satisfy the goal.
- **File Boundaries**: Strictly enforced from Codeflow's **File Boundary Matrix** (zero edits in the Forbidden Zone).
- **Step-by-Step Micro-Execution**: Execute Codeflow's atomic steps sequentially (Step 1 Types -> Step 2 Logic -> Step 3 UI) rather than attempting an unverified monolithic overhaul.

## 2. Self-Verification & Testing Setup
Before declaring any code complete, configure and run automated verification tools autonomously. Do not rely on human review.
- **Project-Specific Test Harness**: Adhere strictly to the project rules defined in [`4-autonomous-execution.md`](file:///.agents/rules/4-autonomous-execution.md) and [`1-trading-invariants.md`](file:///.agents/rules/1-trading-invariants.md):
  - Backend targeted test: `python -m pytest tests/<target_test>.py -v`
  - Backend full suite: `python -m pytest tests/ -q` (all 296+ tests must pass)
  - Frontend typecheck: `npm --prefix frontend run typecheck` (`tsc --noEmit`)
  - Frontend production build: `npm --prefix frontend run build` (`vite build`)
- **Dual-Tier Continuous Evaluation Loop**:
  1. *Micro-Step Loop (Per Task)*: `BUILD ──> TARGET VERIFY ──> FIX` on each Codeflow atomic step. Always use quiet mode (`pytest tests/<target>.py -q`) to keep terminal logs under 15 lines.
  2. *Final Regression Loop*: `FULL TEST BATTERY ──> BUILD CHECK ──> COMPLETE GATE` executed only once at task completion.
- **Token & Log Conservation Invariants**:
  - Never run the full 296+ test suite on intermediate micro-steps.
  - Never poll background tasks in a loop; yield execution and await reactive system notifications.
  - Never re-read a file immediately after editing it; rely on the replacement diff.
  - Never parrot artifact contents in text replies; point the user to the artifact.
- **Zero Human Verification Request**: Never ask the user to test or confirm if code works; execute empirical verification autonomously using shell and diagnostic tools.

## 3. Antigravity-Native Autonomy Rules
During execution, operate as a fully autonomous agent thread within the Antigravity engine without prompting for intermediate human approval:
- **End-to-End Task Execution**: Do not yield control, request mid-task approval, or return partial progress. Continuously chain internal agent steps, terminal commands, and tool calls until all success criteria are satisfied.
- **Antigravity Tooling & Sensible Defaults**: Independently select and invoke available platform capabilities (shell execution, workspace search, targeted file edits). If minor implementation details are unspecified, apply institutional standards without halting execution.
- **Autonomous Error Recovery**: If build steps fail, terminal commands error out, or verification loops detect regressions, inspect execution logs, resolve issues, and immediately re-trigger the verification loop.
- **System Blocker Escalation**: Yield execution control to the user ONLY if you hit an unrecoverable system boundary—such as missing external API credentials, OS-level permission locks, or platform service outages.

## 4. Definitive Completion Gates
Exit the autonomous loop and return control to the user ONLY when ALL completion conditions are met:

### Complete When:
- [ ] All success criteria from the goal are met and verified.
- [ ] Code changes respect Codeflow's File Boundary Matrix (zero unintended diffs in Forbidden Zone).
- [ ] You have actively executed and verified the work yourself (`pytest`, `npm run typecheck`, `npm run build`).
- [ ] No known bugs, compile warnings, or broken features remain.
- [ ] Code is clean, optimized, and fully documented with invariant protections.
- [ ] The deliverable is ready for immediate human deployment or use.

### Not Complete If:
- [ ] You assume or guess it works without running verification tools.
- [ ] Outstanding TODOs or placeholder comments remain in the codebase.
- [ ] You prompt the user for manual testing, verification, or validation help.

## 5. Execution Loop Reference Template
Process all implementation tasks using this internal step-by-step cycle:
1. **INGEST**: Take Codeflow's `GRANULAR TASK CONTRACT` (Workflow Map, File Boundaries, Micro-Steps).
2. **PLAN**: Anchor the steps into measurable Success Criteria and verification commands.
3. **BUILD (Atomic)**: Implement Step 1 (Types/Schemas), Step 2 (Logic), Step 3 (UI).
4. **VERIFY (Step)**: Run immediate targeted checks (e.g. `npm run typecheck` or targeted `pytest`).
5. **FIX**: If gaps or errors exist, isolate root cause and re-verify.
6. **REGRESSION CHECK**: Run the full project test harness (`pytest tests/ -q` and `npm run build`).
7. **COMPLETE**: Document changes in a walkthrough artifact and present verified results.

---

## 6. Continuous 24/7 Dual-Lead Autonomous Architecture
The self-healing and self-verification lifecycle operates 24/7 across two dedicated Gemini Free-Tier leads:

| Autonomous Role | Engine & Model | Operational Domain & Mandate |
|---|---|---|
| **Lead Deer** (Backend Lead) | Google Gemini Free API | **24/7 Autonomous Backend Self-Healer**: Continually monitors `server.py`, error logs, WebSocket sequence gaps, L2 book resyncs, and regressions. Diagnoses runtime exceptions, executes backend self-repairs, and dispatches incident digests to `likhahomebuild`. |
| **Lead Architect** (Frontend Lead) | Google Gemini Free API | **24/7 Autonomous Frontend Quant Designer**: Continually polishes WebCLOB ergonomics, visual hierarchy, dark institutional theming, glanceable telemetry, and layout responsiveness. Operates under strict **harmless execution invariants**: zero tampering with React state hooks, WebSocket feeds, or execution handlers. |

Both 24/7 autonomous leads operate within Google's Free Tier quotas (15 RPM / 1M TPM / $0.00 cost) with zero latency impact on live trading.

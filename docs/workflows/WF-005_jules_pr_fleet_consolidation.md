# WF-005: Automated Jules PR Fleet Consolidation & Verification

> **Workflow ID:** WF-005  
> **Classification:** Release Management, Multi-Agent Git Arbitration & Invariant Hardening  
> **Lead Agents:** 🦌 Agent DEER (Batch Isolation & Hygiene) + 🧢-oko (Flaw & Math Review) + 🏇 Quoquo (Audit Oracle)  
> **Frequency:** On-Demand (when Jules specialists Bolt/Palette/Sentinel open optimization PRs)  
> **Prerequisites:** GitHub CLI (`gh`), Git, active test suites (`pytest`, `tsc`, `vite`).

---

## 1. Overview & Operational Scope

Google Jules autonomous specialists continuously generate micro-optimizations across the repository:
- ⚡️ **Bolt**: Order book hot paths, C-level struct packing, O(1) depth caching, ring buffer slicing.
- 🎨 **Palette**: WebCLOB high-density UI/UX sweeps, accessibility (`aria-labels`), tabular numeral alignments.
- 🊛️ **Sentinel**: Security middleware, CFTC wash-trading arbitration, RSA key handling.

**WF-005** governs how **Agent DEER** systematically batches, isolates, tests, and consolidates the Jules PR fleet without introducing regressions or violating mathematical invariants.

---

## 2. Mandatory Safety Invariants (Zero Blind-Merge Standard)

1. **Zero Blind Acceptance**: Never execute indiscriminate `accept incoming changes` across Git conflicts. Jules branches frequently diverge or lack the latest live server anti-cannibalism guards.
2. **Rule #1 Decimal Math Isolation**: Bolt C-level and float micro-optimizations must strictly apply to internal rate/tick heuristics only--they must **never** leak into account balances, order counts, or live PnL calculations.
3. **Frontend Compile Gate**: Every Palette UI sweep must pass both `npm run typecheck`(`tsc --noEmit`) and `npm run build`(`vite build`) with 0 errors before merging.
4. **Ledger Preservation**: Cumulative optimization logs (`.jules/bolt.md`, `.jules/palette.md`) must be appended without dropping prior entries.

---

## 3. Step-by-Step Execution Guide

### Step 1: Query Remote PR Fleet
``@bash
gh pr list --limit 20
```

### Step 2: Sequential Isolation & Dry-Run Merge
For each open PR in the backlog:
``@bash
git fetch origin pull/<PR_ID>/head:pr-<PR_ID>
git merge pr-<PR_ID> --no-commit --no-ff
```

3!# Step 3: Conflict Arbitration & Test Gates
- **If Markdown conflicts (.jules/*.md)**: Retain both HEAD and incoming historical notes.
- **If Backend Python source**: Run target unit tests immediately:
  ``@bash
  python -m pytest tests/test_orderbook.py tests/test_simulation.py tests/test_statistical_ev.py -v
  ```
- **If Frontend React source**: Run TypeScript check and production bundle:
  ```bash
  cd frontend && npm run typecheck && npm run build && cd ..
  ```

### Step 4: Commit & Temporary Branch Pruning
``@bash
git commit -m "Merge PR #<PR_ID>: <Title>"
git branch -D pr-<<PR_ID>
```

### Step 5: Post-Consolidation Audit
Quoquo generates the final integration ledger summarizing all merged speedups, memory footprints, and passing test runs.

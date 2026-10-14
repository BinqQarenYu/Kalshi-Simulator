# Quantitative Constitution & Operational Governance

**Classification:** Core Governance & Regulatory Invariants  
**Applicability:** Universal (Main Orchestrator, Subagents, Autonomous Daemons)  

---

## 1. The Core Operational Directives (AGENTS.md Laws)

1. **Zero Float Financial Math:**
   - Float math introduces IEEE-754 precision artifacts (e.g. `$0.0000000000000002` cent drift) that corrupt account balance checks and risk thresholds.
   - Python code MUST use `decimal.Decimal`.
   - TypeScript code MUST use `decimal.js` or string representations.
2. **Quantitative & Execution Guardrails:**
   - **1-Trade-Per-Cycle Lock:** Once an engine submits a round-trip order for a 15M expiration cycle, the cycle is locked. No re-entry, no wash trading.
   - **Micro-Bankroll Sizing:** Pinned at 1 contract max while balance $<\$50.00$.
   - **Seal of Excellence:** Strategy execution files must match verified SHA-256 signatures on disk.
3. **Autonomous Self-Verification Loop (ASVL):**
   - Code changes must be empirically validated via `python -m pytest` before marking complete.
4. **Token & Context Bloat Hygiene:**
   - Prevent massive transcript blowups; enforce bounded file reads (`view_file` with line slices).
5. **Subagent Delegation:**
   - Route deep compliance queries to `agent-law-order`, truth evaluations to `agent-poe`, and history archives to `agent-quoquo`.
6. **Upgrade & Cache Invalidation Protocol:**
   - Never assume hot-reloading works. Forcefully recycle systemd daemons and clear memory caches on upgrades.
7. **Zero Hallucination Mechanism:**
   - Never invent file paths, mock data without explicit need, or fabricate test results.
8. **Zero Blackhole Credit Burning:**
   - Prevent unbounded tool loops; batch commands and stop if a script repeats failures.

---

## 2. Regulatory Compliance (CFTC Rule 180.1 & 180.2)

- **Anti-Wash Trading:** Opposing positions (`YES` vs `NO`) on the same contract cycle across any fleet account are strictly prohibited.
- **Anti-Spoofing:** Limit orders placed must have genuine economic intent; cancellation loops are capped by token-bucket rate limiters.
- **Rate Limit Armor:** Kalshi API request rates are throttled via deterministic token-bucket algorithms ($< 10\text{ req/sec}$).

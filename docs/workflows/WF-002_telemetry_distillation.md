# WF-002: Continuous Telemetry Distillation (Warm Path)

## 1. Executive Summary & Purpose
During active 15-minute trading cycles, the terminal logs high-frequency orderbook updates, VPIN indicators, and pre-trade veto checks. Feeding raw log dumps (10,000 to 50,000 tokens) into LLMs wastes thousands of AI credits and pollutes the context window.

**WF-002 defines the autonomous data distillation pipeline:**
1. At the conclusion of every 15M cycle, **Agent DEER** (`DeerScrubber`) reads the raw events.
2. Repetitive wait ticks are collapsed into statistical ranges (min/max spot diff, VPIN range, max queue depth).
3. The dominant veto reason is categorized (`WHALE_QUEUE`, `RAZOR_TIGHT_MOAT`, `VPIN_TOXIC`, `PRICE_CEILING`, `CONVICTION_HURDLE`).
4. **Agent DEER** generates a crisp 2-sentence forensic brief using local **NVIDIA `nemotron-mini:latest`** (or 0ms rule template fallback).
5. Clean digests are deposited into **Quoquo Vault** (`reports/clean_telemetry/cycles.jsonl` and `daily_digest.md`) at under 100 tokens.

---

## 2. Invariants & Safety Armoring
- **Decoupled Warm Path**: Distillation runs asynchronously *after* cycle settlement. It NEVER intercepts the 5Hz CME CF BRTI tick stream or delays live order routing.
- **Resource Hard-Caps**: Local LLM inference is strictly capped to $\le 3$ CPU threads and $\le 8$ GB RAM.
- **Fail-Safe Fallback**: If Ollama is busy, offline, or takes longer than 2.5s, the pipeline instantly generates a deterministic template without blocking.

---

## 3. Telemetry Schema & Access
- Stored records adhere to `CondensedCycleTelemetry` (Pydantic).
- Terminal REST endpoint: `GET /api/telemetry/condensed` (returns last 20 clean cycles).
- Markdown digest: `reports/clean_telemetry/daily_digest.md`.
